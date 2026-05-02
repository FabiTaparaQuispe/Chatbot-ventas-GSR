-- Esquema mínimo para login + chats (MySQL/MariaDB)
-- Base: cia2026 (ver DB_DSN en .env)
-- Si ya tenés login y solo faltan tablas de chat: docs/migrate_chat_tables.sql

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS app_users (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  username VARCHAR(120) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  display_name VARCHAR(160) NULL,
  role VARCHAR(60) NULL,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  last_login_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_app_users_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS app_chat_threads (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  username VARCHAR(120) NOT NULL,
  client_thread_id VARCHAR(64) NOT NULL,
  title VARCHAR(220) NOT NULL DEFAULT 'Nuevo chat',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_thread_user_client (username, client_thread_id),
  KEY ix_thread_user_updated (username, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS app_chat_messages (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  thread_id BIGINT UNSIGNED NOT NULL,
  role ENUM('user','assistant') NOT NULL,
  content MEDIUMTEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY ix_msg_thread_id (thread_id),
  CONSTRAINT fk_msg_thread
    FOREIGN KEY (thread_id) REFERENCES app_chat_threads(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Las preguntas del usuario son las filas con role='user' en app_chat_messages.

-- Usuario de ejemplo (cambia el hash por uno real si quieres).
-- Para generar un hash: en PHP -> password_hash('tu_clave', PASSWORD_DEFAULT)
-- INSERT INTO app_users (username, password_hash, display_name, role) VALUES ('gerente', '$2y$10$...', 'Gerente', 'gerencia');
-- (Rol canónico: admin | gerencia | analista | lector. Si quedó 'gerente' en BD, la app lo trata como gerencia al iniciar sesión.)

