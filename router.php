<?php
declare(strict_types=1);

/**
 * Servidor de desarrollo: php -S localhost:8080 router.php
 * Abrir http://localhost:8080/
 */
$uri = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH) ?: '/';

if ($uri === '/api/chat.php' || $uri === '/api/chat') {
    require __DIR__ . '/api/chat.php';
    return true;
}

if ($uri === '/' || $uri === '/index.html') {
    header('Content-Type: text/html; charset=utf-8');
    readfile(__DIR__ . '/public/index.html');
    return true;
}

$file = __DIR__ . $uri;
if ($uri !== '/' && is_file($file)) {
    return false;
}

http_response_code(404);
header('Content-Type: text/plain; charset=utf-8');
echo 'Not found';
return true;
