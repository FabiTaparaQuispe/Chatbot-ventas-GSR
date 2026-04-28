<?php

declare(strict_types=1);

require_once __DIR__ . '/DocumentoTipoEtiqueta.php';

/**
 * Añade al texto del asistente un resumen numerado desde el JSON de la última herramienta
 * cuando el modelo solo devuelve el enlace al gráfico (o casi).
 */
final class ChatReplyEnricher
{
    public static function enrichReply(string $reply, array $groqMessages): string
    {
        $reply = trim($reply);
        $payload = self::lastToolPayload($groqMessages);
        if ($payload === null) {
            // El LLM respondió sin llamar ninguna herramienta (probablemente desde el historial de
            // conversación). Si además usó etiquetas genéricas "Cliente N", los datos son inventados:
            // se reemplaza la respuesta con un aviso para que el usuario repita la consulta.
            if (self::replyUsesGenericClienteLabels($reply)) {
                $url = self::extractReportePhpUrlFromReply($reply);
                $note = 'Los nombres de cliente no están disponibles porque el asistente respondió desde el historial sin consultar la base de datos. '
                    . 'Hacé la misma pregunta de nuevo para obtener los datos actualizados.';
                return $url !== '' ? trim($note . "\n\n" . $url) : $note;
            }
            return $reply;
        }

        $summary = self::formatPayload($payload);
        if ($summary === '') {
            return $reply;
        }

        // Algunos modelos inventan "Cliente 1/2/3" pese al system prompt; si parece ranking el enricher
        // no corría antes y el usuario veía cifras correctas pero nombres falsos.
        if (self::replyUsesGenericClienteLabels($reply)) {
            return self::summaryWithReporteUrlLine($summary, $reply, $payload);
        }

        if (self::replyLooksLikeRanking($reply)) {
            $u = trim((string) ($payload['reporte_url'] ?? ''));
            if ($u !== '' && self::extractReportePhpUrlFromReply($reply) === '') {
                return trim($reply . "\n\n" . $u);
            }

            return $reply;
        }

        $head = mb_substr($summary, 0, 120);
        if ($head !== '' && $reply !== '' && mb_stripos($reply, mb_substr($head, 0, 60)) !== false) {
            return $reply;
        }

        return trim($summary . ($reply !== '' ? "\n\n" . $reply : ''));
    }

    /** @param list<array<string, mixed>> $groqMessages */
    private static function lastToolPayload(array $groqMessages): ?array
    {
        $last = null;
        foreach ($groqMessages as $m) {
            if (!is_array($m) || ($m['role'] ?? '') !== 'tool') {
                continue;
            }
            $raw = $m['content'] ?? '';
            if (!is_string($raw) || $raw === '') {
                continue;
            }
            $decoded = json_decode($raw, true);
            if (!is_array($decoded)) {
                continue;
            }
            if (isset($decoded['error']) && is_string($decoded['error']) && $decoded['error'] !== '') {
                continue;
            }
            $last = $decoded;
        }

        return $last;
    }

    private static function replyLooksLikeRanking(string $reply): bool
    {
        if ($reply === '') {
            return false;
        }
        return preg_match_all('/^\d+\.\s+/m', $reply) >= 2;
    }

    /**
     * Patrón típico cuando el LLM sustituye nombres reales por etiquetas genéricas.
     */
    private static function replyUsesGenericClienteLabels(string $reply): bool
    {
        return (bool) preg_match('/^\d+\.\s*Cliente\s+\d+/mi', $reply);
    }

    /**
     * @param array<string, mixed> $payload
     */
    private static function summaryWithReporteUrlLine(string $summary, string $reply, array $payload): string
    {
        $url = self::extractReportePhpUrlFromReply($reply);
        if ($url === '') {
            $url = trim((string) ($payload['reporte_url'] ?? ''));
        }
        if ($url !== '') {
            return trim($summary . "\n\n" . $url);
        }

        return trim($summary);
    }

