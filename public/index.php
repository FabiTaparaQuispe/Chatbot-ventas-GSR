<?php
declare(strict_types=1);

require_once __DIR__ . '/includes/bootstrap.php';
app_require_login();

$page = (string) ($_GET['page'] ?? 'ventas');
/** La vista estática de gráficos ya no existe; los informes están en el asistente (chatbot). */
if ($page === 'graficos') {
    header('Location: index.php?page=chatbot', true, 302);
    exit;
}

$allowedPages = ['ventas', 'chatbot', 'historial_preguntas'];
if (!in_array($page, $allowedPages, true)) {
    $page = 'ventas';
}

$currentPage = $page;
$pageTitle = match ($page) {
    'chatbot' => 'Chatbot',
    'historial_preguntas' => 'Preguntas al chatbot',
    default => 'Ventas general',
};
$loadVentasAssets = $page === 'ventas';
$skipFloatingChat = $page === 'chatbot';
$bodyClass = $page === 'chatbot' ? 'app-page-chatbot' : ($page === 'historial_preguntas' ? 'app-page-historial-chat' : '');

$extraScripts = '';
if ($loadVentasAssets) {
    $extraScripts .= '<script src="assets/js/app-ventasgeneral.js"></script>';
}

require __DIR__ . '/includes/layout-start.php';
if ($page === 'chatbot') {
    require __DIR__ . '/partials/chatbot.php';
} elseif ($page === 'historial_preguntas') {
    require __DIR__ . '/partials/historial_preguntas.php';
} else {
    require __DIR__ . '/partials/ventasgeneral.php';
}
require __DIR__ . '/includes/layout-end.php';
