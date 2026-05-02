<?php

declare(strict_types=1);

/**
 * Agregados para reportes con gráfico (ventasgeneral).
 */
final class VentasGeneralReportesGraficos
{
    private static function colEtiqueta(string $dimension): string
    {
        return match ($dimension) {
            'precio' => "COALESCE(NULLIF(TRIM(DescripcionZonaPrecio),''),'(sin zona precio)')",
            'comercial' => "COALESCE(NULLIF(TRIM(ZonaComercial),''),'(sin zona comercial)')",
            'ruta' => "COALESCE(NULLIF(TRIM(RutaComercial),''),'(sin ruta)')",
            'corporativo' => "COALESCE(NULLIF(TRIM(NombreCoorporativo),''),'(sin corporativo)')",
            default => throw new InvalidArgumentException('dimension inválida'),
        };
    }

    /**
     * @return array{filas: list<array<string, mixed>>, total_valor: float, periodo: array{desde: string, hasta: string}, dimension: string}
     */
    public static function barrasPorDimension(PDO $pdo, string $d1, string $d2, string $dimension, int $limit): array
    {
        $limit = max(1, min(100, $limit));
        $expr = self::colEtiqueta($dimension);
        $sql = "SELECT {$expr} AS etiqueta, COUNT(*) AS lineas, COALESCE(SUM(Valor),0) AS suma_valor,
                COALESCE(SUM(Cantidad),0) AS suma_cantidad, COALESCE(SUM(Peso),0) AS suma_peso
            FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2
            GROUP BY {$expr}
            ORDER BY suma_valor DESC
            LIMIT {$limit}";
        $st = $pdo->prepare($sql);
        $st->execute([':d1' => $d1, ':d2' => $d2]);
        $raw = $st->fetchAll(PDO::FETCH_ASSOC);
        $stT = $pdo->prepare('SELECT COALESCE(SUM(Valor),0) FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2');
        $stT->execute([':d1' => $d1, ':d2' => $d2]);
        $total = (float) ($stT->fetchColumn() ?: 0);
        $filas = [];
        foreach ($raw as $row) {
            $sv = (float) ($row['suma_valor'] ?? 0);
            $filas[] = [
                'etiqueta' => (string) ($row['etiqueta'] ?? ''),
                'lineas' => (int) ($row['lineas'] ?? 0),
                'suma_valor' => $sv,
                'suma_cantidad' => (float) ($row['suma_cantidad'] ?? 0),
                'suma_peso' => (float) ($row['suma_peso'] ?? 0),
                'pct_del_total' => $total > 0 ? round(($sv / $total) * 100, 2) : 0.0,
            ];
        }

        return [
            'filas' => $filas,
            'total_valor' => $total,
            'periodo' => ['desde' => $d1, 'hasta' => $d2],
            'dimension' => $dimension,
            '_sql_traces' => [
                ['sql' => $sql, 'params' => [':d1' => $d1, ':d2' => $d2]],
                [
                    'sql' => 'SELECT COALESCE(SUM(Valor),0) FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2',
                    'params' => [':d1' => $d1, ':d2' => $d2],
                ],
            ],
        ];
    }

