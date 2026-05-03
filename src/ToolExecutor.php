<?php

declare(strict_types=1);

require_once __DIR__ . '/VentasGeneralParetoNc.php';
require_once __DIR__ . '/VentasGeneralTopClientesZona.php';
require_once __DIR__ . '/VentasGeneralBuscarQuery.php';
require_once __DIR__ . '/VentasGeneralReportesGraficos.php';
require_once __DIR__ . '/SqlSentenciaTexto.php';

final class ToolExecutor
{
    private const MAX_LIMIT     = 100;
    private const DEFAULT_LIMIT = 50;

    /** @var list<string> sentencias interpoladas (una por consulta ejecutada en esta petición) */
    private array $sqlBloquesEjecutados = [];

    public function __construct(private PDO $pdo)
    {
    }

    /** @return list<string> */
    public function pullSqlBloquesParaEnlace(): array
    {
        return $this->sqlBloquesEjecutados;
    }

    public function execute(string $name, array $args): string
    {
        try {
            $result = match ($name) {
                'ventasgeneral_resumen'                   => $this->ventasgeneralResumen($args),
                'ventasgeneral_buscar'                    => $this->ventasgeneralBuscar($args),
                'ventasgeneral_pareto_nc_zonaprecio'      => $this->ventasgeneralParetoNcZonaprecio($args),
                'ventasgeneral_top_clientes_zona_precio'  => $this->ventasgeneralTopClientesZonaPrecio($args),
                'ventasgeneral_barras_ventas_dimension'   => $this->ventasgeneralBarrasVentasDimension($args),
                'ventasgeneral_comparativo_periodos'      => $this->ventasgeneralComparativoPeriodos($args),
                'ventasgeneral_top_productos'             => $this->ventasgeneralTopProductos($args),
                'ventasgeneral_top_clientes_globales'     => $this->ventasgeneralTopClientesGlobales($args),
                'ventasgeneral_top_clientes_nota_credito' => $this->ventasgeneralTopClientesNotaCredito($args),
                'ventasgeneral_mix_tdoc'                  => $this->ventasgeneralMixTdoc($args),
                'ventasgeneral_barras_ruta_comercial'     => $this->ventasgeneralBarrasRutaComercial($args),
                'ventasgeneral_barras_corporativo'        => $this->ventasgeneralBarrasCorporativo($args),
                'ventasgeneral_serie_mensual_valor'       => $this->ventasgeneralSerieMensualValor($args),
                'ventasgeneral_proyeccion_ventas'         => $this->ventasgeneralProyeccionVentas($args),
                default => ['error' => 'Función no reconocida: ' . $name],
            };
        } catch (Throwable $e) {
            $result = ['error' => $e->getMessage()];
        }
        if (is_array($result)) {
            $this->absorbSqlTraces($result);
        }

        return json_encode($result, JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE);
    }

    // -------------------------------------------------------------------------
    // Helpers internos
    // -------------------------------------------------------------------------

    /** @param array<string, mixed> $result */
    private function absorbSqlTraces(array &$result): void
    {
        $tr = $result['_sql_traces'] ?? null;
        unset($result['_sql_traces']);
        if (!is_array($tr)) {
            return;
        }
        foreach ($tr as $item) {
            if (!is_array($item) || !isset($item['sql'], $item['params']) || !is_string($item['sql']) || !is_array($item['params'])) {
                continue;
            }
            $this->sqlBloquesEjecutados[] = SqlSentenciaTexto::interpolate($this->pdo, $item['sql'], $item['params']);
        }
    }

    /**
     * Parsea y valida un rango de fechas desde $args. Lanza si alguna falta o d1 > d2.
     *
     * @return array{0: string, 1: string}
     */
    private function parseDateRange(
        array $args,
        string $fromKey = 'fecha_desde',
        string $toKey   = 'fecha_hasta'
    ): array {
        $d1 = $this->parseDate($fromKey, $args);
        $d2 = $this->parseDate($toKey, $args);
        if ($d1 > $d2) {
            throw new InvalidArgumentException("$fromKey no puede ser mayor que $toKey");
        }
        return [$d1, $d2];
    }

