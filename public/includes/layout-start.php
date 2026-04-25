<?php
declare(strict_types=1);

$pageTitle = $pageTitle ?? 'Inicio';
$bodyClass = trim('app-shell ' . ($bodyClass ?? ''));
$loadVentasAssets = $loadVentasAssets ?? false;
$loadCharts = $loadCharts ?? false;

// Base URL para soportar acceso vía /<proyecto>/ (sin /public/ en la URL).
$script = str_replace('\\', '/', (string) ($_SERVER['SCRIPT_NAME'] ?? '/index.php'));
$scriptDir = str_replace('\\', '/', dirname($script));
$docRoot = @realpath((string) ($_SERVER['DOCUMENT_ROOT'] ?? '')) ?: '';
$publicFs = @realpath(dirname(__DIR__)) ?: '';
if ($docRoot !== '' && $publicFs !== '' && strcasecmp($docRoot, $publicFs) === 0) {
    $ventasPublicWebBase = ($scriptDir === '/' || $scriptDir === '.') ? '/' : (rtrim($scriptDir, '/') . '/');
} elseif (str_ends_with($script, '/public/index.php')) {
    $ventasPublicWebBase = rtrim($scriptDir, '/') . '/';
} else {
    $ventasPublicWebBase = rtrim($scriptDir, '/') . '/public/';
}

?>
<!DOCTYPE html>
<html lang="es" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <base href="<?= htmlspecialchars($ventasPublicWebBase, ENT_QUOTES, 'UTF-8') ?>">
    <title><?= htmlspecialchars($pageTitle . ' — ' . APP_NAME, ENT_QUOTES, 'UTF-8') ?></title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400,500,600,700;1,9..40,400&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <?php if (!empty($loadVentasAssets)): ?>
    <link rel="stylesheet" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">
    <link rel="stylesheet" href="assets/css/dashboard-vista-tabla-iconos.css">
    <link rel="stylesheet" href="assets/css/dt-tabla-listado-sip.css">
    <?php endif; ?>
    <link rel="stylesheet" href="assets/css/app.css">
    <script>
    (function () {
        function readCookieTheme() {
            try {
                var m = document.cookie.match(/(?:^|; )ix2-theme=([^;]*)/);
                return m ? decodeURIComponent(m[1]).toLowerCase().trim() : '';
            } catch (e) { return ''; }
        }
        var mode = null;
        try {
            var qs = new URLSearchParams(window.location.search || '');
            var q = (qs.get('ix2_theme') || '').toLowerCase();
            if (q === 'dark' || q === 'light') mode = q;
        } catch (e1) {}
        if (mode == null) {
            var ct = readCookieTheme();
            if (ct === 'dark' || ct === 'light') mode = ct;
        }
        if (mode == null) {
            try {
                var st = localStorage.getItem('ix2-theme');
                if (st === 'dark' || st === 'light') mode = st;
            } catch (e2) {}
        }
        if (mode == null) {
            mode = (window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches) ? 'dark' : 'light';
        }
        var d = document.documentElement;
        d.setAttribute('data-theme', mode);
        d.style.colorScheme = mode === 'dark' ? 'dark' : 'light';
    })();
    </script>
</head>
<body class="<?= htmlspecialchars($bodyClass, ENT_QUOTES, 'UTF-8') ?>">

<button type="button" class="app-sidebar-backdrop" id="appSidebarBackdrop" aria-hidden="true" tabindex="-1" aria-label="Cerrar menú"></button>

<div class="app-layout">
    <?php require __DIR__ . '/../partials/sidebar.php'; ?>
    <div class="app-main">
        <header class="app-mobile-bar">
            <button type="button" class="app-icon-btn" id="appOpenSidebar" aria-label="Abrir menú">
                <i class="fas fa-bars" aria-hidden="true"></i>
            </button>
            <span class="app-mobile-title"><?= htmlspecialchars($pageTitle, ENT_QUOTES, 'UTF-8') ?></span>
        </header>
        <main class="app-content">

