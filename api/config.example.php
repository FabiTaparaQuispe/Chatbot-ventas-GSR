<?php
/**
 * Copiar a config.php y ajustar valores.
 * Groq: https://console.groq.com — modelo con tool use, ej. llama-3.3-70b-versatile
 * Local (Qwen u OpenAI-compatible): fijar llm_base_url y llm_api_key vacío si no aplica.
 */
declare(strict_types=1);

return [
    'db' => [
        'dsn' => 'mysql:host=127.0.0.1;dbname=ventas_grs;charset=latin1',
        'user' => 'root',
        'password' => '',
    ],
    'llm' => [
        'base_url' => 'https://api.groq.com/openai/v1',
        'api_key' => getenv('GROQ_API_KEY') ?: '',
        'model' => 'llama-3.3-70b-versatile',
    ],
    // Si usas modelo local compatible OpenAI (LM Studio, Ollama con /v1, etc.):
    // 'llm' => [
    //     'base_url' => 'http://127.0.0.1:1234/v1',
    //     'api_key' => 'not-needed',
    //     'model' => 'qwen2.5-7b-instruct',
    // ],
    'chat' => [
        'max_tool_iterations' => 6,
        'max_date_range_days' => 732,
        'max_limit' => 50,
    ],
];
