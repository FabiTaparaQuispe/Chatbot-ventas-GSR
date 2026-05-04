# Ventas-Chatbot

Asistente de consultas agregadas sobre ventas avícolas: interfaz web (Flask + Jinja2), API JSON y chat con herramientas SQL sobre MySQL (`ventasgeneral2`, y tablas de sesión/chat según `docs/schema_auth_chat.sql`).

## Requisitos

- Python 3.11+ (probado con 3.14)
- MySQL/MariaDB con datos de ventas y, si usa login e historial, tablas `app_users`, `app_chat_threads`, `app_chat_messages` (véase [docs/schema_auth_chat.sql](docs/schema_auth_chat.sql))
- Clave API de [Groq](https://console.groq.com/) en variable de entorno `GROQ_API_KEY`

## Configuración

1. En la **raíz del repositorio**, cree un archivo `.env` (puede partir de [api/python/.env.example](api/python/.env.example) como referencia de variables).
2. Ajuste al menos `DB_DSN`, `DB_USER`, `DB_PASS`, `GROQ_API_KEY` y `FLASK_SECRET` (cadena larga y aleatoria en producción; sirve como `secret_key` de sesión Flask).

## Ejecutar en desarrollo (único stack: Flask)

```bash
cd backend_python
pip install -r requirements.txt
python -m flask --app app run --host 127.0.0.1 --port 5000
```

Si prefiere la forma clásica con variable de entorno: `set FLASK_APP=app` (Windows) o `export FLASK_APP=app` (Unix) y luego `python -m flask run --host 127.0.0.1 --port 5000`.

Abrir [http://127.0.0.1:5000/login](http://127.0.0.1:5000/login) o [http://127.0.0.1:5000/](http://127.0.0.1:5000/). Los estáticos se sirven bajo `/assets/` (contenido de [public/assets/](public/assets/)).

**URLs canónicas:** API e informes usan rutas sin `.php` (p. ej. `/api/chat`, `/api/ventasgeneral`, `/modules/ventasgeneral/resumen-tabla`). Las rutas antiguas con sufijo `.php` siguen registradas en paralelo por compatibilidad. Reinicie Flask tras cambios en `app.py` o plantillas.

**Contraseñas en BD:** los logins aceptan hashes **bcrypt** (passlib, mismo criterio que en `api/python`) y, por compatibilidad, hashes antiguos de Werkzeug (`pbkdf2:…`, `scrypt:…`).

## Estructura útil

| Ruta | Descripción |
|------|-------------|
| [docs/VALIDACION_NEGOCIO.md](docs/VALIDACION_NEGOCIO.md) | Checklist con negocio |
| [docs/DICCIONARIO_DATOS.md](docs/DICCIONARIO_DATOS.md) | Diccionario mínimo |
| [docs/schema_auth_chat.sql](docs/schema_auth_chat.sql) | Esquema usuarios y chat |
| `backend_python/` | Aplicación Flask (rutas, servicios, plantillas) |
| `public/assets/` | CSS y JS del front (DataTables, chat, tablas) |
| `api/python/` | Variante FastAPI (no es el arranque documentado) |

## Despliegue (Apache/Nginx)

Sirva la aplicación detrás de un proxy reverso hacia el worker WSGI de Flask (por ejemplo **gunicorn** o **waitress** apuntando a `app:app` en `backend_python`). Mantenga la misma ruta base para que `/`, `/login`, `/api/chat` y `/assets/` resuelvan correctamente (las URLs `.php` legacy siguen soportadas si algún cliente antiguo las usa).
