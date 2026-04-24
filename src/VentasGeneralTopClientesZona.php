<?php

declare(strict_types=1);

/**
 * Top clientes por SUM(Valor) filtrando prefijo en DescriZonaPrecio (ventasgeneral).
 */
final class VentasGeneralTopClientesZona
{
    /**
     * @return array{
     *   filas: list<array<string, mixed>>,
     *   total_valor_zona: float,
     *   clientes_contados_hasta_80pct_aprox: int,
     *   periodo: array{desde: string, hasta: string},
     *   prefijo_descri_zona_precio: string
     * }
     */
    public static function datos(PDO $pdo, string $d1, string $d2, string $prefijo, int $topN = 10): array
    {
        $topN = max(1, min(100, $topN));
        $pref = strtoupper(trim($prefijo));
        if ($pref === '') {
            throw new InvalidArgumentException('prefijo_descri_zona_precio no puede estar vacío');
        }
        $like = $pref . '%';

        $sqlTotal = 'SELECT COALESCE(SUM(Valor), 0) AS total_valor
            FROM ventasgeneral
            WHERE FechaCont BETWEEN :d1 AND :d2
            AND UPPER(TRIM(COALESCE(DescriZonaPrecio, \'\'))) LIKE :pref';
        $stT = $pdo->prepare($sqlTotal);
        $stT->execute([':d1' => $d1, ':d2' => $d2, ':pref' => $like]);
        $totalRow = $stT->fetch(PDO::FETCH_ASSOC) ?: [];
        $totalZona = (float) ($totalRow['total_valor'] ?? 0);

        $sql = 'SELECT CodCliente,
                MAX(COALESCE(NULLIF(TRIM(NombreCliente), \'\'), \'(sin nombre)\')) AS nombre_cliente,
                COALESCE(SUM(Valor), 0) AS suma_valor,
                COUNT(*) AS lineas_venta
            FROM ventasgeneral
            WHERE FechaCont BETWEEN :d1 AND :d2
            AND UPPER(TRIM(COALESCE(DescriZonaPrecio, \'\'))) LIKE :pref
            GROUP BY CodCliente
            ORDER BY suma_valor DESC
            LIMIT ' . $topN;

        $st = $pdo->prepare($sql);
        $st->execute([':d1' => $d1, ':d2' => $d2, ':pref' => $like]);
        $raw = $st->fetchAll(PDO::FETCH_ASSOC);

        $cum = 0.0;
        $filas = [];
        foreach ($raw as $row) {
            $sv = (float) ($row['suma_valor'] ?? 0);
            $pctFila = $totalZona != 0.0 ? ($sv / $totalZona) * 100.0 : 0.0;
            $cum += $pctFila;
            $filas[] = [
                'cod_cliente' => (string) ($row['CodCliente'] ?? ''),
                'nombre_cliente' => (string) ($row['nombre_cliente'] ?? ''),
                'suma_valor' => $sv,
                'lineas_venta' => (int) ($row['lineas_venta'] ?? 0),
                'pct_del_total_zona' => round($pctFila, 2),
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
            'total_valor_zona' => $totalZona,
            'clientes_contados_hasta_80pct_aprox' => $hasta80,
            'periodo' => ['desde' => $d1, 'hasta' => $d2],
            'prefijo_descri_zona_precio' => $pref,
            '_sql_traces' => [
                ['sql' => $sqlTotal, 'params' => [':d1' => $d1, ':d2' => $d2, ':pref' => $like]],
                ['sql' => $sql, 'params' => [':d1' => $d1, ':d2' => $d2, ':pref' => $like]],
            ],
        ];
    }
}
