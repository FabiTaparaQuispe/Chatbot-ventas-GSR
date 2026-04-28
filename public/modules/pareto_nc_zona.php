<?php

declare(strict_types=1);

require_once dirname(__DIR__, 2) . '/config/bootstrap.php';
require_once dirname(__DIR__, 2) . '/src/VentasGeneralParetoNc.php';

function pareto_parse_get_date(string $key): ?string
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

$desde = pareto_parse_get_date('desde');
$hasta = pareto_parse_get_date('hasta');
$maxZonas = isset($_GET['max']) && is_numeric($_GET['max']) ? (int) $_GET['max'] : 100;
$maxZonas = max(1, min(200, $maxZonas));
if ($desde === null || $hasta === null || $desde > $hasta) {
    http_response_code(400);
    header('Content-Type: text/plain; charset=utf-8');
    echo 'Parámetros inválidos: use desde=YYYY-MM-DD&hasta=YYYY-MM-DD (opcional max=100)';
    exit;
}

require_once __DIR__ . '/reporte_pdf_snippet.php';

$pdo = ventas_pdo();
$pareto = VentasGeneralParetoNc::datos($pdo, $desde, $hasta, $maxZonas);
$pdfName = 'pareto_nc_zonaprecio_' . $desde . '_' . $hasta . '.pdf';
$labels = [];
$impactos = [];
$pctAcum = [];
foreach ($pareto['filas'] as $f) {
    $labels[] = (string) $f['zona'];
    $impactos[] = (float) $f['impacto_abs_valor'];
    $pctAcum[] = (float) $f['pct_acumulado'];
}
$chartJson = json_encode(
    [
        'labels' => $labels,
        'impactos' => $impactos,
        'pctAcum' => $pctAcum,
        'total' => $pareto['total_impacto_nc'],
        'desde' => $desde,
        'hasta' => $hasta,
    ],
    JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE
);
$pageTitle = 'Pareto NC por zona de precio';
?>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title><?= htmlspecialchars($pageTitle, ENT_QUOTES, 'UTF-8') ?></title>
    <script>
    (function () {
        try {
            var m = document.cookie.match(/(?:^|; )ix2-theme=([^;]*)/);
            var mode = m ? decodeURIComponent(m[1]).toLowerCase().trim() : '';
            if (mode !== 'dark' && mode !== 'light') mode = localStorage.getItem('ix2-theme') || '';
            if (mode !== 'dark' && mode !== 'light') mode = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
            document.documentElement.setAttribute('data-theme', mode);
            document.documentElement.style.colorScheme = mode === 'dark' ? 'dark' : 'light';
        } catch (e) {}
    })();
    </script>
    <link rel="stylesheet" href="../assets/css/app.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js" crossorigin="anonymous"></script>
    <style>
        body { margin: 0; }
        canvas { max-height: 70vh; }
    </style>
    <?php ventas_reporte_tabs_styles(); ?>
    <?php ventas_reporte_tabla_styles(); ?>
