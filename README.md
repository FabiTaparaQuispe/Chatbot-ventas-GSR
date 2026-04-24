# Ventas-Chatbot

Asistente de consultas agregadas sobre ventas avícolas: documentación de datos (Fase 1) y API PHP + UI JavaScript (Fase 2).

## Requisitos

- PHP 8.1+ con extensión `pdo_mysql` y `curl`
- MySQL/MariaDB con tablas `sale` y `ventasgeneral` importadas desde los dumps del proyecto
- Clave API de [Groq](https://console.groq.com/) o servidor LLM local compatible OpenAI con tool use

## Configuración

1. `copy api\config.example.php api\config.php` (Windows) o `cp api/config.example.php api/config.php`
2. Editar `api/config.php`: DSN, usuario y contraseña de BD; `llm` (Groq o URL local).
3. Opcional: aplicar índices comentados en [docs/indices_sugeridos.sql](docs/indices_sugeridos.sql).

## Ejecutar en desarrollo

Desde la raíz del repositorio:

```bash
php -S localhost:8080 router.php
```

Abrir [http://localhost:8080/](http://localhost:8080/). El front llama a `POST /api/chat.php`.

## Estructura

| Ruta | Descripción |
|------|-------------|
| [docs/VALIDACION_NEGOCIO.md](docs/VALIDACION_NEGOCIO.md) | Checklist con negocio |
| [docs/DICCIONARIO_DATOS.md](docs/DICCIONARIO_DATOS.md) | Diccionario mínimo |
| [docs/sql_referencia.sql](docs/sql_referencia.sql) | Ejemplos SQL |
| [docs/MODELOS_LLM.md](docs/MODELOS_LLM.md) | Groq vs Qwen local |
| `api/chat.php` | Endpoint del chat |
| `api/src/ToolRegistry.php` | Herramientas y SQL parametrizado |
| `public/` | Interfaz del chat |

`api/config.php` no se versiona (véase `.gitignore`).
