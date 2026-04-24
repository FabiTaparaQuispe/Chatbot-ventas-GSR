<?php

declare(strict_types=1);

require_once dirname(__DIR__, 2) . '/config/bootstrap.php';
require_once dirname(__DIR__, 2) . '/src/VentasGeneralReportesGraficos.php';
require_once __DIR__ . '/ventas_modules_parse_get.php';
require_once __DIR__ . '/reporte_pdf_snippet.php';

$desde = ventas_modules_parse_date_get_any(['desde', 'fecha_desde']);
$hasta = ventas_modules_parse_date_get_any(['hasta', 'fecha_hasta']);
$top = ventas_modules_int_from_get(['top', 'top_n'], 15, 1, 100);
if ($desde === null || $hasta === null || $desde > $hasta) {
    http_response_code(400);
    header('Content-Type: text/plain; charset=utf-8');
    echo 'Parámetros: desde, hasta, top=15';
    exit;
}
$pdo = ventas_pdo();
$data = VentasGeneralReportesGraficos::topRutaComercial($pdo, $desde, $hasta, $top);
$labels = [];
$valores = [];
foreach ($data['filas'] as $f) {
    $lab = (string) ($f['ruta'] ?? '');
    $labels[] = strlen($lab) > 30 ? substr($lab, 0, 27) . '…' : $lab;
    $valores[] = (float) ($f['suma_valor'] ?? 0);
}
$chartJson = json_encode(['labels' => $labels, 'valores' => $valores], JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE);
$pdfName = 'ventas_ruta_' . $desde . '_' . $hasta . '.pdf';
?>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <title>Ventas por ruta comercial</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js" crossorigin="anonymous"></script>
    <style>
        body { font-family: system-ui, sans-serif; margin: 0; background: #0f172a; color: #e2e8f0; }
        header { padding: 1rem 1.25rem; background: linear-gradient(135deg, #1d4ed8, #6d28d9); }
        h1 { margin: 0; font-size: 1.1rem; }
        .meta { margin: 0.35rem 0 0; font-size: 0.85rem; opacity: 0.9; }
        main { padding: 1rem; max-width: 1100px; margin: 0 auto; }
        .chart-wrap { margin-bottom: 1rem; }
    </style>
    <?php ventas_reporte_tabs_styles(); ?>
    <?php ventas_reporte_tabla_styles(); ?>
</head>
<body>
    <header><h1>Ventas por RutaComercial</h1>
        <p class="meta"><?= htmlspecialchars($desde, ENT_QUOTES, 'UTF-8') ?> — <?= htmlspecialchars($hasta, ENT_QUOTES, 'UTF-8') ?></p></header>
    <main>
        <div class="chart-wrap" data-ventas-tabs>
            <div class="reporte-tabs">
                <div class="reporte-tab-bar">
                    <button type="button" class="reporte-tab is-active">Tabla</button>
                    <button type="button" class="reporte-tab">Gráfico</button>
                </div>
                <div class="reporte-tab-panel is-active" data-panel="0">
                    <div class="reporte-toolbar"><button type="button" class="btn-pdf" id="btn-pdf">Descargar PDF</button></div>
                    <div id="reporte-pdf-root">
                        <h2 class="pdf-h2">Top rutas</h2>
                        <table><thead><tr><th>#</th><th>RutaComercial</th><th>Líneas</th><th>SUM(Valor)</th></tr></thead><tbody>
                            <?php $i = 0; foreach ($data['filas'] as $f) { $i++; ?>
                            <tr>
                                <td><?= $i ?></td>
                                <td><?= htmlspecialchars((string) ($f['ruta'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                                <td><?= (int) ($f['lineas'] ?? 0) ?></td>
                                <td><?= number_format((float) ($f['suma_valor'] ?? 0), 2, '.', ',') ?></td>
                            </tr>
                            <?php } ?>
                        </tbody></table>
                    </div>
                </div>
                <div class="reporte-tab-panel chart-panel" data-panel="1"><div class="chart-inner"><canvas id="ch"></canvas></div></div>
            </div>
        </div>
    </main>
    <script>
    (function () {
        var payload = <?= $chartJson !== false ? $chartJson : '{}' ?>;
        var root = document.querySelector('[data-ventas-tabs]');
        var done = false;
        function build() {
            if (done || !window.Chart) return;
            var ctx = document.getElementById('ch');
            if (!ctx || !payload.labels) return;
            new Chart(ctx, {
                type: 'bar',
                data: { labels: payload.labels, datasets: [{ label: 'SUM(Valor)', data: payload.valores, backgroundColor: 'rgba(168,85,247,0.75)' }] },
                options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { color: '#cbd5e1' } } },
                    scales: { x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,0.15)' } }, y: { ticks: { color: '#94a3b8', font: { size: 9 } }, grid: { color: 'rgba(148,163,184,0.15)' } } } },
            });
            done = true;
        }
        if (root) root.addEventListener('ventas-reporte-tab', function (ev) { if (ev.detail && ev.detail.index === 1) build(); });
    })();
    </script>
    <?php ventas_reporte_tabs_script(); ?>
    <?php ventas_reporte_pdf_script(); ?>
    <script>ventasBindPdfDownload('btn-pdf', 'reporte-pdf-root', <?= json_encode($pdfName, JSON_UNESCAPED_UNICODE | JSON_HEX_TAG | JSON_HEX_APOS) ?>);</script>
</body>
</html>
