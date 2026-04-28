<?php

declare(strict_types=1);

require_once dirname(__DIR__, 2) . '/config/bootstrap.php';
require_once dirname(__DIR__, 2) . '/src/VentasGeneralReportesGraficos.php';
require_once __DIR__ . '/ventas_modules_parse_get.php';
require_once __DIR__ . '/reporte_pdf_snippet.php';

$a1 = ventas_modules_parse_date_get_any(['a_desde', 'fecha_desde_a', 'desde_a', 'periodo_a_desde']);
$a2 = ventas_modules_parse_date_get_any(['a_hasta', 'fecha_hasta_a', 'hasta_a', 'periodo_a_hasta']);
$b1 = ventas_modules_parse_date_get_any(['b_desde', 'fecha_desde_b', 'desde_b', 'periodo_b_desde']);
$b2 = ventas_modules_parse_date_get_any(['b_hasta', 'fecha_hasta_b', 'hasta_b', 'periodo_b_hasta']);
$tieneLasCuatro = $a1 !== null && $a2 !== null && $b1 !== null && $b2 !== null;
if (!$tieneLasCuatro) {
    $rawQs = ventas_modules_query_string_raw();
    $candidatos = [
        ventas_comparativo_fechas_desde_hasta_repetidas(),
        ventas_comparativo_fechas_fecha_desde_hasta_repetidas(),
        ventas_comparativo_extrae_cuatro_fechas_en_orden($rawQs),
    ];
    foreach ($candidatos as $dup) {
        if ($dup !== null) {
            [$a1, $a2, $b1, $b2] = $dup;
            break;
        }
    }
}
$dim = ventas_modules_get_dim_precio_comercial();
$top = ventas_modules_int_from_get(['top', 'top_n'], 15, 1, 80);

if ($a1 === null || $a2 === null || $b1 === null || $b2 === null || $a1 > $a2 || $b1 > $b2) {
    http_response_code(400);
    header('Content-Type: text/plain; charset=utf-8');
    echo 'Parámetros: a_desde, a_hasta, b_desde, b_hasta (YYYY-MM-DD). Alias: fecha_desde_a/hasta_a y fecha_desde_b/hasta_b; desde_a/hasta_a y desde_b/hasta_b. '
        . 'Si usas desde/hasta o fecha_desde/fecha_hasta como en otros reportes, repite el par DOS veces (dos desde y dos hasta, en orden). '
        . 'O incluye cuatro fechas YYYY-MM-DD en la URL. dim|dimension=precio|comercial, top|top_n=15';
    exit;
}

$pdo = ventas_pdo();
try {
    $data = VentasGeneralReportesGraficos::comparativoDosPeriodos($pdo, $a1, $a2, $b1, $b2, $dim, $top);
} catch (Throwable $e) {
    http_response_code(400);
    header('Content-Type: text/plain; charset=utf-8');
    echo $e->getMessage();
    exit;
}

$dimLabel = $dim === 'comercial' ? 'Zona comercial' : 'DescriZonaPrecio';
$labels = [];
$va = [];
$vb = [];
foreach ($data['filas'] as $f) {
    $lab = (string) ($f['etiqueta'] ?? '');
    if (strlen($lab) > 28) {
        $lab = substr($lab, 0, 25) . '…';
    }
    $labels[] = $lab;
    $va[] = (float) ($f['valor_periodo_a'] ?? 0);
    $vb[] = (float) ($f['valor_periodo_b'] ?? 0);
}
$chartJson = json_encode([
    'labels' => $labels,
    'valor_a' => $va,
    'valor_b' => $vb,
    'label_a' => 'Periodo A',
    'label_b' => 'Periodo B',
], JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE);
$pdfName = 'ventas_comparativo_' . $dim . '.pdf';
?>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Comparativo ventas</title>
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
                <h1>Comparativo importe (SUM Valor) por <?= htmlspecialchars($dimLabel, ENT_QUOTES, 'UTF-8') ?></h1>
                <p class="reporte-inline-meta">Periodo A: <?= htmlspecialchars($a1, ENT_QUOTES, 'UTF-8') ?> — <?= htmlspecialchars($a2, ENT_QUOTES, 'UTF-8') ?>
                    · Periodo B: <?= htmlspecialchars($b1, ENT_QUOTES, 'UTF-8') ?> — <?= htmlspecialchars($b2, ENT_QUOTES, 'UTF-8') ?></p>
            </div>
            <div class="tabla-listado-wrapper">
                <div class="reporte-toolbar"><button type="button" class="btn btn-primary" id="btn-pdf">Descargar PDF</button></div>
                <div id="reporte-pdf-root">
                    <h2 class="pdf-h2">Comparativo por <?= htmlspecialchars($dimLabel, ENT_QUOTES, 'UTF-8') ?></h2>
                    <div class="table-wrapper overflow-x-auto productos-dt-skin">
                        <table class="data-table config-table display stripe">
                            <thead>
                                <tr><th>N°</th><th>Etiqueta</th><th>Importe periodo A</th><th>Importe periodo B</th><th>Diferencia (B − A)</th></tr>
                            </thead>
                            <tbody>
                                <?php $i = 0; foreach ($data['filas'] as $f) { $i++; ?>
                                <tr>
                                    <td><?= $i ?></td>
                                    <td><?= htmlspecialchars((string) ($f['etiqueta'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                                    <td><?= number_format((float) ($f['valor_periodo_a'] ?? 0), 2, '.', ',') ?></td>
                                    <td><?= number_format((float) ($f['valor_periodo_b'] ?? 0), 2, '.', ',') ?></td>
                                    <td><?= number_format((float) ($f['delta'] ?? 0), 2, '.', ',') ?></td>
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
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: payload.labels,
                    datasets: [
                        { label: payload.label_a || 'A', data: payload.valor_a, backgroundColor: 'rgba(59,130,246,0.75)' },
                        { label: payload.label_b || 'B', data: payload.valor_b, backgroundColor: 'rgba(244,114,182,0.75)' },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { labels: { color: '#cbd5e1' } } },
                    scales: {
                        x: { ticks: { color: '#94a3b8', maxRotation: 45 }, grid: { color: 'rgba(148,163,184,0.15)' } },
                        y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,0.15)' } },
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