    /**
     * @return array{filas: list<array<string, mixed>>, periodo_a: array{desde: string, hasta: string}, periodo_b: array{desde: string, hasta: string}, dimension: string}
     */
    public static function comparativoDosPeriodos(
        PDO $pdo,
        string $a1,
        string $a2,
        string $b1,
        string $b2,
        string $dimension,
        int $limit
    ): array {
        $limit = max(1, min(80, $limit));
        $expr = self::colEtiqueta($dimension);
        $sql = "SELECT etiqueta,
                SUM(va) AS valor_a,
                SUM(vb) AS valor_b
            FROM (
                SELECT {$expr} AS etiqueta, COALESCE(SUM(Valor),0) AS va, 0 AS vb
                FROM ventasgeneral2 WHERE FechaContable BETWEEN :a1 AND :a2
                GROUP BY {$expr}
                UNION ALL
                SELECT {$expr}, 0, COALESCE(SUM(Valor),0)
                FROM ventasgeneral2 WHERE FechaContable BETWEEN :b1 AND :b2
                GROUP BY {$expr}
            ) u
            GROUP BY etiqueta
            HAVING ABS(SUM(va)) + ABS(SUM(vb)) > 0
            ORDER BY GREATEST(ABS(SUM(va)), ABS(SUM(vb))) DESC
            LIMIT {$limit}";
        $st = $pdo->prepare($sql);
        $st->execute([':a1' => $a1, ':a2' => $a2, ':b1' => $b1, ':b2' => $b2]);
        $raw = $st->fetchAll(PDO::FETCH_ASSOC);
        $filas = [];
        foreach ($raw as $row) {
            $va = (float) ($row['valor_a'] ?? 0);
            $vb = (float) ($row['valor_b'] ?? 0);
            $filas[] = [
                'etiqueta' => (string) ($row['etiqueta'] ?? ''),
                'valor_periodo_a' => $va,
                'valor_periodo_b' => $vb,
                'delta' => round($vb - $va, 2),
            ];
        }

        return [
            'filas' => $filas,
            'periodo_a' => ['desde' => $a1, 'hasta' => $a2],
            'periodo_b' => ['desde' => $b1, 'hasta' => $b2],
            'dimension' => $dimension,
            '_sql_traces' => [
                ['sql' => $sql, 'params' => [':a1' => $a1, ':a2' => $a2, ':b1' => $b1, ':b2' => $b2]],
            ],
        ];
    }

    /**
     * @return array{filas: list<array<string, mixed>>, periodo: array{desde: string, hasta: string}}
     */
    public static function topProductos(PDO $pdo, string $d1, string $d2, int $top): array
    {
        $top = max(1, min(100, $top));
        $sql = 'SELECT CodigoItem AS cod_item, MAX(COALESCE(NULLIF(TRIM(GlosaDetalle),\'\'),\'(sin glosa)\')) AS glosa,
                COUNT(*) AS lineas, COALESCE(SUM(Valor),0) AS suma_valor, COALESCE(SUM(Cantidad),0) AS suma_cantidad
            FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2
            GROUP BY CodigoItem
            ORDER BY suma_valor DESC
            LIMIT ' . $top;
        $st = $pdo->prepare($sql);
        $st->execute([':d1' => $d1, ':d2' => $d2]);

        return [
            'filas' => $st->fetchAll(PDO::FETCH_ASSOC),
            'periodo' => ['desde' => $d1, 'hasta' => $d2],
            '_sql_traces' => [
                ['sql' => $sql, 'params' => [':d1' => $d1, ':d2' => $d2]],
            ],
        ];
    }

