<?php

declare(strict_types=1);

require_once dirname(__DIR__, 2) . '/config/bootstrap.php';
require_once dirname(__DIR__, 2) . '/src/VentasGeneralTopClientesZona.php';
require_once __DIR__ . '/ventas_modules_parse_get.php';

$desde = ventas_modules_parse_date_get_any(['desde', 'fecha_desde']);
$hasta = ventas_modules_parse_date_get_any(['hasta', 'fecha_hasta']);
$prefijoRaw = '';
foreach (['prefijo', 'prefijo_descri_zona_precio'] as $pk) {
    if (!isset($_GET[$pk])) {
        continue;
    }
    $t = trim((string) $_GET[$pk]);
    if ($t !== '') {
        $prefijoRaw = $t;
        break;
    }
}
$top = ventas_modules_int_from_get(['top', 'top_n'], 10, 1, 100);

if ($desde === null || $hasta === null || $desde > $hasta || $prefijoRaw === '') {
    http_response_code(400);
    header('Content-Type: text/plain; charset=utf-8');
    echo 'Parámetros inválidos: desde y hasta (YYYY-MM-DD); alias fecha_desde y fecha_hasta. prefijo o prefijo_descri_zona_precio (ej. LAJOYA). Opcional top o top_n=10';
    exit;
}

require_once __DIR__ . '/reporte_pdf_snippet.php';

$pdo = ventas_pdo();
try {
    $data = VentasGeneralTopClientesZona::datos($pdo, $desde, $hasta, $prefijoRaw, $top);
} catch (Throwable $e) {
    http_response_code(400);
    header('Content-Type: text/plain; charset=utf-8');
    echo 'Error: ' . $e->getMessage();
    exit;
}

$labels = [];
$valores = [];
$pctAcum = [];
foreach ($data['filas'] as $f) {
    $nom = (string) ($f['nombre_cliente'] ?? '');
    $cod = (string) ($f['cod_cliente'] ?? '');
    $lab = $nom !== '' ? $nom : $cod;
    if (function_exists('mb_strlen') && mb_strlen($lab, 'UTF-8') > 28) {
        $lab = mb_substr($lab, 0, 25, 'UTF-8') . '…';
    } elseif (strlen($lab) > 28) {
        $lab = substr($lab, 0, 25) . '…';
    }
    $labels[] = $lab;
    $valores[] = (float) ($f['suma_valor'] ?? 0);
    $pctAcum[] = (float) ($f['pct_acumulado'] ?? 0);
}

