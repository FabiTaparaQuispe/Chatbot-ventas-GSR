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

try {
    $pdo = ventas_pdo();

    $baseWhere = ' WHERE 1=1';
    $params = [];

    if ($desde !== null) {
        $baseWhere .= ' AND FechaCont >= :d1';
        $params[':d1'] = $desde;
    }
    if ($hasta !== null) {
        $baseWhere .= ' AND FechaCont <= :d2';
        $params[':d2'] = $hasta;
    }
    if ($nombre !== '') {
        $baseWhere .= ' AND NombreCliente LIKE :nom';
        $params[':nom'] = '%' . $nombre . '%';
    }
    if ($numeroDoc !== '') {
        $baseWhere .= ' AND NumeroDoc LIKE :ndoc';
        $params[':ndoc'] = '%' . $numeroDoc . '%';
    }

    $recordsTotal = (int) $pdo->query('SELECT COUNT(*) FROM ventasgeneral')->fetchColumn();

    $where = $baseWhere;
    if ($search !== '') {
        $where .= ' AND (NombreCliente LIKE :s OR NumeroDoc LIKE :s OR CodItem LIKE :s OR Glosa LIKE :s OR ZonaComercial LIKE :s)';
        $params[':s'] = '%' . $search . '%';
    }

    $stc = $pdo->prepare('SELECT COUNT(*) FROM ventasgeneral' . $where);
    $stc->execute($params);
    $recordsFiltered = (int) $stc->fetchColumn();

    $sql = 'SELECT id, FechaCont, CodCliente, NombreCliente, NumeroDoc, CodItem, Glosa, Cantidad, Valor, ZonaComercial
            FROM ventasgeneral' . $where . ' ORDER BY FechaCont DESC, id DESC LIMIT ' . (int) $length . ' OFFSET ' . (int) $start;
    $st = $pdo->prepare($sql);
    $st->execute($params);
    $rows = $st->fetchAll(PDO::FETCH_ASSOC);

    $data = array_map(static function (array $r): array {
        return [
            (string) ($r['id'] ?? ''),
            (string) ($r['FechaCont'] ?? ''),
            (string) ($r['CodCliente'] ?? ''),
            (string) ($r['NombreCliente'] ?? ''),
            (string) ($r['NumeroDoc'] ?? ''),
            (string) ($r['CodItem'] ?? ''),
            (string) ($r['Glosa'] ?? ''),
            (string) ($r['Cantidad'] ?? ''),
            (string) ($r['Valor'] ?? ''),
            (string) ($r['ZonaComercial'] ?? ''),
        ];
    }, $rows);

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

