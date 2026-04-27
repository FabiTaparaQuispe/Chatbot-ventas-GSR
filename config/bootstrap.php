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

if (!function_exists('ventas_utf8_string')) {
    /**
     * Normaliza strings a UTF-8 para JSON/HTML.
     * Si la BD guardó texto en latin1/Windows-1252, evita que json_encode lo sustituya por.
     */
    function ventas_utf8_string(mixed $v): string
    {
        if ($v === null) {
            return '';
        }
        if (is_int($v) || is_float($v)) {
            return (string) $v;
        }
        $s = (string) $v;
        if ($s === '') {
            return '';
        }
        if (function_exists('mb_check_encoding') && mb_check_encoding($s, 'UTF-8')) {
            return $s;
        }
        if (function_exists('mb_detect_encoding')) {
            $enc = mb_detect_encoding($s, ['UTF-8', 'ISO-8859-1', 'Windows-1252'], true);
            if ($enc !== false && $enc !== 'UTF-8') {
                $c = @mb_convert_encoding($s, 'UTF-8', $enc);
                if (is_string($c) && $c !== '') {
                    return $c;
                }
            }
        }
        if (function_exists('iconv')) {
            $c2 = @iconv('ISO-8859-1', 'UTF-8//IGNORE', $s);
            if (is_string($c2) && $c2 !== '') {
                return $c2;
            }
            $c3 = @iconv('Windows-1252', 'UTF-8//IGNORE', $s);
            if (is_string($c3) && $c3 !== '') {
                return $c3;
            }
        }
        if (function_exists('utf8_encode')) {
            $c4 = @utf8_encode($s);
            if (is_string($c4) && $c4 !== '') {
                return $c4;
            }
        }
        return $s;
    }
}

if (!function_exists('ventas_pdo')) {
    function ventas_pdo(): PDO
    {
        static $pdo = null;
        if ($pdo instanceof PDO) {
            return $pdo;
        }
        $dsn = getenv('DB_DSN') ?: 'mysql:host=127.0.0.1;port=3306;dbname=cia2026;charset=utf8mb4';
        $user = getenv('DB_USER') ?: 'root';
        $pass = getenv('DB_PASS') ?: '';
        $pdo = new PDO($dsn, $user, $pass, [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::MYSQL_ATTR_INIT_COMMAND => 'SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci',
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
