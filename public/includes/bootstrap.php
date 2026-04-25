<?php
declare(strict_types=1);

if (session_status() !== PHP_SESSION_ACTIVE) {
    session_start();
}

// Reutiliza tu bootstrap real para DB/servicios.
$appRoot = dirname(__DIR__, 2);
require_once $appRoot . '/config/bootstrap.php';

define('APP_NAME', 'Ventas · cia2026');
define('APP_COMPANY', 'GRANJA RINCONADA DEL SUR S.A.');

function app_public_base(): string
{
    $script = str_replace('\\', '/', (string) ($_SERVER['SCRIPT_NAME'] ?? '/index.php'));
    $scriptDir = str_replace('\\', '/', dirname($script));
    $docRoot = @realpath((string) ($_SERVER['DOCUMENT_ROOT'] ?? '')) ?: '';
    $publicFs = @realpath(dirname(__DIR__)) ?: '';
    if ($docRoot !== '' && $publicFs !== '' && strcasecmp($docRoot, $publicFs) === 0) {
        return ($scriptDir === '/' || $scriptDir === '.') ? '/' : (rtrim($scriptDir, '/') . '/');
    }
    if (str_ends_with($script, '/public/index.php') || str_ends_with($script, '/public/login.php')) {
        return rtrim($scriptDir, '/') . '/';
    }
    return rtrim($scriptDir, '/') . '/public/';
}

function app_require_login(): void
{
    if (empty($_SESSION['active'])) {
        header('Location: ' . app_public_base() . 'login.php');
        exit;
    }
}

