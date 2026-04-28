<?php

declare(strict_types=1);

require_once dirname(__DIR__, 2) . '/config/bootstrap.php';
require_once dirname(__DIR__, 2) . '/src/VentasGeneralReportesGraficos.php';
require_once __DIR__ . '/ventas_modules_parse_get.php';
require_once __DIR__ . '/reporte_pdf_snippet.php';

$desde = ventas_modules_parse_date_get_any(['desde', 'fecha_desde']);
$hasta = ventas_modules_parse_date_get_any(['hasta', 'fecha_hasta']);
$top = ventas_modules_int_from_get(['top', 'top_n'], 10, 1, 100);
if ($desde === null || $hasta === null || $desde > $hasta) {
    http_response_code(400);
    header('Content-Type: text/plain; charset=utf-8');
    echo 'Parámetros: desde, hasta, top=10 (TDoc=07)';
    exit;
}
$pdo = ventas_pdo();
$data = VentasGeneralReportesGraficos::topClientesNotaCredito($pdo, $desde, $hasta, $top);
$labels = [];
$valores = [];
$pctAcum = [];
foreach ($data['filas'] as $f) {
    $lab = (string) ($f['nombre_cliente'] ?? $f['cod_cliente'] ?? '');
    $labels[] = strlen($lab) > 28 ? substr($lab, 0, 25) . '…' : $lab;
    $valores[] = (float) ($f['lineas'] ?? 0);
    $pctAcum[] = (float) ($f['pct_lineas_acumulado'] ?? 0);
}
$chartJson = json_encode(['labels' => $labels, 'valores' => $valores, 'pctAcum' => $pctAcum], JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE);
$pdfName = 'top_clientes_nc_' . $desde . '_' . $hasta . '.pdf';
?>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Top clientes — notas de crédito (TDoc 07)</title>
    <script>
    (function () {
        function readCookieTheme() {
            try {
                var m = document.cookie.match(/(?:^|; )ix2-theme=([^;]*)/);
                return m ? decodeURIComponent(m[1]).toLowerCase().trim() : '';
            } catch (e) { return ''; }
        }
        var mode = readCookieTheme() || (function () { try { return localStorage.getItem('ix2-theme'); } catch (e) { return null; } })();
        if (mode !== 'dark' && mode !== 'light') {
            mode = (window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches) ? 'dark' : 'light';
        }
        var d = document.documentElement;
        d.setAttribute('data-theme', mode);
        d.style.colorScheme = mode === 'dark' ? 'dark' : 'light';
    })();
    </script>
    <link rel="stylesheet" href="../assets/css/app.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js" crossorigin="anonymous"></script>
    <style>
        body { margin: 0; }
    </style>
    <?php ventas_reporte_tabs_styles(); ?>
    <?php ventas_reporte_tabla_styles(); ?>
