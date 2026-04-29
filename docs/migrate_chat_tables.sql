-- Tablas del historial de chat (hilos + mensajes).
-- IMPORTANTE: ejecutá este script en la MISMA base de datos que indica DB_DSN en .env
-- (parámetro dbname=...). Si ejecutás en otra BD, la app seguirá sin ver las tablas.
--
-- En phpMyAdmin: seleccioná la base → pestaña SQL → pegá todo → Continuar.

SET NAMES utf8mb4;

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
