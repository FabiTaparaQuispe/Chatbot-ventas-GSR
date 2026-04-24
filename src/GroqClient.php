<?php

declare(strict_types=1);

final class GroqClient
{
    private const URL = 'https://api.groq.com/openai/v1/chat/completions';
    private const MAX_ITERATIONS = 10;
    /** Reduce tokens en vueltas con herramientas (evita 413 TPM en modelos pequeños). */
    /** Límite del JSON de herramienta hacia Groq; si es bajo, el modelo puede “inventar” nombres al no ver filas completas. */
    private const MAX_TOOL_JSON_BYTES = 14000;
    private const MAX_429_RETRIES = 5;

    public function __construct(
        private string $apiKey,
        private string $model = 'llama-3.1-8b-instant'
    ) {
    }

    /**
     * @param list<array<string, mixed>> $messages
     * @param list<array<string, mixed>> $tools
     * @param callable(string, array): string $runTool nombre función + args decodificados -> JSON string resultado
     * @return array{reply: string, messages: list<array<string, mixed>>}
     */
    public function chatWithTools(array $messages, array $tools, callable $runTool): array
    {
        $working = $messages;
        $iteration = 0;

        while ($iteration < self::MAX_ITERATIONS) {
            $iteration++;
            // Tras la 1ª respuesta, el mensaje ya incluye tool_calls + tool results: no reenviar el esquema de tools (ahorra miles de tokens).
            $data = $this->requestCompletion($working, $iteration === 1 ? $tools : []);
            $choice = $data['choices'][0] ?? null;
            if ($choice === null) {
                return ['reply' => 'Respuesta vacía del modelo.', 'messages' => $working];
            }

            $msg = $choice['message'] ?? [];
            $assistantPayload = [
                'role' => 'assistant',
                'content' => $msg['content'] ?? null,
            ];
            if (!empty($msg['tool_calls'])) {
                $assistantPayload['tool_calls'] = $msg['tool_calls'];
            }
            $working[] = $assistantPayload;

            $toolCalls = $msg['tool_calls'] ?? [];
            if ($toolCalls === []) {
                $text = is_string($msg['content'] ?? null) ? (string) $msg['content'] : '';
                return ['reply' => $text, 'messages' => $working];
            }

            foreach ($toolCalls as $tc) {
                $id = $tc['id'] ?? '';
                $fn = $tc['function'] ?? [];
                $name = (string) ($fn['name'] ?? '');
                $rawArgs = (string) ($fn['arguments'] ?? '{}');
                $args = json_decode($rawArgs, true);
                if (!is_array($args)) {
                    $args = [];
                }
                $toolJson = $this->clampToolJson($runTool($name, $args));
                $working[] = [
                    'role' => 'tool',
                    'tool_call_id' => $id,
                    'content' => $toolJson,
                ];
            }
        }

        return ['reply' => 'Se alcanzó el límite de iteraciones con herramientas.', 'messages' => $working];
    }

    /**
     * @param list<array<string, mixed>> $messages
     * @param list<array<string, mixed>> $tools
     * @return array<string, mixed>
     */
    private function requestCompletion(array $messages, array $tools): array
    {
        $payload = [
            'model' => $this->model,
            'messages' => $messages,
            'temperature' => 0.2,
        ];
        if ($tools !== []) {
            $payload['tools'] = $tools;
            $payload['tool_choice'] = 'auto';
        }

        $body = json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE);
        if ($body === false) {
            throw new RuntimeException('No se pudo codificar JSON para Groq.');
        }

