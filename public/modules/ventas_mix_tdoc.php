<?php

declare(strict_types=1);

require_once dirname(__DIR__, 2) . '/config/bootstrap.php';
require_once dirname(__DIR__, 2) . '/src/VentasGeneralReportesGraficos.php';
require_once __DIR__ . '/ventas_modules_parse_get.php';
require_once __DIR__ . '/reporte_pdf_snippet.php';

$desde = ventas_modules_parse_date_get_any(['desde', 'fecha_desde']);
$hasta = ventas_modules_parse_date_get_any(['hasta', 'fecha_hasta']);
if ($desde === null || $hasta === null || $desde > $hasta) {
    http_response_code(400);
    header('Content-Type: text/plain; charset=utf-8');
    echo 'Parámetros: desde, hasta';
    exit;
}
$pdo = ventas_pdo();
$data = VentasGeneralReportesGraficos::mixPorTdoc($pdo, $desde, $hasta);
$labels = array_column($data['filas'], 'tdoc');
$valores = array_map(static fn ($r) => (float) ($r['suma_valor'] ?? 0), $data['filas']);
$chartJson = json_encode(['labels' => $labels, 'valores' => $valores], JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE);
$pdfName = 'mix_tdoc_' . $desde . '_' . $hasta . '.pdf';
?>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Mix TDoc</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js" crossorigin="anonymous"></script>
    <style>
        body { font-family: system-ui, sans-serif; margin: 0; background: #0f172a; color: #e2e8f0; }
        header { padding: 1rem 1.25rem; background: linear-gradient(135deg, #1d4ed8, #6d28d9); }
        h1 { margin: 0; font-size: 1.1rem; }
        .meta { margin: 0.35rem 0 0; font-size: 0.85rem; opacity: 0.9; }
        main { padding: 1rem; max-width: 900px; margin: 0 auto; }
        .chart-wrap { margin-bottom: 1rem; }
    </style>
    <?php ventas_reporte_tabs_styles(); ?>
    <?php ventas_reporte_tabla_styles(); ?>
</head>
<body>
    <header><h1>Ventas por tipo de documento (TDoc)</h1>
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
                        <h2 class="pdf-h2">SUM(Valor) por TDoc</h2>
                        <table>
                            <thead><tr><th>TDoc</th><th>Líneas</th><th>SUM(Valor)</th><th>% del total</th></tr></thead>
                            <tbody>
                                <?php foreach ($data['filas'] as $f) { ?>
                                <tr>
                                    <td><?= htmlspecialchars((string) ($f['tdoc'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                                    <td><?= (int) ($f['lineas'] ?? 0) ?></td>
                                    <td><?= number_format((float) ($f['suma_valor'] ?? 0), 2, '.', ',') ?></td>
                                    <td><?= htmlspecialchars((string) ($f['pct_del_total'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                                </tr>
                                <?php } ?>
                            </tbody>
                        </table>
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
                type: 'doughnut',
                data: {
                    labels: payload.labels,
                    datasets: [{ data: payload.valores, backgroundColor: ['#3b82f6','#a855f7','#22c55e','#f97316','#ec4899','#14b8a6','#eab308','#64748b'] }],
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { color: '#cbd5e1' } } } },
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