    /**
     * Extrae _sql_traces de un array de datos devuelto por las clases de consulta.
     *
     * @param array<string, mixed> $data  (modificado in-place: se elimina _sql_traces)
     * @return list<array<string, mixed>>
     */
    private function pullTraces(array &$data): array
    {
        $tr = $data['_sql_traces'] ?? [];
        unset($data['_sql_traces']);
        return is_array($tr) ? $tr : [];
    }

    private function parseDate(string $key, array $args, bool $required = true): ?string
    {
        if (!isset($args[$key]) || $args[$key] === '' || $args[$key] === null) {
            if ($required) {
                throw new InvalidArgumentException("Falta parámetro de fecha: $key");
            }
            return null;
        }
        $s = (string) $args[$key];
        $d = DateTimeImmutable::createFromFormat('Y-m-d', $s);
        if ($d === false || $d->format('Y-m-d') !== $s) {
            throw new InvalidArgumentException("Fecha inválida (use YYYY-MM-DD): $key");
        }
        return $s;
    }

    private function clampLimit(?int $n, int $default = self::DEFAULT_LIMIT): int
    {
        if ($n === null) {
            return $default;
        }
        return max(1, min(self::MAX_LIMIT, $n));
    }

    private function intArg(mixed $v, int $default, int $min, int $max): int
    {
        if ($v === null || $v === '') {
            return $default;
        }
        $n = is_numeric($v) ? (int) $v : $default;
        return max($min, min($max, $n));
    }

    private function dimensionPrecioComercial(mixed $v): string
    {
        $d = strtolower(trim((string) ($v ?? 'precio')));
        if (!in_array($d, ['precio', 'comercial'], true)) {
            throw new InvalidArgumentException('dimension debe ser precio o comercial');
        }
        return $d;
    }

    // -------------------------------------------------------------------------
    // Herramientas
    // -------------------------------------------------------------------------

    /** @return array<string, mixed> */
    private function ventasgeneralResumen(array $args): array
    {
        [$d1, $d2] = $this->parseDateRange($args);

        $sql    = 'SELECT COUNT(*) AS filas, COALESCE(SUM(Valor),0) AS suma_valor,
                          COALESCE(SUM(Cantidad),0) AS suma_cantidad, COALESCE(SUM(Peso),0) AS suma_peso
                   FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2';
        $params = [':d1' => $d1, ':d2' => $d2];

        $zona = isset($args['zona_comercial']) ? trim((string) $args['zona_comercial']) : '';
        if ($zona !== '') {
            $sql .= ' AND ZonaComercial LIKE :zona';
            $params[':zona'] = '%' . $zona . '%';
        }

        $cod = isset($args['cod_cliente']) ? trim((string) $args['cod_cliente']) : '';
        if ($cod !== '') {
            $sql .= ' AND CodigoCliente = :cod';
            $params[':cod'] = $cod;
        }

        $prefZ = isset($args['prefijo_descri_zona_precio']) ? strtoupper(trim((string) $args['prefijo_descri_zona_precio'])) : '';
        if ($prefZ !== '') {
            $sql .= " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE :prefzp";
            $params[':prefzp'] = $prefZ . '%';
        }

        $prov = isset($args['provincia']) ? trim((string) $args['provincia']) : '';
        if ($prov !== '') {
            $sql .= ' AND Provincia LIKE :prov';
            $params[':prov'] = '%' . $prov . '%';
        }

        $tdoc = isset($args['tipo_documento']) ? trim((string) $args['tipo_documento']) : '';
        if ($tdoc !== '') {
            $sql .= ' AND TipoDocumento LIKE :tdoc';
            $params[':tdoc'] = '%' . $tdoc . '%';
        }

        $st = $this->pdo->prepare($sql);
        $st->execute($params);
        $row = $st->fetch(PDO::FETCH_ASSOC) ?: [];

        $tablaQ = ['fecha_desde' => $d1, 'fecha_hasta' => $d2];
        if ($zona !== '')  { $tablaQ['zona_comercial'] = $zona; }
        if ($cod !== '')   { $tablaQ['cod_cliente'] = $cod; }
        if ($prefZ !== '') { $tablaQ['prefijo_descri_zona_precio'] = $prefZ; }
        if ($prov !== '')  { $tablaQ['provincia'] = $prov; }
        if ($tdoc !== '')  { $tablaQ['tipo_documento'] = $tdoc; }

        return [
            'tabla'       => 'ventasgeneral',
            'periodo'     => ['desde' => $d1, 'hasta' => $d2],
            'agregados'   => $row,
            'reporte_url' => 'ventasgeneral_resumen_tabla.php?' . http_build_query($tablaQ, '', '&', PHP_QUERY_RFC3986),
            '_sql_traces' => [['sql' => $sql, 'params' => $params]],
        ];
    }

