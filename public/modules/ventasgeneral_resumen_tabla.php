<?php

declare(strict_types=1);

require_once dirname(__DIR__, 2) . '/config/bootstrap.php';
require_once __DIR__ . '/reporte_pdf_snippet.php';

function vrt_parse_date(string $key): ?string
{
    $s = isset($_GET[$key]) ? trim((string) $_GET[$key]) : '';
    $s = trim($s, " \t\n\r\0\x0B\"'()[]<>");
    if ($s === '') {
        return null;
    }
    $d = DateTimeImmutable::createFromFormat('Y-m-d', $s);
    if ($d === false || $d->format('Y-m-d') !== $s) {
        return null;
    }
    return $s;
}

$d1 = vrt_parse_date('fecha_desde') ?? vrt_parse_date('desde');
$d2 = vrt_parse_date('fecha_hasta') ?? vrt_parse_date('hasta');
if ($d1 === null || $d2 === null || $d1 > $d2) {
    http_response_code(400);
    header('Content-Type: text/plain; charset=utf-8');
    echo 'Parámetros: fecha_desde y fecha_hasta (YYYY-MM-DD); alias desde y hasta. Opcionales: zona_comercial, cod_cliente, prefijo_descri_zona_precio';
    exit;
}

$sql = 'SELECT COUNT(*) AS filas, COALESCE(SUM(Valor),0) AS suma_valor, COALESCE(SUM(Cantidad),0) AS suma_cantidad, COALESCE(SUM(Peso),0) AS suma_peso
    FROM ventasgeneral WHERE FechaCont BETWEEN :d1 AND :d2';
$params = [':d1' => $d1, ':d2' => $d2];

$zona = isset($_GET['zona_comercial']) ? trim((string) $_GET['zona_comercial']) : '';
if ($zona !== '') {
    $sql .= ' AND ZonaComercial LIKE :zona';
    $params[':zona'] = '%' . $zona . '%';
}
$cod = isset($_GET['cod_cliente']) ? trim((string) $_GET['cod_cliente']) : '';
if ($cod !== '') {
    $sql .= ' AND CodCliente = :cod';
    $params[':cod'] = $cod;
}
$prefZ = isset($_GET['prefijo_descri_zona_precio']) ? strtoupper(trim((string) $_GET['prefijo_descri_zona_precio'])) : '';
if ($prefZ !== '') {
    $sql .= ' AND UPPER(TRIM(COALESCE(DescriZonaPrecio,\'\'))) LIKE :prefzp';
    $params[':prefzp'] = $prefZ . '%';
}

$pdo = ventas_pdo();
$st = $pdo->prepare($sql);
$st->execute($params);
$row = $st->fetch(PDO::FETCH_ASSOC) ?: [];

$pdfName = 'resumen_ventasgeneral_' . $d1 . '_' . $d2 . '.pdf';
?>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Tabla · Resumen ventasgeneral</title>
    <style>
        body { font-family: system-ui, sans-serif; margin: 0; background: #0f172a; color: #e2e8f0; }
        header { padding: 1rem 1.25rem; background: linear-gradient(135deg, #1d4ed8, #6d28d9); }
        h1 { margin: 0; font-size: 1.1rem; font-weight: 600; }
        .meta { margin: 0.35rem 0 0; font-size: 0.85rem; opacity: 0.9; }
        main { padding: 1rem; max-width: 900px; margin: 0 auto; }
        .wrap-dark { background: #1e293b; border-radius: 12px; padding: 1rem; border: 1px solid #334155; }
    </style>
    <?php ventas_reporte_tabla_styles(); ?>
</head>
<body>
    <header>
        <h1>Reporte tabular — Resumen agregado ventasgeneral</h1>
        <p class="meta"><?= htmlspecialchars($d1, ENT_QUOTES, 'UTF-8') ?> a <?= htmlspecialchars($d2, ENT_QUOTES, 'UTF-8') ?></p>
    </header>
    <main>
        <div class="wrap-dark">
            <div class="reporte-toolbar">
                <button type="button" class="btn-pdf" id="btn-pdf-resumen">Descargar PDF</button>
            </div>
            <div id="reporte-pdf-root">
                <h2 class="pdf-h2">Agregados del periodo</h2>
                <p class="pdf-meta">FechaCont entre las fechas indicadas (filtros opcionales aplicados).</p>
                <table>
                    <thead>
                        <tr>
                            <th>Filas</th>
                            <th>Suma Valor</th>
                            <th>Suma Cantidad</th>
                            <th>Suma Peso</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td><?= htmlspecialchars((string) ($row['filas'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                            <td><?= number_format((float) ($row['suma_valor'] ?? 0), 2, '.', ',') ?></td>
                            <td><?= htmlspecialchars((string) ($row['suma_cantidad'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                            <td><?= htmlspecialchars((string) ($row['suma_peso'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </main>
    <?php ventas_reporte_pdf_script(); ?>
    <script>
    ventasBindPdfDownload('btn-pdf-resumen', 'reporte-pdf-root', <?= json_encode($pdfName, JSON_UNESCAPED_UNICODE | JSON_HEX_TAG | JSON_HEX_APOS) ?>);
    </script>
</body>
</html>
