<?php

declare(strict_types=1);

$appRoot = dirname(__DIR__, 2);
require_once $appRoot . '/config/bootstrap.php';

$limit = max(1, min(100, (int) ($_GET['limit'] ?? 50)));
$offset = max(0, (int) ($_GET['offset'] ?? 0));
$desde = trim((string) ($_GET['desde'] ?? ''));
$hasta = trim((string) ($_GET['hasta'] ?? ''));
$qnom = trim((string) ($_GET['nombre'] ?? ''));
$qdoc = trim((string) ($_GET['numero_doc'] ?? ''));

function vgt_parse_date(string $s): ?string
{
    if ($s === '') {
        return null;
    }
    $d = DateTimeImmutable::createFromFormat('Y-m-d', $s);
    return ($d && $d->format('Y-m-d') === $s) ? $s : null;
}

$error = null;
$rows = [];
$total = 0;

try {
    $pdo = ventas_pdo();
    $where = ' WHERE 1=1';
    $params = [];

    $d1 = vgt_parse_date($desde);
    $d2 = vgt_parse_date($hasta);
    if ($d1 !== null) {
        $where .= ' AND FechaContable >= :d1';
        $params[':d1'] = $d1;
    }
    if ($d2 !== null) {
        $where .= ' AND FechaContable <= :d2';
        $params[':d2'] = $d2;
    }
    if ($qnom !== '') {
        $where .= ' AND NombreCliente LIKE :nom';
        $params[':nom'] = '%' . $qnom . '%';
    }
    if ($qdoc !== '') {
        $where .= ' AND NumeroFactura LIKE :ndoc';
        $params[':ndoc'] = '%' . $qdoc . '%';
    }

    $stc = $pdo->prepare('SELECT COUNT(*) FROM ventasgeneral2' . $where);
    $stc->execute($params);
    $total = (int) $stc->fetchColumn();

    $sql = 'SELECT id, FechaContable, CodigoCliente, NombreCliente, NumeroFactura, CodigoItem, GlosaDetalle, Cantidad, Valor, ZonaComercial
        FROM ventasgeneral2' . $where . ' ORDER BY FechaContable DESC, id DESC LIMIT ' . (int) $limit . ' OFFSET ' . (int) $offset;
    $st = $pdo->prepare($sql);
    $st->execute($params);
    $rows = $st->fetchAll(PDO::FETCH_ASSOC);
} catch (Throwable $e) {
    $error = $e->getMessage();
}
?>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Ventas general · tabla</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="wrap">
        <header class="top">
            <h1>ventasgeneral</h1>
            <nav><a href="ventasgeneral_table.php">Ventas general</a></nav>
        </header>

        <form method="get" class="card">
            <label>Desde <input type="date" name="desde" value="<?= htmlspecialchars($desde, ENT_QUOTES, 'UTF-8') ?>"></label>
            <label>Hasta <input type="date" name="hasta" value="<?= htmlspecialchars($hasta, ENT_QUOTES, 'UTF-8') ?>"></label>
            <label>Nombre cliente <input type="text" name="nombre" value="<?= htmlspecialchars($qnom, ENT_QUOTES, 'UTF-8') ?>" placeholder="Ingrese su nombre"></label>
            <label>Nº doc <input type="text" name="numero_doc" value="<?= htmlspecialchars($qdoc, ENT_QUOTES, 'UTF-8') ?>"></label>
            <label>Filas <select name="limit">
                <?php foreach ([25, 50, 100] as $n): ?>
                    <option value="<?= $n ?>" <?= $limit === $n ? 'selected' : '' ?>><?= $n ?></option>
                <?php endforeach; ?>
            </select></label>
            <input type="hidden" name="offset" value="0">
            <button type="submit">Filtrar</button>
        </form>

        <?php if ($error): ?>
            <p class="error"><?= htmlspecialchars($error, ENT_QUOTES, 'UTF-8') ?></p>
        <?php else: ?>
            <p class="muted">Total filas que coinciden: <?= (int) $total ?> · mostrando <?= count($rows) ?></p>
            <div class="card" style="overflow-x:auto;">
                <table class="data">
                    <thead>
                        <tr>
                            <th>id</th>
                            <th>Fecha</th>
                            <th>Cliente</th>
                            <th>Doc</th>
                            <th>Ítem</th>
                            <th>Glosa</th>
                            <th>Cant</th>
                            <th>Valor</th>
                            <th>Zona</th>
                        </tr>
                    </thead>
                    <tbody>
                        <?php foreach ($rows as $r): ?>
                            <tr>
                                <td><?= htmlspecialchars((string) ($r['id'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                                <td><?= htmlspecialchars((string) ($r['FechaContable'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                                <td><?= htmlspecialchars((string) ($r['NombreCliente'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                                <td><?= htmlspecialchars((string) ($r['NumeroFactura'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                                <td><?= htmlspecialchars((string) ($r['CodigoItem'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                                <td><?= htmlspecialchars((string) ($r['GlosaDetalle'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                                <td><?= htmlspecialchars((string) ($r['Cantidad'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                                <td><?= htmlspecialchars((string) ($r['Valor'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                                <td><?= htmlspecialchars((string) ($r['ZonaComercial'] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                            </tr>
                        <?php endforeach; ?>
                    </tbody>
                </table>
            </div>
            <div class="pager">
                <?php
                $prev = max(0, $offset - $limit);
                $next = $offset + $limit < $total ? $offset + $limit : null;
                $qs = $_GET;
                ?>
                <?php if ($offset > 0): ?>
                    <?php $qs['offset'] = $prev; ?>
                    <a class="btn" href="?<?= htmlspecialchars(http_build_query($qs), ENT_QUOTES, 'UTF-8') ?>">Anterior</a>
                <?php endif; ?>
                <?php if ($next !== null): ?>
                    <?php $qs['offset'] = $next; ?>
                    <a class="btn" href="?<?= htmlspecialchars(http_build_query($qs), ENT_QUOTES, 'UTF-8') ?>">Siguiente</a>
                <?php endif; ?>
            </div>
        <?php endif; ?>
    </div>
<?php include __DIR__ . '/chat_floating.inc.php'; ?>
</body>
</html>
