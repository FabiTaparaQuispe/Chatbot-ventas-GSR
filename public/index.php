<?php
declare(strict_types=1);

require_once __DIR__ . '/includes/bootstrap.php';
app_require_login();

$pageParam = $_GET['page'] ?? null;
$page = is_string($pageParam) ? $pageParam : '';
if ($page === '') {
    $r = app_user_role();
    $page = in_array($r, ['admin', 'gerencia', 'analista'], true) ? 'ventas' : 'chatbot';
}
/** La vista estática de gráficos ya no existe; los informes están en el asistente (chatbot). */
if ($page === 'graficos') {
    header('Location: index.php?page=chatbot', true, 302);
    exit;
}

$allowedPages = ['ventas', 'chatbot', 'historial_preguntas', 'usuarios'];
if (!in_array($page, $allowedPages, true)) {
    $page = 'ventas';
}

// Alcances por rol (control simple por página).
// - lector: solo chatbot
// - analista: ventas + chatbot
// - gerencia: ventas + chatbot + historial
// - admin: todo
if ($page === 'usuarios') {
    app_require_role('admin');
} elseif ($page === 'historial_preguntas') {
    app_require_role(['admin', 'gerencia']);
} elseif ($page === 'ventas') {
    app_require_role(['admin', 'gerencia', 'analista']);
}

$currentPage = $page;
$pageTitle = match ($page) {
    'chatbot' => 'Chatbot',
    'historial_preguntas' => 'Preguntas al chatbot',
    'usuarios' => 'Usuarios',
    default => 'Ventas general',
};
$loadVentasAssets = $page === 'ventas' || $page === 'usuarios';
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
} elseif ($page === 'usuarios') {
    require __DIR__ . '/partials/usuarios.php';
} else {
    require __DIR__ . '/partials/ventasgeneral.php';
}
require __DIR__ . '/includes/layout-end.php';
