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
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Ventas por ruta comercial</title>
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
    <script src="https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js" crossorigin="anonymous"></script>
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
                <h1>Ventas por ruta comercial</h1>
                <p class="reporte-inline-meta"><?= htmlspecialchars($desde, ENT_QUOTES, 'UTF-8') ?> — <?= htmlspecialchars($hasta, ENT_QUOTES, 'UTF-8') ?></p>
            </div>
            <div class="tabla-listado-wrapper">
                <div class="reporte-toolbar"><button type="button" class="btn btn-primary" id="btn-pdf">Descargar PDF</button></div>
                <div id="reporte-pdf-root">
                    <h2 class="pdf-h2">Top rutas</h2>
                    <div class="table-wrapper overflow-x-auto productos-dt-skin">
                        <table class="data-table config-table display stripe">
                            <thead><tr><th>N°</th><th>Ruta comercial</th><th>Líneas</th><th>Importe</th></tr></thead>
                            <tbody>
                            <?php $i = 0; foreach ($data['filas'] as $f) { $i++; ?>
                            <tr>
                                <td><?= $i ?></td>
                                <td><?= htmlspecialchars((string) ($f['ruta'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                                <td><?= (int) ($f['lineas'] ?? 0) ?></td>
                                <td><?= number_format((float) ($f['suma_valor'] ?? 0), 2, '.', ',') ?></td>
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
        var done = false;
        function build() {
            if (done || !window.Chart) return;
            var ctx = document.getElementById('ch');
            if (!ctx || !payload.labels) return;
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
                        label: 'SUM(Valor)',
                        data: payload.valores,
                        backgroundColor: bg,
                        borderColor: br,
                        borderWidth: 1,
                        maxBarThickness: 48
                    }]
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: {
                        duration: 1500,
                        easing: 'easeOutCubic',
                        delay: function (context) {
                            if (context.type === 'data' && context.mode === 'default') return (context.dataIndex || 0) * 125;
                            return 0;
                        }
                    },
                    plugins: {
                        legend: { display: false },
                        tooltip: { backgroundColor: 'rgba(15, 23, 42, 0.92)', padding: 12, cornerRadius: 8 }
                    },
                    scales: {
                        x: { beginAtZero: true, ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,0.15)' } },
                        y: { ticks: { color: '#94a3b8', font: { size: 9 } }, grid: { display: false } }
                    }
                },
            });
            done = true;
        }
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', build);
        } else {
            build();
        }
    })();
    </script>
    <?php ventas_reporte_tabs_script(); ?>
    <?php ventas_reporte_pdf_script(); ?>
    <script>ventasBindPdfDownload('btn-pdf', 'reporte-pdf-root', <?= json_encode($pdfName, JSON_UNESCAPED_UNICODE | JSON_HEX_TAG | JSON_HEX_APOS) ?>);</script>
</body>
</html>
