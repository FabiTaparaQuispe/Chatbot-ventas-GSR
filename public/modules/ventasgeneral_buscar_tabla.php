<?php

declare(strict_types=1);

require_once dirname(__DIR__, 2) . '/config/bootstrap.php';
require_once dirname(__DIR__, 2) . '/src/VentasGeneralBuscarQuery.php';
require_once __DIR__ . '/reporte_pdf_snippet.php';

$fd = isset($_GET['fecha_desde']) ? trim((string) $_GET['fecha_desde']) : '';
$fh = isset($_GET['fecha_hasta']) ? trim((string) $_GET['fecha_hasta']) : '';
if ($fd === '' && isset($_GET['desde'])) {
    $fd = trim((string) $_GET['desde']);
}
if ($fh === '' && isset($_GET['hasta'])) {
    $fh = trim((string) $_GET['hasta']);
}
$args = [
    'fecha_desde' => $fd,
    'fecha_hasta' => $fh,
    'nombre_cliente' => isset($_GET['nombre_cliente']) ? trim((string) $_GET['nombre_cliente']) : '',
    'numero_doc' => isset($_GET['numero_doc']) ? trim((string) $_GET['numero_doc']) : '',
    'cod_item' => isset($_GET['cod_item']) ? trim((string) $_GET['cod_item']) : '',
    'tdoc' => isset($_GET['tdoc']) ? trim((string) $_GET['tdoc']) : '',
    'prefijo_descri_zona_precio' => isset($_GET['prefijo_descri_zona_precio']) ? trim((string) $_GET['prefijo_descri_zona_precio']) : '',
    'limit' => isset($_GET['limit']) && is_numeric($_GET['limit']) ? (int) $_GET['limit'] : 50,
    'offset' => isset($_GET['offset']) && is_numeric($_GET['offset']) ? (int) $_GET['offset'] : 0,
];
foreach (['fecha_desde', 'fecha_hasta', 'nombre_cliente', 'numero_doc', 'cod_item', 'tdoc', 'prefijo_descri_zona_precio'] as $k) {
    if ($args[$k] === '') {
        unset($args[$k]);
    }
}

$pdo = ventas_pdo();
try {
    $out = VentasGeneralBuscarQuery::search($pdo, $args);
} catch (Throwable $e) {
    http_response_code(400);
    header('Content-Type: text/plain; charset=utf-8');
    echo $e->getMessage();
    exit;
}

$rows = $out['filas'];
$limit = $out['limit'];
$offset = $out['offset'];
$pdfName = 'ventasgeneral_buscar_' . date('Y-m-d_His') . '.pdf';
?>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Tabla · Búsqueda ventasgeneral</title>
    <style>
        body { font-family: system-ui, sans-serif; margin: 0; background: #0f172a; color: #e2e8f0; }
        header { padding: 1rem 1.25rem; background: linear-gradient(135deg, #1d4ed8, #6d28d9); }
        h1 { margin: 0; font-size: 1.1rem; font-weight: 600; }
        .meta { margin: 0.35rem 0 0; font-size: 0.85rem; opacity: 0.9; }
        main { padding: 1rem; max-width: 1400px; margin: 0 auto; }
        .wrap-dark { background: #1e293b; border-radius: 12px; padding: 1rem; border: 1px solid #334155; }
    </style>
    <?php ventas_reporte_tabla_styles(); ?>
</head>
<body>
    <header>
        <h1>Reporte tabular — ventasgeneral (búsqueda)</h1>
        <p class="meta">Filas mostradas: <?= count($rows) ?> · limit <?= (int) $limit ?> · offset <?= (int) $offset ?></p>
    </header>
    <main>
        <div class="wrap-dark">
            <div class="reporte-toolbar">
                <button type="button" class="btn-pdf" id="btn-pdf-buscar">Descargar PDF</button>
            </div>
            <div id="reporte-pdf-root">
                <h2 class="pdf-h2">Líneas de ventasgeneral</h2>
                <p class="pdf-meta">Mismos filtros que la consulta del asistente.</p>
                <?php if ($rows === []) { ?>
                    <p>Sin filas.</p>
                <?php } else { ?>
                <table>
                    <thead>
                        <tr>
                            <?php foreach (array_keys($rows[0]) as $col) { ?>
                            <th><?= htmlspecialchars((string) $col, ENT_QUOTES, 'UTF-8') ?></th>
                            <?php } ?>
                        </tr>
                    </thead>
                    <tbody>
                        <?php foreach ($rows as $r) { ?>
                        <tr>
                            <?php foreach ($r as $v) { ?>
                            <td><?= htmlspecialchars((string) $v, ENT_QUOTES, 'UTF-8') ?></td>
                            <?php } ?>
                        </tr>
                        <?php } ?>
                    </tbody>
                </table>
                <?php } ?>
            </div>
        </div>
    </main>
    <?php ventas_reporte_pdf_script(); ?>
    <script>
    ventasBindPdfDownload('btn-pdf-buscar', 'reporte-pdf-root', <?= json_encode($pdfName, JSON_UNESCAPED_UNICODE | JSON_HEX_TAG | JSON_HEX_APOS) ?>);
    </script>
</body>
</html>