    /**
     * @return array{filas: list<array<string, mixed>>, total_valor: float, periodo: array{desde: string, hasta: string}}
     */
    public static function topClientesGlobal(PDO $pdo, string $d1, string $d2, int $top): array
    {
        $top = max(1, min(100, $top));
        $sql = 'SELECT CodigoCliente AS cod_cliente,
                MAX(COALESCE(NULLIF(TRIM(NombreCliente),\'\'),\'(sin nombre)\')) AS nombre_cliente,
                COUNT(*) AS lineas, COALESCE(SUM(Valor),0) AS suma_valor
            FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2
            GROUP BY CodigoCliente
            ORDER BY suma_valor DESC
            LIMIT ' . $top;
        $st = $pdo->prepare($sql);
        $st->execute([':d1' => $d1, ':d2' => $d2]);
        $raw = $st->fetchAll(PDO::FETCH_ASSOC);
        $stT = $pdo->prepare('SELECT COALESCE(SUM(Valor),0) FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2');
        $stT->execute([':d1' => $d1, ':d2' => $d2]);
        $total = (float) ($stT->fetchColumn() ?: 0);
        $cum = 0.0;
        $filas = [];
        foreach ($raw as $row) {
            $sv = (float) ($row['suma_valor'] ?? 0);
            $pct = $total > 0 ? ($sv / $total) * 100.0 : 0.0;
            $cum += $pct;
            $filas[] = [
                'cod_cliente' => (string) ($row['cod_cliente'] ?? ''),
                'nombre_cliente' => (string) ($row['nombre_cliente'] ?? ''),
                'lineas' => (int) ($row['lineas'] ?? 0),
                'suma_valor' => $sv,
                'pct_del_total' => round($pct, 2),
                'pct_acumulado' => round($cum, 2),
            ];
        }

        return [
            'filas' => $filas,
            'total_valor' => $total,
            'periodo' => ['desde' => $d1, 'hasta' => $d2],
            '_sql_traces' => [
                ['sql' => $sql, 'params' => [':d1' => $d1, ':d2' => $d2]],
                [
                    'sql' => 'SELECT COALESCE(SUM(Valor),0) FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2',
                    'params' => [':d1' => $d1, ':d2' => $d2],
                ],
            ],
        ];
    }

    /**
     * Top clientes por cantidad de líneas con TDoc = 07 (nota de crédito), desempate por SUM(Valor) ascendente.
     *
     * @return array{filas: list<array<string, mixed>>, total_lineas_nc: int, total_valor_nc: float, periodo: array{desde: string, hasta: string}}
     */
    public static function topClientesNotaCredito(PDO $pdo, string $d1, string $d2, int $top): array
    {
        $top = max(1, min(100, $top));
        $tdoc = "COALESCE(NULLIF(TRIM(CodigoDocumento),''),'') = '07'";
        $sql = "SELECT CodigoCliente AS cod_cliente,
                MAX(COALESCE(NULLIF(TRIM(NombreCliente),''),'(sin nombre)')) AS nombre_cliente,
                COUNT(*) AS lineas,
                COALESCE(SUM(Valor),0) AS suma_valor
            FROM ventasgeneral2
            WHERE FechaContable BETWEEN :d1 AND :d2 AND {$tdoc}
            GROUP BY CodigoCliente
            ORDER BY lineas DESC, suma_valor ASC
            LIMIT {$top}";
        $st = $pdo->prepare($sql);
        $st->execute([':d1' => $d1, ':d2' => $d2]);
        $raw = $st->fetchAll(PDO::FETCH_ASSOC);
        $sqlTot = "SELECT COUNT(*) AS n, COALESCE(SUM(Valor),0) AS v FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2 AND {$tdoc}";
        $stT = $pdo->prepare($sqlTot);
        $stT->execute([':d1' => $d1, ':d2' => $d2]);
        $totRow = $stT->fetch(PDO::FETCH_ASSOC) ?: [];
        $totalLineas = (int) ($totRow['n'] ?? 0);
        $totalValorNc = (float) ($totRow['v'] ?? 0);
        $cum = 0.0;
        $filas = [];
        foreach ($raw as $row) {
            $ln = (int) ($row['lineas'] ?? 0);
            $pct = $totalLineas > 0 ? ($ln / $totalLineas) * 100.0 : 0.0;
            $cum += $pct;
            $filas[] = [
                'cod_cliente' => (string) ($row['cod_cliente'] ?? ''),
                'nombre_cliente' => (string) ($row['nombre_cliente'] ?? ''),
                'lineas' => $ln,
                'suma_valor' => (float) ($row['suma_valor'] ?? 0),
                'pct_lineas_del_total' => round($pct, 2),
                'pct_lineas_acumulado' => round($cum, 2),
            ];
        }

        return [
            'filas' => $filas,
            'total_lineas_nc' => $totalLineas,
            'total_valor_nc' => $totalValorNc,
            'periodo' => ['desde' => $d1, 'hasta' => $d2],
            '_sql_traces' => [
                ['sql' => $sql, 'params' => [':d1' => $d1, ':d2' => $d2]],
                ['sql' => $sqlTot, 'params' => [':d1' => $d1, ':d2' => $d2]],
            ],
        ];
    }

    /**
     * @return array{filas: list<array<string, mixed>>, periodo: array{desde: string, hasta: string}}
     */
    public static function mixPorTdoc(PDO $pdo, string $d1, string $d2): array
    {
        $sql = 'SELECT COALESCE(NULLIF(TRIM(CodigoDocumento),\'\'),\'(sin TDoc)\') AS tdoc, COUNT(*) AS lineas, COALESCE(SUM(Valor),0) AS suma_valor
            FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2
            GROUP BY COALESCE(NULLIF(TRIM(CodigoDocumento),\'\'),\'(sin TDoc)\')
            ORDER BY suma_valor DESC';
        $st = $pdo->prepare($sql);
        $st->execute([':d1' => $d1, ':d2' => $d2]);
        $rows = $st->fetchAll(PDO::FETCH_ASSOC);
        $total = 0.0;
        foreach ($rows as $r) {
            $total += (float) ($r['suma_valor'] ?? 0);
        }
        $filas = [];
        foreach ($rows as $r) {
            $sv = (float) ($r['suma_valor'] ?? 0);
            $filas[] = [
                'tdoc' => (string) ($r['tdoc'] ?? ''),
                'lineas' => (int) ($r['lineas'] ?? 0),
                'suma_valor' => $sv,
                'pct_del_total' => $total > 0 ? round(($sv / $total) * 100, 2) : 0.0,
            ];
        }

        return [
            'filas' => $filas,
            'total_valor' => $total,
            'periodo' => ['desde' => $d1, 'hasta' => $d2],
            '_sql_traces' => [
                ['sql' => $sql, 'params' => [':d1' => $d1, ':d2' => $d2]],
            ],
        ];
    }

    /**
     * @return array{filas: list<array<string, mixed>>, periodo: array{desde: string, hasta: string}}
     */
    public static function topRutaComercial(PDO $pdo, string $d1, string $d2, int $top): array
    {
        $top = max(1, min(100, $top));
        $expr = self::colEtiqueta('ruta');
        $sql = "SELECT {$expr} AS ruta, COUNT(*) AS lineas, COALESCE(SUM(Valor),0) AS suma_valor
            FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2
            GROUP BY {$expr}
            ORDER BY suma_valor DESC
            LIMIT {$top}";
        $st = $pdo->prepare($sql);
        $st->execute([':d1' => $d1, ':d2' => $d2]);

        return [
            'filas' => $st->fetchAll(PDO::FETCH_ASSOC),
            'periodo' => ['desde' => $d1, 'hasta' => $d2],
            '_sql_traces' => [
                ['sql' => $sql, 'params' => [':d1' => $d1, ':d2' => $d2]],
            ],
        ];
    }

    /**
     * @return array{filas: list<array<string, mixed>>, periodo: array{desde: string, hasta: string}}
     */
    public static function topCorporativo(PDO $pdo, string $d1, string $d2, int $top): array
    {
        $top = max(1, min(100, $top));
        $expr = self::colEtiqueta('corporativo');
        $sql = "SELECT {$expr} AS nombre_coorporativo,
                MAX(COALESCE(NULLIF(TRIM(CodigoCoorporativo),''),'')) AS cod_coorporativo,
                COUNT(*) AS lineas, COALESCE(SUM(Valor),0) AS suma_valor
            FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2
            GROUP BY {$expr}
            ORDER BY suma_valor DESC
            LIMIT {$top}";
        $st = $pdo->prepare($sql);
        $st->execute([':d1' => $d1, ':d2' => $d2]);

        return [
            'filas' => $st->fetchAll(PDO::FETCH_ASSOC),
            'periodo' => ['desde' => $d1, 'hasta' => $d2],
            '_sql_traces' => [
                ['sql' => $sql, 'params' => [':d1' => $d1, ':d2' => $d2]],
            ],
        ];
    }

    /**
     * @return array{filas: list<array<string, mixed>>, periodo: array{desde: string, hasta: string}}
     */
    public static function serieMensualValor(PDO $pdo, string $d1, string $d2): array
    {
        $sql = 'SELECT DATE_FORMAT(FechaContable, \'%Y-%m\') AS mes, COALESCE(SUM(Valor),0) AS suma_valor, COUNT(*) AS lineas
            FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2
            GROUP BY DATE_FORMAT(FechaContable, \'%Y-%m\')
            ORDER BY mes';
        $st = $pdo->prepare($sql);
        $st->execute([':d1' => $d1, ':d2' => $d2]);

        return [
            'filas' => $st->fetchAll(PDO::FETCH_ASSOC),
            'periodo' => ['desde' => $d1, 'hasta' => $d2],
            '_sql_traces' => [
                ['sql' => $sql, 'params' => [':d1' => $d1, ':d2' => $d2]],
            ],
        ];
    }
}
