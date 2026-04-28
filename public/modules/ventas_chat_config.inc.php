<?php

declare(strict_types=1);

/** Incluido por `chat_floating.inc.php` y la vista pantalla completa del asistente. */

$ventasChatApiUrl = 'api/chat.php';

$ventasWebModulesBase = null;
if (function_exists('app_public_base')) {
    $ventasWebModulesBase = app_public_base() . 'modules/';
}
if ($ventasWebModulesBase === null) {
    $d = str_replace('\\', '/', dirname($_SERVER['SCRIPT_NAME'] ?? ''));
    $baseDir = rtrim($d, '/');
    if ($baseDir !== '' && str_ends_with($baseDir, '/modules')) {
        $ventasWebModulesBase = $baseDir . '/';
    } elseif ($baseDir !== '' && str_ends_with($baseDir, '/public')) {
        $ventasWebModulesBase = $baseDir . '/modules/';
    } elseif ($baseDir !== '') {
        $ventasWebModulesBase = $baseDir . '/public/modules/';
    } else {
        $ventasWebModulesBase = '/public/modules/';
    }
}

$ventasPublicWebBase = '/';
if (function_exists('app_public_base')) {
    $ventasPublicWebBase = app_public_base();
}

// Clave de usuario para storage local (historial, borradores, favoritos).
// Si no hay sesión, cae a 'anon'.
$ventasChatUserKey = 'anon';
try {
    if (isset($_SESSION) && is_array($_SESSION) && isset($_SESSION['usuario'])) {
        $u = trim((string) $_SESSION['usuario']);
        if ($u !== '') {
            $ventasChatUserKey = $u;
        }
    }
} catch (Throwable $e) {
    // ignore
}
