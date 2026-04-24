<?php

declare(strict_types=1);

/**
 * Construye una sentencia SQL legible con literales sustituidos (solo para mostrar / enlaces).
 */
final class SqlSentenciaTexto
{
    /**
     * @param array<string|int, mixed> $params claves con o sin prefijo ':'
     */
    public static function interpolate(PDO $pdo, string $sql, array $params): string
    {
        if ($params === []) {
            return $sql;
        }

        $keys = array_keys($params);
        usort($keys, static function ($a, $b): int {
            $la = strlen((string) $a);
            $lb = strlen((string) $b);

            return $lb <=> $la;
        });

        $out = $sql;
        foreach ($keys as $k) {
            $ph = is_string($k) && str_starts_with($k, ':') ? $k : ':' . $k;
            $v = $params[$k];
            $lit = self::literal($pdo, $v);
            $out = str_replace($ph, $lit, $out);
        }

        return $out;
    }

    private static function literal(PDO $pdo, mixed $v): string
    {
        if ($v === null) {
            return 'NULL';
        }
        if (is_bool($v)) {
            return $v ? '1' : '0';
        }
        if (is_int($v) || is_float($v)) {
            return (string) $v;
        }
        if (is_string($v)) {
            $q = $pdo->quote($v);

            return $q !== false ? $q : "'" . str_replace(["\\", "'"], ["\\\\", "\\'"], $v) . "'";
        }

        $q = $pdo->quote((string) $v);

        return $q !== false ? $q : "'" . str_replace(["\\", "'"], ["\\\\", "\\'"], (string) $v) . "'";
    }
}
