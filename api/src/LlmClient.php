<?php
declare(strict_types=1);

final class LlmClient
{
    public function __construct(
        private readonly string $baseUrl,
        private readonly string $apiKey,
        private readonly string $model
    ) {
    }

    /**
     * @param list<array<string, mixed>> $messages
     * @param list<array<string, mixed>> $tools
     * @return array<string, mixed>
     */
    public function chat(array $messages, array $tools): array
    {
        $url = rtrim($this->baseUrl, '/') . '/chat/completions';
        $body = [
            'model' => $this->model,
            'messages' => $messages,
            'temperature' => 0.2,
        ];
        if ($tools !== []) {
            $body['tools'] = $tools;
            $body['tool_choice'] = 'auto';
        }

        $ch = curl_init($url);
        $headers = ['Content-Type: application/json'];
        if ($this->apiKey !== '') {
            $headers[] = 'Authorization: Bearer ' . $this->apiKey;
        }
        curl_setopt_array($ch, [
            CURLOPT_POST => true,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_HTTPHEADER => $headers,
            CURLOPT_POSTFIELDS => json_encode($body, JSON_UNESCAPED_UNICODE),
            CURLOPT_TIMEOUT => 120,
        ]);
        $raw = curl_exec($ch);
        $code = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $err = curl_error($ch);
        curl_close($ch);

        if ($raw === false) {
            return ['_error' => 'curl: ' . $err];
        }
        $decoded = json_decode($raw, true);
        if (!is_array($decoded)) {
            return ['_error' => 'respuesta LLM no JSON', '_raw' => $raw];
        }
        if ($code >= 400) {
            return ['_error' => 'HTTP ' . $code, '_body' => $decoded];
        }
        return $decoded;
    }
}
