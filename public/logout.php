<?php
declare(strict_types=1);

require_once __DIR__ . '/includes/bootstrap.php';

$_SESSION = [];
if (ini_get('session.use_cookies')) {
    $params = session_get_cookie_params();
    // A veces el cookie puede haberse creado con otro path; limpiamos ambos para asegurar cierre real.
    setcookie(session_name(), '', time() - 42000, $params['path'], $params['domain'], (bool) $params['secure'], (bool) $params['httponly']);
    setcookie(session_name(), '', time() - 42000, '/', $params['domain'], (bool) $params['secure'], (bool) $params['httponly']);
    setcookie(session_name(), '', time() - 42000, $params['path'], '', (bool) $params['secure'], (bool) $params['httponly']);
    setcookie(session_name(), '', time() - 42000, '/', '', (bool) $params['secure'], (bool) $params['httponly']);
}
session_destroy();
session_write_close();

header('Location: ' . app_public_base() . 'login.php');
exit;