        for ($attempt = 1; $attempt <= self::MAX_429_RETRIES; $attempt++) {
            $ch = curl_init(self::URL);
            if ($ch === false) {
                throw new RuntimeException('curl_init falló');
            }
            curl_setopt_array($ch, [
                CURLOPT_POST => true,
                CURLOPT_HTTPHEADER => [
                    'Content-Type: application/json',
                    'Authorization: Bearer ' . $this->apiKey,
                ],
                CURLOPT_POSTFIELDS => $body,
                CURLOPT_RETURNTRANSFER => true,
                CURLOPT_CONNECTTIMEOUT => 30,
                CURLOPT_TIMEOUT => 120,
            ]);
            $response = curl_exec($ch);
            $code = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
            $err = curl_error($ch);
            curl_close($ch);

            if ($response === false) {
                throw new RuntimeException('Error cURL Groq: ' . $err);
            }

            $decoded = json_decode($response, true);
            if (!is_array($decoded)) {
                throw new RuntimeException('Respuesta Groq no JSON: ' . substr($response, 0, 500));
            }

            $errMsg = (string) ($decoded['error']['message'] ?? '');
            if ($code === 429 && $this->isGroqDailyTokenLimit($errMsg)) {
                throw new RuntimeException($this->groqFriendlyDailyLimitMessage($errMsg));
            }

            if ($code === 429 && $attempt < self::MAX_429_RETRIES) {
                $sleepSec = $this->parseGroqRetrySeconds($errMsg);
                if ($sleepSec < 1.0) {
                    $sleepSec = min(8.0, 2.0 * $attempt);
                }
                usleep((int) round($sleepSec * 1_000_000));
                continue;
            }

            if ($code >= 400) {
                $msg = $decoded['error']['message'] ?? $response;
                throw new RuntimeException($this->groqFriendlyHttpError($code, (string) $msg));
            }

            return $decoded;
        }

        throw new RuntimeException('Groq: se agotaron los reintentos sin obtener una respuesta válida.');
    }

    private function isGroqDailyTokenLimit(string $message): bool
    {
        return stripos($message, 'tokens per day') !== false
            || stripos($message, 'TPD') !== false;
    }

    private function groqFriendlyDailyLimitMessage(string $raw): string
    {
        $hint = '';
        if (preg_match('/try again in\s+([^\n.]+)/i', $raw, $m)) {
            $hint = ' Indicación de Groq: esperar ~' . trim($m[1]) . '.';
        }
        return 'Se alcanzó el límite diario de tokens (TPD) de Groq para este modelo.' . $hint
            . ' Reduce uso (menos preguntas repetidas, menos historial en el chat), prueba otro modelo en GROQ_MODEL (.env), o revisa tu cuota en console.groq.com.'
            . ' [Detalle] ' . $raw;
    }

    private function groqFriendlyHttpError(int $code, string $raw): string
    {
        if ($code === 429) {
            return 'Groq devolvió límite de velocidad (429). Espera unos minutos o cambia de modelo en GROQ_MODEL. [Detalle] ' . $raw;
        }
        return 'Groq HTTP ' . $code . ': ' . $raw;
    }

    private function parseGroqRetrySeconds(string $message): float
    {
        if (preg_match('/try again in ([\d.]+)\s*s/i', $message, $m)) {
            return min(30.0, max(0.5, (float) $m[1]));
        }
        return 0.0;
    }

    private function clampToolJson(string $json): string
    {
        if (strlen($json) <= self::MAX_TOOL_JSON_BYTES) {
            return $json;
        }
        $data = json_decode($json, true);
        $sliceKeys = ['filas', 'filas_ranking', 'filas_pareto'];
        foreach ($sliceKeys as $key) {
            if (!is_array($data) || !isset($data[$key]) || !is_array($data[$key])) {
                continue;
            }
            $all = $data[$key];
            foreach ([12, 8, 5, 3] as $n) {
                $data[$key] = array_slice($all, 0, $n);
                $data['_nota'] = "Respuesta truncada: primeras {$n} filas en {$key} (límite API).";
                $out = json_encode($data, JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE);
                if ($out !== false && strlen($out) <= self::MAX_TOOL_JSON_BYTES) {
                    return $out;
                }
            }
            $data[$key] = $all;
        }
        return json_encode([
            'error' => 'respuesta_herramienta_muy_grande',
            'mensaje' => 'La consulta devolvió demasiados datos. Acote fechas o filtros.',
        ], JSON_UNESCAPED_UNICODE);
    }
}
