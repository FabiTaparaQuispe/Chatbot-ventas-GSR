<?php

declare(strict_types=1);

use OpenAI\Exceptions\ErrorException;

final class GroqClient
{
    private const MAX_ITERATIONS = 10;
    private const MAX_TOOL_JSON_BYTES = 14000;
    private const MAX_429_RETRIES = 5;

    private \OpenAI\Client $client;

    public function __construct(
        private string $apiKey,
        private string $model = 'llama-3.1-8b-instant'
    ) {
        $this->client = \OpenAI::factory()
            ->withApiKey($apiKey)
            ->withBaseUri('api.groq.com/openai/v1')
            ->make();
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
            $response = $this->requestCompletion($working, $iteration === 1 ? $tools : []);

            $choice = $response->choices[0] ?? null;
            if ($choice === null) {
                return ['reply' => 'Respuesta vacía del modelo.', 'messages' => $working];
            }

            $message = $choice->message;
            $toolCalls = $message->toolCalls ?? [];

            $assistantPayload = [
                'role'    => 'assistant',
                'content' => $message->content,
            ];
            if (!empty($toolCalls)) {
                $assistantPayload['tool_calls'] = array_map(
                    fn($tc) => [
                        'id'       => $tc->id,
                        'type'     => $tc->type,
                        'function' => [
                            'name'      => $tc->function->name,
                            'arguments' => $tc->function->arguments,
                        ],
                    ],
                    $toolCalls
                );
            }
            $working[] = $assistantPayload;

            if (empty($toolCalls)) {
                return ['reply' => (string) ($message->content ?? ''), 'messages' => $working];
            }

            foreach ($toolCalls as $tc) {
                $args = json_decode($tc->function->arguments, true);
                if (!is_array($args)) {
                    $args = [];
                }
                $toolJson = $this->clampToolJson($runTool($tc->function->name, $args));
                $working[] = [
                    'role'         => 'tool',
                    'tool_call_id' => $tc->id,
                    'content'      => $toolJson,
                ];
            }
        }

        return ['reply' => 'Se alcanzó el límite de iteraciones con herramientas.', 'messages' => $working];
    }

    private function requestCompletion(array $messages, array $tools): \OpenAI\Responses\Chat\CreateResponse
    {
        $params = [
            'model'       => $this->model,
            'messages'    => $messages,
            'temperature' => 0.2,
        ];
        if ($tools !== []) {
            $params['tools']       = $tools;
            $params['tool_choice'] = 'auto';
        }

        for ($attempt = 1; $attempt <= self::MAX_429_RETRIES; $attempt++) {
            try {
                return $this->client->chat()->create($params);
            } catch (ErrorException $e) {
                $msg = $e->getMessage();

                if ($this->isGroqDailyTokenLimit($msg)) {
                    throw new \RuntimeException($this->groqFriendlyDailyLimitMessage($msg));
                }

                if ($this->isRateLimit($msg) && $attempt < self::MAX_429_RETRIES) {
                    $sleepSec = $this->parseGroqRetrySeconds($msg);
                    if ($sleepSec < 1.0) {
                        $sleepSec = min(8.0, 2.0 * $attempt);
                    }
                    usleep((int) round($sleepSec * 1_000_000));
                    continue;
                }

                throw new \RuntimeException($this->groqFriendlyErrorMessage($msg));
            }
        }

        throw new \RuntimeException('Groq: se agotaron los reintentos sin obtener una respuesta válida.');
    }

    private function isGroqDailyTokenLimit(string $message): bool
    {
        return stripos($message, 'tokens per day') !== false
            || stripos($message, 'TPD') !== false;
    }

    private function isRateLimit(string $message): bool
    {
        return stripos($message, 'rate_limit') !== false
            || stripos($message, 'rate limit') !== false
            || stripos($message, 'too many requests') !== false;
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

    private function groqFriendlyErrorMessage(string $raw): string
    {
        if ($this->isRateLimit($raw)) {
            return 'Groq devolvió límite de velocidad (429). Espera unos minutos o cambia de modelo en GROQ_MODEL. [Detalle] ' . $raw;
        }
        return 'Groq error: ' . $raw;
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
            'error'   => 'respuesta_herramienta_muy_grande',
            'mensaje' => 'La consulta devolvió demasiados datos. Acote fechas o filtros.',
        ], JSON_UNESCAPED_UNICODE);
    }
}
