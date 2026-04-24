<?php
declare(strict_types=1);

/**
 * Catálogo de herramientas: solo SELECT parametrizado y agregados / límites estrictos.
 */
final class ToolRegistry
{
    public function __construct(
        private readonly \PDO $pdo,
        private readonly DateRangeValidator $dates,
        private readonly int $maxLimit
    ) {
    }

    /** @return list<array<string, mixed>> */
    public function definitions(): array
    {
        return [
            $this->fn(
                'top_clientes_valor',
                'Ranking de clientes por importe total en un periodo. Usa ventasgeneral para nombres; sale para alinearse al ERP.',
                [
                    'fecha_desde' => ['type' => 'string', 'description' => 'Inicio YYYY-MM-DD'],
                    'fecha_hasta' => ['type' => 'string', 'description' => 'Fin YYYY-MM-DD'],
                    'limite' => ['type' => 'integer', 'description' => 'Top N, max 50', 'default' => 15],
                    'fuente' => [
                        'type' => 'string',
                        'enum' => ['ventasgeneral', 'sale'],
                        'description' => 'ventasgeneral: Valor/Cantidad/Peso; sale: timport/tcantid',
                    ],
                ],
                ['fecha_desde', 'fecha_hasta', 'fuente']
            ),
            $this->fn(
                'compras_cliente_periodo',
                'Totales y conteo de lineas de un cliente en un periodo. codigo_cliente = DNI o RUC (sale.tprocli o ventasgeneral.CodCliente).',
                [
                    'codigo_cliente' => ['type' => 'string'],
                    'fecha_desde' => ['type' => 'string'],
                    'fecha_hasta' => ['type' => 'string'],
                    'fuente' => ['type' => 'string', 'enum' => ['ventasgeneral', 'sale']],
                ],
                ['codigo_cliente', 'fecha_desde', 'fecha_hasta', 'fuente']
            ),
            $this->fn(
                'serie_temporal_mensual',
                'Serie mensual de totales (valor, cantidad, peso segun fuente).',
                [
                    'fecha_desde' => ['type' => 'string'],
                    'fecha_hasta' => ['type' => 'string'],
                    'fuente' => ['type' => 'string', 'enum' => ['ventasgeneral', 'sale']],
                ],
                ['fecha_desde', 'fecha_hasta', 'fuente']
            ),
            $this->fn(
                'ventas_por_zona',
                'Agrega ventas por zona comercial o descripcion de zona de distribucion (solo ventasgeneral).',
                [
                    'fecha_desde' => ['type' => 'string'],
                    'fecha_hasta' => ['type' => 'string'],
                    'tipo_zona' => [
                        'type' => 'string',
                        'enum' => ['comercial', 'distribucion'],
                        'description' => 'comercial = ZonaComercial; distribucion = DescriZonaDistribucion',
                    ],
                    'limite' => ['type' => 'integer', 'default' => 15],
                ],
                ['fecha_desde', 'fecha_hasta', 'tipo_zona']
            ),
            $this->fn(
                'ventas_por_centro_costo',
                'Suma importes y cantidades agrupadas por codigo completo de centro de costos (sale.tcencos). La nomenclatura del codigo depende del ERP.',
                [
                    'fecha_desde' => ['type' => 'string'],
                    'fecha_hasta' => ['type' => 'string'],
                    'limite' => ['type' => 'integer', 'default' => 20],
                ],
                ['fecha_desde', 'fecha_hasta']
            ),
            $this->fn(
                'top_productos',
                'Productos mas vendidos por importe en el periodo.',
                [
                    'fecha_desde' => ['type' => 'string'],
                    'fecha_hasta' => ['type' => 'string'],
                    'fuente' => ['type' => 'string', 'enum' => ['ventasgeneral', 'sale']],
                    'limite' => ['type' => 'integer', 'default' => 15],
                ],
                ['fecha_desde', 'fecha_hasta', 'fuente']
            ),
        ];
    }

    /**
     * @param array<string, array<string, mixed>> $props
     * @param list<string> $required
     */
    private function fn(string $name, string $description, array $props, array $required): array
    {
        return [
            'type' => 'function',
            'function' => [
                'name' => $name,
                'description' => $description,
                'parameters' => [
                    'type' => 'object',
                    'properties' => $props,
                    'required' => $required,
                ],
            ],
        ];
    }

