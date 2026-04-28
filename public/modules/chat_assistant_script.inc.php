<?php

declare(strict_types=1);

/** Requiere `ventas_chat_config.inc.php` y variables listas. */
?>
<script>
(function () {
    const CHAT_API = <?= json_encode($ventasChatApiUrl, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) ?>;
    const VENTAS_PUBLIC_BASE = <?= json_encode($ventasPublicWebBase, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) ?>;
    const VENTAS_MODULES_WEB_BASE = <?= json_encode($ventasWebModulesBase, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) ?>;
    const LS_HISTORY = 'ventasChatbot_history_v1';
    const LS_DRAFT = 'ventasChatbot_draft_v1';
    const MAX_LOCAL_MESSAGES = 120;
    const isFull = typeof window !== 'undefined' && window.VENTAS_CHAT_FULL === true;

    const log = document.getElementById('ventasChatLog');
    const input = document.getElementById('ventasChatInput');
    const send = document.getElementById('ventasChatSend');
    const errEl = document.getElementById('ventasChatError');
    const fab = isFull ? null : document.getElementById('ventasChatFab');
    const panel = document.getElementById('ventasChatPanel');
    const closeBtn = document.getElementById('ventasChatClose');
    const clearBtn = document.getElementById('ventasChatClear');
    const faqSelect = document.getElementById('ventasChatFaqSelect');
    let faqTemplatesCache = [];
    const history = [];

    function syncFullPageHero() {
        if (!isFull) return;
        const hero = document.getElementById('chatbotHero');
        if (!hero || !log) return;
        hero.hidden = log.children && log.children.length > 0;
    }

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
            { label: 'Top clientes (valor)', text: 'Del ' + desde + ' al ' + hasta + ', muéstrame el top 10 de clientes (global) por suma de Valor.' },
            { label: 'Top productos', text: 'Del ' + desde + ' al ' + hasta + ', muéstrame el top 15 de productos por suma de Valor.' },
            { label: 'Serie mensual', text: 'Del ' + desde + ' al ' + hasta + ', muéstrame la serie mensual de la suma de Valor.' },
            { label: 'Mix por tipo de documento', text: 'Del ' + desde + ' al ' + hasta + ', muéstrame el mix de suma de Valor por tipo de documento.' },
            { label: 'NC por zona precio', text: 'Del ' + desde + ' al ' + hasta + ', muéstrame el pareto de notas de crédito (tipo 07) por zona de precio (DescriZonaPrecio).' },
            { label: 'Top en zona TACNA', text: 'Del ' + desde + ' al ' + hasta + ', muéstrame el top 10 de clientes por suma de Valor dentro de la zona de precio con prefijo TACNA.' },
            { label: 'Barras (precio)', text: 'Del ' + desde + ' al ' + hasta + ', muéstrame un gráfico de barras de suma de Valor por zona de precio (DescriZonaPrecio).' },
            { label: 'Comparar 2 meses', text: 'Compara la suma de Valor por zona de precio (DescriZonaPrecio): período A del ' + b1 + ' al ' + b2 + ' vs período B del ' + c1 + ' al ' + c2 + ' (top 10).' },
        ];
    }
    function renderVentasFaqSelect() {
        if (!faqSelect) return;
        const r = defaultReportRange();
        faqTemplatesCache = faqChipTemplates(r.desde, r.hasta);
        faqSelect.innerHTML = '';
        const ph = document.createElement('option');
        ph.value = '';
        ph.textContent = '— Selecciona una consulta —';
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

    function normalizeTextForLinkify(s) {
        return String(s).replace(/[\u200b-\u200d\ufeff\u00a0]/g, '');
    }

    function collapseDateLineBreaks(text) {
        let t = String(text);
        let prev;
        do {
            prev = t;
            t = t.replace(/(\d{4}-\d{2}-)\r?\n(\d{2})\b/g, '$1$2');
        } while (t !== prev);
        return t;
    }

    function unwrapBackticksAroundPhpUrls(text) {
        return String(text).replace(/`([^`\n]*\.php\?[^`\n]*)`/gi, '$1');
    }

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

    function linkifyAssistant(text) {
        let t = normalizeTextForLinkify(text);
        t = unwrapBackticksAroundPhpUrls(t);
        t = collapseDateLineBreaks(t);
        t = collapseMultilineQueryUrls(t);
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

    let assistantStreamGen = 0;

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
            if (log) log.scrollTop = log.scrollHeight;
            if (pos < len) {
                window.setTimeout(tick, stepMs);
            } else {
                if (!bodyEl.isConnected || gen !== assistantStreamGen) return;
                bodyEl.innerHTML = linkifyAssistant(full);
                if (outerDiv) outerDiv.classList.remove('ventas-chat-msg--streaming');
                if (log) log.scrollTop = log.scrollHeight;
            }
        }
        window.setTimeout(tick, 0);
    }

    function finalizeStreamingAssistantIfAny() {
        if (!log) return;
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
        if (!log) return;
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
        syncFullPageHero();
    }

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
        } catch (e) { /* ignore */ }
    }

    function loadHistory() {
        try {
            const raw = localStorage.getItem(LS_HISTORY);
            if (!raw) return;
            const arr = JSON.parse(raw);
            if (!Array.isArray(arr)) return;
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
    if (input) {
        input.addEventListener('input', function () {
            if (draftTimer) clearTimeout(draftTimer);
            draftTimer = setTimeout(saveDraft, 400);
        });
    }

    function autosizeInput() {
        if (!input) return;
        try {
            input.style.height = 'auto';
            const minH = isFull ? 52 : 44;
            const maxH = isFull ? 200 : 120;
            const next = Math.max(minH, Math.min(maxH, input.scrollHeight || minH));
            input.style.height = next + 'px';
        } catch (e) { /* ignore */ }
    }

    if (input) {
        input.addEventListener('input', autosizeInput);
    }

    function openPanel() {
        if (isFull) return;
        if (panel) panel.hidden = false;
        if (fab) {
            fab.hidden = true;
            fab.setAttribute('aria-expanded', 'true');
        }
        if (errEl) errEl.hidden = true;
        renderVentasFaqSelect();
        loadDraft();
        autosizeInput();
        if (input) input.focus();
    }

    function closePanel() {
        if (isFull) return;
        saveDraft();
        if (panel) panel.hidden = true;
        if (fab) {
            fab.hidden = false;
            fab.setAttribute('aria-expanded', 'false');
            fab.focus();
        }
    }

    if (fab) {
        fab.addEventListener('click', openPanel);
    }
    if (closeBtn) {
        closeBtn.addEventListener('click', closePanel);
    }
    if (clearBtn) {
        clearBtn.addEventListener('click', function () {
            assistantStreamGen += 1;
            history.length = 0;
            if (log) log.innerHTML = '';
            if (input) input.value = '';
            autosizeInput();
            try {
                localStorage.removeItem(LS_HISTORY);
                localStorage.removeItem(LS_DRAFT);
            } catch (e) { /* ignore */ }
            if (errEl) errEl.hidden = true;
            syncFullPageHero();
            if (input) input.focus();
        });
    }

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && panel && !panel.hidden) {
            if (isFull) {
                return;
            }
            closePanel();
        }
    });

    loadHistory();
    if (isFull) {
        syncFullPageHero();
    }
    renderVentasFaqSelect();
    if (isFull) {
        loadDraft();
        autosizeInput();
    }

    let sendInFlight = false;
    async function sendMessage() {
        if (!input || !send) return;
        const text = input.value.trim();
        if (!text || sendInFlight) return;
        finalizeStreamingAssistantIfAny();
        if (errEl) errEl.hidden = true;
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
            if (errEl) errEl.hidden = true;
        } finally {
            send.disabled = false;
            sendInFlight = false;
        }
    }

    if (send) {
        send.addEventListener('click', sendMessage);
    }
    if (input) {
        input.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }
})();
</script>
