<?php

declare(strict_types=1);

$usuario = trim((string) ($_SESSION['usuario'] ?? ''));
$rows = [];
$dbError = '';

if ($usuario === '') {
    $dbError = 'Sesión sin usuario.';
} else {
    try {
        $pdo = ventas_pdo();
        $sql = <<<'SQL'
SELECT
    m.id AS msg_id,
    m.created_at AS preguntado_en,
    m.content AS pregunta,
    t.client_thread_id AS thread_id,
    t.title AS chat_titulo,
    (
        SELECT LEFT(m2.content, 180)
        FROM app_chat_messages m2
        WHERE m2.thread_id = m.thread_id
          AND m2.role = 'assistant'
          AND m2.id > m.id
        ORDER BY m2.id ASC
        LIMIT 1
    ) AS respuesta_extracto
FROM app_chat_messages m
INNER JOIN app_chat_threads t ON t.id = m.thread_id
WHERE t.username = :u
  AND m.role = 'user'
ORDER BY m.created_at DESC, m.id DESC
LIMIT 400
SQL;
        $st = $pdo->prepare($sql);
        $st->execute([':u' => $usuario]);
        while ($r = $st->fetch(PDO::FETCH_ASSOC)) {
            $rows[] = $r;
        }
    } catch (Throwable $e) {
        $raw = $e->getMessage();
        $sqlState = '';
        if ($e instanceof PDOException && isset($e->errorInfo[0])) {
            $sqlState = (string) $e->errorInfo[0];
        }
        $missingTable = $sqlState === '42S02'
            || stripos($raw, "doesn't exist") !== false
            || stripos($raw, 'no existe') !== false
            || stripos($raw, 'Unknown table') !== false
            || stripos($raw, 'Base table') !== false;
        if ($missingTable) {
            $dbError = 'Las tablas del chat aún no están creadas en esta base de datos. '
                . 'En phpMyAdmin (o tu cliente MySQL) seleccioná la base que usa la aplicación (revisá el parámetro dbname= en DB_DSN dentro del archivo .env) y ejecutá el script '
                . 'docs/migrate_chat_tables.sql del proyecto. Si también necesitás usuarios de login, podés usar docs/schema_auth_chat.sql completo. Después recargá esta página.';
        } else {
            $dbError = 'No se pudo leer el historial. Revisá la conexión a la base de datos (DB_DSN en .env) y que existan app_chat_threads y app_chat_messages.';
            if (getenv('APP_DEBUG') === '1' || getenv('APP_DEBUG') === 'true') {
                $dbError .= ' Detalle: ' . $raw;
            }
        }
    }
}

$historialBackPage = in_array(app_user_role(), app_roles_ventas_general(), true) ? 'ventas' : 'chatbot';
$historialBackLabel = $historialBackPage === 'ventas' ? 'Volver a Ventas general' : 'Volver al Chatbot';

function historial_preview(string $text, int $max = 220): string
{
    $text = trim(preg_replace('/\s+/u', ' ', $text));
    if ($text === '') {
        return '—';
    }
    if (function_exists('mb_strlen') && function_exists('mb_substr')) {
        if (mb_strlen($text, 'UTF-8') <= $max) {
            return $text;
        }

        return mb_substr($text, 0, $max, 'UTF-8') . '…';
    }
    if (strlen($text) <= $max) {
        return $text;
    }

    return substr($text, 0, $max) . '…';
}

?>
<div class="app-historial-chat">
    <header class="app-historial-chat-head">
        <a href="index.php?page=<?= htmlspecialchars($historialBackPage, ENT_QUOTES, 'UTF-8') ?>" class="app-historial-chat-back" aria-label="<?= htmlspecialchars($historialBackLabel, ENT_QUOTES, 'UTF-8') ?>" title="Volver">
            <i class="fas fa-arrow-left" aria-hidden="true"></i>
        </a>
        <div class="app-historial-chat-head-text">
            <h1 class="app-historial-chat-title">Preguntas al chatbot</h1>
            <p class="app-historial-chat-sub">Todas las consultas que enviaste al asistente (según lo guardado en la base de datos).</p>
        </div>
    </header>

    <?php if ($dbError !== ''): ?>
        <div class="app-historial-chat-alert" role="alert"><?= htmlspecialchars($dbError, ENT_QUOTES, 'UTF-8') ?></div>
    <?php endif; ?>

    <?php if ($dbError === '' && count($rows) === 0): ?>
        <p class="app-historial-chat-empty">Aún no hay preguntas guardadas. Usá el <a href="index.php?page=chatbot">Chatbot</a>; al enviar mensajes se sincronizan en tu cuenta.</p>
    <?php elseif ($dbError === ''): ?>
        <div class="app-historial-chat-table-wrap">
            <table class="app-historial-chat-table">
                <thead>
                    <tr>
                        <th scope="col">#</th>
                        <th scope="col">Fecha</th>
                        <th scope="col">Pregunta</th>
                        <th scope="col">Respuesta (extracto)</th>
                        <th scope="col">Conversación</th>
                    </tr>
                </thead>
                <tbody>
                    <?php
                    $n = 0;
foreach ($rows as $r) {
    $n++;
    $threadId = (string) ($r['thread_id'] ?? '');
    $hrefChat = 'index.php?page=chatbot' . ($threadId !== '' ? ('&thread=' . rawurlencode($threadId)) : '');
    $pregunta = (string) ($r['pregunta'] ?? '');
    $extracto = (string) ($r['respuesta_extracto'] ?? '');
    $fecha = (string) ($r['preguntado_en'] ?? '');
    ?>
                    <tr>
                        <td class="app-historial-chat-td-num"><?= $n ?></td>
                        <td class="app-historial-chat-td-date"><time datetime="<?= htmlspecialchars($fecha, ENT_QUOTES, 'UTF-8') ?>"><?= htmlspecialchars($fecha, ENT_QUOTES, 'UTF-8') ?></time></td>
                        <td class="app-historial-chat-td-q" title="<?= htmlspecialchars($pregunta, ENT_QUOTES, 'UTF-8') ?>"><?= htmlspecialchars(historial_preview($pregunta, 260), ENT_QUOTES, 'UTF-8') ?></td>
                        <td class="app-historial-chat-td-a" title="<?= htmlspecialchars($extracto, ENT_QUOTES, 'UTF-8') ?>"><?= htmlspecialchars(historial_preview($extracto, 140), ENT_QUOTES, 'UTF-8') ?></td>
                        <td class="app-historial-chat-td-link">
                            <a href="<?= htmlspecialchars($hrefChat, ENT_QUOTES, 'UTF-8') ?>">Abrir chat</a>
                            <span class="app-historial-chat-meta" title="<?= htmlspecialchars((string) ($r['chat_titulo'] ?? ''), ENT_QUOTES, 'UTF-8') ?>"><?= htmlspecialchars(historial_preview((string) ($r['chat_titulo'] ?? ''), 28), ENT_QUOTES, 'UTF-8') ?></span>
                        </td>
                    </tr>
                    <?php } ?>
                </tbody>
            </table>
        </div>
    <?php endif; ?>
</div>
