<?php

declare(strict_types=1);

/**
 * Enlace HTTP para servir la sentencia SQL como texto plano (payload comprimido en query).
 */
final class SqlTextoHttpLink
{
    private const MAX_DECOMPRESSED_BYTES = 524288;

    /** Tamaño máximo aproximado del parámetro s en la URL (evita 414 / límites del servidor). */
    private const MAX_QUERY_PARAM_CHARS = 7200;

    public static function encodeQueryParam(string $sql): ?string
    {
        $compressed = @gzcompress($sql, 6);
        $useZip = $compressed !== false && $compressed !== '' && strlen($compressed) < strlen($sql);
        $payload = $useZip ? $compressed : $sql;
        $flag = $useZip ? '1' : '0';
        $b64 = base64_encode($payload);
        $s = $flag . rtrim(strtr($b64, '+/', '-_'), '=');
        if (strlen($s) > self::MAX_QUERY_PARAM_CHARS) {
            return null;
        }

        return $s;
    }

    /**
     * URL absoluta a public/sql_texto.php desde el script que atiende la petición (p. ej. public/api/chat.php).
     */
    public static function absoluteUrlForSql(string $sql): ?string
    {
        $s = self::encodeQueryParam($sql);
        if ($s === null) {
            return null;
        }
        $script = (string) ($_SERVER['SCRIPT_NAME'] ?? '/');
        $script = str_replace('\\', '/', $script);
        $publicBase = dirname(dirname($script));
        if ($publicBase === '/' || $publicBase === '.') {
            $publicBase = '';
        }
        $scheme = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') ? 'https' : 'http';
        $host = (string) ($_SERVER['HTTP_HOST'] ?? 'localhost');
        $path = ($publicBase === '' ? '' : $publicBase) . '/sql_texto.php';

        return $scheme . '://' . $host . $path . '?z=1&s=' . rawurlencode($s);
    }

    /**
     * @param list<string> $bloques una o más sentencias (p. ej. varias consultas del mismo informe)
     * @return list<string> líneas listas para anexar al reply (URL o aviso)
     */
    public static function formatAppendLines(array $bloques): array
    {
        if ($bloques === []) {
            return [];
        }
        $lines = ['---', 'Sentencia SQL ejecutada (texto plano):'];
        $n = 0;
        foreach ($bloques as $sql) {
            $sql = trim($sql);
            if ($sql === '') {
                continue;
            }
            $n++;
            $url = self::absoluteUrlForSql($sql);
            if ($url !== null) {
                $lines[] = $n > 1 ? "Consulta {$n}: {$url}" : $url;
            } else {
                $lines[] = $n > 1
                    ? "Consulta {$n}: (demasiado larga para enlace; ejecute la misma consulta desde el depurador SQL.)"
                    : '(Sentencia demasiado larga para enlace; ejecute la misma consulta desde el depurador SQL.)';
            }
        }

        return $lines;
    }

    public static function decodeQueryParam(string $s): ?string
    {
        $s = trim($s);
        if ($s === '') {
            return null;
        }
        $flag = $s[0];
        $body = substr($s, 1);
        $raw = self::base64UrlDecode($body);
        if ($raw === false || $raw === '') {
            return null;
        }
        if ($flag === '1') {
            $dec = @gzuncompress($raw);
            if ($dec === false || $dec === '') {
                return null;
            }
            $raw = $dec;
        }
        if (strlen($raw) > self::MAX_DECOMPRESSED_BYTES) {
            return null;
        }

        return $raw;
    }

    private static function base64UrlDecode(string $data): string|false
    {
        $data = strtr($data, '-_', '+/');
        $pad = strlen($data) % 4;
        if ($pad > 0) {
            $data .= str_repeat('=', 4 - $pad);
        }

        $out = base64_decode($data, true);

        return $out === false ? false : $out;
    }
}
