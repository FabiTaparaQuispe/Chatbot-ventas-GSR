<?php

declare(strict_types=1);

require_once __DIR__ . '/ventas_chat_config.inc.php';

?>
<style>
    body:not(.app-page-chatbot) { padding-bottom: 5rem; }

    .chat-fab {
        position: fixed;
        bottom: 1.25rem;
        right: 1.25rem;
        z-index: 9998;
        width: 3.5rem;
        height: 3.5rem;
        border-radius: 50%;
        border: none;
        cursor: pointer;
        background: linear-gradient(135deg, var(--accent, #2563eb) 0%, #6366f1 100%);
        color: #fff;
        box-shadow: 0 6px 24px rgba(37, 99, 235, 0.35);
        display: flex;
        align-items: center;
        justify-content: center;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    html[data-theme="dark"] .chat-fab {
        box-shadow: 0 6px 24px rgba(0, 0, 0, 0.45);
    }
    .chat-fab:hover {
        transform: scale(1.05);
        box-shadow: 0 8px 28px rgba(37, 99, 235, 0.45);
    }
    html[data-theme="dark"] .chat-fab:hover {
        box-shadow: 0 8px 28px rgba(0, 0, 0, 0.55);
    }
    .chat-fab:focus-visible {
        outline: 2px solid var(--accent, #2563eb);
        outline-offset: 3px;
    }
    .chat-fab[hidden] { display: none !important; }

    .chat-panel {
        position: fixed;
        bottom: 1.25rem;
        right: 1.25rem;
        z-index: 9999;
        width: min(100vw - 1.5rem, 460px);
        max-height: min(690px, calc(100vh - 1.5rem));
        display: flex;
        flex-direction: column;
        background: var(--surface, #ffffff);
        border: 1px solid var(--border, #e2e8f0);
        color: var(--text, #0f172a);
        border-radius: 16px;
        box-shadow: var(--shadow-soft, 0 16px 48px rgba(15, 23, 42, 0.12));
        overflow: hidden;
    }
    html[data-theme="dark"] .chat-panel {
        box-shadow: 0 16px 48px rgba(0, 0, 0, 0.55);
    }
    .chat-panel[hidden] { display: none !important; }

    .chat-panel-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.5rem;
        padding: 0.85rem 1rem;
        background: linear-gradient(135deg, #1d4ed8 0%, #6d28d9 100%);
        color: #fff;
        flex-shrink: 0;
    }
    html[data-theme="dark"] .chat-panel-head {
        background: linear-gradient(135deg, #1e40af 0%, #5b21b6 100%);
    }
    .chat-panel-head h2 {
        margin: 0;
        font-size: 1rem;
        font-weight: 600;
    }
    .chat-panel-actions { display: flex; align-items: center; gap: 0.25rem; }
    .chat-icon-btn {
        width: 2.25rem;
        height: 2.25rem;
        padding: 0;
        border: none;
        border-radius: 8px;
        background: rgba(255, 255, 255, 0.15);
        color: #fff;
        cursor: pointer;
        font-size: 1.35rem;
        line-height: 1;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .chat-icon-btn:hover { background: rgba(255, 255, 255, 0.25); }

    .chat-panel #ventasChatLog {
        flex: 1;
        min-height: 200px;
        max-height: 42vh;
        overflow-y: auto;
        padding: 0.85rem 1rem;
        background: var(--surface-2, #f8fafc);
        color: var(--text, #0f172a);
    }
    html[data-theme="dark"] .chat-panel #ventasChatLog {
        background: var(--surface-2, #27272a);
        color: var(--text, #f4f4f5);
    }

    .chat-panel-foot {
        padding: 0.65rem 0.75rem 0.85rem;
        border-top: 1px solid var(--border, #e2e8f0);
        background: var(--surface, #ffffff);
        flex-shrink: 0;
    }
    html[data-theme="dark"] .chat-panel-foot {
        border-top-color: var(--border, #3f3f46);
        background: var(--surface, #18181b);
    }
    .chat-panel-foot .row { display: flex; gap: 0.45rem; align-items: flex-end; }
    .chat-panel-foot textarea {
        flex: 1;
        min-height: 44px;
        max-height: 120px;
        padding: 0.55rem 0.7rem;
        border-radius: 10px;
        border: 1px solid var(--input-border, #cbd5e1);
        background: var(--input-bg, #f8fafc);
        color: var(--text, #0f172a);
        resize: none;
        font: inherit;
        font-size: 0.9rem;
        overflow: hidden;
    }
    html[data-theme="dark"] .chat-panel-foot textarea {
        border-color: var(--input-border, #52525b);
        background: var(--input-bg, #27272a);
        color: var(--text, #f4f4f5);
    }
    .chat-panel-foot textarea::placeholder {
        color: var(--muted, #64748b);
    }
    html[data-theme="dark"] .chat-panel-foot textarea::placeholder {
        color: var(--muted, #a1a1aa);
    }
    .chat-panel-foot button#ventasChatSend {
        padding: 0.55rem 0.9rem;
        border-radius: 10px;
        border: none;
        background: var(--accent, #2563eb);
        color: #fff;
        font-weight: 600;
        cursor: pointer;
        font: inherit;
        font-size: 0.85rem;
        flex-shrink: 0;
    }
    .chat-panel-foot button#ventasChatSend:hover { background: var(--accent-hover, #1d4ed8); }
    .chat-panel-foot button#ventasChatSend:disabled { opacity: 0.5; cursor: not-allowed; }

    .chat-panel .ventas-chat-shortcuts {
        margin: 0 0.75rem;
    }
    .chat-panel .ventas-chat-err {
        margin: 0 0.75rem 0.65rem;
    }
</style>

<button type="button" id="ventasChatFab" class="chat-fab" aria-controls="ventasChatPanel" aria-expanded="false" aria-label="Abrir asistente de consultas" title="Asistente">
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z" fill="currentColor"/>
        <path d="M7 9h10v1.5H7V9zm0 3h7v1.5H7V12z" fill="currentColor" opacity="0.85"/>
    </svg>
</button>

<div id="ventasChatPanel" class="chat-panel" hidden role="dialog" aria-modal="true" aria-labelledby="ventasChatPanelTitle">
    <div class="chat-panel-head">
        <h2 id="ventasChatPanelTitle">Asistente de ventas</h2>
        <div class="chat-panel-actions">
            <button type="button" id="ventasChatClear" class="chat-icon-btn" aria-label="Limpiar conversación" title="Limpiar chat">⌫</button>
            <button type="button" id="ventasChatClose" class="chat-icon-btn" aria-label="Cerrar">×</button>
        </div>
    </div>
    <div id="ventasChatLog" aria-live="polite"></div>
    <details class="ventas-chat-shortcuts">
        <summary>Consejos para tu consulta</summary>
        <ul>
            <li><strong>Fechas</strong>: indica desde qué día y hasta qué día te interesa (por ejemplo <em>1 de marzo al 31 de marzo de 2026</em>, o también <em>2026-03-01</em> y <em>2026-03-31</em>). Si falta eso, el asistente te lo preguntará antes de sacar números.</li>
            <li><strong>Zona o mercado</strong>: si quieres acotar por región, usa el mismo nombre corto que suele aparecer en tus listas o facturas (como AQP, TACNA o MOQUEGUA). No filtramos por “ciudad” aparte; va por esa zona comercial.</li>
            <li><strong>Notas de crédito o devoluciones</strong>: solo las ponemos en primer plano en rankings especiales si lo pides explícitamente en tu mensaje.</li>
        </ul>
    </details>
    <div class="ventas-chat-chips-wrap">
        <label for="ventasChatFaqSelect" class="ventas-chat-faq-label">Preguntas frecuentes</label>
        <select id="ventasChatFaqSelect" class="ventas-chat-faq-select" aria-label="Seleccionar pregunta frecuente"></select>
    </div>
    <div class="chat-panel-foot">
        <div class="row">
            <textarea id="ventasChatInput" placeholder="Ej.: ¿Cuánto sumó Valor en marzo de 2026?" rows="2"></textarea>
            <button type="button" id="ventasChatSend">Enviar</button>
        </div>
    </div>
    <p id="ventasChatError" class="ventas-chat-err" hidden></p>
</div>

<?php require __DIR__ . '/chat_assistant_script.inc.php'; ?>
