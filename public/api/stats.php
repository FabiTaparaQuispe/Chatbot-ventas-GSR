<?php

declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');

$appRoot = dirname(__DIR__, 2);
require_once $appRoot . '/config/bootstrap.php';

$type = $_GET['type'] ?? '';
$desde = $_GET['desde'] ?? '';
$hasta = $_GET['hasta'] ?? '';

function parse_ymd(string $s): ?string
{
    $d = DateTimeImmutable::createFromFormat('Y-m-d', $s);
    if ($d === false || $d->format('Y-m-d') !== $s) {
        return null;
    }
    return $s;
}

function assert_range(string $d1, string $d2): void
{
    if ($d1 > $d2) {
        throw new InvalidArgumentException('desde > hasta');
    }
    $a = new DateTimeImmutable($d1);
    $b = new DateTimeImmutable($d2);
    if ($a->diff($b)->days > 366) {
        throw new InvalidArgumentException('Rango máximo 366 días');
    }
}

try {
    $d1 = parse_ymd($desde);
    $d2 = parse_ymd($hasta);
    if ($d1 === null || $d2 === null) {
        throw new InvalidArgumentException('Parámetros desde y hasta requeridos (YYYY-MM-DD)');
    }
    assert_range($d1, $d2);

    $pdo = ventas_pdo();

    switch ($type) {
        case 'vg_daily':
            $st = $pdo->prepare(
                'SELECT FechaContable AS dia, COUNT(*) AS filas, COALESCE(SUM(Valor),0) AS suma_valor
                FROM ventasgeneral2 WHERE FechaContable BETWEEN :a AND :b
                GROUP BY FechaContable ORDER BY FechaContable'
            );
            $st->execute([':a' => $d1, ':b' => $d2]);
            echo json_encode(['ok' => true, 'series' => $st->fetchAll(PDO::FETCH_ASSOC)], JSON_UNESCAPED_UNICODE);
            break;

        case 'vg_zonas':
            $limit = (int) ($_GET['limit'] ?? 12);
            $limit = max(1, min(25, $limit));
            $st = $pdo->prepare(
                "SELECT COALESCE(NULLIF(TRIM(ZonaComercial),''),'(sin zona)') AS zona,
                    COUNT(*) AS filas, COALESCE(SUM(Valor),0) AS suma_valor
                FROM ventasgeneral2 WHERE FechaContable BETWEEN :a AND :b
                GROUP BY COALESCE(NULLIF(TRIM(ZonaComercial),''),'(sin zona)')
                ORDER BY suma_valor DESC LIMIT $limit"
            );
            $st->execute([':a' => $d1, ':b' => $d2]);
            echo json_encode(['ok' => true, 'series' => $st->fetchAll(PDO::FETCH_ASSOC)], JSON_UNESCAPED_UNICODE);
            break;

        case 'sale_daily':
            $campo = $_GET['campo'] ?? 'tfecfac';
            if ($campo !== 'tfecfac' && $campo !== 'tfectra') {
                throw new InvalidArgumentException('campo debe ser tfecfac o tfectra');
            }
            $sql = "SELECT `$campo` AS dia, COUNT(*) AS filas, COALESCE(SUM(timport),0) AS suma_importe
                FROM sale WHERE `$campo` BETWEEN :a AND :b
                GROUP BY `$campo` ORDER BY dia";
            $st = $pdo->prepare($sql);
            $st->execute([':a' => $d1, ':b' => $d2]);
            echo json_encode(['ok' => true, 'campo' => $campo, 'series' => $st->fetchAll(PDO::FETCH_ASSOC)], JSON_UNESCAPED_UNICODE);
            break;

        default:
            throw new InvalidArgumentException('type inválido (vg_daily|vg_zonas|sale_daily)');
    }
} catch (Throwable $e) {
    http_response_code(400);
    echo json_encode(['ok' => false, 'error' => $e->getMessage()], JSON_UNESCAPED_UNICODE);
}
