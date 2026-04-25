<?php

declare(strict_types=1);

require_once dirname(__DIR__, 2) . '/config/bootstrap.php';
require_once dirname(__DIR__, 2) . '/src/VentasGeneralReportesGraficos.php';
require_once __DIR__ . '/ventas_modules_parse_get.php';
require_once __DIR__ . '/reporte_pdf_snippet.php';

$desde = ventas_modules_parse_date_get_any(['desde', 'fecha_desde']);
$hasta = ventas_modules_parse_date_get_any(['hasta', 'fecha_hasta']);
$dim = ventas_modules_get_dim_precio_comercial();
$top = ventas_modules_int_from_get(['top', 'top_n'], 20, 1, 100);

if ($desde === null || $hasta === null || $desde > $hasta) {
    http_response_code(400);
    header('Content-Type: text/plain; charset=utf-8');
    echo 'Parámetros: desde, hasta (YYYY-MM-DD); alias fecha_desde, fecha_hasta. dim|dimension=precio|comercial, top|top_n=20';
    exit;
}

$pdo = ventas_pdo();
try {
    $data = VentasGeneralReportesGraficos::barrasPorDimension($pdo, $desde, $hasta, $dim, $top);
} catch (Throwable $e) {
    http_response_code(400);
    header('Content-Type: text/plain; charset=utf-8');
    echo $e->getMessage();
    exit;
}

