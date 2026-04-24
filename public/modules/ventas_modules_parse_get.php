<?php

declare(strict_types=1);

function ventas_modules_parse_date_string(string $raw): ?string
{
    $s = trim($raw, " \t\n\r\0\x0B\"'()[]<>");
    if ($s === '') {
        return null;
    }
    $d = DateTimeImmutable::createFromFormat('Y-m-d', $s);
    if ($d === false || $d->format('Y-m-d') !== $s) {
        return null;
    }

    return $s;
}

function ventas_modules_parse_date_get(string $key): ?string
{
    if (!isset($_GET[$key])) {
        return null;
    }

    return ventas_modules_parse_date_string((string) $_GET[$key]);
}

/**
 * Query string cruda (puede estar vacía en algunos proxies; intentar alternativas).
 */
function ventas_modules_query_string_raw(): string
{
    $qs = (string) ($_SERVER['QUERY_STRING'] ?? '');
    if ($qs === '' && isset($_SERVER['REDIRECT_QUERY_STRING'])) {
        $qs = (string) $_SERVER['REDIRECT_QUERY_STRING'];
    }
    if ($qs === '' && isset($_SERVER['REQUEST_URI'])) {
        $uri = (string) $_SERVER['REQUEST_URI'];
        $p = strpos($uri, '?');
        if ($p !== false) {
            $qs = substr($uri, $p + 1);
            $h = strpos($qs, '#');
            if ($h !== false) {
                $qs = substr($qs, 0, $h);
            }
        }
    }

    return str_replace('&amp;', '&', $qs);
}

/**
 * Pares (clave, valor) desde la query conservando claves repetidas
 * (en PHP $_GET['desde'] solo queda el último si hay varios `desde=`).
 * Acepta separador & o ; (arg_separator.input).
 *
 * @return list<array{0: string, 1: string}>
 */
function ventas_modules_query_string_pairs(): array
{
    $qs = ventas_modules_query_string_raw();
    if ($qs === '') {
        return [];
    }
    $out = [];
    foreach (preg_split('/[&;]/', $qs) as $chunk) {
        if ($chunk === '') {
            continue;
        }
        $eq = strpos($chunk, '=');
        if ($eq === false) {
            continue;
        }
        $k = urldecode(str_replace('+', ' ', substr($chunk, 0, $eq)));
        $v = urldecode(str_replace('+', ' ', substr($chunk, $eq + 1)));
        $out[] = [$k, $v];
    }

    return $out;
}

/**
 * Dos periodos con la misma pareja de nombres repetida en la query (p. ej. dos `desde=` y dos `hasta=`).
 *
 * @return array{0: string, 1: string, 2: string, 3: string}|null a_desde, a_hasta, b_desde, b_hasta
 */
function ventas_comparativo_extrae_dos_pares_repetidos(string $claveDesde, string $claveHasta): ?array
{
    $desdes = [];
    $hastas = [];
    foreach (ventas_modules_query_string_pairs() as [$k, $v]) {
        if ($k !== $claveDesde && $k !== $claveHasta) {
            continue;
        }
        $d = ventas_modules_parse_date_string($v);
        if ($d === null) {
            continue;
        }
        if ($k === $claveDesde) {
            $desdes[] = $d;
        } else {
            $hastas[] = $d;
        }
    }
    if (count($desdes) >= 2 && count($hastas) >= 2) {
        return [$desdes[0], $hastas[0], $desdes[1], $hastas[1]];
    }

    return null;
}

/**
 * Patrón erróneo pero frecuente: `desde=…&hasta=…&desde=…&hasta=…`.
 *
 * @return array{0: string, 1: string, 2: string, 3: string}|null
 */
function ventas_comparativo_fechas_desde_hasta_repetidas(): ?array
{
    return ventas_comparativo_extrae_dos_pares_repetidos('desde', 'hasta');
}

/**
 * Igual que desde/hasta pero con nombres de tool (fecha_desde / fecha_hasta duplicados).
 *
 * @return array{0: string, 1: string, 2: string, 3: string}|null
 */
function ventas_comparativo_fechas_fecha_desde_hasta_repetidas(): ?array
{
    return ventas_comparativo_extrae_dos_pares_repetidos('fecha_desde', 'fecha_hasta');
}

/**
 * Último recurso: las primeras cuatro fechas YYYY-MM-DD válidas en orden de aparición en la query.
 *
 * @return array{0: string, 1: string, 2: string, 3: string}|null
 */
function ventas_comparativo_extrae_cuatro_fechas_en_orden(string $qs): ?array
{
    if ($qs === '') {
        return null;
    }
    if (!preg_match_all('/\b(20[0-9]{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01]))\b/', $qs, $m)) {
        return null;
    }
    $out = [];
    foreach ($m[1] as $cand) {
        $d = ventas_modules_parse_date_string($cand);
        if ($d !== null) {
            $out[] = $d;
        }
        if (count($out) >= 4) {
            break;
        }
    }
    if (count($out) < 4) {
        return null;
    }

    return [$out[0], $out[1], $out[2], $out[3]];
}

/**
 * Usa el primer parámetro GET válido (misma regla que ventas_modules_parse_date_get).
 * Sirve para alias (ej. fecha_desde_a vs a_desde) cuando el modelo arma la URL con nombres de la API.
 *
 * @param list<string> $keys
 */
function ventas_modules_parse_date_get_any(array $keys): ?string
{
    foreach ($keys as $key) {
        $v = ventas_modules_parse_date_get($key);
        if ($v !== null) {
            return $v;
        }
    }

    return null;
}

/**
 * @param list<string> $keys
 */
function ventas_modules_int_from_get(array $keys, int $default, int $min, int $max): int
{
    foreach ($keys as $key) {
        if (!isset($_GET[$key]) || $_GET[$key] === '' || !is_numeric($_GET[$key])) {
            continue;
        }
        $n = (int) $_GET[$key];

        return max($min, min($max, $n));
    }

    return max($min, min($max, $default));
}

function ventas_modules_get_dim_precio_comercial(): string
{
    foreach (['dim', 'dimension'] as $key) {
        if (!isset($_GET[$key])) {
            continue;
        }
        $d = strtolower(trim((string) $_GET[$key]));
        if (in_array($d, ['precio', 'comercial'], true)) {
            return $d;
        }
    }

    return 'precio';
}