</head>
<body>
    <main class="reporte-modulo-main">
        <div class="reporte-page">
            <div class="page-head">
                <h1><?= htmlspecialchars($pageTitle, ENT_QUOTES, 'UTF-8') ?></h1>
                <p class="reporte-inline-meta">Notas de crédito (TDoc 07) · <?= htmlspecialchars($desde, ENT_QUOTES, 'UTF-8') ?> — <?= htmlspecialchars($hasta, ENT_QUOTES, 'UTF-8') ?>
                    · Impacto total: <?= number_format((float) $pareto['total_impacto_nc'], 2, '.', ',') ?>
                    · Hasta <?= (int) $maxZonas ?> zonas</p>
            </div>
            <div class="tabla-listado-wrapper">
                <div class="reporte-toolbar">
                    <button type="button" class="btn btn-primary" id="btn-pdf-nc-inline">Descargar PDF</button>
                </div>
                <div id="reporte-pdf-root">
                    <h2 class="pdf-h2">Pareto NC por zona de precio</h2>
                    <p class="pdf-meta">TDoc = 07 · <?= htmlspecialchars($desde, ENT_QUOTES, 'UTF-8') ?> — <?= htmlspecialchars($hasta, ENT_QUOTES, 'UTF-8') ?></p>
                    <div class="table-wrapper overflow-x-auto productos-dt-skin">
                        <table class="data-table config-table display stripe">
                            <thead>
                                <tr>
                                    <th>N°</th>
                                    <th>Zona precio</th>
                                    <th>Líneas NC</th>
                                    <th>Impacto |Valor|</th>
                                    <th>% del total</th>
                                    <th>% acumulado</th>
                                </tr>
                            </thead>
                            <tbody>
                                <?php $i = 0; foreach ($pareto['filas'] as $f) { $i++; ?>
                                <tr>
                                    <td><?= $i ?></td>
                                    <td><?= htmlspecialchars((string) ($f['zona'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                                    <td><?= (int) ($f['lineas_nc'] ?? 0) ?></td>
                                    <td><?= number_format((float) ($f['impacto_abs_valor'] ?? 0), 2, '.', ',') ?></td>
                                    <td><?= htmlspecialchars((string) ($f['pct_del_total'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                                    <td><?= htmlspecialchars((string) ($f['pct_acumulado'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                                </tr>
                                <?php } ?>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
            <section class="reporte-chart-section" aria-label="Gráfico">
                <h3 class="reporte-chart-heading">Gráfico</h3>
                <div class="chart-inner">
                    <canvas id="paretoChart" aria-label="Gráfico Pareto"></canvas>
                </div>
            </section>
        </div>
    </main>
    <script>
    (function () {
        var payload = <?= $chartJson !== false ? $chartJson : '{}' ?>;
        var created = false;
        function buildChart() {
            if (created || !window.Chart) return;
            var ctx = document.getElementById('paretoChart');
            if (!ctx || !payload.labels) return;
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: payload.labels,
                    datasets: [
                        {
                            label: 'Impacto NC (|Valor|)',
                            data: payload.impactos,
                            backgroundColor: 'rgba(59, 130, 246, 0.65)',
                            borderColor: 'rgba(59, 130, 246, 1)',
                            borderWidth: 1,
                            yAxisID: 'y',
                            order: 2,
                        },
                        {
                            type: 'line',
                            label: '% acumulado',
                            data: payload.pctAcum,
                            borderColor: 'rgba(248, 113, 113, 1)',
                            backgroundColor: 'rgba(248, 113, 113, 0.15)',
                            borderWidth: 2,
                            tension: 0.15,
                            yAxisID: 'y1',
                            order: 1,
                            pointRadius: 2,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    stacked: false,
                    plugins: {
                        legend: { labels: { color: '#cbd5e1' } },
                        tooltip: {
                            callbacks: {
                                label: function (ctx) {
                                    var v = ctx.parsed.y;
                                    if (ctx.dataset.label && ctx.dataset.label.indexOf('%') >= 0) {
                                        return ctx.dataset.label + ': ' + (v != null ? v.toFixed(2) : '') + '%';
                                    }
                                    return ctx.dataset.label + ': ' + (v != null ? v.toLocaleString('es-PE', { maximumFractionDigits: 2 }) : '');
                                },
                            },
                        },
                    },
                    scales: {
                        x: {
                            ticks: { color: '#94a3b8', maxRotation: 60, minRotation: 45, autoSkip: true, maxTicksLimit: 24 },
                            grid: { color: 'rgba(148, 163, 184, 0.15)' },
                        },
                        y: {
                            type: 'linear',
                            position: 'left',
                            ticks: { color: '#94a3b8' },
                            grid: { color: 'rgba(148, 163, 184, 0.15)' },
                            title: { display: true, text: 'Impacto', color: '#cbd5e1' },
                        },
                        y1: {
                            type: 'linear',
                            position: 'right',
                            min: 0,
                            max: 100,
                            grid: { drawOnChartArea: false },
                            ticks: { color: '#fca5a5', callback: function (v) { return v + '%'; } },
                            title: { display: true, text: '% acumulado', color: '#fecaca' },
                        },
                    },
                },
            });
            created = true;
        }
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', buildChart);
        } else {
            buildChart();
        }
    })();
    </script>
    <?php ventas_reporte_tabs_script(); ?>
    <?php ventas_reporte_pdf_script(); ?>
    <script>
    ventasBindPdfDownload('btn-pdf-nc-inline', 'reporte-pdf-root', <?= json_encode($pdfName, JSON_UNESCAPED_UNICODE | JSON_HEX_TAG | JSON_HEX_APOS) ?>);
    </script>
</body>
</html>
