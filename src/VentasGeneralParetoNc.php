<?php

declare(strict_types=1);

/**
 * Pareto de notas de crédito (CodigoDocumento = '07') por DescripcionZonaPrecio en ventasgeneral2.
 */
final class VentasGeneralParetoNc
{
    /**
     * @return array{filas: list<array<string, mixed>>, total_impacto_nc: float, periodo: array{desde: string, hasta: string}}
     */
    public static function datos(PDO $pdo, string $d1, string $d2, int $maxZonas = 100): array
    {
        $maxZonas = max(1, min(200, $maxZonas));
        $sql = 'SELECT COALESCE(NULLIF(TRIM(DescripcionZonaPrecio),\'\'),\'(sin zona)\') AS zona,
                COUNT(*) AS lineas_nc,
                COALESCE(SUM(ABS(Valor)),0) AS impacto_abs_valor
            FROM ventasgeneral2
            WHERE FechaContable BETWEEN :d1 AND :d2 AND CodigoDocumento = \'07\'
            GROUP BY COALESCE(NULLIF(TRIM(DescripcionZonaPrecio),\'\'),\'(sin zona)\')
            ORDER BY impacto_abs_valor DESC
            LIMIT ' . $maxZonas;
        $st = $pdo->prepare($sql);
        $st->execute([':d1' => $d1, ':d2' => $d2]);
        $raw = $st->fetchAll(PDO::FETCH_ASSOC);
        $total = 0.0;
        foreach ($raw as $row) {
            $total += (float) ($row['impacto_abs_valor'] ?? 0);
        }
        $cum = 0.0;
        $filas = [];
        foreach ($raw as $row) {
            $imp = (float) ($row['impacto_abs_valor'] ?? 0);
            $pctFila = $total > 0 ? ($imp / $total) * 100.0 : 0.0;
            $cum += $pctFila;
            $filas[] = [
                'zona' => (string) ($row['zona'] ?? ''),
                'lineas_nc' => (int) ($row['lineas_nc'] ?? 0),
                'impacto_abs_valor' => $imp,
                'pct_del_total' => round($pctFila, 2),
                'pct_acumulado' => round($cum, 2),
            ];
        }
        $hasta80 = 0;
        foreach ($filas as $i => $f) {
            $hasta80 = $i + 1;
            if ((float) $f['pct_acumulado'] >= 80.0) {
                break;
            }
        }

        return [
            'filas' => $filas,
            'total_impacto_nc' => $total,
            'zonas_contadas_hasta_80pct_aprox' => $hasta80,
            'periodo' => ['desde' => $d1, 'hasta' => $d2],
            '_sql_traces' => [
                ['sql' => $sql, 'params' => [':d1' => $d1, ':d2' => $d2]],
            ],
        ];
    }
}
