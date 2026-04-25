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

?>
<style>
    :root {
        --ventas-chat-surface: #1a2332;
        --ventas-chat-border: #2d3a4d;
        --ventas-chat-text: #e7edf4;
        --ventas-chat-muted: #8b9cb3;
        --ventas-chat-accent: #3b82f6;
        --ventas-chat-accent-dim: #2563eb;
    }
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
        background: linear-gradient(135deg, var(--ventas-chat-accent) 0%, #6366f1 100%);
        color: #fff;
        box-shadow: 0 6px 24px rgba(37, 99, 235, 0.45);
        display: flex;
        align-items: center;
        justify-content: center;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .chat-fab:hover {
        transform: scale(1.05);
        box-shadow: 0 8px 28px rgba(37, 99, 235, 0.55);
    }
    .chat-fab:focus-visible {
        outline: 2px solid #93c5fd;
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
        background: var(--ventas-chat-surface);
        border: 1px solid var(--ventas-chat-border);
        border-radius: 16px;
        box-shadow: 0 16px 48px rgba(0, 0, 0, 0.5);
        overflow: hidden;
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
        background: #141c28;
    }
    .ventas-chat-msg { margin-bottom: 1rem; font-size: 0.9rem; }
    .ventas-chat-msg.user { color: #93c5fd; }
    .ventas-chat-msg.assistant { color: var(--ventas-chat-text); white-space: pre-wrap; }
    .ventas-chat-msg.assistant a,
    .ventas-chat-msg.assistant a.ventas-chat-link {
        color: #60a5fa;
        text-decoration: underline;
        word-break: break-all;
    }
    .ventas-chat-msg.assistant a:hover { color: #93c5fd; }
    .ventas-chat-msg .ventas-chat-label {
        font-size: 0.65rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--ventas-chat-muted);
        margin-bottom: 0.2rem;
    }

    .chat-panel-foot {
        padding: 0.65rem 0.75rem 0.85rem;
        border-top: 1px solid var(--ventas-chat-border);
        background: var(--ventas-chat-surface);
        flex-shrink: 0;
    }
    .chat-panel-foot .row { display: flex; gap: 0.45rem; align-items: flex-end; }
    .chat-panel-foot textarea {
        flex: 1;
        min-height: 44px;
        max-height: 120px;
        padding: 0.55rem 0.7rem;
        border-radius: 10px;
        border: 1px solid var(--ventas-chat-border);
        background: #141c28;
        color: var(--ventas-chat-text);
        resize: vertical;
        font: inherit;
        font-size: 0.9rem;
    }
    .chat-panel-foot button#ventasChatSend {
        padding: 0.55rem 0.9rem;
        border-radius: 10px;
        border: none;
        background: var(--ventas-chat-accent);
        color: #fff;
        font-weight: 600;
        cursor: pointer;
        font: inherit;
        font-size: 0.85rem;
        flex-shrink: 0;
    }
    .chat-panel-foot button#ventasChatSend:hover { background: var(--ventas-chat-accent-dim); }
    .chat-panel-foot button#ventasChatSend:disabled { opacity: 0.5; cursor: not-allowed; }

    .ventas-chat-shortcuts {
        margin: 0 0.75rem;
        font-size: 0.72rem;
        color: var(--ventas-chat-muted);
        max-height: 7.5rem;
        overflow-y: auto;
    }
    .ventas-chat-shortcuts summary {
        cursor: pointer;
        color: #93c5fd;
        font-weight: 600;
    }
    .ventas-chat-shortcuts ul { margin: 0.35rem 0 0; padding-left: 1.1rem; }
    .ventas-chat-chips-wrap {
        padding: 0.45rem 0.75rem 0.35rem;
        border-top: 1px solid var(--ventas-chat-border);
        background: #141c28;
        flex-shrink: 0;
    }
    .ventas-chat-chips-label {
        display: block;
        font-size: 0.62rem;
        color: var(--ventas-chat-muted);
        margin-bottom: 0.35rem;
        line-height: 1.35;
    }
    .ventas-chat-chips { display: flex; flex-wrap: wrap; gap: 0.35rem; }
    .ventas-chat-chip {
        border: 1px solid var(--ventas-chat-accent);
        color: #93c5fd;
        background: transparent;
        border-radius: 999px;
        padding: 0.28rem 0.55rem;
        font-size: 0.68rem;
        cursor: pointer;
        font: inherit;
        line-height: 1.2;
    }
    .ventas-chat-chip:hover { background: rgba(59, 130, 246, 0.15); }

    .chat-panel .ventas-chat-err {
        color: #f87171;
        font-size: 0.8rem;
        margin: 0 0.75rem 0.65rem;
        padding: 0 0.25rem;
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
        <span class="ventas-chat-chips-label">Preguntas frecuentes — mes calendario anterior completo. Tocá un chip, revisá o editá fechas en el cuadro y pulsá Enviar.</span>
        <div id="ventasChatChips" class="ventas-chat-chips" aria-label="Preguntas frecuentes"></div>
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
    /** Ruta absoluta desde la raíz del sitio (p. ej. /Ventas-Chatbot/public/modules/) para enlaces del asistente. */
    const VENTAS_MODULES_WEB_BASE = <?= json_encode($ventasWebModulesBase, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) ?>;
    const LS_HISTORY = 'ventasChatbot_history_v1';
    const LS_DRAFT = 'ventasChatbot_draft_v1';
    const MAX_LOCAL_MESSAGES = 40;

    const log = document.getElementById('ventasChatLog');
    const input = document.getElementById('ventasChatInput');
    const send = document.getElementById('ventasChatSend');
    const errEl = document.getElementById('ventasChatError');
    const fab = document.getElementById('ventasChatFab');
    const panel = document.getElementById('ventasChatPanel');
    const closeBtn = document.getElementById('ventasChatClose');
    const clearBtn = document.getElementById('ventasChatClear');
    const chipsMount = document.getElementById('ventasChatChips');
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
            { label: 'Totales del período', text: 'Del ' + desde + ' al ' + hasta + ': totales en ventasgeneral (filas y sumas Valor, Cantidad, Peso). Usá ventasgeneral_resumen y una línea reporte_url ventasgeneral_resumen_tabla.php con los mismos parámetros.' },
            { label: 'Top clientes (valor)', text: 'Del ' + desde + ' al ' + hasta + ': top 10 clientes globales por suma Valor. Usá ventasgeneral_top_clientes_globales y reporte_url ventas_top_clientes_global.php.' },
            { label: 'Top productos', text: 'Del ' + desde + ' al ' + hasta + ': top 15 productos por suma Valor. Usá ventasgeneral_top_productos y reporte_url ventas_top_productos.php.' },
            { label: 'Serie mensual', text: 'Del ' + desde + ' al ' + hasta + ': serie mensual de suma Valor. Usá ventasgeneral_serie_mensual_valor y reporte_url ventas_serie_mensual.php.' },
            { label: 'Mix por TDoc', text: 'Del ' + desde + ' al ' + hasta + ': mix de suma Valor por TDoc. Usá ventasgeneral_mix_tdoc y reporte_url ventas_mix_tdoc.php.' },
            { label: 'NC por zona precio', text: 'Del ' + desde + ' al ' + hasta + ': pareto NC (TDoc 07) por DescriZonaPrecio. Usá ventasgeneral_pareto_nc_zonaprecio y reporte_url pareto_nc_zona.php.' },
            { label: 'Top en zona TACNA', text: 'Del ' + desde + ' al ' + hasta + ': top 10 clientes por Valor con prefijo_descri_zona_precio TACNA. Usá ventasgeneral_top_clientes_zona_precio y reporte_url pareto_clientes_zona.php.' },
            { label: 'Barras (precio)', text: 'Del ' + desde + ' al ' + hasta + ': barras suma Valor con dimension precio. Usá ventasgeneral_barras_ventas_dimension y reporte_url ventas_barras_dimension.php.' },
            { label: 'Comparar 2 meses', text: 'Comparativo: período A del ' + b1 + ' al ' + b2 + ' vs período B del ' + c1 + ' al ' + c2 + ', dimensión precio, top 10. Usá ventasgeneral_comparativo_periodos y reporte_url ventas_comparativo.php.' },
        ];
    }
    function renderVentasChips() {
        if (!chipsMount) return;
        chipsMount.innerHTML = '';
        const r = defaultReportRange();
        faqChipTemplates(r.desde, r.hasta).forEach(function (item) {
            const b = document.createElement('button');
            b.type = 'button';
            b.className = 'ventas-chat-chip';
            b.textContent = item.label;
            b.addEventListener('click', function () {
                input.value = item.text;
                input.focus();
            });
            chipsMount.appendChild(b);
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
        const re = /(https?:\/\/[^\s<]+|(?:pareto_nc_zona|pareto_clientes_zona)(?:_tabla)?\.php\?[^\s<]+|ventasgeneral_top_clientes_nc\.php\?[^\s<]+|ventasgeneral_top_clientes_zona_precio\.php\?[^\s<]+|ventas_(?:barras_dimension|comparativo|top_productos|top_clientes_global|top_clientes_nc|mix_tdoc|barras_ruta|barras_corporativo|serie_mensual)\.php\?[^\s<]+|ventasgeneral_(?:buscar|resumen)(?:_tabla)?\.php\?[^\s<]+)/gi;
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

    function append(role, text) {
        const div = document.createElement('div');
        div.className = 'ventas-chat-msg ' + role;
        const label = document.createElement('div');
        label.className = 'ventas-chat-label';
        label.textContent = role === 'user' ? 'Tú' : 'Asistente';
        const body = document.createElement('div');
        if (role === 'assistant') {
            body.innerHTML = linkifyAssistant(text);
        } else {
            body.textContent = text;
        }
        div.appendChild(label);
        div.appendChild(body);
        log.appendChild(div);
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

    function openPanel() {
        panel.hidden = false;
        fab.hidden = true;
        fab.setAttribute('aria-expanded', 'true');
        errEl.hidden = true;
        renderVentasChips();
        loadDraft();
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
        history.length = 0;
        log.innerHTML = '';
        input.value = '';
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
    renderVentasChips();

    let sendInFlight = false;
    async function sendMessage() {
        const text = input.value.trim();
        if (!text || sendInFlight) return;
        errEl.hidden = true;
        input.value = '';
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
                append('assistant', reply);
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