$chartJson = json_encode(
    [
        'labels' => $labels,
        'valores' => $valores,
        'pctAcum' => $pctAcum,
        'total' => $data['total_valor_zona'],
        'desde' => $desde,
        'hasta' => $hasta,
        'prefijo' => $data['prefijo_descri_zona_precio'],
    ],
    JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE
);
$pageTitle = 'Pareto clientes · ' . htmlspecialchars($data['prefijo_descri_zona_precio'], ENT_QUOTES, 'UTF-8');
$pdfName = 'pareto_clientes_' . preg_replace('/[^a-zA-Z0-9_-]+/', '_', $data['prefijo_descri_zona_precio']) . '_' . $desde . '_' . $hasta . '.pdf';
?>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title><?= $pageTitle ?></title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js" crossorigin="anonymous"></script>
    <style>
        body { font-family: system-ui, sans-serif; margin: 0; background: #0f172a; color: #e2e8f0; }
        header { padding: 1rem 1.25rem; background: linear-gradient(135deg, #1d4ed8, #6d28d9); }
        h1 { margin: 0; font-size: 1.1rem; font-weight: 600; }
        .meta { margin: 0.35rem 0 0; font-size: 0.85rem; opacity: 0.9; }
        main { padding: 1rem; max-width: 1100px; margin: 0 auto; }
        .chart-wrap { margin-bottom: 1rem; }
        canvas { max-height: 70vh; }
    </style>
    <?php ventas_reporte_tabs_styles(); ?>
    <?php ventas_reporte_tabla_styles(); ?>
</head>
<body>
    <header>
        <h1>Top clientes por Valor — zona <?= htmlspecialchars($data['prefijo_descri_zona_precio'], ENT_QUOTES, 'UTF-8') ?></h1>
        <p class="meta">ventasgeneral · <?= htmlspecialchars($desde, ENT_QUOTES, 'UTF-8') ?> a <?= htmlspecialchars($hasta, ENT_QUOTES, 'UTF-8') ?>
            · Total SUM(Valor) en zona: <?= number_format((float) $data['total_valor_zona'], 2, '.', ',') ?>
            · Top <?= (int) $top ?></p>
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
                        <button type="button" class="btn-pdf" id="btn-pdf-clientes-inline">Descargar PDF</button>
                    </div>
                    <div id="reporte-pdf-root">
                        <h2 class="pdf-h2">Ranking de clientes por SUM(Valor)</h2>
                        <p class="pdf-meta">DescriZonaPrecio LIKE <?= htmlspecialchars($data['prefijo_descri_zona_precio'], ENT_QUOTES, 'UTF-8') ?>% · <?= htmlspecialchars($desde, ENT_QUOTES, 'UTF-8') ?> — <?= htmlspecialchars($hasta, ENT_QUOTES, 'UTF-8') ?></p>
                        <table>
                            <thead>
                                <tr>
                                    <th>#</th>
                                    <th>Cod. cliente</th>
                                    <th>Nombre cliente</th>
                                    <th>SUM(Valor)</th>
                                    <th>Líneas</th>
                                    <th>% zona</th>
                                    <th>% acum.</th>
                                </tr>
                            </thead>
                            <tbody>
                                <?php $i = 0; foreach ($data['filas'] as $f) { $i++; ?>
                                <tr>
                                    <td><?= $i ?></td>
                                    <td><?= htmlspecialchars((string) ($f['cod_cliente'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                                    <td><?= htmlspecialchars((string) ($f['nombre_cliente'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                                    <td><?= number_format((float) ($f['suma_valor'] ?? 0), 2, '.', ',') ?></td>
                                    <td><?= (int) ($f['lineas_venta'] ?? 0) ?></td>
                                    <td><?= htmlspecialchars((string) ($f['pct_del_total_zona'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                                    <td><?= htmlspecialchars((string) ($f['pct_acumulado'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                                </tr>
                                <?php } ?>
                            </tbody>
                        </table>
                    </div>
                </div>
                <div class="reporte-tab-panel chart-panel" data-panel="1">
                    <div class="chart-inner">
                        <canvas id="paretoChart" aria-label="Gráfico Pareto clientes"></canvas>
                    </div>
                </div>
            </div>
        </div>
    </main>
    <script>
    (function () {
        var payload = <?= $chartJson !== false ? $chartJson : '{}' ?>;
        var root = document.querySelector('[data-ventas-tabs]');
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
                            label: 'SUM(Valor)',
                            data: payload.valores,
                            backgroundColor: 'rgba(59, 130, 246, 0.65)',
                            borderColor: 'rgba(59, 130, 246, 1)',
                            borderWidth: 1,
                            yAxisID: 'y',
                            order: 2,
                        },
                        {
                            type: 'line',
                            label: '% acumulado (sobre total zona)',
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
                            title: { display: true, text: 'Valor', color: '#cbd5e1' },
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
        if (root) {
            root.addEventListener('ventas-reporte-tab', function (ev) {
                if (ev.detail && ev.detail.index === 1) buildChart();
            });
        }
    })();
    </script>
    <?php ventas_reporte_tabs_script(); ?>
    <?php ventas_reporte_pdf_script(); ?>
    <script>
    ventasBindPdfDownload('btn-pdf-clientes-inline', 'reporte-pdf-root', <?= json_encode($pdfName, JSON_UNESCAPED_UNICODE | JSON_HEX_TAG | JSON_HEX_APOS) ?>);
    </script>
</body>
</html>
