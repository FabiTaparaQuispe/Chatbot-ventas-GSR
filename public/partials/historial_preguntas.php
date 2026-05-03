<?php
declare(strict_types=1);

app_require_role(['estrategico', 'administrador']);

$usuario  = trim((string) ($_SESSION['usuario'] ?? ''));
$rows     = [];
$stats    = [];
$dbError  = '';

$categorias = [
    'Clientes'         => '/cliente|comprador|quién|quien|top.*client|client.*top/ui',
    'Productos'        => '/producto|artículo|articulo|item|ítem/ui',
    'Por zona'         => '/zona|región|region|mercado|tacna|arequipa|moquegua|lajoya|aqp/ui',
    'Notas de crédito' => '/nota.*créd|nota.*cred|devoluci|devoluc|\bnc\b|anulac|crédit.*nota|cred.*nota/ui',
    'Comparativos'     => '/compar|versus|\bvs\.?\b|período.*vs|vs.*período/ui',
    'Proyecciones'     => '/proyecc|proyect|tendencia|predi[cg]/ui',
    'Ventas / resumen' => '/venta|factur|resumen|total|importe|monto|valor|facturado/ui',
];

function clasificar_pregunta(string $texto, array $cats): string
{
    foreach ($cats as $nombre => $patron) {
        if (preg_match($patron, $texto)) {
            return $nombre;
        }
    }
    return 'Otras';
}

function historial_preview(string $text, int $max = 220): string
{
    $text = trim(preg_replace('/\s+/u', ' ', $text));
    if ($text === '') return '—';
    if (function_exists('mb_strlen') && mb_strlen($text, 'UTF-8') <= $max) return $text;
    if (strlen($text) <= $max) return $text;
    return (function_exists('mb_substr') ? mb_substr($text, 0, $max, 'UTF-8') : substr($text, 0, $max)) . '…';
}

if ($usuario === '') {
    $dbError = 'Sesión sin usuario.';
} else {
    try {
        $pdo = ventas_pdo();

        // ── Todas las preguntas de todos los usuarios (vista estratégica global) ──
        $sqlAll = <<<'SQL'
SELECT
    m.id         AS msg_id,
    m.created_at AS preguntado_en,
    m.content    AS pregunta,
    t.username   AS usuario,
    t.client_thread_id AS thread_id,
    t.title      AS chat_titulo,
    (
        SELECT LEFT(m2.content, 180)
        FROM app_chat_messages m2
        WHERE m2.thread_id = m.thread_id
          AND m2.role      = 'assistant'
          AND m2.id        > m.id
        ORDER BY m2.id ASC
        LIMIT 1
    ) AS respuesta_extracto
FROM app_chat_messages m
INNER JOIN app_chat_threads t ON t.id = m.thread_id
WHERE m.role = 'user'
ORDER BY m.created_at DESC, m.id DESC
LIMIT 600
SQL;
        $st = $pdo->query($sqlAll);
        while ($r = $st->fetch(PDO::FETCH_ASSOC)) {
            $rows[] = $r;
        }

        // ── Estadísticas de frecuencia por categoría ──
        $conteos   = array_fill_keys(array_keys($categorias), 0);
        $conteos['Otras'] = 0;
        $totalPregs = 0;
        $usuariosUnicos = [];

        foreach ($rows as $r) {
            $texto = (string) ($r['pregunta'] ?? '');
            $cat   = clasificar_pregunta($texto, $categorias);
            $conteos[$cat] = ($conteos[$cat] ?? 0) + 1;
            $totalPregs++;
            $usuariosUnicos[(string)($r['usuario'] ?? '')] = true;
        }

        arsort($conteos);
        $stats = $conteos;

    } catch (Throwable $e) {
        $raw = $e->getMessage();
        $sqlState = $e instanceof PDOException ? (string)($e->errorInfo[0] ?? '') : '';
        $missingTable = $sqlState === '42S02'
            || stripos($raw, "doesn't exist") !== false
            || stripos($raw, 'Unknown table') !== false;
        $dbError = $missingTable
            ? 'Las tablas del chat aún no están creadas. Ejecutá docs/schema_auth_chat.sql en la base de datos y recargá.'
            : 'No se pudo leer el historial. Revisá DB_DSN en .env y que existan app_chat_threads y app_chat_messages.';
    }
}

