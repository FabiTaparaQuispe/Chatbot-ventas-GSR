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
$data = VentasGeneralReportesGraficos::topProductos($pdo, $desde, $hasta, $top);
$labels = [];
$valores = [];
foreach ($data['filas'] as $f) {
    $g = (string) ($f['glosa'] ?? $f['cod_item'] ?? '');
    $labels[] = strlen($g) > 30 ? substr($g, 0, 27) . '…' : $g;
    $valores[] = (float) ($f['suma_valor'] ?? 0);
}
$chartJson = json_encode(['labels' => $labels, 'valores' => $valores], JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE);
$pdfName = 'top_productos_' . $desde . '_' . $hasta . '.pdf';
?>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Top productos</title>
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
                <h1>Top productos por importe (SUM Valor)</h1>
                <p class="reporte-inline-meta"><?= htmlspecialchars($desde, ENT_QUOTES, 'UTF-8') ?> — <?= htmlspecialchars($hasta, ENT_QUOTES, 'UTF-8') ?> · Top <?= (int) $top ?></p>
            </div>
            <div class="tabla-listado-wrapper">
                <div class="reporte-toolbar"><button type="button" class="btn btn-primary" id="btn-pdf">Descargar PDF</button></div>
                <div id="reporte-pdf-root">
                    <h2 class="pdf-h2">Top productos</h2>
                    <div class="table-wrapper overflow-x-auto productos-dt-skin">
                        <table class="data-table config-table display stripe">
                            <thead><tr><th>N°</th><th>Código ítem</th><th>Descripción</th><th>Líneas</th><th>Importe</th><th>Cantidad</th></tr></thead>
                            <tbody>
                                <?php $i = 0; foreach ($data['filas'] as $f) { $i++; ?>
                                <tr>
                                    <td><?= $i ?></td>
                                    <td><?= htmlspecialchars((string) ($f['cod_item'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                                    <td><?= htmlspecialchars((string) ($f['glosa'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                                    <td><?= (int) ($f['lineas'] ?? 0) ?></td>
                                    <td><?= number_format((float) ($f['suma_valor'] ?? 0), 2, '.', ',') ?></td>
                                    <td><?= htmlspecialchars((string) ($f['suma_cantidad'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
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
            [34, 197, 94],
            [59, 130, 246],
            [168, 85, 247],
            [249, 115, 22],
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
                            label: 'SUM(Valor)',
                            data: payload.valores,
                            backgroundColor: cols.bg,
                            borderColor: cols.br,
                            borderWidth: 1,
                            maxBarThickness: 52,
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
                            beginAtZero: true,
                            title: { display: true, text: 'SUM(Valor)', color: Chart.defaults.color },
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
