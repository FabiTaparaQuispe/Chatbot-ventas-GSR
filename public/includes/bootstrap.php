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
    // Si el script actual YA está dentro de /public, la base es ese directorio.
    if (str_ends_with($scriptDir, '/public')) {
        return rtrim($scriptDir, '/') . '/';
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

function app_user_username(): string
{
    return (string) ($_SESSION['usuario'] ?? '');
}

function app_user_display_name(): string
{
    $v = (string) ($_SESSION['display_name'] ?? '');
    return trim($v);
}

/**
 * Alinea variantes guardadas en BD con los roles que usa la app (p. ej. schema de ejemplo usa "gerente").
 */
function app_normalize_user_role(string $r): string
{
    $r = strtolower(trim($r));
    if ($r === 'gerente') {
        return 'gerencia';
    }
    if ($r === 'estrategico' || $r === 'estratégico') {
        return 'estrategico';
    }
    if ($r === 'tactico' || $r === 'táctico') {
        return 'tactico';
    }
    if ($r === 'usuario2') {
        return 'tactico';
    }
    return $r;
}

function app_user_role(): string
{
    $r = strtolower(trim((string) ($_SESSION['role'] ?? '')));
    if ($r === '') {
        return 'lector';
    }
    return app_normalize_user_role($r);
}

function app_is_admin(): bool
{
    return app_user_role() === 'admin';
}

/** Inicio por defecto en «Ventas general» (equipo comercial / gestión). */
function app_roles_home_ventas(): array
{
    return ['admin', 'gerencia', 'estrategico', 'tactico', 'operativo', 'analista'];
}

/** Acceso a vistas de tabla ventasgeneral2 (incluye lector en solo lectura). */
function app_roles_ventas_general(): array
{
    return array_values(array_unique(array_merge(app_roles_home_ventas(), ['lector'])));
}

/**
 * Requiere que el usuario tenga uno de los roles permitidos.
 * Si no coincide, redirige al inicio.
 *
 * @param string|array<int,string> $roles
 */
function app_require_role(string|array $roles): void
{
    app_require_login();
    $r = app_user_role();
    $allowed = is_array($roles) ? $roles : [$roles];
    $allowed = array_map(static fn($x) => strtolower(trim((string) $x)), $allowed);
    if ($r === '' || !in_array($r, $allowed, true)) {
        header('Location: ' . app_public_base() . 'index.php');
        exit;
    }
}

function app_csrf_token(): string
{
    $t = (string) ($_SESSION['csrf_token'] ?? '');
    if ($t !== '') {
        return $t;
    }
    try {
        $t = bin2hex(random_bytes(32));
    } catch (Throwable) {
        $t = bin2hex((string) microtime(true) . ':' . (string) mt_rand());
    }
    $_SESSION['csrf_token'] = $t;
    return $t;
}

function app_check_csrf(): void
{
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
        return;
    }
    $sent = (string) ($_POST['csrf_token'] ?? '');
    $real = (string) ($_SESSION['csrf_token'] ?? '');
    if ($sent === '' || $real === '' || !hash_equals($real, $sent)) {
        http_response_code(400);
        echo 'Solicitud inválida (CSRF).';
        exit;
    }
}