    private static function extractReportePhpUrlFromReply(string $reply): string
    {
        $reply = preg_replace('/[\x{200B}-\x{200D}\x{FEFF}\x{00A0}]/u', '', $reply);
        if (preg_match(
            '/(https?:\/\/[^\s<]+|(?:ventas_(?:barras_dimension|comparativo|top_productos|top_clientes_global|top_clientes_nc|mix_tdoc|barras_ruta|barras_corporativo|serie_mensual)|pareto_(?:nc_zona|clientes_zona)(?:_tabla)?|ventasgeneral_(?:buscar|resumen)(?:_tabla)?)\.php\?[^\s<>"\']+)/iu',
            $reply,
            $m
        )) {
            return rtrim($m[1], "),.;'\"`");
        }

        return '';
    }

    private static function fmtNum(mixed $v, int $decimals = 2): string
    {
        if (!is_numeric($v)) {
            return (string) $v;
        }

        return number_format((float) $v, $decimals, '.', ',');
    }

    /** @param array<string, mixed> $payload */
    private static function formatPayload(array $payload): string
    {
        if (isset($payload['agregados']) && is_array($payload['agregados']) && !isset($payload['filas'])) {
            $a = $payload['agregados'];
            $p = $payload['periodo'] ?? [];
            $d1 = is_array($p) ? (string) ($p['desde'] ?? '') : '';
            $d2 = is_array($p) ? (string) ($p['hasta'] ?? '') : '';
            $filas = (string) ($a['filas'] ?? '');
            $sv = self::fmtNum($a['suma_valor'] ?? 0);

            return 'Resumen del periodo'
                . ($d1 !== '' && $d2 !== '' ? " {$d1} – {$d2}" : '')
                . ": {$filas} filas, suma Valor {$sv}.";
        }

        $filas = null;
        if (isset($payload['filas_pareto']) && is_array($payload['filas_pareto'])) {
            $filas = $payload['filas_pareto'];
        } elseif (isset($payload['filas_ranking']) && is_array($payload['filas_ranking'])) {
            $filas = $payload['filas_ranking'];
        } elseif (isset($payload['filas']) && is_array($payload['filas'])) {
            $filas = $payload['filas'];
        } elseif (isset($payload['proyecciones']) && is_array($payload['proyecciones'])) {
            return self::linesProyecciones($payload['proyecciones'], $payload);
        }

        if ($filas === null || $filas === []) {
            return '';
        }

        $tipo = (string) ($payload['tipo'] ?? '');
        $criterio = (string) ($payload['criterio'] ?? '');
        $first = $filas[0];
        if (!is_array($first)) {
            return '';
        }

        if (isset($first['zona'], $first['lineas_nc'], $first['impacto_abs_valor'])) {
            return self::linesParetoNc($filas);
        }
        if (isset($first['nombre_cliente'], $first['lineas_venta'], $first['suma_valor'])) {
            return self::linesTopZonaPrecio($filas);
        }
        if (isset($first['nombre_cliente'], $first['lineas'], $first['suma_valor'])) {
            $isNc = stripos($criterio, 'TDoc') !== false
                || stripos($criterio, 'nota') !== false
                || stripos($criterio, '07') !== false;

            return $isNc ? self::linesTopNc($filas) : self::linesTopClientesGlobal($filas);
        }
        if (isset($first['etiqueta'], $first['suma_valor'])) {
            return self::linesEtiquetaValor($filas);
        }
        if (isset($first['glosa'], $first['suma_valor']) || isset($first['cod_item'], $first['suma_valor'])) {
            return self::linesProductos($filas);
        }
        if (isset($first['tdoc'], $first['suma_valor'])) {
            return self::linesMixTdoc($filas);
        }
        if (isset($first['valor_periodo_a'], $first['valor_periodo_b'], $first['etiqueta'])) {
            return self::linesComparativo($filas);
        }
        if (isset($first['ruta'], $first['suma_valor'])) {
            return self::linesEtiquetaNamed($filas, 'ruta');
        }
        if (isset($first['nombre_coorporativo'], $first['suma_valor'])) {
            return self::linesEtiquetaNamed($filas, 'nombre_coorporativo');
        }
        if (isset($first['mes'], $first['suma_valor'])) {
            return self::linesSerieMensual($filas);
        }

        return self::linesGenericBuscar($filas);
    }

