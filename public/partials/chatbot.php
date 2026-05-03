<?php
declare(strict_types=1);

require_once __DIR__ . '/../modules/ventas_chat_config.inc.php';
$ventasHistorialPreguntasUrl = $ventasPublicWebBase;
if ($ventasHistorialPreguntasUrl !== '' && !str_ends_with($ventasHistorialPreguntasUrl, '/')) {
    $ventasHistorialPreguntasUrl .= '/';
}
$ventasHistorialPreguntasUrl .= 'index.php?page=historial_preguntas';

$usuario = (string) ($_SESSION['usuario'] ?? '');
$nomCorto = '';
if ($usuario !== '') {
    $p = explode('@', $usuario, 2)[0];
    $p = str_replace(['.', '_', '-'], ' ', $p);
    $nomCorto = trim($p) !== '' ? (', ' . ucfirst(trim($p))) : '';
}
?>
<style>
    /* Drawer historial (vista completa). El flotante ya tiene sus estilos propios. */
    .ventas-chat-drawer-full {
        position: fixed;
        inset: 0;
        z-index: 9999;
        display: flex;
        pointer-events: none;
    }
    .ventas-chat-drawer-full[hidden] { display: none !important; }
    .ventas-chat-drawer-full[data-open="1"] { pointer-events: auto; }
    .ventas-chat-drawer-full[data-open="1"] .ventas-chat-drawer-backdrop { opacity: 1; }
    .ventas-chat-drawer-full[data-open="1"] .ventas-chat-drawer-panel { opacity: 1; transform: translateX(0); }

    .ventas-chat-drawer-backdrop {
        flex: 1;
        background: rgba(15, 23, 42, 0.38);
        opacity: 0;
        transition: opacity 0.18s ease;
    }
    html[data-theme="dark"] .ventas-chat-drawer-backdrop { background: rgba(0, 0, 0, 0.55); }
    .ventas-chat-drawer-panel {
        width: min(92vw, 380px);
        background: var(--surface, #ffffff);
        color: var(--text, #0f172a);
        border-left: 1px solid var(--border, #e2e8f0);
        transform: translateX(12px);
        opacity: 0;
        transition: transform 0.18s ease, opacity 0.18s ease;
        display: flex;
        flex-direction: column;
    }
    html[data-theme="dark"] .ventas-chat-drawer-panel {
        background: var(--surface, #18181b);
        color: var(--text, #f4f4f5);
        border-left-color: var(--border, #3f3f46);
    }
    .ventas-chat-drawer-head {
        padding: 0.75rem 0.9rem;
        border-bottom: 1px solid var(--border, #e2e8f0);
        display: grid;
        align-items: center;
        justify-content: space-between;
        gap: 0.5rem;
    }
    html[data-theme="dark"] .ventas-chat-drawer-head { border-bottom-color: var(--border, #3f3f46); }
    .ventas-chat-drawer-title { font-weight: 800; font-size: 0.95rem; margin: 0; }
    .ventas-chat-drawer-tools { display: flex; gap: 0.35rem; align-items: center; }
    .ventas-chat-drawer-btn {
        border: 1px solid var(--border, #e2e8f0);
        background: var(--surface-2, #f8fafc);
        color: inherit;
        border-radius: 10px;
        padding: 0.45rem 0.65rem;
        cursor: pointer;
        font: inherit;
        font-size: 0.85rem;
    }
    html[data-theme="dark"] .ventas-chat-drawer-btn {
        border-color: var(--border, #3f3f46);
        background: var(--surface-2, #27272a);
    }
    .ventas-chat-drawer-head-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.5rem;
    }
    .ventas-chat-drawer-search {
        width: 100%;
        border: 1px solid var(--border, #e2e8f0);
        background: var(--surface-2, #f8fafc);
        color: inherit;
        border-radius: 10px;
        padding: 0.5rem 0.6rem;
        font: inherit;
        font-size: 0.85rem;
    }
    html[data-theme="dark"] .ventas-chat-drawer-search {
        border-color: var(--border, #3f3f46);
        background: var(--surface-2, #27272a);
    }
    .ventas-chat-drawer-section {
        padding: 0.2rem 0.25rem 0.4rem;
        font-size: 0.78rem;
        opacity: 0.75;
        font-weight: 800;
        letter-spacing: 0.02em;
        text-transform: uppercase;
    }
    .ventas-chat-drawer-list { padding: 0.6rem; overflow: auto; flex: 1; }
    .ventas-chat-thread {
        width: 100%;
        text-align: left;
        border: 1px solid var(--border, #e2e8f0);
        background: var(--surface, #ffffff);
        color: inherit;
        border-radius: 12px;
        padding: 0.6rem 0.7rem;
        cursor: pointer;
        display: grid;
        gap: 0.25rem;
        margin-bottom: 0.55rem;
    }
    html[data-theme="dark"] .ventas-chat-thread {
        border-color: var(--border, #3f3f46);
        background: var(--surface, #18181b);
    }
    .ventas-chat-thread[aria-current="true"] {
        border-color: rgba(37, 99, 235, 0.6);
        box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.18);
    }
    .ventas-chat-thread-title { font-weight: 800; font-size: 0.92rem; line-height: 1.2; }
    .ventas-chat-thread-meta { font-size: 0.78rem; opacity: 0.75; }
    .ventas-chat-thread-row { display: flex; justify-content: space-between; gap: 0.5rem; align-items: center; }
    .ventas-chat-thread-del {
        border: none;
        background: transparent;
        color: inherit;
        opacity: 0.7;
        cursor: pointer;
        padding: 0.2rem 0.35rem;
        border-radius: 8px;
        font-size: 1rem;
        line-height: 1;
    }
    .ventas-chat-thread-del:hover { background: rgba(148, 163, 184, 0.18); opacity: 1; }

    .ventas-chat-mic-btn-full {
        border: 1px solid var(--border, #e2e8f0);
        background: var(--surface-2, #f8fafc);
        color: inherit;
        border-radius: 12px;
        padding: 0.55rem 0.75rem;
        cursor: pointer;
        font: inherit;
    }
    html[data-theme="dark"] .ventas-chat-mic-btn-full {
        border-color: var(--border, #3f3f46);
        background: var(--surface-2, #27272a);
    }
    .ventas-chat-mic-btn-full[aria-pressed="true"] {
        border-color: rgba(239, 68, 68, 0.65);
        box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.15);
    }
</style>
<div class="chatbot-page" id="ventasChatPanel">
    <header class="chatbot-topbar">
        <a href="index.php?page=ventas" class="chatbot-back" aria-label="Volver a Ventas general" title="Volver">
            <i class="fas fa-arrow-left" aria-hidden="true"></i>
        </a>
        <span class="chatbot-topbar-title">Asistente de ventas</span>
        <div class="chatbot-topbar-actions">
            <button
                type="button"
                id="ventasChatThreadsBtn"
                class="chatbot-icon-btn"
                title="Conversaciones recientes"
                aria-label="Conversaciones recientes"
            >💬</button>
            <button type="button" id="ventasChatClear" class="chatbot-icon-btn" title="Limpiar conversación" aria-label="Limpiar conversación">⌫</button>
            <details class="ventas-chat-head-menu" id="ventasChatHeadMenu">
                <summary class="chatbot-icon-btn ventas-chat-menu-summary" aria-label="Más opciones" title="Más">⋮</summary>
                <div class="ventas-chat-menu-panel ventas-chat-menu-panel--page" role="menu">
                    <button type="button" class="ventas-chat-menu-item" id="ventasChatMenuNew" role="menuitem">Nueva conversación</button>
                    <button type="button" class="ventas-chat-menu-item" id="ventasChatMenuClear" role="menuitem">Limpiar esta conversación…</button>
                    <button type="button" class="ventas-chat-menu-item" id="ventasChatMenuPrefs" role="menuitem">Personalización…</button>
                    <button type="button" class="ventas-chat-menu-item" id="ventasChatMenuClearLocal" role="menuitem">Borrar caché local (este navegador)…</button>
                    <button type="button" class="ventas-chat-menu-item" id="ventasChatMenuPurgeAll" role="menuitem">Borrar todo el historial en servidor…</button>
                    <?php
                    $rolChat = app_user_role();
                    if ($rolChat === 'estrategico' || $rolChat === 'administrador'): ?>
                    <a class="ventas-chat-menu-item ventas-chat-menu-link" role="menuitem" href="<?= htmlspecialchars($ventasHistorialPreguntasUrl, ENT_QUOTES, 'UTF-8') ?>">Preguntas guardadas</a>
                    <?php endif; ?>
                </div>
            </details>
        </div>
    </header>
    <div class="chatbot-body">
        <div class="chatbot-center">
            <div id="chatbotHero" class="chatbot-hero">
                <p class="chatbot-greet">Hola<?= htmlspecialchars($nomCorto, ENT_QUOTES, 'UTF-8') ?></p>
                <h1 class="chatbot-hero-title">¿Por dónde empezamos?</h1>
            </div>
            <div id="ventasChatLog" class="chatbot-log" aria-live="polite"></div>
        </div>
    </div>
    <div class="chatbot-surface">
        <details class="ventas-chat-shortcuts chatbot-shortcuts">
            <summary>Consejos para tu consulta</summary>
            <ul>
                <li><strong>Fechas</strong>: indica desde qué día y hasta qué día te interesa (por ejemplo <em>1 de marzo al 31 de marzo de 2026</em>, o también <em>2026-03-01</em> y <em>2026-03-31</em>). Si falta eso, el asistente te lo preguntará antes de sacar números.</li>
                <li><strong>Zona o mercado</strong>: si quieres acotar por región, usa el mismo nombre corto que suele aparecer en tus listas o facturas (como AQP, TACNA o MOQUEGUA). No filtramos por “ciudad” aparte; va por esa zona comercial.</li>
                <li><strong>Notas de crédito o devoluciones</strong>: solo las ponemos en primer plano en rankings especiales si lo pides explícitamente en tu mensaje.</li>
            </ul>
        </details>
        <div class="ventas-chat-chips-wrap chatbot-faq-wrap">
            <label for="ventasChatFaqSelect" class="ventas-chat-faq-label">Preguntas frecuentes</label>
            <select id="ventasChatFaqSelect" class="ventas-chat-faq-select" aria-label="Seleccionar pregunta frecuente"></select>
        </div>
        <div class="chatbot-composer">
            <textarea id="ventasChatInput" rows="1" placeholder="Escribe tu pregunta sobre ventas, fechas, clientes, productos…"></textarea>
            <div class="chatbot-composer-row">
                <button type="button" id="ventasChatMic" class="ventas-chat-mic-btn-full" aria-label="Dictado por voz" title="Dictado por voz" aria-pressed="false">🎙 Dictar</button>
                <button type="button" id="ventasChatSend" class="btn btn-primary chatbot-send">Enviar</button>
            </div>
        </div>
        <p id="ventasChatError" class="ventas-chat-err" hidden></p>
    </div>

    <div id="ventasChatThreadsDrawer" class="ventas-chat-drawer-full" hidden>
        <div class="ventas-chat-drawer-backdrop" data-action="close" aria-hidden="true"></div>
        <aside class="ventas-chat-drawer-panel" aria-label="Conversaciones recientes">
            <div class="ventas-chat-drawer-head">
                <div class="ventas-chat-drawer-head-top">
                    <p class="ventas-chat-drawer-title">Conversaciones recientes</p>
                    <div class="ventas-chat-drawer-tools">
                        <button type="button" id="ventasChatNewThread" class="ventas-chat-drawer-btn" title="Nuevo chat">Nuevo</button>
                        <button type="button" id="ventasChatCloseThreads" class="ventas-chat-drawer-btn" title="Cerrar historial">Cerrar</button>
                    </div>
                </div>
                <input id="ventasChatThreadsSearch" class="ventas-chat-drawer-search" type="search" placeholder="Buscar chats…" aria-label="Buscar chats">
            </div>
            <div id="ventasChatThreadsList" class="ventas-chat-drawer-list" role="list"></div>
        </aside>
    </div>
</div>
<script>window.VENTAS_CHAT_FULL = true;</script>
<?php
require_once __DIR__ . '/../modules/chat_assistant_script.inc.php';
