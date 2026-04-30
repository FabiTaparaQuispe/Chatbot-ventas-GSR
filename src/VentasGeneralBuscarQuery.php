<?php

declare(strict_types=1);

/**
 * Búsqueda parametrizada en ventasgeneral (misma lógica que ToolExecutor::ventasgeneralBuscar).
 */
final class VentasGeneralBuscarQuery
{
    private const MAX_LIMIT = 100;
    private const DEFAULT_LIMIT = 50;

    private static function parseDateFromMixed(mixed $v): ?string
    {
        if ($v === null || $v === '') {
            return null;
        }
        $s = trim((string) $v);
        $d = DateTimeImmutable::createFromFormat('Y-m-d', $s);
        if ($d === false || $d->format('Y-m-d') !== $s) {
            throw new InvalidArgumentException('Fecha inválida (YYYY-MM-DD)');
        }
        return $s;
    }

    private static function clampLimit(?int $n): int
    {
        if ($n === null) {
            return self::DEFAULT_LIMIT;
        }
        return max(1, min(self::MAX_LIMIT, $n));
    }

    /**
     * @param array<string, mixed> $args mismas claves que la herramienta ventasgeneral_buscar
     * @return array{filas: list<array<string, mixed>>, limit: int, offset: int}
     */
    public static function search(PDO $pdo, array $args): array
    {
        $limit = self::clampLimit(isset($args['limit']) && is_numeric($args['limit']) ? (int) $args['limit'] : null);
        $offset = max(0, isset($args['offset']) && is_numeric($args['offset']) ? (int) $args['offset'] : 0);

        $sql = 'SELECT id, FechaContable, CodigoCoorporativo, NombreCoorporativo, CodigoCliente, NombreCliente, CodigoDocumento, TipoDocumento, SerieDocumento, NumeroDocumento, NumeroFactura, CodigoItem, GlosaDetalle, Cantidad, Peso, Valor, ZonaComercial, DescripcionZonaPrecio, RutaComercial, Provincia, LineaComercial
            FROM ventasgeneral2 WHERE 1=1';
        $params = [];

        $fd = self::parseDateFromMixed($args['fecha_desde'] ?? null);
        $fh = self::parseDateFromMixed($args['fecha_hasta'] ?? null);
        if ($fd !== null && $fh !== null) {
            if ($fd > $fh) {
                throw new InvalidArgumentException('fecha_desde no puede ser mayor que fecha_hasta');
            }
            $sql .= ' AND FechaContable BETWEEN :fd AND :fh';
            $params[':fd'] = $fd;
            $params[':fh'] = $fh;
        } elseif ($fd !== null) {
            $sql .= ' AND FechaContable >= :fd';
            $params[':fd'] = $fd;
        } elseif ($fh !== null) {
            $sql .= ' AND FechaContable <= :fh';
            $params[':fh'] = $fh;
        }

        $nom = isset($args['nombre_cliente']) ? trim((string) $args['nombre_cliente']) : '';
        if ($nom !== '') {
            $sql .= ' AND NombreCliente LIKE :nom';
            $params[':nom'] = '%' . $nom . '%';
        }

        $ndoc = isset($args['numero_doc']) ? trim((string) $args['numero_doc']) : '';
        if ($ndoc !== '') {
            $sql .= ' AND NumeroFactura LIKE :ndoc';
            $params[':ndoc'] = '%' . $ndoc . '%';
        }

        $item = isset($args['cod_item']) ? trim((string) $args['cod_item']) : '';
        if ($item !== '') {
            $sql .= ' AND CodigoItem = :item';
            $params[':item'] = $item;
        }

        $tdoc = isset($args['tdoc']) ? trim((string) $args['tdoc']) : '';
        if ($tdoc !== '') {
            if (strlen($tdoc) > 4) {
                throw new InvalidArgumentException('tdoc demasiado largo');
            }
            $sql .= ' AND CodigoDocumento = :tdoc';
            $params[':tdoc'] = $tdoc;
        }

        $prefZ = isset($args['prefijo_descri_zona_precio']) ? strtoupper(trim((string) $args['prefijo_descri_zona_precio'])) : '';
        if ($prefZ !== '') {
            $sql .= ' AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,\'\'))) LIKE :prefzp';
            $params[':prefzp'] = $prefZ . '%';
        }

        $prov = isset($args['provincia']) ? trim((string) $args['provincia']) : '';
        if ($prov !== '') {
            $sql .= ' AND Provincia LIKE :prov';
            $params[':prov'] = '%' . $prov . '%';
        }

        $tdoctipo = isset($args['tipo_documento']) ? trim((string) $args['tipo_documento']) : '';
        if ($tdoctipo !== '') {
            $sql .= ' AND TipoDocumento LIKE :tdoctipo';
            $params[':tdoctipo'] = '%' . $tdoctipo . '%';
        }

        $sql .= ' ORDER BY FechaContable DESC, id DESC LIMIT ' . (int) $limit . ' OFFSET ' . (int) $offset;

        $st = $pdo->prepare($sql);
        $st->execute($params);
        $rows = $st->fetchAll(PDO::FETCH_ASSOC);

        return [
            'filas' => $rows,
            'limit' => $limit,
            'offset' => $offset,
            '_sql_traces' => [
                ['sql' => $sql, 'params' => $params],
            ],
        ];
    }

    /**
     * @param array<string, mixed> $args
     */
    public static function buildTablaUrl(array $args): string
    {
        $q = [];
        foreach (['fecha_desde', 'fecha_hasta', 'nombre_cliente', 'numero_doc', 'cod_item', 'tdoc', 'prefijo_descri_zona_precio', 'provincia', 'tipo_documento'] as $k) {
            if (!isset($args[$k]) || $args[$k] === '' || $args[$k] === null) {
                continue;
            }
            $q[$k] = (string) $args[$k];
        }
        if (isset($args['limit']) && is_numeric($args['limit'])) {
            $q['limit'] = (string) (int) $args['limit'];
        }
        if (isset($args['offset']) && is_numeric($args['offset'])) {
            $q['offset'] = (string) (int) $args['offset'];
        }

        return 'ventasgeneral_buscar_tabla.php?' . http_build_query($q, '', '&', PHP_QUERY_RFC3986);
    }
}
