<?php

declare(strict_types=1);

$appRoot = dirname(__DIR__, 2);
require_once $appRoot . '/config/bootstrap.php';

$defaultHasta = (new DateTimeImmutable('today'))->format('Y-m-d');
$defaultDesde = (new DateTimeImmutable('today'))->modify('-30 days')->format('Y-m-d');

$desde = $_GET['desde'] ?? $defaultDesde;
$hasta = $_GET['hasta'] ?? $defaultHasta;

function vg_parse_date(string $s): ?string
{
    $d = DateTimeImmutable::createFromFormat('Y-m-d', $s);
    return ($d && $d->format('Y-m-d') === $s) ? $s : null;
}

$d1 = vg_parse_date($desde);
$d2 = vg_parse_date($hasta);
$error = null;
$vg = null;
$saleFec = null;
$saleTra = null;

if ($d1 === null || $d2 === null) {
    $error = 'Use fechas YYYY-MM-DD válidas.';
} elseif ($d1 > $d2) {
    $error = 'La fecha inicial no puede ser mayor que la final.';
} else {
    try {
        $pdo = ventas_pdo();
        $st = $pdo->prepare(
            'SELECT COUNT(*) AS filas, COALESCE(SUM(Valor),0) AS suma_valor, COALESCE(SUM(Cantidad),0) AS suma_cant, COALESCE(SUM(Peso),0) AS suma_peso
            FROM ventasgeneral WHERE FechaCont BETWEEN :a AND :b'
        );
        $st->execute([':a' => $d1, ':b' => $d2]);
        $vg = $st->fetch(PDO::FETCH_ASSOC);

        $st2 = $pdo->prepare(
            'SELECT COUNT(*) AS filas, COALESCE(SUM(timport),0) AS suma_importe, COALESCE(SUM(tcantid),0) AS suma_cant
            FROM sale WHERE tfecfac BETWEEN :a AND :b'
        );
        $st2->execute([':a' => $d1, ':b' => $d2]);
        $saleFec = $st2->fetch(PDO::FETCH_ASSOC);

        $st3 = $pdo->prepare(
            'SELECT COUNT(*) AS filas, COALESCE(SUM(timport),0) AS suma_importe, COALESCE(SUM(tcantid),0) AS suma_cant
            FROM sale WHERE tfectra BETWEEN :a AND :b'
        );
        $st3->execute([':a' => $d1, ':b' => $d2]);
        $saleTra = $st3->fetch(PDO::FETCH_ASSOC);
    } catch (Throwable $e) {
        $error = $e->getMessage();
    }
}
?>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Resumen · ventas</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="wrap">
        <header class="top">
            <h1>Resumen por fechas</h1>
            <nav><a href="ventasgeneral_table.php">Ventas general</a></nav>
        </header>

        <form method="get" class="card">
            <label>Desde <input type="date" name="desde" value="<?= htmlspecialchars($desde, ENT_QUOTES, 'UTF-8') ?>"></label>
            <label>Hasta <input type="date" name="hasta" value="<?= htmlspecialchars($hasta, ENT_QUOTES, 'UTF-8') ?>"></label>
            <button type="submit">Actualizar</button>
        </form>

        <?php if ($error): ?>
            <p class="error"><?= htmlspecialchars($error, ENT_QUOTES, 'UTF-8') ?></p>
        <?php else: ?>
            <div class="grid">
                <section class="card">
                    <h2>ventasgeneral</h2>
                    <p>FechaCont entre <?= htmlspecialchars($d1, ENT_QUOTES, 'UTF-8') ?> y <?= htmlspecialchars($d2, ENT_QUOTES, 'UTF-8') ?></p>
                    <ul class="stats">
                        <li>Filas: <strong><?= htmlspecialchars((string) ($vg['filas'] ?? ''), ENT_QUOTES, 'UTF-8') ?></strong></li>
                        <li>Suma Valor: <strong><?= htmlspecialchars(number_format((float) ($vg['suma_valor'] ?? 0), 2, '.', ','), ENT_QUOTES, 'UTF-8') ?></strong></li>
                        <li>Suma Cantidad: <strong><?= htmlspecialchars(number_format((float) ($vg['suma_cant'] ?? 0), 4, '.', ','), ENT_QUOTES, 'UTF-8') ?></strong></li>
                        <li>Suma Peso: <strong><?= htmlspecialchars(number_format((float) ($vg['suma_peso'] ?? 0), 4, '.', ','), ENT_QUOTES, 'UTF-8') ?></strong></li>
                    </ul>
                </section>
                <section class="card">
                    <h2>sale</h2>
                    <ul class="stats">
                        <li>Filas: <strong><?= htmlspecialchars((string) ($saleFec['filas'] ?? ''), ENT_QUOTES, 'UTF-8') ?></strong></li>
                        <li>Suma timport: <strong><?= htmlspecialchars(number_format((float) ($saleFec['suma_importe'] ?? 0), 2, '.', ','), ENT_QUOTES, 'UTF-8') ?></strong></li>
                        <li>Suma tcantid: <strong><?= htmlspecialchars(number_format((float) ($saleFec['suma_cant'] ?? 0), 4, '.', ','), ENT_QUOTES, 'UTF-8') ?></strong></li>
                    </ul>
                </section>
                <section class="card">
                    <h2>sale (tfectra)</h2>
                    <ul class="stats">
                        <li>Filas: <strong><?= htmlspecialchars((string) ($saleTra['filas'] ?? ''), ENT_QUOTES, 'UTF-8') ?></strong></li>
                        <li>Suma timport: <strong><?= htmlspecialchars(number_format((float) ($saleTra['suma_importe'] ?? 0), 2, '.', ','), ENT_QUOTES, 'UTF-8') ?></strong></li>
                        <li>Suma tcantid: <strong><?= htmlspecialchars(number_format((float) ($saleTra['suma_cant'] ?? 0), 4, '.', ','), ENT_QUOTES, 'UTF-8') ?></strong></li>
                    </ul>
                </section>
            </div>
        <?php endif; ?>
    </div>
</body>
</html>
