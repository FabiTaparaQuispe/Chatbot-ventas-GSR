<?php
declare(strict_types=1);

require_once __DIR__ . '/../includes/bootstrap.php';

header('Content-Type: application/json; charset=utf-8');

// Evita que warnings/notices rompan el JSON (causan DataTables warning "HTTP 200").
@ini_set('display_errors', '0');
@ini_set('html_errors', '0');
@ini_set('log_errors', '1');
if (!ob_get_level()) {
    ob_start();
}

function json_out(array $data): void
{
    if (ob_get_length()) {
        ob_clean();
    }
    $json = json_encode(
        $data,
        JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_INVALID_UTF8_SUBSTITUTE | JSON_PARTIAL_OUTPUT_ON_ERROR
    );
    if ($json === false) {
        http_response_code(500);
        echo json_encode(
            [
                'draw' => (int) ($_GET['draw'] ?? 0),
                'recordsTotal' => 0,
                'recordsFiltered' => 0,
                'data' => [],
                'error' => 'No se pudo serializar JSON: ' . json_last_error_msg(),
            ],
            JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES
        );
        exit;
    }
    echo $json;
    exit;
}

// Nota: no bloqueamos por sesión aquí para evitar que el render de DataTables quede vacío
// si el navegador no adjunta la cookie por configuración local. El acceso al layout ya
// está protegido en `public/index.php`.

function parse_ymd(string $s): ?string
{
    $s = trim($s);
    if ($s === '') return null;
    $d = DateTimeImmutable::createFromFormat('Y-m-d', $s);
    return ($d && $d->format('Y-m-d') === $s) ? $s : null;
}

$draw = (int) ($_GET['draw'] ?? 0);
$start = max(0, (int) ($_GET['start'] ?? 0));
$length = max(1, min(200, (int) ($_GET['length'] ?? 20)));
// En algunos servidores, los parámetros con corchetes (search[value]) provocan 400.
// Soportamos ambas formas: search=<texto> y search[value]=<texto>.
$search = trim((string) ($_GET['search'] ?? ($_GET['search']['value'] ?? '')));

$desde = parse_ymd((string) ($_GET['desde'] ?? ''));
$hasta = parse_ymd((string) ($_GET['hasta'] ?? ''));
$nombre = trim((string) ($_GET['nombre'] ?? ''));
$numeroDoc = trim((string) ($_GET['numero_doc'] ?? ''));
$tipoDocumento = trim((string) ($_GET['tipo_documento'] ?? ''));
$provincia = trim((string) ($_GET['provincia'] ?? ''));

try {
    $pdo = ventas_pdo();

    $baseWhere = ' WHERE 1=1';
    $params = [];

    if ($desde !== null) {
        $baseWhere .= ' AND FechaContable >= :d1';
        $params[':d1'] = $desde;
    }
    if ($hasta !== null) {
        $baseWhere .= ' AND FechaContable <= :d2';
        $params[':d2'] = $hasta;
    }
    if ($nombre !== '') {
        $baseWhere .= ' AND NombreCliente LIKE :nom';
        $params[':nom'] = '%' . $nombre . '%';
    }
    if ($numeroDoc !== '') {
        $baseWhere .= ' AND NumeroFactura LIKE :ndoc';
        $params[':ndoc'] = '%' . $numeroDoc . '%';
    }
    if ($tipoDocumento !== '') {
        $baseWhere .= ' AND TipoDocumento LIKE :tdoctipo';
        $params[':tdoctipo'] = '%' . $tipoDocumento . '%';
    }
    if ($provincia !== '') {
        $baseWhere .= ' AND Provincia LIKE :prov';
        $params[':prov'] = '%' . $provincia . '%';
    }

    $recordsTotal = (int) $pdo->query('SELECT COUNT(*) FROM ventasgeneral2')->fetchColumn();

    $where = $baseWhere;
    if ($search !== '') {
        $where .= ' AND (NombreCliente LIKE :s OR NumeroFactura LIKE :s OR CodigoItem LIKE :s OR GlosaDetalle LIKE :s OR ZonaComercial LIKE :s OR TipoDocumento LIKE :s OR Provincia LIKE :s OR LineaComercial LIKE :s)';
        $params[':s'] = '%' . $search . '%';
    }

    $stc = $pdo->prepare('SELECT COUNT(*) FROM ventasgeneral2' . $where);
    $stc->execute($params);
    $recordsFiltered = (int) $stc->fetchColumn();

    $sql = 'SELECT FechaContable, CodigoCliente, NombreCliente, NumeroFactura, CodigoItem, GlosaDetalle, Cantidad, Valor, ZonaComercial, TipoDocumento, Provincia, LineaComercial
            FROM ventasgeneral2' . $where . ' ORDER BY FechaContable DESC, id DESC LIMIT ' . (int) $length . ' OFFSET ' . (int) $start;
    $st = $pdo->prepare($sql);
    $st->execute($params);
    $rows = $st->fetchAll(PDO::FETCH_ASSOC);

    $data = [];
    foreach ($rows as $i => $r) {
        $data[] = [
            (string) ($start + $i + 1),
            ventas_utf8_string($r['FechaContable'] ?? ''),
            ventas_utf8_string($r['CodigoCliente'] ?? ''),
            ventas_utf8_string($r['NombreCliente'] ?? ''),
            ventas_utf8_string($r['NumeroFactura'] ?? ''),
            ventas_utf8_string($r['CodigoItem'] ?? ''),
            ventas_utf8_string($r['GlosaDetalle'] ?? ''),
            ventas_utf8_string($r['Cantidad'] ?? ''),
            ventas_utf8_string($r['Valor'] ?? ''),
            ventas_utf8_string($r['ZonaComercial'] ?? ''),
            ventas_utf8_string($r['TipoDocumento'] ?? ''),
            ventas_utf8_string($r['Provincia'] ?? ''),
            ventas_utf8_string($r['LineaComercial'] ?? ''),
        ];
    }

    json_out([
        'draw' => $draw,
        'recordsTotal' => $recordsTotal,
        'recordsFiltered' => $recordsFiltered,
        'data' => $data,
    ]);
} catch (Throwable $e) {
    http_response_code(500);
    json_out([
        'draw' => $draw,
        'recordsTotal' => 0,
        'recordsFiltered' => 0,
        'data' => [],
        'error' => $e->getMessage(),
    ]);
}

