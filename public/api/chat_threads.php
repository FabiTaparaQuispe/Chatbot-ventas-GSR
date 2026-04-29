<?php
declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');

require_once __DIR__ . '/../includes/bootstrap.php';
app_require_login();

$pdo = ventas_pdo();
$username = trim((string) ($_SESSION['usuario'] ?? ''));
if ($username === '') {
    http_response_code(401);
    echo json_encode(['ok' => false, 'error' => 'Sesión inválida'], JSON_UNESCAPED_UNICODE);
    exit;
}

function json_body(): array {
    $raw = file_get_contents('php://input') ?: '';
    $data = json_decode($raw, true);
    return is_array($data) ? $data : [];
}

try {
    $method = strtoupper((string) ($_SERVER['REQUEST_METHOD'] ?? 'GET'));

    if ($method === 'GET') {
        $clientId = isset($_GET['thread']) ? trim((string) $_GET['thread']) : '';
        $q = isset($_GET['q']) ? trim((string) $_GET['q']) : '';

        if ($clientId !== '') {
            $st = $pdo->prepare('SELECT id, client_thread_id, title, created_at, updated_at FROM app_chat_threads WHERE username = :u AND client_thread_id = :cid LIMIT 1');
            $st->execute([':u' => $username, ':cid' => $clientId]);
            $t = $st->fetch(PDO::FETCH_ASSOC) ?: null;
            if (!$t) {
                echo json_encode(['ok' => true, 'thread' => null], JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE);
                exit;
            }

            $stM = $pdo->prepare('SELECT role, content, created_at FROM app_chat_messages WHERE thread_id = :tid ORDER BY id ASC');
            $stM->execute([':tid' => (int) $t['id']]);
            $msgs = [];
            while ($r = $stM->fetch(PDO::FETCH_ASSOC)) {
                $msgs[] = [
                    'role' => (string) ($r['role'] ?? ''),
                    'content' => (string) ($r['content'] ?? ''),
                    'createdAt' => (string) ($r['created_at'] ?? ''),
                ];
            }

            echo json_encode([
                'ok' => true,
                'thread' => [
                    'id' => (string) ($t['client_thread_id'] ?? ''),
                    'title' => (string) ($t['title'] ?? ''),
                    'createdAt' => (string) ($t['created_at'] ?? ''),
                    'updatedAt' => (string) ($t['updated_at'] ?? ''),
                    'messages' => $msgs,
                ],
            ], JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE);
            exit;
        }

        // Listado
        $sql = 'SELECT t.client_thread_id, t.title, t.updated_at,
                       (SELECT COUNT(*) FROM app_chat_messages m WHERE m.thread_id = t.id) AS n
                FROM app_chat_threads t
                WHERE t.username = :u';
        $params = [':u' => $username];
        if ($q !== '') {
            $sql .= ' AND (t.title LIKE :q OR EXISTS (
                        SELECT 1 FROM app_chat_messages m2
                        WHERE m2.thread_id = t.id AND m2.content LIKE :q
                    ))';
            $params[':q'] = '%' . $q . '%';
        }
        $sql .= ' ORDER BY t.updated_at DESC LIMIT 60';

        $st = $pdo->prepare($sql);
        $st->execute($params);
        $threads = [];
        while ($r = $st->fetch(PDO::FETCH_ASSOC)) {
            $threads[] = [
                'id' => (string) ($r['client_thread_id'] ?? ''),
                'title' => (string) ($r['title'] ?? ''),
                'updatedAt' => (string) ($r['updated_at'] ?? ''),
                'n' => (int) ($r['n'] ?? 0),
            ];
        }

        echo json_encode(['ok' => true, 'threads' => $threads], JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE);
        exit;
    }

    if ($method === 'POST') {
        $body = json_body();
        $clientId = isset($body['id']) ? trim((string) $body['id']) : '';
        $title = isset($body['title']) ? trim((string) $body['title']) : 'Nuevo chat';
        $messages = isset($body['messages']) && is_array($body['messages']) ? $body['messages'] : [];

        if ($clientId === '') {
            http_response_code(400);
            echo json_encode(['ok' => false, 'error' => 'Falta id'], JSON_UNESCAPED_UNICODE);
            exit;
        }
        if ($title === '') $title = 'Nuevo chat';
        if (strlen($title) > 220) $title = substr($title, 0, 220);

        $pdo->beginTransaction();

        $st = $pdo->prepare('SELECT id FROM app_chat_threads WHERE username = :u AND client_thread_id = :cid LIMIT 1');
        $st->execute([':u' => $username, ':cid' => $clientId]);
        $row = $st->fetch(PDO::FETCH_ASSOC) ?: null;

        if ($row) {
            $threadId = (int) $row['id'];
            $stU = $pdo->prepare('UPDATE app_chat_threads SET title = :t, updated_at = NOW() WHERE id = :id');
            $stU->execute([':t' => $title, ':id' => $threadId]);
            $pdo->prepare('DELETE FROM app_chat_messages WHERE thread_id = :id')->execute([':id' => $threadId]);
        } else {
            $stI = $pdo->prepare('INSERT INTO app_chat_threads (username, client_thread_id, title) VALUES (:u, :cid, :t)');
            $stI->execute([':u' => $username, ':cid' => $clientId, ':t' => $title]);
            $threadId = (int) $pdo->lastInsertId();
        }

        $stM = $pdo->prepare('INSERT INTO app_chat_messages (thread_id, role, content) VALUES (:tid, :role, :content)');
        $n = 0;
        foreach ($messages as $m) {
            if (!is_array($m)) continue;
            $role = (string) ($m['role'] ?? '');
            if ($role !== 'user' && $role !== 'assistant') continue;
            $content = (string) ($m['content'] ?? '');
            if ($content === '') continue;
            // MEDIUMTEXT en BD; evitamos truncar respuestas largas del asistente (listas + SQL).
            if (strlen($content) > 524288) {
                $content = substr($content, 0, 524288);
            }
            $stM->execute([':tid' => $threadId, ':role' => $role, ':content' => $content]);
            $n++;
            if ($n >= 500) {
                break;
            }
        }

        $pdo->commit();
        echo json_encode(['ok' => true], JSON_UNESCAPED_UNICODE);
        exit;
    }

    if ($method === 'DELETE') {
        $body = json_body();
        $clientId = isset($body['id']) ? trim((string) $body['id']) : '';
        if ($clientId === '') {
            http_response_code(400);
            echo json_encode(['ok' => false, 'error' => 'Falta id'], JSON_UNESCAPED_UNICODE);
            exit;
        }
        $st = $pdo->prepare('DELETE FROM app_chat_threads WHERE username = :u AND client_thread_id = :cid');
        $st->execute([':u' => $username, ':cid' => $clientId]);
        echo json_encode(['ok' => true], JSON_UNESCAPED_UNICODE);
        exit;
    }

    http_response_code(405);
    echo json_encode(['ok' => false, 'error' => 'Método no permitido'], JSON_UNESCAPED_UNICODE);
} catch (Throwable $e) {
    if ($pdo->inTransaction()) {
        try { $pdo->rollBack(); } catch (Throwable) {}
    }
    http_response_code(500);
    echo json_encode(['ok' => false, 'error' => $e->getMessage()], JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE);
}