    /** @param list<array<string, mixed>> $filas */
    private static function linesParetoNc(array $filas): string
    {
        $out = [];
        $i = 1;
        foreach ($filas as $row) {
            if (!is_array($row)) {
                continue;
            }
            $z = (string) ($row['zona'] ?? '');
            $n = (int) ($row['lineas_nc'] ?? 0);
            $v = self::fmtNum($row['impacto_abs_valor'] ?? 0);
            $out[] = "{$i}. {$z}: {$n} líneas NC, impacto (|Valor|) {$v}";
            $i++;
            if ($i > 25) {
                break;
            }
        }

        return implode("\n", $out);
    }

    /** @param list<array<string, mixed>> $filas */
    private static function linesTopZonaPrecio(array $filas): string
    {
        $out = [];
        $i = 1;
        foreach ($filas as $row) {
            if (!is_array($row)) {
                continue;
            }
            $nom = (string) ($row['nombre_cliente'] ?? '');
            $ln = (int) ($row['lineas_venta'] ?? 0);
            $v = self::fmtNum($row['suma_valor'] ?? 0);
            $out[] = "{$i}. {$nom}: " . $ln . ' líneas, suma Valor ' . $v;
            $i++;
            if ($i > 25) {
                break;
            }
        }

        return implode("\n", $out);
    }

    /** @param list<array<string, mixed>> $filas */
    private static function linesTopNc(array $filas): string
    {
        $out = [];
        $i = 1;
        foreach ($filas as $row) {
            if (!is_array($row)) {
                continue;
            }
            $nom = (string) ($row['nombre_cliente'] ?? '');
            $ln = (int) ($row['lineas'] ?? 0);
            $v = self::fmtNum($row['suma_valor'] ?? 0);
            $out[] = "{$i}. {$nom}: {$ln} notas de crédito por valor de " . $v;
            $i++;
            if ($i > 25) {
                break;
            }
        }

        return implode("\n", $out);
    }

    /** @param list<array<string, mixed>> $filas */
    private static function linesTopClientesGlobal(array $filas): string
    {
        $out = [];
        $i = 1;
        foreach ($filas as $row) {
            if (!is_array($row)) {
                continue;
            }
            $nom = (string) ($row['nombre_cliente'] ?? '');
            $ln = (int) ($row['lineas'] ?? 0);
            $v = self::fmtNum($row['suma_valor'] ?? 0);
            $pct = $row['pct_del_total'] ?? null;
            $pctS = is_numeric($pct) ? ', ' . self::fmtNum($pct, 2) . '% del total' : '';
            $out[] = "{$i}. {$nom}: {$ln} líneas, suma Valor {$v}{$pctS}";
            $i++;
            if ($i > 25) {
                break;
            }
        }

        return implode("\n", $out);
    }

    /** @param list<array<string, mixed>> $filas */
    private static function linesEtiquetaValor(array $filas): string
    {
        $out = [];
        $i = 1;
        foreach ($filas as $row) {
            if (!is_array($row)) {
                continue;
            }
            $e = (string) ($row['etiqueta'] ?? '');
            $ln = (int) ($row['lineas'] ?? 0);
            $v = self::fmtNum($row['suma_valor'] ?? 0);
            $out[] = "{$i}. {$e}: {$ln} líneas, suma Valor " . $v;
            $i++;
            if ($i > 25) {
                break;
            }
        }

        return implode("\n", $out);
    }

    /** @param list<array<string, mixed>> $filas */
    private static function linesProductos(array $filas): string
    {
        $out = [];
        $i = 1;
        foreach ($filas as $row) {
            if (!is_array($row)) {
                continue;
            }
            $g = (string) ($row['glosa'] ?? $row['cod_item'] ?? '');
            $v = self::fmtNum($row['suma_valor'] ?? 0);
            $ln = (int) ($row['lineas'] ?? 0);
            $out[] = "{$i}. {$g}: {$ln} líneas, suma Valor " . $v;
            $i++;
            if ($i > 25) {
                break;
            }
        }

        return implode("\n", $out);
    }