</head>
<body>
    <main class="reporte-modulo-main">
        <div class="reporte-page">
            <div class="page-head">
                <h1>Top clientes por notas de crédito (TDoc = 07)</h1>
                <p class="reporte-inline-meta"><?= htmlspecialchars($desde, ENT_QUOTES, 'UTF-8') ?> — <?= htmlspecialchars($hasta, ENT_QUOTES, 'UTF-8') ?>
                    · Líneas NC en periodo: <?= (int) ($data['total_lineas_nc'] ?? 0) ?>
                    · Importe NC: <?= number_format((float) ($data['total_valor_nc'] ?? 0), 2, '.', ',') ?></p>
            </div>
            <div class="tabla-listado-wrapper">
                <div class="reporte-toolbar"><button type="button" class="btn btn-primary" id="btn-pdf">Descargar PDF</button></div>
                <div id="reporte-pdf-root">
                    <h2 class="pdf-h2">Ranking clientes (notas de crédito)</h2>
                    <div class="table-wrapper overflow-x-auto productos-dt-skin">
                        <table class="data-table config-table display stripe">
                            <thead><tr><th>N°</th><th>Cód. cliente</th><th>Nombre cliente</th><th>Líneas NC</th><th>Importe</th><th>% líneas</th><th>% acum. líneas</th></tr></thead>
                            <tbody>
                                <?php $i = 0; foreach ($data['filas'] as $f) { $i++; ?>
                                <tr>
                                    <td><?= $i ?></td>
                                    <td><?= htmlspecialchars((string) ($f['cod_cliente'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                                    <td><?= htmlspecialchars((string) ($f['nombre_cliente'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                                    <td><?= (int) ($f['lineas'] ?? 0) ?></td>
                                    <td><?= number_format((float) ($f['suma_valor'] ?? 0), 2, '.', ',') ?></td>
                                    <td><?= htmlspecialchars((string) ($f['pct_lineas_del_total'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                                    <td><?= htmlspecialchars((string) ($f['pct_lineas_acumulado'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                                </tr>
                                <?php } ?>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
            <section class="reporte-chart-section" aria-label="Gráfico">
                <h3 class="reporte-chart-heading">Gráfico</h3>
                <div class="chart-inner"><canvas id="ch"></canvas></div>
            </section>
        </div>
    </main>
    <script>
    (function () {
        var payload = <?= $chartJson !== false ? $chartJson : '{}' ?>;
        var chart = null;

        var PALETTE = [
            [251, 146, 60],
            [59, 130, 246],
            [168, 85, 247],
            [34, 197, 94],
            [236, 72, 153],
            [20, 184, 166],
            [234, 179, 8],
            [100, 116, 139],
        ];
        function rgba(rgb, a) {
            return 'rgba(' + rgb[0] + ',' + rgb[1] + ',' + rgb[2] + ',' + a + ')';
        }
        function isDark() {
            return document.documentElement.getAttribute('data-theme') === 'dark';
        }
        function applyThemeDefaults() {
            var dark = isDark();
            Chart.defaults.color = dark ? '#a1a1aa' : '#64748b';
            Chart.defaults.borderColor = dark ? '#3f3f46' : '#e5e7eb';
        }
        function colorsForBars(n) {
            var bg = [];
            var br = [];
            for (var i = 0; i < n; i++) {
                var c = PALETTE[i % PALETTE.length];
                bg.push(rgba(c, 0.78));
                br.push(rgba(c, 1));
            }
            return { bg: bg, br: br };
        }
        function build() {
            if (!window.Chart || !payload.labels) return;
            var ctx = document.getElementById('ch');
            if (!ctx || !payload.labels) return;
            if (chart) {
                try { chart.destroy(); } catch (e0) {}
                chart = null;
            }
            applyThemeDefaults();
            var cols = colorsForBars(payload.valores ? payload.valores.length : 0);
            chart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: payload.labels,
                    datasets: [
                        {
                            label: 'Cantidad NC (líneas)',
                            data: payload.valores,
                            backgroundColor: cols.bg,
                            borderColor: cols.br,
                            borderWidth: 1,
                            yAxisID: 'y',
                            order: 2,
                        },
                        {
                            type: 'line',
                            label: '% acum. líneas',
                            data: payload.pctAcum,
                            borderColor: rgba([248, 113, 113], 1),
                            backgroundColor: rgba([248, 113, 113], 0.14),
                            borderWidth: 2,
                            yAxisID: 'y1',
                            order: 1,
                            tension: 0.22,
                            pointRadius: 2,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    animation: {
                        duration: 1200,
                        easing: 'easeOutCubic',
                        delay: function (context) {
                            if (context.type === 'data' && context.mode === 'default') return (context.dataIndex || 0) * 55;
                            return 0;
                        },
                    },
                    plugins: { legend: { labels: { color: Chart.defaults.color } } },
                    scales: {
                        x: {
                            ticks: { color: Chart.defaults.color, maxRotation: 60, minRotation: 35, autoSkip: true, maxTicksLimit: 20 },
                            grid: { color: Chart.defaults.borderColor },
                        },
                        y: {
                            ticks: { color: Chart.defaults.color },
                            grid: { color: Chart.defaults.borderColor },
                            title: { display: true, text: 'Líneas NC', color: Chart.defaults.color },
                        },
                        y1: {
                            type: 'linear',
                            position: 'right',
                            min: 0,
                            max: 100,
                            grid: { drawOnChartArea: false },
                            ticks: { color: isDark() ? '#fca5a5' : '#ef4444', callback: function (v) { return v + '%'; } },
                            title: { display: true, text: '% acumulado', color: isDark() ? '#fecaca' : '#ef4444' },
                        },
                    },
                },
            });
        }
        function setTheme(mode) {
            try {
                document.documentElement.setAttribute('data-theme', mode);
                document.documentElement.style.colorScheme = mode === 'dark' ? 'dark' : 'light';
            } catch (e) {}
        }
        function bootChart() {
            build();
        }
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', bootChart);
        } else {
            bootChart();
        }
        window.addEventListener('storage', function (ev) {
            if (!ev || ev.key !== 'ix2-theme') return;
            var mode = (ev.newValue === 'dark' || ev.newValue === 'light') ? ev.newValue : null;
            if (!mode) return;
            setTheme(mode);
            if (chart) build();
        });
    })();
    </script>
    <?php ventas_reporte_tabs_script(); ?>
    <?php ventas_reporte_pdf_script(); ?>
    <script>ventasBindPdfDownload('btn-pdf', 'reporte-pdf-root', <?= json_encode($pdfName, JSON_UNESCAPED_UNICODE | JSON_HEX_TAG | JSON_HEX_APOS) ?>);</script>
</body>
</html>
