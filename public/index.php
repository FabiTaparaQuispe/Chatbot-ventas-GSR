<?php
declare(strict_types=1);

require_once __DIR__ . '/includes/bootstrap.php';
app_require_login();

$page = (string) ($_GET['page'] ?? 'ventas');
if ($page !== 'ventas' && $page !== 'graficos') {
    $page = 'ventas';
}

$currentPage = $page;
$pageTitle = $page === 'graficos' ? 'Gráficos' : 'Ventas general';
$loadVentasAssets = $page === 'ventas';
$loadCharts = $page === 'graficos';

$extraScripts = '';
if ($loadVentasAssets) {
    $extraScripts .= '<script src="assets/js/app-ventasgeneral.js"></script>';
}
if ($loadCharts) {
    $extraScripts .= '<script src="assets/js/app-charts-ventas.js"></script>';
}

require __DIR__ . '/includes/layout-start.php';
if ($page === 'graficos') {
    require __DIR__ . '/partials/graficos.php';
} else {
    require __DIR__ . '/partials/ventasgeneral.php';
}
require __DIR__ . '/includes/layout-end.php';
