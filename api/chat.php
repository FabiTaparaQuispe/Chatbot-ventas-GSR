<?php
declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

if (($_SERVER['REQUEST_METHOD'] ?? '') === 'OPTIONS') {
    http_response_code(204);
    exit;
}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    http_response_code(405);
    echo json_encode(['ok' => false, 'error' => 'Use POST'], JSON_UNESCAPED_UNICODE);
    exit;
}

$configPath = __DIR__ . '/config.php';
if (!is_readable($configPath)) {
    http_response_code(503);
    echo json_encode([
        'ok' => false,
        'error' => 'Falta api/config.php. Copie api/config.example.php a api/config.php y configure BD y LLM.',
    ], JSON_UNESCAPED_UNICODE);
    exit;
}

require_once __DIR__ . '/src/Database.php';
require_once __DIR__ . '/src/DateRangeValidator.php';
require_once __DIR__ . '/src/LlmClient.php';
require_once __DIR__ . '/src/ToolRegistry.php';
require_once __DIR__ . '/src/ChatOrchestrator.php';

/** @var array<string, mixed> $config */
$config = require $configPath;

$rawIn = file_get_contents('php://input') ?: '';
$input = json_decode($rawIn, true);
if (!is_array($input)) {
    http_response_code(400);
    echo json_encode(['ok' => false, 'error' => 'Cuerpo JSON invalido'], JSON_UNESCAPED_UNICODE);
    exit;
}

$messagesIn = $input['messages'] ?? null;
if (!is_array($messagesIn) || $messagesIn === []) {
    http_response_code(400);
    echo json_encode(['ok' => false, 'error' => 'Campo messages (array) requerido'], JSON_UNESCAPED_UNICODE);
    exit;
}

$clean = [];
foreach ($messagesIn as $m) {
    if (!is_array($m) || !isset($m['role'])) {
        continue;
    }
    $role = $m['role'];
    if ($role !== 'user' && $role !== 'assistant') {
        continue;
    }
    $content = isset($m['content']) && is_string($m['content']) ? $m['content'] : '';
    if ($role === 'user' && $content === '') {
        continue;
    }
    $clean[] = ['role' => $role, 'content' => $content];
}

if ($clean === []) {
    http_response_code(400);
    echo json_encode(['ok' => false, 'error' => 'Sin mensajes user/assistant validos'], JSON_UNESCAPED_UNICODE);
    exit;
}

if (count($clean) > 24) {
    $clean = array_slice($clean, -24);
}

try {
    $pdo = Database::pdo($config['db']);
} catch (\Throwable $e) {
    http_response_code(503);
    echo json_encode([
        'ok' => false,
        'error' => 'Error de conexion a la base de datos',
        'detail' => $e->getMessage(),
    ], JSON_UNESCAPED_UNICODE);
    exit;
}

$chatCfg = is_array($config['chat'] ?? null) ? $config['chat'] : [];
$maxDays = (int) ($chatCfg['max_date_range_days'] ?? 732);
$maxLimit = (int) ($chatCfg['max_limit'] ?? 50);
$maxIter = (int) ($chatCfg['max_tool_iterations'] ?? 6);

$llmCfg = $config['llm'] ?? [];
if (!is_array($llmCfg) || ($llmCfg['model'] ?? '') === '') {
    http_response_code(503);
    echo json_encode(['ok' => false, 'error' => 'Configure llm.model y llm.base_url en config.php'], JSON_UNESCAPED_UNICODE);
    exit;
}

$dates = new DateRangeValidator($maxDays);
$tools = new ToolRegistry($pdo, $dates, max(1, min($maxLimit, 100)));
$llm = new LlmClient(
    (string) ($llmCfg['base_url'] ?? ''),
    (string) ($llmCfg['api_key'] ?? ''),
    (string) $llmCfg['model']
);
$orch = new ChatOrchestrator($llm, $tools, max(1, min($maxIter, 12)));

try {
    $out = $orch->run($clean);
    echo json_encode($out, JSON_UNESCAPED_UNICODE);
} catch (\Throwable $e) {
    http_response_code(500);
    echo json_encode([
        'ok' => false,
        'error' => 'Error interno',
        'detail' => $e->getMessage(),
    ], JSON_UNESCAPED_UNICODE);
}