    /** @return array<string, mixed> */
    private function ventasgeneralBuscar(array $args): array
    {
        $out       = VentasGeneralBuscarQuery::search($this->pdo, $args);
        $tr        = $this->pullTraces($out);
        $tablaArgs = array_merge($args, ['limit' => $out['limit'], 'offset' => $out['offset']]);

        return [
            'tabla'          => 'ventasgeneral',
            'count_devuelto' => count($out['filas']),
            'limit'          => $out['limit'],
            'offset'         => $out['offset'],
            'filas'          => $out['filas'],
            'reporte_url'    => VentasGeneralBuscarQuery::buildTablaUrl($tablaArgs),
            '_sql_traces'    => $tr,
        ];
    }

    /** @return array<string, mixed> */
    private function ventasgeneralParetoNcZonaprecio(array $args): array
    {
        [$d1, $d2] = $this->parseDateRange($args);
        $maxZ = $this->intArg($args['max_zonas'] ?? null, 100, 1, 200);
        $data = VentasGeneralParetoNc::datos($this->pdo, $d1, $d2, $maxZ);
        $tr   = $this->pullTraces($data);
        $q    = http_build_query(['desde' => $d1, 'hasta' => $d2, 'max' => $maxZ], '', '&', PHP_QUERY_RFC3986);

        return [
            'tabla'                      => 'ventasgeneral',
            'criterio_nc'                => "TDoc = '07' (notas de crédito en ETL ventasgeneral)",
            'agrupacion'                 => 'DescripcionZonaPrecio',
            'periodo'                    => $data['periodo'],
            'total_impacto_nc_valor_abs' => $data['total_impacto_nc'],
            'filas_pareto'               => $data['filas'],
            'zonas_hasta_80pct_aprox'    => $data['zonas_contadas_hasta_80pct_aprox'],
            'reporte_url'                => 'pareto_nc_zona.php?' . $q,
            '_sql_traces'                => $tr,
        ];
    }

    /** @return array<string, mixed> */
    private function ventasgeneralTopClientesZonaPrecio(array $args): array
    {
        [$d1, $d2] = $this->parseDateRange($args);
        $pref = isset($args['prefijo_descri_zona_precio']) ? trim((string) $args['prefijo_descri_zona_precio']) : '';
        if ($pref === '') {
            throw new InvalidArgumentException('Falta prefijo_descri_zona_precio (ej. LAJOYA)');
        }
        $top  = $this->intArg($args['top_n'] ?? null, 10, 1, 100);
        $data = VentasGeneralTopClientesZona::datos($this->pdo, $d1, $d2, $pref, $top);
        $tr   = $this->pullTraces($data);
        $q    = http_build_query([
            'desde'   => $d1,
            'hasta'   => $d2,
            'prefijo' => $data['prefijo_descri_zona_precio'],
            'top'     => $top,
        ], '', '&', PHP_QUERY_RFC3986);

        return [
            'tabla'                      => 'ventasgeneral',
            'criterio'                   => 'SUM(Valor) por CodigoCliente; solo líneas con DescripcionZonaPrecio LIKE prefijo%',
            'agrupacion'                 => 'CodigoCliente (NombreCliente)',
            'periodo'                    => $data['periodo'],
            'prefijo_descri_zona_precio' => $data['prefijo_descri_zona_precio'],
            'total_valor_zona'           => $data['total_valor_zona'],
            'filas_ranking'              => $data['filas'],
            'clientes_hasta_80pct_aprox' => $data['clientes_contados_hasta_80pct_aprox'],
            'reporte_url'                => 'pareto_clientes_zona.php?' . $q,
            '_sql_traces'                => $tr,
        ];
    }

