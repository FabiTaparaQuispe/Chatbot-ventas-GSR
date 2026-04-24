# Groq y modelo local (Qwen u OpenAI-compatible)

El backend usa la API **Chat Completions** estilo OpenAI (`/v1/chat/completions`) con **tool calling**. El mismo código sirve para:

## Groq (pruebas iniciales)

1. Cree una clave en [Groq Console](https://console.groq.com/).
2. En `api/config.php`, deje `llm.base_url` en `https://api.groq.com/openai/v1` y `llm.api_key` con su clave (o variable de entorno `GROQ_API_KEY` si la carga su servidor).
3. Use un modelo que soporte tools, por ejemplo `llama-3.3-70b-versatile` (ajuste en `llm.model` si Groq actualiza nombres).

## Qwen u otro modelo local

1. Levante un servidor con endpoint compatible OpenAI (LM Studio, Ollama con modo OpenAI, vLLM, etc.).
2. En `api/config.php`, apunte:
   - `llm.base_url` → por ejemplo `http://127.0.0.1:1234/v1`
   - `llm.model` → nombre exacto del modelo cargado
   - `llm.api_key` → cadena vacía o un placeholder si el servidor no valida token
3. Verifique que el modelo **soporte function calling**; si no, el asistente no podrá invocar herramientas y habría que degradar a respuestas sin datos o a un flujo distinto.

No hace falta cambiar PHP ni JavaScript al cambiar de Groq a local: solo `config.php`.