    /**
     * @param array<string, mixed> $args
     * @return array<string, mixed>
     */
    public function execute(string $name, array $args): array
    {
        try {
            return match ($name) {
                'top_clientes_valor' => $this->topClientesValor($args),
                'compras_cliente_periodo' => $this->comprasClientePeriodo($args),
                'serie_temporal_mensual' => $this->serieTemporalMensual($args),
                'ventas_por_zona' => $this->ventasPorZona($args),
                'ventas_por_centro_costo' => $this->ventasPorCentroCosto($args),
                'ventas_por_granja' => $this->ventasPorCentroCosto($args),
                'top_productos' => $this->topProductos($args),
                default => ['error' => 'herramienta desconocida'],
            };
        } catch (\Throwable $e) {
            return ['error' => 'sql', 'detail' => $e->getMessage()];
        }
    }

    private function clampLimit(mixed $lim): int
    {
        $n = (int) $lim;
        if ($n < 1) {
            $n = 15;
        }
        return min($n, $this->maxLimit);
    }

    /** @param array<string, mixed> $args */
    private function topClientesValor(array $args): array
    {
        $v = $this->dates->validate((string) $args['fecha_desde'], (string) $args['fecha_hasta']);
        if (isset($v['error'])) {
            return $v;
        }
        [$d1, $d2] = $v;
        $lim = $this->clampLimit($args['limite'] ?? 15);
        $fuente = (string) $args['fuente'];

        if ($fuente === 'ventasgeneral') {
            $sql = 'SELECT CodCliente AS codigo, MAX(NombreCliente) AS nombre, SUM(Valor) AS total_valor, SUM(Cantidad) AS total_cantidad, SUM(Peso) AS total_peso
                    FROM ventasgeneral WHERE FechaCont BETWEEN :d1 AND :d2 GROUP BY CodCliente ORDER BY total_valor DESC LIMIT ' . $lim;
        } else {
            $sql = 'SELECT tprocli AS codigo, SUM(timport) AS total_importe, SUM(tcantid) AS total_cantidad
                    FROM sale WHERE tfecfac BETWEEN :d1 AND :d2 AND tlib = \'RV\' GROUP BY tprocli ORDER BY total_importe DESC LIMIT ' . $lim;
        }
        $st = $this->pdo->prepare($sql);
        $st->execute(['d1' => $d1, 'd2' => $d2]);
        return ['filas' => $st->fetchAll(), 'meta' => ['fuente' => $fuente, 'desde' => $d1, 'hasta' => $d2]];
    }

    /** @param array<string, mixed> $args */
    private function comprasClientePeriodo(array $args): array
    {
        $v = $this->dates->validate((string) $args['fecha_desde'], (string) $args['fecha_hasta']);
        if (isset($v['error'])) {
            return $v;
        }
        [$d1, $d2] = $v;
        $cod = trim((string) $args['codigo_cliente']);
        if ($cod === '' || strlen($cod) > 32) {
            return ['error' => 'codigo_cliente invalido'];
        }
        $fuente = (string) $args['fuente'];

        if ($fuente === 'ventasgeneral') {
            $sql = 'SELECT COUNT(*) AS lineas, SUM(Valor) AS total_valor, SUM(Cantidad) AS total_cantidad, SUM(Peso) AS total_peso
                    FROM ventasgeneral WHERE CodCliente = :c AND FechaCont BETWEEN :d1 AND :d2';
        } else {
            $sql = 'SELECT COUNT(*) AS lineas, SUM(timport) AS total_importe, SUM(tcantid) AS total_cantidad
                    FROM sale WHERE tprocli = :c AND tfecfac BETWEEN :d1 AND :d2 AND tlib = \'RV\'';
        }
        $st = $this->pdo->prepare($sql);
        $st->execute(['c' => $cod, 'd1' => $d1, 'd2' => $d2]);
        $row = $st->fetch() ?: [];
        return ['resumen' => $row, 'codigo_cliente' => $cod, 'fuente' => $fuente, 'desde' => $d1, 'hasta' => $d2];
    }

