<?php
declare(strict_types=1);

require_once __DIR__ . '/includes/bootstrap.php';
app_require_login();

$pageParam = $_GET['page'] ?? null;
$page = is_string($pageParam) ? $pageParam : '';
if ($page === '') {
    $r = app_user_role();
    $page = in_array($r, app_roles_home_ventas(), true) ? 'ventas' : 'chatbot';
}
/** La vista estática de gráficos ya no existe; los informes están en el asistente (chatbot). */
if ($page === 'graficos') {
    header('Location: index.php?page=chatbot', true, 302);
    exit;
}

$allowedPages = ['ventas', 'ventasgeneral2', 'chatbot', 'historial_preguntas', 'usuarios', 'gestion_usuarios'];
if (!in_array($page, $allowedPages, true)) {
    $page = 'ventas';
}

// Alcances por rol (control simple por página).
// - lector: chatbot + tabla ventas (solo lectura) + historial propio
// - tactico / analista / estrategico / gerencia / admin: ventas + chatbot + historial; usuarios solo admin
if ($page === 'usuarios') {
    app_require_role('admin');
} elseif ($page === 'gestion_usuarios') {
    app_require_role('estrategico');
} elseif ($page === 'historial_preguntas') {
    app_require_role('estrategico');
} elseif ($page === 'ventas' || $page === 'ventasgeneral2') {
    app_require_role(app_roles_ventas_general());
}

$currentPage = $page;
$pageTitle = match ($page) {
    'chatbot' => 'Chatbot',
    'historial_preguntas' => 'Preguntas al chatbot',
    'usuarios' => 'Usuarios',
    'gestion_usuarios' => 'Creación de usuarios',
    'ventasgeneral2' => 'Ventas general 2',
    default => 'Ventas general',
};
$loadVentasAssets = $page === 'ventas' || $page === 'ventasgeneral2' || $page === 'usuarios' || $page === 'gestion_usuarios';
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
} elseif ($page === 'gestion_usuarios') {
    require __DIR__ . '/partials/gestion_usuarios.php';
} else {
    require __DIR__ . '/partials/ventasgeneral.php';
}
require __DIR__ . '/includes/layout-end.php';
