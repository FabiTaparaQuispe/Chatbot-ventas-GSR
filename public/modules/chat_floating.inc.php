<?php

declare(strict_types=1);

$ventasChatApiUrl = 'api/chat.php';

$ventasWebModulesBase = null;
if (function_exists('app_public_base')) {
    $ventasWebModulesBase = app_public_base() . 'modules/';
}
if ($ventasWebModulesBase === null) {
    $d = str_replace('\\', '/', dirname($_SERVER['SCRIPT_NAME'] ?? ''));
    $baseDir = rtrim($d, '/');
    if ($baseDir !== '' && str_ends_with($baseDir, '/modules')) {
        $ventasWebModulesBase = $baseDir . '/';
    } elseif ($baseDir !== '' && str_ends_with($baseDir, '/public')) {
        $ventasWebModulesBase = $baseDir . '/modules/';
    } elseif ($baseDir !== '') {
        $ventasWebModulesBase = $baseDir . '/public/modules/';
    } else {
        $ventasWebModulesBase = '/public/modules/';
    }
}

$ventasPublicWebBase = '/';
if (function_exists('app_public_base')) {
    $ventasPublicWebBase = app_public_base();
}

?>
<style>
    /* Tema: mismos tokens que `app.css` en `html[data-theme]` (sidebar). Fallbacks si la página no carga app.css. */
    body { padding-bottom: 5rem; }

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

    #ventasChatLog {
        flex: 1;
        min-height: 200px;
        max-height: 42vh;
        overflow-y: auto;
        padding: 0.85rem 1rem;
        background: var(--surface-2, #f8fafc);
        color: var(--text, #0f172a);
    }
    html[data-theme="dark"] #ventasChatLog {
        background: var(--surface-2, #27272a);
        color: var(--text, #f4f4f5);
    }
    .ventas-chat-msg { margin-bottom: 1rem; font-size: 0.9rem; }
    .ventas-chat-msg.user { color: var(--accent, #2563eb); }
    html[data-theme="dark"] .ventas-chat-msg.user {
        color: var(--accent, #60a5fa);
    }
    .ventas-chat-msg.assistant { color: var(--text, #0f172a); white-space: pre-wrap; }
    .ventas-chat-msg--streaming .ventas-chat-msg-body {
        min-height: 1.35em;
    }
    html[data-theme="dark"] .ventas-chat-msg.assistant {
        color: var(--text, #f4f4f5);
    }
    .ventas-chat-msg.assistant a,
    .ventas-chat-msg.assistant a.ventas-chat-link {
        color: var(--accent, #2563eb);
        text-decoration: underline;
        word-break: break-all;
    }
    html[data-theme="dark"] .ventas-chat-msg.assistant a,
    html[data-theme="dark"] .ventas-chat-msg.assistant a.ventas-chat-link {
        color: var(--accent, #60a5fa);
    }
    .ventas-chat-msg.assistant a:hover { color: var(--accent-hover, #1d4ed8); }
    html[data-theme="dark"] .ventas-chat-msg.assistant a:hover {
        color: var(--accent-hover, #93c5fd);
    }
    .ventas-chat-msg .ventas-chat-label {
        font-size: 0.65rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--muted, #64748b);
        margin-bottom: 0.2rem;
    }
    html[data-theme="dark"] .ventas-chat-msg .ventas-chat-label {
        color: var(--muted, #a1a1aa);
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

    .ventas-chat-shortcuts {
        margin: 0 0.75rem;
        font-size: 0.72rem;
        color: var(--muted, #64748b);
        max-height: 7.5rem;
        overflow-y: auto;
    }
    html[data-theme="dark"] .ventas-chat-shortcuts {
        color: var(--muted, #a1a1aa);
    }
    .ventas-chat-shortcuts summary {
        cursor: pointer;
        color: var(--accent, #2563eb);
        font-weight: 600;
    }
    html[data-theme="dark"] .ventas-chat-shortcuts summary {
        color: var(--accent, #60a5fa);
    }
    .ventas-chat-shortcuts ul { margin: 0.35rem 0 0; padding-left: 1.1rem; }
    .ventas-chat-chips-wrap {
        padding: 0.45rem 0.75rem 0.35rem;
        border-top: 1px solid var(--border, #e2e8f0);
        background: var(--surface-2, #f8fafc);
        flex-shrink: 0;
    }
    html[data-theme="dark"] .ventas-chat-chips-wrap {
        border-top-color: var(--border, #3f3f46);
        background: var(--surface-2, #27272a);
    }
    .ventas-chat-faq-label {
        display: block;
        font-size: 0.68rem;
        font-weight: 600;
        color: var(--muted, #64748b);
        margin-bottom: 0.35rem;
        line-height: 1.35;
    }
    html[data-theme="dark"] .ventas-chat-faq-label {
        color: var(--muted, #a1a1aa);
    }
    .ventas-chat-faq-select {
        width: 100%;
        box-sizing: border-box;
        padding: 0.45rem 0.65rem;
        border-radius: 10px;
        border: 1px solid var(--input-border, #cbd5e1);
        background: var(--input-bg, #f8fafc);
        color: var(--text, #0f172a);
        font: inherit;
        font-size: 0.82rem;
        line-height: 1.35;
        cursor: pointer;
    }
    html[data-theme="dark"] .ventas-chat-faq-select {
        border-color: var(--input-border, #52525b);
        background: var(--input-bg, #27272a);
        color: var(--text, #f4f4f5);
    }
    .ventas-chat-faq-select:focus {
        outline: none;
        border-color: var(--accent, #2563eb);
        box-shadow: 0 0 0 2px var(--accent-soft, rgba(37, 99, 235, 0.2));
    }

    .chat-panel .ventas-chat-err {
        color: #dc2626;
        font-size: 0.8rem;
        margin: 0 0.75rem 0.65rem;
        padding: 0 0.25rem;
    }
    html[data-theme="dark"] .chat-panel .ventas-chat-err {
        color: #f87171;
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
        <summary>Atajos y palabras clave</summary>
        <ul>
            <li><strong>Fechas</strong>: dos fechas en formato YYYY-MM-DD o un mes claro; si faltan, el asistente debe pedirlas antes de consultar.</li>
            <li><strong>Zona / mercado</strong>: prefijos (AQP, TACNA, MOQUEGUA…) sobre DescriZonaPrecio; no hay campo ciudad.</li>
            <li><strong>NC</strong> o <strong>TDoc 07</strong>: nota de crédito (rankings NC solo si lo pedís).</li>
        </ul>
    </details>
    <div class="ventas-chat-chips-wrap">
        <label for="ventasChatFaqSelect" class="ventas-chat-faq-label">Preguntas frecuentes</label>
        <select id="ventasChatFaqSelect" class="ventas-chat-faq-select" aria-label="Elegir pregunta frecuente"></select>
    </div>
    <div class="chat-panel-foot">
        <div class="row">
            <textarea id="ventasChatInput" placeholder="Ej.: ¿Cuánto sumó Valor en marzo de 2026?" rows="2"></textarea>
            <button type="button" id="ventasChatSend">Enviar</button>
        </div>
    </div>
    <p id="ventasChatError" class="ventas-chat-err" hidden></p>
</div>

<script>
(function () {
    const CHAT_API = <?= json_encode($ventasChatApiUrl, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) ?>;
    /** Base pública (misma que `<base href>`) para `sql_texto.php` y assets. */
    const VENTAS_PUBLIC_BASE = <?= json_encode($ventasPublicWebBase, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) ?>;
    /** Ruta absoluta desde la raíz del sitio (p. ej. /Ventas-Chatbot/public/modules/) para enlaces del asistente. */
    const VENTAS_MODULES_WEB_BASE = <?= json_encode($ventasWebModulesBase, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) ?>;
    const LS_HISTORY = 'ventasChatbot_history_v1';
    const LS_DRAFT = 'ventasChatbot_draft_v1';
    const MAX_LOCAL_MESSAGES = 120;

    const log = document.getElementById('ventasChatLog');
    const input = document.getElementById('ventasChatInput');
    const send = document.getElementById('ventasChatSend');
    const errEl = document.getElementById('ventasChatError');
    const fab = document.getElementById('ventasChatFab');
    const panel = document.getElementById('ventasChatPanel');
    const closeBtn = document.getElementById('ventasChatClose');
    const clearBtn = document.getElementById('ventasChatClear');
    const faqSelect = document.getElementById('ventasChatFaqSelect');
    /** Plantillas FAQ vigentes (índice = value de cada option) */
    let faqTemplatesCache = [];
    const history = [];

    function pad2(n) {
        return String(n).padStart(2, '0');
    }
    function toYmd(d) {
        return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate());
    }
    function defaultReportRange() {
        const now = new Date();
        const first = new Date(now.getFullYear(), now.getMonth() - 1, 1);
        const last = new Date(now.getFullYear(), now.getMonth(), 0);
        return { desde: toYmd(first), hasta: toYmd(last) };
    }
    function faqChipTemplates(desde, hasta) {
        const y = new Date().getFullYear();
        const b1 = toYmd(new Date(y, 0, 1));
        const b2 = toYmd(new Date(y, 1, 0));
        const c1 = toYmd(new Date(y, 1, 1));
        const c2 = toYmd(new Date(y, 2, 0));
        return [
            { label: 'Totales del período', text: 'Del ' + desde + ' al ' + hasta + ', ¿cuáles son los totales de ventas (filas, suma de Valor, suma de Cantidad y suma de Peso)?' },
            { label: 'Top clientes (valor)', text: 'Del ' + desde + ' al ' + hasta + ', dame el top 10 de clientes (global) por suma de Valor.' },
            { label: 'Top productos', text: 'Del ' + desde + ' al ' + hasta + ', dame el top 15 de productos por suma de Valor.' },
            { label: 'Serie mensual', text: 'Del ' + desde + ' al ' + hasta + ', dame la serie mensual de la suma de Valor.' },
            { label: 'Mix por TDoc', text: 'Del ' + desde + ' al ' + hasta + ', dame el mix de suma de Valor por TDoc.' },
            { label: 'NC por zona precio', text: 'Del ' + desde + ' al ' + hasta + ', dame el pareto de notas de crédito (TDoc 07) por zona de precio (DescriZonaPrecio).' },
            { label: 'Top en zona TACNA', text: 'Del ' + desde + ' al ' + hasta + ', dame el top 10 de clientes por suma de Valor dentro de la zona de precio con prefijo TACNA.' },
            { label: 'Barras (precio)', text: 'Del ' + desde + ' al ' + hasta + ', muéstrame un gráfico de barras de suma de Valor por zona de precio (DescriZonaPrecio).' },
            { label: 'Comparar 2 meses', text: 'Compará la suma de Valor por zona de precio (DescriZonaPrecio): período A del ' + b1 + ' al ' + b2 + ' vs período B del ' + c1 + ' al ' + c2 + ' (top 10).' },
        ];
    }
    function renderVentasFaqSelect() {
        if (!faqSelect) return;
        const r = defaultReportRange();
        faqTemplatesCache = faqChipTemplates(r.desde, r.hasta);
        faqSelect.innerHTML = '';
        const ph = document.createElement('option');
        ph.value = '';
        ph.textContent = '— Elegí una consulta —';
        faqSelect.appendChild(ph);
        faqTemplatesCache.forEach(function (item, i) {
            const o = document.createElement('option');
            o.value = String(i);
            o.textContent = item.label;
            faqSelect.appendChild(o);
        });
        faqSelect.selectedIndex = 0;
    }

    if (faqSelect) {
        faqSelect.addEventListener('change', function () {
            const v = faqSelect.value;
            if (v === '') return;
            const idx = parseInt(v, 10);
            if (!isNaN(idx) && faqTemplatesCache[idx]) {
                input.value = faqTemplatesCache[idx].text;
                input.focus();
            }
            faqSelect.selectedIndex = 0;
        });
    }

    function escapeHtml(s) {
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function hasGenericClienteLabels(text) {
        return /^\d+\.\s*Cliente\s+\d+/mi.test(String(text));
    }

    function stripTrailingUrlJunk(url) {
        return String(url).replace(/[),.;'\]}>*`]+$/g, '');
    }

    /** Quita caracteres invisibles que a veces inserta el LLM y rompen el match del regex. */
    function normalizeTextForLinkify(s) {
        return String(s).replace(/[\u200b-\u200d\ufeff\u00a0]/g, '');
    }

    /**
     * El modelo parte fechas YYYY-MM-DD en dos líneas (ej. 2026-01-\\n01), lo que rompe el regex de URLs.
     */
    function collapseDateLineBreaks(text) {
        let t = String(text);
        let prev;
        do {
            prev = t;
            t = t.replace(/(\d{4}-\d{2}-)\r?\n(\d{2})\b/g, '$1$2');
        } while (t !== prev);
        return t;
    }

    /** El modelo envuelve URLs en `code`; quita una sola capa de backticks si rodea .php? */
    function unwrapBackticksAroundPhpUrls(text) {
        return String(text).replace(/`([^`\n]*\.php\?[^`\n]*)`/gi, '$1');
    }

    /**
     * El modelo a veces parte URLs largas en varias líneas; el regex de enlaces cortaba en \\n y el href
     * quedaba solo con el primer parámetro (PHP respondía 400). Une "\\n&" con el fragmento anterior.
     */
    function collapseMultilineQueryUrls(text) {
        let t = String(text);
        let prev;
        const blocks = [
            /(ventas_(?:barras_dimension|comparativo|top_productos|top_clientes_global|top_clientes_nc|mix_tdoc|barras_ruta|barras_corporativo|serie_mensual)\.php\?[^\n\r]*)\r?\n\s*&/gi,
            /(ventasgeneral_top_clientes_nc\.php\?[^\n\r]*)\r?\n\s*&/gi,
            /((?:pareto_nc_zona|pareto_clientes_zona)(?:_tabla)?\.php\?[^\n\r]*)\r?\n\s*&/gi,
            /(ventasgeneral_(?:buscar|resumen)(?:_tabla)?\.php\?[^\n\r]*)\r?\n\s*&/gi,
            /(ventasgeneral_top_clientes_zona_precio\.php\?[^\n\r]*)\r?\n\s*&/gi,
            /(sql_texto\.php\?[^\n\r]*)\r?\n\s*&/gi,
            /((?:https?:)\/\/[^\s\n<]+\?[^\n\r]*)\r?\n\s*&/gi,
        ];
        do {
            prev = t;
            for (let i = 0; i < blocks.length; i++) {
                t = t.replace(blocks[i], '$1&');
            }
        } while (t !== prev);
        return t;
    }

    function normalizeVentasgeneralTablaHref(u) {
        // El modelo suele omitir _tabla en el nombre de archivo; el real está en *_tabla.php (también en URL absoluta).
        // Nombres inventados de pareto NC → archivo real en modules/
        return String(u)
            .replace(/ventasgeneral_resumen\.php\?/gi, 'ventasgeneral_resumen_tabla.php?')
            .replace(/ventasgeneral_buscar\.php\?/gi, 'ventasgeneral_buscar_tabla.php?')
            .replace(/ventasgeneral_top_clientes_nc\.php\?/gi, 'ventas_top_clientes_nc.php?')
            .replace(/ventasgeneral_pareto_nc[^?]*\.php\?/gi, 'pareto_nc_zona.php?')
            .replace(/pareto_nc_zonaprecio\.php\?/gi, 'pareto_nc_zona.php?')
            .replace(/ventasgeneral_top_clientes_zona_precio\.php\?/gi, 'pareto_clientes_zona.php?');
    }

    function resolveAssistantHref(raw) {
        let path = normalizeVentasgeneralTablaHref(stripTrailingUrlJunk(raw));
        path = path.replace(/^modules\//i, '');
        path = path.replace(/^\.\//, '');
        if (/^https?:\/\//i.test(path)) {
            return path;
        }
        if (/^sql_texto\.php\?/i.test(path)) {
            let b = String(typeof VENTAS_PUBLIC_BASE !== 'undefined' ? VENTAS_PUBLIC_BASE : '').trim();
            if (b !== '' && !b.endsWith('/')) {
                b += '/';
            }
            return (b === '' ? '/' : b) + path.replace(/^\//, '');
        }
        if (path.startsWith('/')) {
            return path;
        }
        const needsModule = /^(?:ventas_(?:barras_dimension|comparativo|top_productos|top_clientes_global|top_clientes_nc|mix_tdoc|barras_ruta|barras_corporativo|serie_mensual)|pareto_(?:nc_zona|clientes_zona)(?:_tabla)?|ventasgeneral_(?:buscar|resumen)(?:_tabla)?)\.php\?/i.test(path);
        if (needsModule) {
            const base = VENTAS_MODULES_WEB_BASE.endsWith('/') ? VENTAS_MODULES_WEB_BASE : (VENTAS_MODULES_WEB_BASE + '/');
            return base + path;
        }
        return path;
    }

    /**
     * Enlaza URLs en el texto original (sin escapar antes): si se escapa todo el texto,
     * el & de la query string pasa a &amp; y el enlace rompe los parámetros desde/hasta.
     */
    function linkifyAssistant(text) {
        let t = normalizeTextForLinkify(text);
        t = unwrapBackticksAroundPhpUrls(t);
        t = collapseDateLineBreaks(t);
        t = collapseMultilineQueryUrls(t);
        // Incluye nombre erróneo ventasgeneral_top_clientes_nc.php / ventasgeneral_top_clientes_zona_precio.php que usa el LLM
        const re = /(https?:\/\/[^\s<]+|sql_texto\.php\?[^\s<]+|(?:pareto_nc_zona|pareto_clientes_zona)(?:_tabla)?\.php\?[^\s<]+|ventasgeneral_top_clientes_nc\.php\?[^\s<]+|ventasgeneral_top_clientes_zona_precio\.php\?[^\s<]+|ventas_(?:barras_dimension|comparativo|top_productos|top_clientes_global|top_clientes_nc|mix_tdoc|barras_ruta|barras_corporativo|serie_mensual)\.php\?[^\s<]+|ventasgeneral_(?:buscar|resumen)(?:_tabla)?\.php\?[^\s<]+)/gi;
        const out = [];
        let last = 0;
        let m;
        re.lastIndex = 0;
        while ((m = re.exec(t)) !== null) {
            out.push(escapeHtml(t.slice(last, m.index)));
            const raw = stripTrailingUrlJunk(m[0]);
            const hrefResolved = resolveAssistantHref(raw);
            const href = escapeHtml(hrefResolved);
            const label = escapeHtml(raw);
            out.push('<a class="ventas-chat-link" href="' + href + '" target="_blank" rel="noopener noreferrer">' + label + '</a>');
            last = m.index + m[0].length;
        }
        out.push(escapeHtml(t.slice(last)));
        return out.join('');
    }

    /** Cancela animaciones de escritura del asistente al iniciar otra o limpiar chat */
    let assistantStreamGen = 0;

    /**
     * Efecto máquina de escribir: texto plano y al final linkify (evita href rotos a medias).
     */
    function streamAssistantIntoBody(bodyEl, fullText, gen, outerDiv) {
        const full = String(fullText);
        const len = full.length;
        let pos = 0;
        let charsPerStep = 1;
        if (len > 1200) charsPerStep = 2;
        if (len > 2800) charsPerStep = 3;
        if (len > 5500) charsPerStep = 5;
        const stepMs = 26;

        function tick() {
            if (!bodyEl.isConnected || gen !== assistantStreamGen) return;
            pos = Math.min(len, pos + charsPerStep);
            bodyEl.textContent = full.slice(0, pos);
            log.scrollTop = log.scrollHeight;
            if (pos < len) {
                window.setTimeout(tick, stepMs);
            } else {
                if (!bodyEl.isConnected || gen !== assistantStreamGen) return;
                bodyEl.innerHTML = linkifyAssistant(full);
                if (outerDiv) outerDiv.classList.remove('ventas-chat-msg--streaming');
                log.scrollTop = log.scrollHeight;
            }
        }
        /* Primer frame asíncrono: el panel pinta la burbuja vacía y se nota el tipeo desde el primer carácter */
        window.setTimeout(tick, 0);
    }

    /** Si había una respuesta a medio animar, la completa (p. ej. el usuario envía otra consulta). */
    function finalizeStreamingAssistantIfAny() {
        const el = log.querySelector('.ventas-chat-msg.assistant.ventas-chat-msg--streaming');
        if (!el) return;
        assistantStreamGen += 1;
        const body = el.querySelector('.ventas-chat-msg-body');
        const last = history.length ? history[history.length - 1] : null;
        if (body && last && last.role === 'assistant' && typeof last.content === 'string') {
            body.innerHTML = linkifyAssistant(last.content);
        }
        el.classList.remove('ventas-chat-msg--streaming');
        log.scrollTop = log.scrollHeight;
    }

    function append(role, text, options) {
        options = options || {};
        const div = document.createElement('div');
        div.className = 'ventas-chat-msg ' + role;
        const label = document.createElement('div');
        label.className = 'ventas-chat-label';
        label.textContent = role === 'user' ? 'Tú' : 'Asistente';
        const body = document.createElement('div');
        body.className = 'ventas-chat-msg-body';
        div.appendChild(label);
        div.appendChild(body);
        log.appendChild(div);

        if (role === 'assistant') {
            if (options && options.streamAssistant === true) {
                assistantStreamGen += 1;
                const gen = assistantStreamGen;
                div.classList.add('ventas-chat-msg--streaming');
                streamAssistantIntoBody(body, text, gen, div);
            } else {
                body.innerHTML = linkifyAssistant(text);
            }
        } else {
            body.textContent = text;
        }
        log.scrollTop = log.scrollHeight;
    }

    /**
     * @returns {boolean} true si reconstruyó el log (el caller NO debe volver a append ese mensaje).
     */
    function trimHistory() {
        let changed = false;
        while (history.length > MAX_LOCAL_MESSAGES) {
            history.shift();
            changed = true;
        }
        if (changed) {
            log.innerHTML = '';
            history.forEach(function (m) {
                append(m.role, m.content);
            });
            return true;
        }
        return false;
    }

    function saveHistory() {
        try {
            localStorage.setItem(LS_HISTORY, JSON.stringify(history));
        } catch (e) { /* ignore quota */ }
    }

    function loadHistory() {
        try {
            const raw = localStorage.getItem(LS_HISTORY);
            if (!raw) return;
            const arr = JSON.parse(raw);
            if (!Array.isArray(arr)) return;
            // Si algún mensaje del asistente tiene etiquetas genéricas "Cliente N:" es historial
            // contaminado: el LLM respondió sin llamar a la herramienta y los nombres son ficticios.
            // Limpiarlo evita que el modelo siga repitiendo ese patrón en la próxima consulta.
            const stale = arr.some(m => m && m.role === 'assistant' && hasGenericClienteLabels(m.content || ''));
            if (stale) {
                localStorage.removeItem(LS_HISTORY);
                localStorage.removeItem(LS_DRAFT);
                return;
            }
            history.length = 0;
            log.innerHTML = '';
            for (const m of arr) {
                if (!m || (m.role !== 'user' && m.role !== 'assistant') || typeof m.content !== 'string') continue;
                history.push({ role: m.role, content: m.content });
                append(m.role, m.content);
            }
        } catch (e) { /* ignore */ }
    }

    function saveDraft() {
        try {
            localStorage.setItem(LS_DRAFT, input.value);
        } catch (e) { /* ignore */ }
    }

    function loadDraft() {
        try {
            const d = localStorage.getItem(LS_DRAFT);
            if (d && input.value === '') input.value = d;
        } catch (e) { /* ignore */ }
    }

    let draftTimer = null;
    input.addEventListener('input', function () {
        if (draftTimer) clearTimeout(draftTimer);
        draftTimer = setTimeout(saveDraft, 400);
    });

    function autosizeInput() {
        try {
            input.style.height = 'auto';
            const minH = 44;
            const maxH = 120;
            const next = Math.max(minH, Math.min(maxH, input.scrollHeight || minH));
            input.style.height = next + 'px';
        } catch (e) { /* ignore */ }
    }

    input.addEventListener('input', autosizeInput);

    function openPanel() {
        panel.hidden = false;
        fab.hidden = true;
        fab.setAttribute('aria-expanded', 'true');
        errEl.hidden = true;
        renderVentasFaqSelect();
        loadDraft();
        autosizeInput();
        input.focus();
    }

    function closePanel() {
        saveDraft();
        panel.hidden = true;
        fab.hidden = false;
        fab.setAttribute('aria-expanded', 'false');
        fab.focus();
    }

    fab.addEventListener('click', openPanel);
    closeBtn.addEventListener('click', closePanel);
    clearBtn.addEventListener('click', function () {
        assistantStreamGen += 1;
        history.length = 0;
        log.innerHTML = '';
        input.value = '';
        autosizeInput();
        try {
            localStorage.removeItem(LS_HISTORY);
            localStorage.removeItem(LS_DRAFT);
        } catch (e) { /* ignore */ }
        errEl.hidden = true;
        input.focus();
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && !panel.hidden) {
            closePanel();
        }
    });

    loadHistory();
    renderVentasFaqSelect();

    let sendInFlight = false;
    async function sendMessage() {
        const text = input.value.trim();
        if (!text || sendInFlight) return;
        finalizeStreamingAssistantIfAny();
        errEl.hidden = true;
        input.value = '';
        autosizeInput();
        try { localStorage.removeItem(LS_DRAFT); } catch (e) { /* ignore */ }
        append('user', text);
        history.push({ role: 'user', content: text });
        trimHistory();
        saveHistory();
        send.disabled = true;
        sendInFlight = true;

        try {
            const res = await fetch(CHAT_API, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ messages: history }),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok || data.ok === false) {
                throw new Error(data.error || ('HTTP ' + res.status));
            }
            const reply = data.reply || '';
            history.push({ role: 'assistant', content: reply });
            saveHistory();
            if (!trimHistory()) {
                append('assistant', reply, { streamAssistant: true });
            }
        } catch (e) {
            const errMsg = String(e.message || e).toLowerCase();
            const friendly = (errMsg.includes('token') || errMsg.includes('rate limit') || errMsg.includes('tpd') || errMsg.includes('diario'))
                ? 'Un momento, estoy pensando… Se alcanzó el límite de consultas. Intentá de nuevo en unos minutos.'
                : 'Un momento, estoy procesando… Hubo un inconveniente. Por favor intentá de nuevo.';
            append('assistant', friendly);
            history.pop();
            input.value = text;
            saveDraft();
            saveHistory();
            errEl.hidden = true;
        } finally {
            send.disabled = false;
            sendInFlight = false;
        }
    }

    send.addEventListener('click', sendMessage);
    input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
})();
</script>
