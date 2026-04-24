<?php

declare(strict_types=1);

define('APP_ROOT', dirname(__DIR__));

if (!function_exists('ventas_load_env')) {
    function ventas_load_env(string $path): void
    {
        if (!is_readable($path)) {
            return;
        }
        $lines = file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) ?: [];
        foreach ($lines as $line) {
            $line = trim($line);
            if ($line === '' || str_starts_with($line, '#')) {
                continue;
            }
            if (!str_contains($line, '=')) {
                continue;
            }
            [$k, $v] = explode('=', $line, 2);
            $k = trim($k);
            $v = trim($v, " \t\"'");
            // El archivo .env del proyecto debe prevalecer sobre variables heredadas
            // del sistema (p. ej. DB_PASS en Windows), para que XAMPP/local coincida.
            if ($k !== '') {
                putenv("$k=$v");
                $_ENV[$k] = $v;
            }
        }
    }
}

ventas_load_env(APP_ROOT . DIRECTORY_SEPARATOR . '.env');

if (!function_exists('ventas_pdo')) {
    function ventas_pdo(): PDO
    {
        static $pdo = null;
        if ($pdo instanceof PDO) {
            return $pdo;
        }
        $dsn = getenv('DB_DSN') ?: 'mysql:host=127.0.0.1;port=3306;dbname=cia2026;charset=latin1';
        $user = getenv('DB_USER') ?: 'root';
        $pass = getenv('DB_PASS') ?: '';
        $pdo = new PDO($dsn, $user, $pass, [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        ]);
        // MySQL 8+: aborta SELECT que excedan ~120 s (evita chat “pendiente” por SQL lento).
        if (str_starts_with($dsn, 'mysql:')) {
            try {
                $pdo->exec('SET SESSION max_execution_time = 120000');
            } catch (Throwable) {
                // MariaDB / versiones sin la variable: se ignora
            }
        }
        return $pdo;
    }
}
