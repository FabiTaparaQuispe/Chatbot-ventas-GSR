<?php

declare(strict_types=1);

$appRoot = dirname(__DIR__, 2);
require_once $appRoot . '/config/bootstrap.php';

$limit = max(1, min(100, (int) ($_GET['limit'] ?? 50)));
$offset = max(0, (int) ($_GET['offset'] ?? 0));
$desde = trim((string) ($_GET['desde'] ?? ''));
$hasta = trim((string) ($_GET['hasta'] ?? ''));
$campoFecha = ($_GET['campo_fecha'] ?? 'tfectra') === 'tfecfac' ? 'tfecfac' : 'tfectra';
$tprocli = trim((string) ($_GET['tprocli'] ?? ''));
$tcodigo = trim((string) ($_GET['tcodigo'] ?? ''));

function st_parse_date(string $s): ?string
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

    $d1 = st_parse_date($desde);
    $d2 = st_parse_date($hasta);
    if ($d1 !== null) {
        $where .= " AND `$campoFecha` >= :d1";
        $params[':d1'] = $d1;
    }
    if ($d2 !== null) {
        $where .= " AND `$campoFecha` <= :d2";
        $params[':d2'] = $d2;
    }
    if ($tprocli !== '') {
        $where .= ' AND tprocli = :tprocli';
        $params[':tprocli'] = $tprocli;
    }
    if ($tcodigo !== '') {
        $where .= ' AND tcodigo = :tcodigo';
        $params[':tcodigo'] = $tcodigo;
    }

    $stc = $pdo->prepare('SELECT COUNT(*) FROM sale' . $where);
    $stc->execute($params);
    $total = (int) $stc->fetchColumn();

    $sql = "SELECT tfectra, tfecfac, tdoc, tserie, tnumfac, tprocli, tcodigo, tglosa, tcantid, timport, placa, talm
        FROM sale" . $where . " ORDER BY tfectra DESC, treg DESC LIMIT " . (int) $limit . ' OFFSET ' . (int) $offset;
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
    <title>Sale · tabla</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="wrap">
        <header class="top">
            <h1>sale</h1>
            <nav><a href="ventasgeneral_table.php">Ventas general</a></nav>
        </header>

        <form method="get" class="card">
            <label>Fecha por
                <select name="campo_fecha">
                    <option value="tfectra" <?= $campoFecha === 'tfectra' ? 'selected' : '' ?>>tfectra</option>
                    <option value="tfecfac" <?= $campoFecha === 'tfecfac' ? 'selected' : '' ?>>tfecfac</option>
                </select>
            </label>
            <label>Desde <input type="date" name="desde" value="<?= htmlspecialchars($desde, ENT_QUOTES, 'UTF-8') ?>"></label>
            <label>Hasta <input type="date" name="hasta" value="<?= htmlspecialchars($hasta, ENT_QUOTES, 'UTF-8') ?>"></label>
            <label>tprocli <input type="text" name="tprocli" value="<?= htmlspecialchars($tprocli, ENT_QUOTES, 'UTF-8') ?>"></label>
            <label>tcodigo <input type="text" name="tcodigo" value="<?= htmlspecialchars($tcodigo, ENT_QUOTES, 'UTF-8') ?>"></label>
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
            <p class="muted">Total filas: <?= (int) $total ?> · mostrando <?= count($rows) ?></p>
            <div class="card" style="overflow-x:auto;">
                <table class="data">
                    <thead>
                        <tr>
                            <th>tfectra</th>
                            <th>tfecfac</th>
                            <th>tdoc</th>
                            <th>tserie</th>
                            <th>tnumfac</th>
                            <th>tprocli</th>
                            <th>tcodigo</th>
                            <th>tglosa</th>
                            <th>tcantid</th>
                            <th>timport</th>
                            <th>placa</th>
                            <th>talm</th>
                        </tr>
                    </thead>
                    <tbody>
                        <?php foreach ($rows as $r): ?>
                            <tr>
                                <?php foreach (['tfectra', 'tfecfac', 'tdoc', 'tserie', 'tnumfac', 'tprocli', 'tcodigo', 'tglosa', 'tcantid', 'timport', 'placa', 'talm'] as $col): ?>
                                    <td><?= htmlspecialchars((string) ($r[$col] ?? ''), ENT_QUOTES, 'UTF-8') ?></td>
                                <?php endforeach; ?>
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