    /** @param list<array<string, mixed>> $filas */
    private static function linesMixTdoc(array $filas): string
    {
        $out = [];
        $i = 1;
        foreach ($filas as $row) {
            if (!is_array($row)) {
                continue;
            }
            $t = (string) ($row['tdoc'] ?? '');
            $label = DocumentoTipoEtiqueta::etiqueta($t);
            $ln = (int) ($row['lineas'] ?? 0);
            $v = self::fmtNum($row['suma_valor'] ?? 0);
            $out[] = "{$i}. {$label}: {$ln} líneas, suma Valor " . $v;
            $i++;
            if ($i > 25) {
                break;
            }
        }

        return implode("\n", $out);
    }

    /** @param list<array<string, mixed>> $filas */
    private static function linesComparativo(array $filas): string
    {
        $out = [];
        $i = 1;
        foreach ($filas as $row) {
            if (!is_array($row)) {
                continue;
            }
            $e = (string) ($row['etiqueta'] ?? '');
            $a = self::fmtNum($row['valor_periodo_a'] ?? 0);
            $b = self::fmtNum($row['valor_periodo_b'] ?? 0);
            $d = self::fmtNum($row['delta'] ?? 0);
            $out[] = "{$i}. {$e}: periodo A {$a}, periodo B {$b}, delta " . $d;
            $i++;
            if ($i > 25) {
                break;
            }
        }

        return implode("\n", $out);
    }

    /**
     * @param list<array<string, mixed>> $filas
     */
    private static function linesEtiquetaNamed(array $filas, string $key): string
    {
        $out = [];
        $i = 1;
        foreach ($filas as $row) {
            if (!is_array($row)) {
                continue;
            }
            $e = (string) ($row[$key] ?? '');
            $ln = (int) ($row['lineas'] ?? 0);
            $v = self::fmtNum($row['suma_valor'] ?? 0);
            $out[] = "{$i}. {$e}: {$ln} líneas, suma Valor " . $v;
            $i++;
            if ($i > 25) {
                break;
            }
        }

        return implode("\n", $out);
    }

    /** @param list<array<string, mixed>> $filas */
    private static function linesSerieMensual(array $filas): string
    {
        $out = [];
        $i = 1;
        foreach ($filas as $row) {
            if (!is_array($row)) {
                continue;
            }
            $m = (string) ($row['mes'] ?? '');
            $v = self::fmtNum($row['suma_valor'] ?? 0);
            $ln = (int) ($row['lineas'] ?? 0);
            $out[] = "{$i}. {$m}: {$ln} líneas, suma Valor " . $v;
            $i++;
            if ($i > 40) {
                break;
            }
        }

        return implode("\n", $out);
    }

    /** @param list<array<string, mixed>> $filas */
    private static function linesGenericBuscar(array $filas): string
    {
        $maxRows = 12;
        $out = [];
        $n = 1;
        foreach ($filas as $row) {
            if (!is_array($row)) {
                continue;
            }
            $parts = [];
            $k = 0;
            foreach ($row as $col => $val) {
                if ($k >= 4) {
                    break;
                }
                $parts[] = $col . '=' . (is_scalar($val) ? (string) $val : '…');
                $k++;
            }
            $out[] = $n . '. ' . implode(', ', $parts);
            $n++;
            if ($n > $maxRows) {
                $rest = count($filas) - $maxRows;
                if ($rest > 0) {
                    $out[] = '(+' . $rest . ' filas más en el reporte.)';
                }
                break;
            }
        }

        return implode("\n", $out);
    }

    /** @param list<array<string, mixed>> $proyecciones @param array<string, mixed> $payload */
    private static function linesProyecciones(array $proyecciones, array $payload): string
    {
        $out = [];
        $mesesHist = (int) ($payload['meses_historicos'] ?? 0);
        $pendiente = self::fmtNum($payload['pendiente_tendencia'] ?? 0);
        $out[] = "Proyección basada en {$mesesHist} meses históricos (pendiente: {$pendiente}).";

        foreach ($proyecciones as $row) {
            if (!is_array($row)) {
                continue;
            }
            $mes = (string) ($row['mes'] ?? '');
            $valor = self::fmtNum($row['valor_proyectado'] ?? 0);
            $out[] = "{$mes}: {$valor}";
        }

        $nota = (string) ($payload['nota'] ?? '');
        if ($nota !== '') {
            $out[] = "Nota: {$nota}";
        }

        return implode("\n", $out);
    }
}