    /** @return array<string, mixed> */
    private function ventasgeneralBarrasVentasDimension(array $args): array
    {
        [$d1, $d2] = $this->parseDateRange($args);
        $dim  = $this->dimensionPrecioComercial($args['dimension'] ?? 'precio');
        $top  = $this->intArg($args['top_n'] ?? null, 20, 1, 100);
        $data = VentasGeneralReportesGraficos::barrasPorDimension($this->pdo, $d1, $d2, $dim, $top);
        $tr   = $this->pullTraces($data);
        $q    = http_build_query(['desde' => $d1, 'hasta' => $d2, 'dim' => $dim, 'top' => $top], '', '&', PHP_QUERY_RFC3986);

        return [
            'tabla'               => 'ventasgeneral',
            'tipo'                => 'barras_por_' . $dim,
            'periodo'             => $data['periodo'],
            'total_valor_periodo' => $data['total_valor'],
            'filas'               => $data['filas'],
            'reporte_url'         => 'ventas_barras_dimension.php?' . $q,
            '_sql_traces'         => $tr,
        ];
    }

    /** @return array<string, mixed> */
    private function ventasgeneralComparativoPeriodos(array $args): array
    {
        [$a1, $a2] = $this->parseDateRange($args, 'fecha_desde_a', 'fecha_hasta_a');
        [$b1, $b2] = $this->parseDateRange($args, 'fecha_desde_b', 'fecha_hasta_b');
        $dim  = $this->dimensionPrecioComercial($args['dimension'] ?? 'precio');
        $top  = $this->intArg($args['top_n'] ?? null, 15, 1, 80);
        $data = VentasGeneralReportesGraficos::comparativoDosPeriodos($this->pdo, $a1, $a2, $b1, $b2, $dim, $top);
        $tr   = $this->pullTraces($data);
        $q    = http_build_query([
            'a_desde' => $a1, 'a_hasta' => $a2,
            'b_desde' => $b1, 'b_hasta' => $b2,
            'dim'     => $dim, 'top' => $top,
        ], '', '&', PHP_QUERY_RFC3986);

        return [
            'tabla'       => 'ventasgeneral',
            'tipo'        => 'comparativo_periodos',
            'periodo_a'   => $data['periodo_a'],
            'periodo_b'   => $data['periodo_b'],
            'dimension'   => $dim,
            'filas'       => $data['filas'],
            'reporte_url' => 'ventas_comparativo.php?' . $q,
            '_sql_traces' => $tr,
        ];
    }

    /** @return array<string, mixed> */
    private function ventasgeneralTopProductos(array $args): array
    {
        [$d1, $d2] = $this->parseDateRange($args);
        $top  = $this->intArg($args['top_n'] ?? null, 15, 1, 100);
        $data = VentasGeneralReportesGraficos::topProductos($this->pdo, $d1, $d2, $top);
        $tr   = $this->pullTraces($data);
        $q    = http_build_query(['desde' => $d1, 'hasta' => $d2, 'top' => $top], '', '&', PHP_QUERY_RFC3986);

        return [
            'tabla'       => 'ventasgeneral',
            'tipo'        => 'top_productos',
            'periodo'     => $data['periodo'],
            'filas'       => $data['filas'],
            'reporte_url' => 'ventas_top_productos.php?' . $q,
            '_sql_traces' => $tr,
        ];
    }