$totalUsuarios = count($usuariosUnicos ?? []);
$colores = [
    'Ventas / resumen' => '#2563eb',
    'Clientes'         => '#7c3aed',
    'Productos'        => '#059669',
    'Por zona'         => '#d97706',
    'Notas de crédito' => '#dc2626',
    'Comparativos'     => '#0891b2',
    'Proyecciones'     => '#9333ea',
    'Otras'            => '#6b7280',
];
?>
<style>
.hp-wrap { max-width: 100%; }

/* ── Header ── */
.hp-head { padding: 1.25rem 1.5rem .5rem; }
.hp-head h1 { font-size: 1.35rem; font-weight: 800; margin: 0 0 .2rem; }
.hp-head p  { margin: 0; color: var(--muted, #6b7280); font-size: .875rem; }

/* ── Tarjetas resumen ── */
.hp-kpi-row { display: flex; gap: .75rem; flex-wrap: wrap; padding: 0 1.5rem 1rem; }
.hp-kpi {
    flex: 1; min-width: 130px;
    background: var(--card-bg, #f8fafc);
    border: 1px solid var(--border, #e2e8f0);
    border-radius: .75rem; padding: .85rem 1rem;
}
[data-theme="dark"] .hp-kpi { background: var(--card-bg, #1e293b); border-color: var(--border, #334155); }
.hp-kpi-val { font-size: 1.7rem; font-weight: 800; line-height: 1; }
.hp-kpi-lbl { font-size: .75rem; color: var(--muted, #6b7280); margin-top: .2rem; }

/* ── Card frecuencias ── */
.hp-freq-card {
    margin: 0 1.5rem 1.25rem;
    background: var(--card-bg, #f8fafc);
    border: 1px solid var(--border, #e2e8f0);
    border-radius: .875rem; overflow: hidden;
}
[data-theme="dark"] .hp-freq-card { background: var(--card-bg, #1e293b); border-color: var(--border, #334155); }
.hp-freq-title {
    font-size: .8rem; font-weight: 700; letter-spacing: .04em;
    text-transform: uppercase; color: var(--muted, #6b7280);
    padding: .75rem 1rem .5rem;
}
.hp-freq-row {
    display: grid;
    grid-template-columns: 9rem 3rem 3.5rem 1fr;
    align-items: center; gap: .5rem;
    padding: .38rem 1rem;
    border-top: 1px solid var(--border, #e2e8f0);
    font-size: .83rem;
}
[data-theme="dark"] .hp-freq-row { border-color: var(--border, #334155); }
.hp-freq-cat  { font-weight: 600; }
.hp-freq-n    { text-align: right; font-weight: 700; font-variant-numeric: tabular-nums; }
.hp-freq-pct  { text-align: right; color: var(--muted, #6b7280); font-size: .78rem; }
.hp-freq-bar-wrap { height: 7px; background: var(--border, #e2e8f0); border-radius: 999px; overflow: hidden; }
.hp-freq-bar  { height: 100%; border-radius: 999px; transition: width .4s ease; }

/* ── Tabla preguntas ── */
.hp-table-section { padding: 0 1.5rem 1.5rem; }
.hp-table-section h2 { font-size: .95rem; font-weight: 700; margin: 0 0 .75rem; }
.hp-table-wrap { overflow-x: auto; }
.hp-table {
    width: 100%; border-collapse: collapse;
    font-size: .82rem;
}
.hp-table thead th {
    background: var(--card-bg, #f1f5f9);
    padding: .55rem .75rem; text-align: left;
    font-size: .75rem; font-weight: 700;
    letter-spacing: .03em; text-transform: uppercase;
    color: var(--muted, #6b7280);
    border-bottom: 1px solid var(--border, #e2e8f0);
    white-space: nowrap;
}
[data-theme="dark"] .hp-table thead th {
    background: var(--card-bg, #0f172a);
    border-color: var(--border, #334155);
}
.hp-table tbody td {
    padding: .5rem .75rem;
    border-bottom: 1px solid var(--border, #f1f5f9);
    vertical-align: top;
}
[data-theme="dark"] .hp-table tbody td { border-color: var(--border, #1e293b); }
.hp-table tbody tr:hover td { background: var(--hover-bg, rgba(0,0,0,.03)); }
.hp-td-num { color: var(--muted, #9ca3af); font-weight: 600; width: 2.5rem; }
.hp-td-user { white-space: nowrap; font-weight: 600; }
.hp-td-cat .hp-cat-pill {
    display: inline-block; padding: .15rem .55rem;
    border-radius: 999px; font-size: .72rem; font-weight: 700;
    white-space: nowrap;
}
.hp-td-date { white-space: nowrap; color: var(--muted, #6b7280); }
.hp-td-q    { max-width: 260px; }
.hp-td-a    { max-width: 220px; color: var(--muted, #6b7280); }
.hp-td-link a { color: var(--accent, #2563eb); text-decoration: none; font-weight: 600; }
.hp-td-link a:hover { text-decoration: underline; }

.hp-alert {
    margin: 1rem 1.5rem;
    padding: .9rem 1rem;
    background: rgba(239,68,68,.08);
    border-left: 4px solid rgba(239,68,68,.6);
    border-radius: .5rem; font-size: .875rem;
}
.hp-empty { padding: 1.5rem; color: var(--muted, #6b7280); font-size: .9rem; }
</style>

<div class="hp-wrap">

    <div class="hp-head">
        <h1><i class="fas fa-chart-bar" style="color:var(--accent,#2563eb);margin-right:.5rem;" aria-hidden="true"></i>Preguntas al chatbot</h1>
        <p>Registro global de consultas realizadas por todos los usuarios.</p>
    </div>

    <?php if ($dbError !== ''): ?>
        <div class="hp-alert" role="alert"><?= htmlspecialchars($dbError, ENT_QUOTES, 'UTF-8') ?></div>
    <?php endif; ?>

    <?php if ($dbError === ''): ?>

    <!-- KPIs -->
    <div class="hp-kpi-row">
        <div class="hp-kpi">
            <div class="hp-kpi-val"><?= number_format($totalPregs) ?></div>
            <div class="hp-kpi-lbl">Preguntas totales</div>
        </div>
        <div class="hp-kpi">
            <div class="hp-kpi-val"><?= $totalUsuarios ?></div>
            <div class="hp-kpi-lbl">Usuarios activos</div>
        </div>
        <div class="hp-kpi">
            <div class="hp-kpi-val"><?= $totalPregs > 0 && $totalUsuarios > 0 ? number_format($totalPregs / $totalUsuarios, 1) : '—' ?></div>
            <div class="hp-kpi-lbl">Preguntas / usuario</div>
        </div>
        <div class="hp-kpi">
            <div class="hp-kpi-val"><?= $stats ? array_key_first($stats) : '—' ?></div>
            <div class="hp-kpi-lbl">Categoría más frecuente</div>
        </div>
    </div>

    <!-- Frecuencia por categoría -->
    <?php if ($totalPregs > 0): ?>
    <div class="hp-freq-card">
        <div class="hp-freq-title">Frecuencia por tipo de pregunta</div>
        <?php foreach ($stats as $cat => $cnt):
            if ($cnt === 0) continue;
            $pct   = round($cnt / $totalPregs * 100);
            $color = $colores[$cat] ?? '#6b7280';
        ?>
        <div class="hp-freq-row">
            <span class="hp-freq-cat"><?= htmlspecialchars($cat, ENT_QUOTES, 'UTF-8') ?></span>
            <span class="hp-freq-n"><?= $cnt ?></span>
            <span class="hp-freq-pct"><?= $pct ?>%</span>
            <div class="hp-freq-bar-wrap">
                <div class="hp-freq-bar" style="width:<?= $pct ?>%;background:<?= $color ?>;"></div>
            </div>
        </div>
        <?php endforeach; ?>
    </div>
    <?php endif; ?>

    <!-- Tabla de preguntas -->
    <div class="hp-table-section">
        <h2>Detalle de preguntas <span style="font-weight:400;color:var(--muted,#6b7280);font-size:.85em;">(últimas <?= count($rows) ?>)</span></h2>

        <?php if (count($rows) === 0): ?>
            <p class="hp-empty">Aún no hay preguntas guardadas.</p>
        <?php else: ?>
        <div class="hp-table-wrap">
            <table class="hp-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Usuario</th>
                        <th>Categoría</th>
                        <th>Fecha</th>
                        <th>Pregunta</th>
                        <th>Respuesta (extracto)</th>
                        <th>Chat</th>
                    </tr>
                </thead>
                <tbody>
                <?php $n = 0; foreach ($rows as $r): $n++;
                    $pregunta  = (string) ($r['pregunta'] ?? '');
                    $extracto  = (string) ($r['respuesta_extracto'] ?? '');
                    $fecha     = (string) ($r['preguntado_en'] ?? '');
                    $threadId  = (string) ($r['thread_id'] ?? '');
                    $uname     = (string) ($r['usuario'] ?? '');
                    $titulo    = (string) ($r['chat_titulo'] ?? '');
                    $cat       = clasificar_pregunta($pregunta, $categorias);
                    $catColor  = $colores[$cat] ?? '#6b7280';
                    $hrefChat  = 'index.php?page=chatbot' . ($threadId !== '' ? '&thread=' . rawurlencode($threadId) : '');
                ?>
                <tr>
                    <td class="hp-td-num"><?= $n ?></td>
                    <td class="hp-td-user"><?= htmlspecialchars($uname, ENT_QUOTES, 'UTF-8') ?></td>
                    <td class="hp-td-cat">
                        <span class="hp-cat-pill" style="background:<?= $catColor ?>22;color:<?= $catColor ?>;border:1px solid <?= $catColor ?>44;">
                            <?= htmlspecialchars($cat, ENT_QUOTES, 'UTF-8') ?>
                        </span>
                    </td>
                    <td class="hp-td-date"><time datetime="<?= htmlspecialchars($fecha, ENT_QUOTES, 'UTF-8') ?>"><?= htmlspecialchars($fecha, ENT_QUOTES, 'UTF-8') ?></time></td>
                    <td class="hp-td-q" title="<?= htmlspecialchars($pregunta, ENT_QUOTES, 'UTF-8') ?>"><?= htmlspecialchars(historial_preview($pregunta, 200), ENT_QUOTES, 'UTF-8') ?></td>
                    <td class="hp-td-a" title="<?= htmlspecialchars($extracto, ENT_QUOTES, 'UTF-8') ?>"><?= htmlspecialchars(historial_preview($extracto, 130), ENT_QUOTES, 'UTF-8') ?></td>
                    <td class="hp-td-link">
                        <a href="<?= htmlspecialchars($hrefChat, ENT_QUOTES, 'UTF-8') ?>">Abrir</a>
                        <?php if ($titulo !== ''): ?>
                        <br><small style="color:var(--muted,#9ca3af);" title="<?= htmlspecialchars($titulo, ENT_QUOTES, 'UTF-8') ?>"><?= htmlspecialchars(historial_preview($titulo, 28), ENT_QUOTES, 'UTF-8') ?></small>
                        <?php endif; ?>
                    </td>
                </tr>
                <?php endforeach; ?>
                </tbody>
            </table>
        </div>
        <?php endif; ?>
    </div>

    <?php endif; ?>
</div>
