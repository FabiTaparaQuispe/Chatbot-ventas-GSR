<?php
declare(strict_types=1);

final class ChatOrchestrator
{
    public function __construct(
        private readonly LlmClient $llm,
        private readonly ToolRegistry $tools,
        private readonly int $maxIterations
    ) {
    }

    private function systemPrompt(): string
    {
        return <<<'SYS'
Eres un asistente de analisis de ventas de una empresa avicola.
Responde en español, con cifras claras y contexto breve.
Usa las herramientas para obtener datos agregados; no inventes numeros.
Datos:
- ventasgeneral: lineas con CodCliente, NombreCliente, FechaCont, Valor, Cantidad, Peso, ZonaComercial, DescriZonaDistribucion, CodItem, Glosa.
- sale: lineas ERP con tprocli (DNI/RUC), tfecfac (fecha comprobante), timport (moneda tmon), tcantid, tcodigo, tglosa, tcencos (centro de costos; nomenclatura del ERP), tasi (dia del mes), tlib (libro; ventas tipicas RV).
Si el usuario no indica fechas, pregunta un rango (maximo ~2 años) o propone el ultimo mes.
SYS;
    }

    /**
     * @param list<array{role: string, content: string}> $userMessages
     * @return array{ok: bool, message?: string, error?: string, detail?: mixed, usage?: mixed}
     */
    public function run(array $userMessages): array
    {
        $messages = array_merge(
            [['role' => 'system', 'content' => $this->systemPrompt()]],
            $userMessages
        );
        $toolDefs = $this->tools->definitions();

        for ($i = 0; $i < $this->maxIterations; $i++) {
            $resp = $this->llm->chat($messages, $toolDefs);
            if (isset($resp['_error'])) {
                $error = (string) $resp['_error'];
                $detail = $resp['_body'] ?? $resp['_raw'] ?? null;
                $normalized = strtolower($error . ' ' . (is_string($detail) ? $detail : json_encode($detail, JSON_UNESCAPED_UNICODE)));
                if (
                    str_contains($normalized, 'token') ||
                    str_contains($normalized, 'rate limit') ||
                    str_contains($normalized, '429') ||
                    str_contains($normalized, 'quota') ||
                    str_contains($normalized, 'too many')
                ) {
                    $error = 'Límite de tokens o rate limit. Intente luego de unos minutos.';
                }
                return [
                    'ok' => false,
                    'error' => $error,
                    'detail' => $detail,
                ];
            }
            $choice = $resp['choices'][0] ?? null;
            if (!is_array($choice)) {
                return ['ok' => false, 'error' => 'respuesta LLM sin choices'];
            }
            $msg = $choice['message'] ?? [];
            if (!is_array($msg)) {
                return ['ok' => false, 'error' => 'mensaje assistant invalido'];
            }
            $messages[] = $msg;

            $toolCalls = $msg['tool_calls'] ?? null;
            if (is_array($toolCalls) && $toolCalls !== []) {
                foreach ($toolCalls as $tc) {
                    if (!is_array($tc)) {
                        continue;
                    }
                    $id = (string) ($tc['id'] ?? '');
                    $fn = $tc['function'] ?? [];
                    $name = is_array($fn) ? (string) ($fn['name'] ?? '') : '';
                    $argsJson = is_array($fn) ? (string) ($fn['arguments'] ?? '{}') : '{}';
                    $args = json_decode($argsJson, true);
                    if (!is_array($args)) {
                        $args = [];
                    }
                    $result = $this->tools->execute($name, $args);
                    $messages[] = [
                        'role' => 'tool',
                        'tool_call_id' => $id,
                        'content' => json_encode($result, JSON_UNESCAPED_UNICODE),
                    ];
                }
                continue;
            }

            $content = $msg['content'] ?? '';
            $text = is_string($content) ? $content : '';

            return [
                'ok' => true,
                'message' => $text,
                'usage' => $resp['usage'] ?? null,
            ];
        }

        return ['ok' => false, 'error' => 'demasiadas iteraciones de herramientas'];
    }
}
