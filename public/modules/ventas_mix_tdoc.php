<?php

declare(strict_types=1);

require_once dirname(__DIR__, 2) . '/config/bootstrap.php';
require_once dirname(__DIR__, 2) . '/src/VentasGeneralReportesGraficos.php';
require_once dirname(__DIR__, 2) . '/src/DocumentoTipoEtiqueta.php';
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
$data['filas'] = DocumentoTipoEtiqueta::enriquecerFilas($data['filas']);
$labels = array_column($data['filas'], 'tdoc_etiqueta');
$valores = array_map(static fn ($r) => (float) ($r['suma_valor'] ?? 0), $data['filas']);
$chartJson = json_encode(['labels' => $labels, 'valores' => $valores], JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE);
$pdfName = 'mix_tdoc_' . $desde . '_' . $hasta . '.pdf';
?>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Ventas por tipo de documento</title>
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
    </style>
    <?php ventas_reporte_tabs_styles(); ?>
    <?php ventas_reporte_tabla_styles(); ?>
</head>
<body>
    <main class="reporte-modulo-main">
        <div class="reporte-page">
            <div class="page-head">
                <h1>Ventas por tipo de documento</h1>
                <p class="reporte-inline-meta"><?= htmlspecialchars($desde, ENT_QUOTES, 'UTF-8') ?> — <?= htmlspecialchars($hasta, ENT_QUOTES, 'UTF-8') ?></p>
            </div>
            <div class="tabla-listado-wrapper">
                <div class="reporte-toolbar"><button type="button" class="btn btn-primary" id="btn-pdf">Descargar PDF</button></div>
                <div id="reporte-pdf-root">
                    <h2 class="pdf-h2">Importe por tipo de documento</h2>
                    <div class="table-wrapper overflow-x-auto productos-dt-skin">
                        <table class="data-table config-table display stripe">
                            <thead><tr><th>Tipo de documento</th><th>Líneas</th><th>Importe</th><th>% del total</th></tr></thead>
                            <tbody>
                                <?php foreach ($data['filas'] as $f) { ?>
                                <tr>
                                    <td><?= htmlspecialchars((string) ($f['tdoc_etiqueta'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                                    <td><?= (int) ($f['lineas'] ?? 0) ?></td>
                                    <td><?= number_format((float) ($f['suma_valor'] ?? 0), 2, '.', ',') ?></td>
                                    <td><?= htmlspecialchars((string) ($f['pct_del_total'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
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
            var isDark = document.documentElement.getAttribute('data-theme') === 'dark';
            new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: payload.labels,
                    datasets: [{ data: payload.valores, backgroundColor: ['#3b82f6','#a855f7','#22c55e','#f97316','#ec4899','#14b8a6','#eab308','#64748b'] }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            labels: { color: isDark ? '#e2e8f0' : '#0f172a' },
                        },
                    },
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