    /** @return array<string, mixed> */
    private function ventasgeneralTopClientesGlobales(array $args): array
    {
        [$d1, $d2] = $this->parseDateRange($args);
        $top  = $this->intArg($args['top_n'] ?? null, 10, 1, 100);
        $data = VentasGeneralReportesGraficos::topClientesGlobal($this->pdo, $d1, $d2, $top);
        $tr   = $this->pullTraces($data);
        $q    = http_build_query(['desde' => $d1, 'hasta' => $d2, 'top' => $top], '', '&', PHP_QUERY_RFC3986);

        return [
            'tabla'       => 'ventasgeneral',
            'tipo'        => 'top_clientes_global',
            'periodo'     => $data['periodo'],
            'total_valor' => $data['total_valor'],
            'filas'       => $data['filas'],
            'reporte_url' => 'ventas_top_clientes_global.php?' . $q,
            '_sql_traces' => $tr,
        ];
    }

    /** @return array<string, mixed> */
    private function ventasgeneralTopClientesNotaCredito(array $args): array
    {
        [$d1, $d2] = $this->parseDateRange($args);
        $top  = $this->intArg($args['top_n'] ?? null, 10, 1, 100);
        $data = VentasGeneralReportesGraficos::topClientesNotaCredito($this->pdo, $d1, $d2, $top);
        $tr   = $this->pullTraces($data);
        $q    = http_build_query(['desde' => $d1, 'hasta' => $d2, 'top' => $top], '', '&', PHP_QUERY_RFC3986);

        return [
            'tabla'           => 'ventasgeneral',
            'criterio'        => 'CodigoDocumento = 07; ranking por COUNT(*) por CodigoCliente (notas de crédito)',
            'periodo'         => $data['periodo'],
            'total_lineas_nc' => $data['total_lineas_nc'],
            'total_valor_nc'  => $data['total_valor_nc'],
            'filas'           => $data['filas'],
            'reporte_url'     => 'ventas_top_clientes_nc.php?' . $q,
            '_sql_traces'     => $tr,
        ];
    }

    /** @return array<string, mixed> */
    private function ventasgeneralMixTdoc(array $args): array
    {
        [$d1, $d2] = $this->parseDateRange($args);
        $data = VentasGeneralReportesGraficos::mixPorTdoc($this->pdo, $d1, $d2);
        $tr   = $this->pullTraces($data);
        $q    = http_build_query(['desde' => $d1, 'hasta' => $d2], '', '&', PHP_QUERY_RFC3986);

        return [
            'tabla'       => 'ventasgeneral',
            'tipo'        => 'mix_tdoc',
            'periodo'     => $data['periodo'],
            'total_valor' => $data['total_valor'],
            'filas'       => $data['filas'],
            'reporte_url' => 'ventas_mix_tdoc.php?' . $q,
            '_sql_traces' => $tr,
        ];
    }

    /** @return array<string, mixed> */
    private function ventasgeneralBarrasRutaComercial(array $args): array
    {
        [$d1, $d2] = $this->parseDateRange($args);
        $top  = $this->intArg($args['top_n'] ?? null, 15, 1, 100);
        $data = VentasGeneralReportesGraficos::topRutaComercial($this->pdo, $d1, $d2, $top);
        $tr   = $this->pullTraces($data);
        $q    = http_build_query(['desde' => $d1, 'hasta' => $d2, 'top' => $top], '', '&', PHP_QUERY_RFC3986);

        return [
            'tabla'       => 'ventasgeneral',
            'tipo'        => 'barras_ruta',
            'periodo'     => $data['periodo'],
            'filas'       => $data['filas'],
            'reporte_url' => 'ventas_barras_ruta.php?' . $q,
            '_sql_traces' => $tr,
        ];
    }

