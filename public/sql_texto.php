<?php

declare(strict_types=1);

/**
 * Devuelve la sentencia SQL recibida por parámetro (solo texto; uso interno con enlaces del chat).
 */

header('Content-Type: text/plain; charset=utf-8');
header('X-Content-Type-Options: nosniff');
header('Cache-Control: no-store');

$s = isset($_GET['s']) && is_string($_GET['s']) ? $_GET['s'] : '';
if ($s === '') {
    http_response_code(400);
    echo 'Parámetro s requerido.';

    exit;
}

$appRoot = dirname(__DIR__);
require_once $appRoot . '/src/SqlTextoHttpLink.php';

$sql = SqlTextoHttpLink::decodeQueryParam($s);
if ($sql === null || $sql === '') {
    http_response_code(400);
    echo 'Payload inválido o caducado.';

    exit;
}

echo $sql;