$dimLabel = $dim === 'comercial' ? 'Zona comercial' : 'DescriZonaPrecio';
$labels = [];
$valores = [];
foreach ($data['filas'] as $f) {
    $lab = (string) ($f['etiqueta'] ?? '');
    if (function_exists('mb_strlen') && mb_strlen($lab, 'UTF-8') > 32) {
        $lab = mb_substr($lab, 0, 29, 'UTF-8') . '…';
    } elseif (strlen($lab) > 32) {
        $lab = substr($lab, 0, 29) . '…';
    }
    $labels[] = $lab;
    $valores[] = (float) ($f['suma_valor'] ?? 0);
}
$chartJson = json_encode([
    'labels' => $labels,
    'valores' => $valores,
    'titulo' => 'SUM(Valor) por ' . $dimLabel,
], JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE);
$pdfName = 'ventas_barras_' . $dim . '_' . $desde . '_' . $hasta . '.pdf';
$pageTitle = 'Ventas por ' . $dimLabel;
?>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title><?= htmlspecialchars($pageTitle, ENT_QUOTES, 'UTF-8') ?></title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js" crossorigin="anonymous"></script>
    <style>
        body { font-family: system-ui, sans-serif; margin: 0; background: #0f172a; color: #e2e8f0; }
        header { padding: 1rem 1.25rem; background: linear-gradient(135deg, #1d4ed8, #6d28d9); }
        h1 { margin: 0; font-size: 1.1rem; font-weight: 600; }
        .meta { margin: 0.35rem 0 0; font-size: 0.85rem; opacity: 0.9; }
        main { padding: 1rem; max-width: 1100px; margin: 0 auto; }
        .chart-wrap { margin-bottom: 1rem; }
    </style>
    <?php ventas_reporte_tabs_styles(); ?>
    <?php ventas_reporte_tabla_styles(); ?>
</head>
<body>
    <header>
        <h1><?= htmlspecialchars($pageTitle, ENT_QUOTES, 'UTF-8') ?></h1>
        <p class="meta">ventasgeneral · <?= htmlspecialchars($desde, ENT_QUOTES, 'UTF-8') ?> a <?= htmlspecialchars($hasta, ENT_QUOTES, 'UTF-8') ?>
            · Top <?= (int) $top ?> · Total periodo: <?= number_format((float) $data['total_valor'], 2, '.', ',') ?></p>
    </header>
    <main>
        <div class="chart-wrap" data-ventas-tabs>
            <div class="reporte-tabs">
                <div class="reporte-tab-bar">
                    <button type="button" class="reporte-tab is-active">Tabla</button>
                    <button type="button" class="reporte-tab">Gráfico</button>
                </div>
                <div class="reporte-tab-panel is-active" data-panel="0">
                    <div class="reporte-toolbar">
                        <button type="button" class="btn-pdf" id="btn-pdf">Descargar PDF</button>
                    </div>
                    <div id="reporte-pdf-root">
                        <h2 class="pdf-h2">Ranking por <?= htmlspecialchars($dimLabel, ENT_QUOTES, 'UTF-8') ?></h2>
                        <p class="pdf-meta"><?= htmlspecialchars($desde, ENT_QUOTES, 'UTF-8') ?> — <?= htmlspecialchars($hasta, ENT_QUOTES, 'UTF-8') ?></p>
                        <table>
                            <thead>
                                <tr><th>#</th><th><?= htmlspecialchars($dimLabel, ENT_QUOTES, 'UTF-8') ?></th><th>Líneas</th><th>SUM(Valor)</th><th>% total</th><th>Cantidad</th><th>Peso</th></tr>
                            </thead>
                            <tbody>
                                <?php $i = 0; foreach ($data['filas'] as $f) { $i++; ?>
                                <tr>
                                    <td><?= $i ?></td>
                                    <td><?= htmlspecialchars((string) ($f['etiqueta'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                                    <td><?= (int) ($f['lineas'] ?? 0) ?></td>
                                    <td><?= number_format((float) ($f['suma_valor'] ?? 0), 2, '.', ',') ?></td>
                                    <td><?= htmlspecialchars((string) ($f['pct_del_total'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                                    <td><?= htmlspecialchars((string) ($f['suma_cantidad'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                                    <td><?= htmlspecialchars((string) ($f['suma_peso'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                                </tr>
                                <?php } ?>
                            </tbody>
                        </table>
                    </div>
                </div>
                <div class="reporte-tab-panel chart-panel" data-panel="1">
                    <div class="chart-inner"><canvas id="ch" aria-label="Gráfico"></canvas></div>
                </div>
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
            // Estilo y animación alineados al proyecto de referencia (app-charts.js)
            var LAB = [
                { f: 0.8, b: 1, rgb: [54, 162, 235] },
                { f: 0.8, b: 1, rgb: [75, 192, 192] },
                { f: 0.8, b: 1, rgb: [153, 102, 255] },
                { f: 0.8, b: 1, rgb: [255, 99, 132] },
                { f: 0.8, b: 1, rgb: [255, 159, 64] },
                { f: 0.8, b: 1, rgb: [255, 205, 86] },
                { f: 0.8, b: 1, rgb: [201, 203, 207] },
            ];
            function rgba(c, a) { return 'rgba(' + c.rgb[0] + ', ' + c.rgb[1] + ', ' + c.rgb[2] + ', ' + a + ')'; }
            var bg = payload.labels.map(function (_, i) { return rgba(LAB[i % LAB.length], 0.8); });
            var br = payload.labels.map(function (_, i) { return rgba(LAB[i % LAB.length], 1); });

            Chart.defaults.color = '#94a3b8';
            Chart.defaults.borderColor = 'rgba(148,163,184,0.15)';

            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: payload.labels,
                    datasets: [{
                        label: payload.titulo || 'Valor',
                        data: payload.valores,
                        backgroundColor: bg,
                        borderColor: br,
                        borderWidth: 1,
                        maxBarThickness: 48
                    }],
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: {
                        duration: 1500,
                        easing: 'easeOutCubic',
                        delay: function (context) {
                            if (context.type === 'data' && context.mode === 'default') {
                                return (context.dataIndex || 0) * 125;
                            }
                            return 0;
                        }
                    },
                    plugins: {
                        legend: { display: false },
                        tooltip: { backgroundColor: 'rgba(15, 23, 42, 0.92)', padding: 12, cornerRadius: 8 }
                    },
                    scales: {
                        x: { beginAtZero: true, ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,0.15)' } },
                        y: { ticks: { color: '#94a3b8', font: { size: 10 } }, grid: { display: false } },
                    },
                },
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