    /** @return array<string, mixed> */
    private function ventasgeneralBarrasCorporativo(array $args): array
    {
        [$d1, $d2] = $this->parseDateRange($args);
        $top  = $this->intArg($args['top_n'] ?? null, 15, 1, 100);
        $data = VentasGeneralReportesGraficos::topCorporativo($this->pdo, $d1, $d2, $top);
        $tr   = $this->pullTraces($data);
        $q    = http_build_query(['desde' => $d1, 'hasta' => $d2, 'top' => $top], '', '&', PHP_QUERY_RFC3986);

        return [
            'tabla'       => 'ventasgeneral',
            'tipo'        => 'barras_corporativo',
            'periodo'     => $data['periodo'],
            'filas'       => $data['filas'],
            'reporte_url' => 'ventas_barras_corporativo.php?' . $q,
            '_sql_traces' => $tr,
        ];
    }

    /** @return array<string, mixed> */
    private function ventasgeneralSerieMensualValor(array $args): array
    {
        [$d1, $d2] = $this->parseDateRange($args);
        $data = VentasGeneralReportesGraficos::serieMensualValor($this->pdo, $d1, $d2);
        $tr   = $this->pullTraces($data);
        $q    = http_build_query(['desde' => $d1, 'hasta' => $d2], '', '&', PHP_QUERY_RFC3986);

        return [
            'tabla'       => 'ventasgeneral',
            'tipo'        => 'serie_mensual_valor',
            'periodo'     => $data['periodo'],
            'filas'       => $data['filas'],
            'reporte_url' => 'ventas_serie_mensual.php?' . $q,
            '_sql_traces' => $tr,
        ];
    }

    /** @return array<string, mixed> */
    private function ventasgeneralProyeccionVentas(array $args): array
    {
        [$d1, $d2] = $this->parseDateRange($args);
        $meses = $this->intArg($args['meses_a_proyectar'] ?? null, 3, 1, 12);

        $sql    = "SELECT DATE_FORMAT(FechaContable, '%Y-%m') AS mes, SUM(Valor) AS suma_valor
                   FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2
                   GROUP BY DATE_FORMAT(FechaContable, '%Y-%m') ORDER BY mes";
        $params = [':d1' => $d1, ':d2' => $d2];
        $st     = $this->pdo->prepare($sql);
        $st->execute($params);
        $filas  = $st->fetchAll(PDO::FETCH_ASSOC);

        if (count($filas) < 2) {
            throw new InvalidArgumentException('Se necesitan al menos 2 meses de datos históricos para proyectar');
        }

        // Regresión lineal simple: y = m·x + b  (x = índice mensual)
        $n = count($filas);
        $sumX = $sumY = $sumXY = $sumXX = 0.0;
        foreach ($filas as $i => $row) {
            $x     = (float) $i;
            $y     = (float) $row['suma_valor'];
            $sumX  += $x;
            $sumY  += $y;
            $sumXY += $x * $y;
            $sumXX += $x * $x;
        }
        $m = ($n * $sumXY - $sumX * $sumY) / ($n * $sumXX - $sumX * $sumX);
        $b = ($sumY - $m * $sumX) / $n;

        $proyecciones = [];
        $fechaBase    = DateTimeImmutable::createFromFormat('Y-m', end($filas)['mes']);
        for ($i = 1; $i <= $meses; $i++) {
            $proyecciones[] = [
                'mes'              => $fechaBase->modify("+$i month")->format('Y-m'),
                'valor_proyectado' => max(0.0, $m * ($n + $i - 1) + $b),
            ];
        }

        return [
            'tabla'               => 'ventasgeneral',
            'tipo'                => 'proyeccion_ventas',
            'periodo_historico'   => ['desde' => $d1, 'hasta' => $d2],
            'meses_historicos'    => $n,
            'pendiente_tendencia' => $m,
            'intercepto'          => $b,
            'proyecciones'        => $proyecciones,
            'nota'                => 'Proyección basada en regresión lineal simple. No considera estacionalidad ni factores externos.',
            '_sql_traces'         => [['sql' => $sql, 'params' => $params]],
        ];
    }
}