    /** @param array<string, mixed> $args */
    private function serieTemporalMensual(array $args): array
    {
        $v = $this->dates->validate((string) $args['fecha_desde'], (string) $args['fecha_hasta']);
        if (isset($v['error'])) {
            return $v;
        }
        [$d1, $d2] = $v;
        $fuente = (string) $args['fuente'];

        if ($fuente === 'ventasgeneral') {
            $sql = 'SELECT DATE_FORMAT(FechaCont, \'%Y-%m\') AS mes, SUM(Valor) AS total_valor, SUM(Cantidad) AS total_cantidad, SUM(Peso) AS total_peso
                    FROM ventasgeneral WHERE FechaCont BETWEEN :d1 AND :d2 GROUP BY DATE_FORMAT(FechaCont, \'%Y-%m\') ORDER BY mes';
        } else {
            $sql = 'SELECT DATE_FORMAT(tfecfac, \'%Y-%m\') AS mes, SUM(timport) AS total_importe, SUM(tcantid) AS total_cantidad
                    FROM sale WHERE tfecfac BETWEEN :d1 AND :d2 AND tlib = \'RV\' GROUP BY DATE_FORMAT(tfecfac, \'%Y-%m\') ORDER BY mes';
        }
        $st = $this->pdo->prepare($sql);
        $st->execute(['d1' => $d1, 'd2' => $d2]);
        return ['serie' => $st->fetchAll(), 'fuente' => $fuente];
    }

    /** @param array<string, mixed> $args */
    private function ventasPorZona(array $args): array
    {
        $v = $this->dates->validate((string) $args['fecha_desde'], (string) $args['fecha_hasta']);
        if (isset($v['error'])) {
            return $v;
        }
        [$d1, $d2] = $v;
        $tipo = (string) $args['tipo_zona'];
        $lim = $this->clampLimit($args['limite'] ?? 15);

        if ($tipo === 'comercial') {
            $col = 'ZonaComercial';
        } else {
            $col = 'DescriZonaDistribucion';
        }
        $sql = "SELECT COALESCE(NULLIF(TRIM(`{$col}`), ''), '(sin zona)') AS zona, SUM(Valor) AS total_valor, SUM(Cantidad) AS total_cantidad, SUM(Peso) AS total_peso
                FROM ventasgeneral WHERE FechaCont BETWEEN :d1 AND :d2
                GROUP BY COALESCE(NULLIF(TRIM(`{$col}`), ''), '(sin zona)') ORDER BY total_valor DESC LIMIT {$lim}";
        $st = $this->pdo->prepare($sql);
        $st->execute(['d1' => $d1, 'd2' => $d2]);
        return ['filas' => $st->fetchAll(), 'tipo_zona' => $tipo];
    }

    /** @param array<string, mixed> $args */
    private function ventasPorCentroCosto(array $args): array
    {
        $v = $this->dates->validate((string) $args['fecha_desde'], (string) $args['fecha_hasta']);
        if (isset($v['error'])) {
            return $v;
        }
        [$d1, $d2] = $v;
        $lim = $this->clampLimit($args['limite'] ?? 20);
        $sql = 'SELECT TRIM(tcencos) AS centro_costo, SUM(timport) AS total_importe, SUM(tcantid) AS total_cantidad
                FROM sale WHERE tfecfac BETWEEN :d1 AND :d2 AND tlib = \'RV\'
                AND tcencos IS NOT NULL AND TRIM(tcencos) <> \'\'
                GROUP BY TRIM(tcencos) ORDER BY total_importe DESC LIMIT ' . $lim;
        $st = $this->pdo->prepare($sql);
        $st->execute(['d1' => $d1, 'd2' => $d2]);
        return ['filas' => $st->fetchAll(), 'tabla' => 'sale'];
    }

    /** @param array<string, mixed> $args */
    private function topProductos(array $args): array
    {
        $v = $this->dates->validate((string) $args['fecha_desde'], (string) $args['fecha_hasta']);
        if (isset($v['error'])) {
            return $v;
        }
        [$d1, $d2] = $v;
        $lim = $this->clampLimit($args['limite'] ?? 15);
        $fuente = (string) $args['fuente'];

        if ($fuente === 'ventasgeneral') {
            $sql = 'SELECT CodItem AS codigo, MAX(Glosa) AS descripcion, SUM(Valor) AS total_valor, SUM(Cantidad) AS total_cantidad, SUM(Peso) AS total_peso
                    FROM ventasgeneral WHERE FechaCont BETWEEN :d1 AND :d2 GROUP BY CodItem ORDER BY total_valor DESC LIMIT ' . $lim;
        } else {
            $sql = 'SELECT tcodigo AS codigo, MAX(tglosa) AS descripcion, SUM(timport) AS total_importe, SUM(tcantid) AS total_cantidad
                    FROM sale WHERE tfecfac BETWEEN :d1 AND :d2 AND tlib = \'RV\' GROUP BY tcodigo ORDER BY total_importe DESC LIMIT ' . $lim;
        }
        $st = $this->pdo->prepare($sql);
        $st->execute(['d1' => $d1, 'd2' => $d2]);
        return ['filas' => $st->fetchAll(), 'fuente' => $fuente];
    }
}
