<?php

declare(strict_types=1);

/** Requiere `ventas_chat_config.inc.php` y variables listas. */
?>
<script>
(function () {
    const CHAT_API = <?= json_encode($ventasChatApiUrl, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) ?>;
    const VENTAS_PUBLIC_BASE = <?= json_encode($ventasPublicWebBase, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) ?>;
    const VENTAS_MODULES_WEB_BASE = <?= json_encode($ventasWebModulesBase, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) ?>;
    const USER_KEY_RAW = <?= json_encode($ventasChatUserKey ?? 'anon', JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) ?>;
    const USER_KEY = String(USER_KEY_RAW || 'anon')
        .toLowerCase()
        .replace(/\s+/g, '')
        .replace(/[^a-z0-9@._-]+/g, '_')
        .slice(0, 80) || 'anon';
    const NS = 'ventasChatbot:' + USER_KEY + ':';
    const LS_HISTORY = NS + 'history_v1'; // legado (una sola conversación)
    const LS_THREADS = NS + 'threads_v1';
    const LS_ACTIVE_THREAD = NS + 'active_thread_v1';
    const LS_DRAFT = NS + 'draft_v1';
    const LS_FAVS = NS + 'favs_v1';
    const LS_PREFS_CONTEXT = NS + 'prefs_context_v1';
    const LS_HIDE_TIPS = NS + 'hide_consejos_v1';
    const MAX_LOCAL_MESSAGES = 120;
    const MAX_THREADS = 40;
    const isFull = typeof window !== 'undefined' && window.VENTAS_CHAT_FULL === true;
    const THREADS_API = (typeof VENTAS_PUBLIC_BASE !== 'undefined' ? String(VENTAS_PUBLIC_BASE || '') : '') + 'api/chat_threads.php';

    const log = document.getElementById('ventasChatLog');
    const input = document.getElementById('ventasChatInput');
    const send = document.getElementById('ventasChatSend');
    const errEl = document.getElementById('ventasChatError');
    const fab = isFull ? null : document.getElementById('ventasChatFab');
    const panel = document.getElementById('ventasChatPanel');
    const closeBtn = document.getElementById('ventasChatClose');
    const clearBtn = document.getElementById('ventasChatClear');
    const faqSelect = document.getElementById('ventasChatFaqSelect');
    const threadsBtn = document.getElementById('ventasChatThreadsBtn');
    const threadsDrawer = document.getElementById('ventasChatThreadsDrawer');
    const threadsList = document.getElementById('ventasChatThreadsList');
    const threadsSearch = document.getElementById('ventasChatThreadsSearch');
    const newThreadBtn = document.getElementById('ventasChatNewThread');
    const closeThreadsBtn = document.getElementById('ventasChatCloseThreads');
    const micBtn = document.getElementById('ventasChatMic');
    const recentsBtn = document.getElementById('ventasChatRecentsBtn');
    let faqTemplatesCache = [];
    const history = [];
    let threads = [];
    let activeThreadId = '';
    let threadsQuery = '';

    // Favoritos ("Mis preguntas frecuentes")
    function loadFavs() {
        try {
            const raw = localStorage.getItem(LS_FAVS);
            const arr = raw ? safeJsonParse(raw) : null;
            if (!Array.isArray(arr)) return [];
            return arr
                .filter(x => x && typeof x.text === 'string' && x.text.trim() !== '')
                .map(x => ({ title: typeof x.title === 'string' ? x.title : '', text: String(x.text) }))
                .slice(0, 30);
        } catch (e) { return []; }
    }
    function saveFavs(arr) {
        try { localStorage.setItem(LS_FAVS, JSON.stringify(arr || [])); } catch (e) { /* ignore */ }
    }
    function addFavFromInput() {
        if (!input) return;
        const t = String(input.value || '').trim();
        if (!t) return;
        const title = t.replace(/\s+/g, ' ').slice(0, 42) + (t.length > 42 ? '…' : '');
        const favs = loadFavs();
        const exists = favs.some(f => (f && String(f.text).trim()) === t);
        if (!exists) {
            favs.unshift({ title: title || 'Frecuente', text: t });
            saveFavs(favs.slice(0, 30));
        }
        renderVentasFaqSelect();
    }

    function nowTs() { return Date.now(); }
    function safeJsonParse(raw) {
        try { return JSON.parse(raw); } catch (e) { return null; }
    }
    function makeId() {
        return 't_' + nowTs().toString(36) + '_' + Math.random().toString(36).slice(2, 9);
    }
    function firstUserTitle(msgs) {
        const m = (Array.isArray(msgs) ? msgs : []).find(x => x && x.role === 'user' && typeof x.content === 'string' && x.content.trim() !== '');
        if (!m) return 'Nuevo chat';
        const t = m.content.trim().replace(/\s+/g, ' ');
        return t.length > 42 ? (t.slice(0, 39) + '…') : t;
    }

    function loadThreads() {
        let out = [];
        try {
            const raw = localStorage.getItem(LS_THREADS);
            const arr = raw ? safeJsonParse(raw) : null;
            if (Array.isArray(arr)) out = arr;
        } catch (e) { /* ignore */ }
        out = out
            .filter(t => t && typeof t.id === 'string')
            .map(t => ({
                id: String(t.id),
                title: typeof t.title === 'string' ? t.title : 'Nuevo chat',
                createdAt: typeof t.createdAt === 'number' ? t.createdAt : nowTs(),
                updatedAt: typeof t.updatedAt === 'number' ? t.updatedAt : (typeof t.createdAt === 'number' ? t.createdAt : nowTs()),
                messages: Array.isArray(t.messages) ? t.messages.filter(m => m && (m.role === 'user' || m.role === 'assistant') && typeof m.content === 'string') : [],
            }));
        out.sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
        if (out.length > MAX_THREADS) out = out.slice(0, MAX_THREADS);
        return out;
    }

    async function serverListThreads(query) {
        const q = (query || '').trim();
        const url = THREADS_API + (q ? ('?q=' + encodeURIComponent(q)) : '');
        const res = await fetch(url, { method: 'GET', credentials: 'same-origin' });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || !data || data.ok !== true || !Array.isArray(data.threads)) throw new Error('server');
        return data.threads.map(t => ({
            id: String(t.id || ''),
            title: String(t.title || 'Nuevo chat'),
            updatedAt: Date.parse(String(t.updatedAt || '')) || nowTs(),
            createdAt: nowTs(),
            messages: [], // lazy-load
        })).filter(t => t.id !== '');
    }

    async function serverLoadThread(clientId) {
        const url = THREADS_API + '?thread=' + encodeURIComponent(String(clientId || ''));
        const res = await fetch(url, { method: 'GET', credentials: 'same-origin' });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || !data || data.ok !== true) throw new Error('server');
        const t = data.thread;
        if (!t) return null;
        return {
            id: String(t.id || ''),
            title: String(t.title || 'Nuevo chat'),
            createdAt: Date.parse(String(t.createdAt || '')) || nowTs(),
            updatedAt: Date.parse(String(t.updatedAt || '')) || nowTs(),
            messages: Array.isArray(t.messages) ? t.messages.map(m => ({ role: m.role, content: m.content })) : [],
        };
    }

    async function serverSaveThread(thread) {
        const payload = {
            id: thread.id,
            title: thread.title || 'Nuevo chat',
            messages: Array.isArray(thread.messages) ? thread.messages : [],
        };
        const res = await fetch(THREADS_API, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || !data || data.ok !== true) throw new Error('server');
        return true;
    }

    async function serverDeleteThread(clientId) {
        const res = await fetch(THREADS_API, {
            method: 'DELETE',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: String(clientId || '') }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || !data || data.ok !== true) throw new Error('server');
        return true;
    }
    function saveThreads() {
        try {
            localStorage.setItem(LS_THREADS, JSON.stringify(threads));
        } catch (e) { /* ignore */ }
    }
    function loadActiveThreadId() {
        try {
            const v = localStorage.getItem(LS_ACTIVE_THREAD);
            return v ? String(v) : '';
        } catch (e) { return ''; }
    }
    function setActiveThreadId(id) {
        activeThreadId = String(id || '');
        try {
            localStorage.setItem(LS_ACTIVE_THREAD, activeThreadId);
        } catch (e) { /* ignore */ }
    }

    function migrateLegacyHistoryIfAny() {
        // Si el usuario ya tenía historial "antiguo", lo convertimos a un thread.
        let legacy = null;
        try {
            const raw = localStorage.getItem(LS_HISTORY);
            if (raw) legacy = safeJsonParse(raw);
        } catch (e) { legacy = null; }
        if (!Array.isArray(legacy) || legacy.length === 0) return;
        const stale = legacy.some(m => m && m.role === 'assistant' && hasGenericClienteLabels(m.content || ''));
        if (stale) {
            try { localStorage.removeItem(LS_HISTORY); } catch (e) { /* ignore */ }
            return;
        }
        const tid = makeId();
        threads.unshift({
            id: tid,
            title: firstUserTitle(legacy),
            createdAt: nowTs(),
            updatedAt: nowTs(),
            messages: legacy.filter(m => m && (m.role === 'user' || m.role === 'assistant') && typeof m.content === 'string'),
        });
        if (threads.length > MAX_THREADS) threads = threads.slice(0, MAX_THREADS);
        saveThreads();
        setActiveThreadId(tid);
        try { localStorage.removeItem(LS_HISTORY); } catch (e) { /* ignore */ }
    }

    function formatDate(ts) {
        try {
            const d = new Date(ts);
            const dd = String(d.getDate()).padStart(2, '0');
            const mm = String(d.getMonth() + 1).padStart(2, '0');
            const yy = d.getFullYear();
            return dd + '/' + mm + '/' + yy;
        } catch (e) {
            return '';
        }
    }

    function dayBucketLabel(ts) {
        const n = typeof ts === 'number' ? ts : parseInt(String(ts), 10);
        const d = new Date(n);
        if (isNaN(d.getTime())) return 'Anteriores';
        const now = new Date();
        const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
        const startYesterday = startToday - 86400000;
        const startWeek = startToday - 7 * 86400000;
        const t = d.getTime();
        if (t >= startToday) return 'Hoy';
        if (t >= startYesterday) return 'Ayer';
        if (t >= startWeek) return 'Últimos 7 días';
        return 'Anteriores';
    }

    function buildChatRequestBody() {
        const body = { messages: history };
        const u = loadUserContextForApi();
        if (u !== '') body.user_context = u;
        return body;
    }
    function loadPrefsContextRaw() {
        try {
            return localStorage.getItem(LS_PREFS_CONTEXT) || '';
        } catch (e) {
            return '';
        }
    }
    function savePrefsContextRaw(s) {
        try {
            localStorage.setItem(LS_PREFS_CONTEXT, String(s || '').slice(0, 4000));
        } catch (e) { /* ignore */ }
    }
    function loadUserContextForApi() {
        const t = loadPrefsContextRaw().trim();
        return t.length > 800 ? t.slice(0, 800) : t;
    }
    function applyShortcutsVisibility() {
        const secciones = document.querySelectorAll('.ventas-chat-shortcuts');
        let hide = false;
        try {
            hide = localStorage.getItem(LS_HIDE_TIPS) === '1';
        } catch (e) { /* ignore */ }
        secciones.forEach(function (el) {
            el.classList.toggle('ventas-chat-shortcuts--user-hidden', hide);
        });
    }
    function closeHeadMenu() {
        const hm = document.getElementById('ventasChatHeadMenu');
        if (hm) hm.removeAttribute('open');
    }

    let prefsDialog = null;
    function ensurePrefsDialog() {
        if (prefsDialog) return prefsDialog;
        prefsDialog = document.createElement('dialog');
        prefsDialog.id = 'ventasChatPrefsDialog';
        prefsDialog.className = 'ventas-chat-prefs-dialog';
        prefsDialog.innerHTML = ''
            + '<div class="ventas-chat-prefs-inner">'
            + '<h3 class="ventas-chat-prefs-title">Personalización</h3>'
            + '<p class="ventas-chat-prefs-lead">Opcional: el asistente tendrá en cuenta esto (tono, formato y prioridades). No reemplaza datos ni permite inventar cifras.</p>'
            + '<label class="ventas-chat-prefs-label" for="ventasChatPrefsTextarea">Instrucciones personalizadas</label>'
            + '<textarea id="ventasChatPrefsTextarea" class="ventas-chat-prefs-textarea" rows="5" maxlength="2000" placeholder="Ej.: Responde en pocas frases. Si hay tablas, resume primero el hallazgo principal."></textarea>'
            + '<label class="ventas-chat-prefs-check"><input type="checkbox" id="ventasChatPrefsHideTips"> Ocultar «Consejos para tu consulta» en este chat</label>'
            + '<div class="ventas-chat-prefs-actions">'
            + '<button type="button" class="ventas-chat-prefs-btn ventas-chat-prefs-btn--ghost" data-prefs-cancel>Cancelar</button>'
            + '<button type="button" class="ventas-chat-prefs-btn ventas-chat-prefs-btn--primary" data-prefs-save>Guardar</button>'
            + '</div></div>';
        document.body.appendChild(prefsDialog);
        prefsDialog.querySelector('[data-prefs-cancel]').addEventListener('click', function () {
            prefsDialog.close();
        });
        prefsDialog.querySelector('[data-prefs-save]').addEventListener('click', function () {
            const ta = prefsDialog.querySelector('#ventasChatPrefsTextarea');
            const ck = prefsDialog.querySelector('#ventasChatPrefsHideTips');
            savePrefsContextRaw(ta ? ta.value : '');
            try {
                localStorage.setItem(LS_HIDE_TIPS, ck && ck.checked ? '1' : '0');
            } catch (e) { /* ignore */ }
            applyShortcutsVisibility();
            prefsDialog.close();
        });
        return prefsDialog;
    }
    function openPrefsDialog() {
        const d = ensurePrefsDialog();
        const ta = d.querySelector('#ventasChatPrefsTextarea');
        const ck = d.querySelector('#ventasChatPrefsHideTips');
        if (ta) ta.value = loadPrefsContextRaw();
        try {
            if (ck) ck.checked = localStorage.getItem(LS_HIDE_TIPS) === '1';
        } catch (e2) {
            if (ck) ck.checked = false;
        }
        if (typeof d.showModal === 'function') d.showModal();
        if (ta) ta.focus();
    }

    function clearActiveConversationMaybeConfirm() {
        if (history.length > 0) {
            if (!window.confirm('¿Borrar todos los mensajes de esta conversación? Puedes abrir otras desde «Chats recientes».')) {
                return;
            }
        }
        clearUiChat();
        if (input) input.value = '';
        autosizeInput();
        try { localStorage.removeItem(LS_DRAFT); } catch (e) { /* ignore */ }
        persistActiveThreadFromHistory();
        if (input) input.focus();
    }

    function openThreadsDrawer() {
        if (!threadsDrawer) return;
        threadsDrawer.hidden = false;
        threadsDrawer.setAttribute('data-open', '1');
        renderThreadsList();
        if (threadsSearch) threadsSearch.focus();
    }
    function closeThreadsDrawer() {
        if (!threadsDrawer) return;
        threadsDrawer.removeAttribute('data-open');
        threadsDrawer.hidden = true;
    }
    function threadMatchesQuery(t, q) {
        if (!q) return true;
        const qq = q.toLowerCase().trim();
        if (!qq) return true;
        const title = String(t.title || '').toLowerCase();
        if (title.includes(qq)) return true;
        const msgs = Array.isArray(t.messages) ? t.messages : [];
        for (let i = 0; i < Math.min(10, msgs.length); i++) {
            const m = msgs[i];
            if (m && typeof m.content === 'string' && m.content.toLowerCase().includes(qq)) return true;
        }
        return false;
    }

    function renderThreadsList() {
        if (!threadsList) return;
        threadsList.innerHTML = '';
        const q = String(threadsQuery || '').trim();
        const filtered = (threads || []).filter(t => threadMatchesQuery(t, q));
        if (!filtered || filtered.length === 0) {
            const p = document.createElement('p');
            p.style.margin = '0.5rem';
            p.style.opacity = '0.75';
            p.textContent = q ? 'No hay resultados para tu búsqueda.' : 'Aún no hay conversaciones. Usá «Nueva conversación» o enviá un mensaje para crear una.';
            threadsList.appendChild(p);
            return;
        }

        const buckets = { Hoy: [], Ayer: [], 'Últimos 7 días': [], Anteriores: [] };
        const order = ['Hoy', 'Ayer', 'Últimos 7 días', 'Anteriores'];
        filtered.forEach(function (t) {
            const b = dayBucketLabel(t.updatedAt);
            if (buckets[b]) buckets[b].push(t);
        });

        function sectionLabel(txt) {
            const s = document.createElement('div');
            s.className = 'ventas-chat-drawer-section';
            s.textContent = txt;
            threadsList.appendChild(s);
        }

        function renderThreadItem(t) {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'ventas-chat-thread';
            btn.setAttribute('role', 'listitem');
            btn.dataset.threadId = t.id;
            btn.setAttribute('aria-current', t.id === activeThreadId ? 'true' : 'false');

            const row = document.createElement('div');
            row.className = 'ventas-chat-thread-row';

            const title = document.createElement('div');
            title.className = 'ventas-chat-thread-title';
            title.textContent = t.title || 'Nuevo chat';

            const del = document.createElement('button');
            del.type = 'button';
            del.className = 'ventas-chat-thread-del';
            del.title = 'Eliminar conversación';
            del.setAttribute('aria-label', 'Eliminar conversación');
            del.textContent = '×';
            del.addEventListener('click', function (ev) {
                ev.preventDefault();
                ev.stopPropagation();
                deleteThread(t.id);
            });

            row.appendChild(title);
            row.appendChild(del);

            const meta = document.createElement('div');
            meta.className = 'ventas-chat-thread-meta';
            const n = Array.isArray(t.messages) ? t.messages.length : 0;
            meta.textContent = (formatDate(t.updatedAt) || '') + (n ? (' · ' + n + ' mensajes') : '');

            btn.appendChild(row);
            btn.appendChild(meta);

            btn.addEventListener('click', function () {
                switchToThread(t.id);
                closeThreadsDrawer();
                if (input) input.focus();
            });
            threadsList.appendChild(btn);
        }

        order.forEach(function (label) {
            const arr = buckets[label];
            if (!arr.length) return;
            sectionLabel(label);
            arr.forEach(renderThreadItem);
        });
    }

    function clearUiChat() {
        assistantStreamGen += 1;
        history.length = 0;
        if (log) log.innerHTML = '';
        if (errEl) errEl.hidden = true;
        syncFullPageHero();
    }

    function ensureAtLeastOneThread() {
        if (threads.length > 0) return;
        const tid = makeId();
        threads = [{
            id: tid,
            title: 'Nuevo chat',
            createdAt: nowTs(),
            updatedAt: nowTs(),
            messages: [],
        }];
        saveThreads();
        setActiveThreadId(tid);
    }

    function persistActiveThreadFromHistory() {
        if (!activeThreadId) return;
        const idx = threads.findIndex(t => t && t.id === activeThreadId);
        if (idx < 0) return;
        const t = threads[idx];
        t.messages = history.slice(0);
        t.updatedAt = nowTs();
        t.title = firstUserTitle(t.messages);
        // Move to top
        threads.splice(idx, 1);
        threads.unshift(t);
        if (threads.length > MAX_THREADS) threads = threads.slice(0, MAX_THREADS);
        saveThreads();
        renderThreadsList();
        // Best-effort: sincroniza con servidor.
        serverSaveThread({ id: t.id, title: t.title, messages: t.messages }).catch(() => {});
    }

    function switchToThread(id) {
        const t = threads.find(x => x && x.id === id);
        if (!t) return;
        setActiveThreadId(t.id);
        clearUiChat();
        if (input) input.value = '';
        autosizeInput();
        try { localStorage.removeItem(LS_DRAFT); } catch (e) { /* ignore */ }
        (async function () {
            // Lazy-load desde servidor si no hay mensajes en cache local.
            if ((!t.messages || t.messages.length === 0) && t.id) {
                try {
                    const full = await serverLoadThread(t.id);
                    if (full && Array.isArray(full.messages)) {
                        t.messages = full.messages;
                        t.title = full.title || t.title;
                        t.updatedAt = full.updatedAt || t.updatedAt;
                        saveThreads();
                    }
                } catch (e) { /* ignore */ }
            }
            for (const m of (t.messages || [])) {
                // No enviar al LLM respuestas hallucinated (Cliente 1/2/3…),
                // pero sí mostrarlas en pantalla para que el usuario vea qué pasó.
                const isStale = m.role === 'assistant' && hasGenericClienteLabels(m.content || '');
                if (!isStale) {
                    history.push({ role: m.role, content: m.content });
                }
                append(m.role, m.content);
            }
            renderThreadsList();
        })();
    }

    function createNewThread() {
        const tid = makeId();
        const t = { id: tid, title: 'Nuevo chat', createdAt: nowTs(), updatedAt: nowTs(), messages: [] };
        threads.unshift(t);
        if (threads.length > MAX_THREADS) threads = threads.slice(0, MAX_THREADS);
        saveThreads();
        setActiveThreadId(tid);
        clearUiChat();
        if (input) {
            input.value = '';
            autosizeInput();
            input.focus();
        }
        try { localStorage.removeItem(LS_DRAFT); } catch (e) { /* ignore */ }
        renderThreadsList();
        serverSaveThread({ id: t.id, title: t.title, messages: [] }).catch(() => {});
    }

    function deleteThread(id) {
        const idx = threads.findIndex(t => t && t.id === id);
        if (idx < 0) return;
        const wasActive = threads[idx].id === activeThreadId;
        threads.splice(idx, 1);
        if (threads.length === 0) {
            ensureAtLeastOneThread();
        }
        saveThreads();
        serverDeleteThread(id).catch(() => {});
        if (wasActive) {
            setActiveThreadId(threads[0].id);
            switchToThread(threads[0].id);
        }
        renderThreadsList();
    }

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
            { label: 'Totales del período', text: 'Del ' + desde + ' al ' + hasta + ', ¿cuáles son los totales de ventas (líneas de detalle, importe total en soles, unidades y peso)?' },
            { label: 'Top clientes (importe)', text: 'Del ' + desde + ' al ' + hasta + ', muéstrame el top 10 de clientes a nivel global por importe total facturado (soles).' },
            { label: 'Top productos', text: 'Del ' + desde + ' al ' + hasta + ', muéstrame el top 15 de productos por importe total (soles).' },
            { label: 'Serie mensual', text: 'Del ' + desde + ' al ' + hasta + ', muéstrame la serie mensual del importe total (soles).' },
            { label: 'Mix por tipo de documento', text: 'Del ' + desde + ' al ' + hasta + ', muéstrame el mix del importe total (soles) por tipo de documento.' },
            { label: 'NC por zona precio', text: 'Del ' + desde + ' al ' + hasta + ', muéstrame el pareto de notas de crédito (tipo 07) por zona de precio (DescripcionZonaPrecio).' },
            { label: 'Top en zona TACNA', text: 'Del ' + desde + ' al ' + hasta + ', muéstrame el top 10 de clientes por importe total (soles) dentro de la zona de precio con prefijo TACNA.' },
            { label: 'Barras (precio)', text: 'Del ' + desde + ' al ' + hasta + ', muéstrame un gráfico de barras del importe total (soles) por zona de precio (DescripcionZonaPrecio).' },
            { label: 'Barras por ruta comercial', text: 'Del ' + desde + ' al ' + hasta + ', muéstrame el top 10 de rutas comerciales por importe total (soles).' },
            { label: 'Barras por corporativo', text: 'Del ' + desde + ' al ' + hasta + ', muéstrame el top 10 de corporativos por importe total (soles).' },
            { label: 'Comparar 2 meses', text: 'Compará el importe total (soles) por zona de precio (DescripcionZonaPrecio): período A del ' + b1 + ' al ' + b2 + ' vs período B del ' + c1 + ' al ' + c2 + ' (top 10).' },
            { label: 'Proyección próximos 3 meses', text: 'Del ' + desde + ' al ' + hasta + ', proyectá las ventas para los próximos 3 meses basándote en la tendencia histórica.' },
            { label: 'Totales en provincia AREQUIPA', text: 'Del ' + desde + ' al ' + hasta + ', muéstrame el resumen de ventas (líneas, importe en soles, unidades) filtrando solo la provincia de AREQUIPA.' },
            { label: 'Totales en provincia TACNA', text: 'Del ' + desde + ' al ' + hasta + ', muéstrame el resumen de ventas (líneas, importe en soles, unidades) filtrando solo la provincia de TACNA.' },
            { label: 'Solo Boletas de Venta', text: 'Del ' + desde + ' al ' + hasta + ', muéstrame el resumen de ventas considerando solo las Boletas de Venta.' },
            { label: 'Solo Facturas', text: 'Del ' + desde + ' al ' + hasta + ', muéstrame el resumen de ventas considerando solo las Facturas.' },
            { label: 'Top clientes zona AQP', text: 'Del ' + desde + ' al ' + hasta + ', muéstrame el top 10 de clientes por importe total (soles) dentro de la zona de precio con prefijo AQP.' },
            { label: 'Top clientes zona MOQUEGUA', text: 'Del ' + desde + ' al ' + hasta + ', muéstrame el top 10 de clientes por importe total (soles) dentro de la zona de precio con prefijo MOQUEGUA.' },
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

        const favs = loadFavs();
        if (favs.length) {
            const og = document.createElement('optgroup');
            og.label = 'Mis preguntas frecuentes';
            favs.forEach(function (f, i) {
                const o = document.createElement('option');
                o.value = 'fav:' + String(i);
                o.textContent = f.title || ('Frecuente ' + (i + 1));
                og.appendChild(o);
            });
            faqSelect.appendChild(og);
        }

        const og2 = document.createElement('optgroup');
        og2.label = 'Sugerencias';
        faqTemplatesCache.forEach(function (item, i) {
            const o = document.createElement('option');
            o.value = 'tpl:' + String(i);
            o.textContent = item.label;
            og2.appendChild(o);
        });
        faqSelect.appendChild(og2);
        faqSelect.selectedIndex = 0;
    }

    if (faqSelect) {
        faqSelect.addEventListener('change', function () {
            const v = faqSelect.value;
            if (v === '') return;
            if (String(v).startsWith('tpl:')) {
                const idx = parseInt(String(v).slice(4), 10);
                if (!isNaN(idx) && faqTemplatesCache[idx]) input.value = faqTemplatesCache[idx].text;
            } else if (String(v).startsWith('fav:')) {
                const idx = parseInt(String(v).slice(4), 10);
                const favs = loadFavs();
                if (!isNaN(idx) && favs[idx]) input.value = favs[idx].text;
            }
            if (input && input.value) {
                input.focus();
                autosizeInput();
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

    /** Montos mostrados como soles (S/), no dólares ($), en la vista del chat. */
    function formatImportesSoles(text) {
        let s = String(text || '');
        // $ 1,234.56 o $1234567.89 (evita tocar URLs: no hay espacio tras $ en http)
        s = s.replace(/\$\s*([\d]{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)/g, 'S/ $1');
        return s;
    }

    function linkifyAssistant(text) {
        let t = normalizeTextForLinkify(text);
        t = unwrapBackticksAroundPhpUrls(t);
        t = collapseDateLineBreaks(t);
        t = collapseMultilineQueryUrls(t);
        t = formatImportesSoles(t);
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

    function splitAssistantAnswerAndSql(fullText) {
        const s = String(fullText || '');
        if (!s) return { head: '', tail: '' };
        const markers = [
            '\n\nSELECT ',
            '\nSELECT ',
            '\n\nSentencia SQL ejecutada',
            '\nSentencia SQL ejecutada',
            '\n\nSentencia SQL',
            '\nSentencia SQL',
            '\n\n---\n',
        ];
        let idx = -1;
        for (let i = 0; i < markers.length; i++) {
            const m = markers[i];
            const at = s.indexOf(m);
            if (at >= 0 && (idx < 0 || at < idx)) idx = at;
        }
        if (idx < 0) return { head: s, tail: '' };
        const head = s.slice(0, idx).replace(/\s+$/g, '');
        const tail = s.slice(idx).replace(/^\s+/g, '');
        // Evita “cortar” demasiado pronto si el texto solo menciona SELECT como palabra.
        if (tail.length < 20) return { head: s, tail: '' };
        return { head: head, tail: tail };
    }

    function renderAssistantHtml(fullText) {
        const parts = splitAssistantAnswerAndSql(fullText);
        if (!parts.tail) return linkifyAssistant(parts.head);
        return (
            linkifyAssistant(parts.head) +
            '\n\n' +
            '<div class="ventas-chat-sql-block">' +
            linkifyAssistant(parts.tail) +
            '</div>'
        );
    }

    let assistantStreamGen = 0;

    function streamAssistantIntoBody(bodyEl, fullText, gen, outerDiv) {
        const full = String(fullText);
        const parts = splitAssistantAnswerAndSql(full);
        const head = parts.head || '';
        const len = head.length;
        let pos = 0;
        let charsPerStep = 1;
        if (len > 1200) charsPerStep = 2;
        if (len > 2800) charsPerStep = 3;
        if (len > 5500) charsPerStep = 5;
        const stepMs = 26;

        function tick() {
            if (!bodyEl.isConnected || gen !== assistantStreamGen) return;
            pos = Math.min(len, pos + charsPerStep);
            bodyEl.textContent = formatImportesSoles(head.slice(0, pos));
            if (log) log.scrollTop = log.scrollHeight;
            if (pos < len) {
                window.setTimeout(tick, stepMs);
            } else {
                if (!bodyEl.isConnected || gen !== assistantStreamGen) return;
                // La respuesta (head) ya terminó de “escribirse”.
                // El anexo SQL (tail) aparece de golpe sin animación.
                bodyEl.innerHTML = renderAssistantHtml(full);
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
            body.innerHTML = renderAssistantHtml(last.content);
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
                body.innerHTML = renderAssistantHtml(text);
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
        // Compat: mantiene el legacy por si algo externo aún lo usa, pero el origen de verdad es threads.
        try { localStorage.setItem(LS_HISTORY, JSON.stringify(history)); } catch (e) { /* ignore */ }
        persistActiveThreadFromHistory();
    }

    function getThreadIdFromUrl() {
        try {
            const q = new URLSearchParams(window.location.search || '');
            const t = String(q.get('thread') || '').trim();
            return t !== '' ? t : '';
        } catch (e) {
            return '';
        }
    }

    function resolveActiveThreadIdFromState() {
        const urlT = getThreadIdFromUrl();
        if (urlT && threads.some(t => t && t.id === urlT)) {
            return urlT;
        }
        const stored = loadActiveThreadId();
        if (stored && threads.some(t => t && t.id === stored)) {
            return stored;
        }
        return threads[0] && threads[0].id ? threads[0].id : '';
    }

    function purgeLocalVentasChatStorageForCurrentUser() {
        try {
            const prefix = NS;
            const toRemove = [];
            for (let i = 0; i < localStorage.length; i++) {
                const k = localStorage.key(i);
                if (k && k.startsWith(prefix)) {
                    toRemove.push(k);
                }
            }
            for (let j = 0; j < toRemove.length; j++) {
                try {
                    localStorage.removeItem(toRemove[j]);
                } catch (e) { /* ignore */ }
            }
        } catch (e) { /* ignore */ }
    }

    async function serverPurgeAllThreadsForUser() {
        const res = await fetch(THREADS_API, {
            method: 'DELETE',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ purge_all: true }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || !data || data.ok !== true) {
            const msg = (data && data.error) ? String(data.error) : ('HTTP ' + res.status);
            throw new Error(msg);
        }
        return true;
    }

    function resetAssistantStateAfterStorageClear() {
        threads = [];
        activeThreadId = '';
        setActiveThreadId('');
        clearUiChat();
        if (input) {
            input.value = '';
            autosizeInput();
        }
    }

    function clearLocalAssistantCacheAndReload() {
        if (!window.confirm('Se borrarán borradores, favoritos locales, chats en caché y preferencias del asistente guardadas en ESTE navegador. Si tenés chats guardados en el servidor, se volverán a descargar después.\n\n¿Continuar?')) {
            return;
        }
        closeHeadMenu();
        closeThreadsDrawer();
        purgeLocalVentasChatStorageForCurrentUser();
        resetAssistantStateAfterStorageClear();
        loadHistory();
        renderVentasFaqSelect();
    }

    async function purgeServerThreadsAndLocalThenReload() {
        if (!window.confirm('Se eliminarán TODAS tus conversaciones del asistente en la base de datos del servidor y la copia local en este navegador. La lista «Preguntas al chatbot» quedará vacía hasta nuevas consultas.\n\n¿Seguro?')) {
            return;
        }
        if (!window.confirm('Confirmación final: borrar todo el historial de chat en servidor y navegador.')) {
            return;
        }
        closeHeadMenu();
        closeThreadsDrawer();
        try {
            await serverPurgeAllThreadsForUser();
        } catch (e) {
            window.alert('No se pudo borrar en el servidor: ' + (e.message || e) + '. Revisá la conexión o probá de nuevo.');
            return;
        }
        purgeLocalVentasChatStorageForCurrentUser();
        resetAssistantStateAfterStorageClear();
        loadHistory();
        renderVentasFaqSelect();
    }

    function loadHistory() {
        threads = loadThreads();
        migrateLegacyHistoryIfAny();
        threads = loadThreads(); // recargar tras migración
        // Mejor esfuerzo: reemplaza con threads del servidor (si hay login + tablas).
        (async function () {
            try {
                const srv = await serverListThreads('');
                if (srv && srv.length) {
                    threads = srv;
                    saveThreads();
                }
            } catch (e) { /* ignore */ }
            ensureAtLeastOneThread();
            const tid = resolveActiveThreadIdFromState();
            if (tid) {
                setActiveThreadId(tid);
                switchToThread(tid);
            }
        })();
        ensureAtLeastOneThread();
        const tid0 = resolveActiveThreadIdFromState();
        if (tid0) {
            setActiveThreadId(tid0);
            switchToThread(tid0);
        }
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
        applyShortcutsVisibility();
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
            clearActiveConversationMaybeConfirm();
        });
    }

    if (threadsBtn) {
        threadsBtn.addEventListener('click', function (ev) {
            // Si el botón está configurado como acceso directo (por ejemplo a “Preguntas al chatbot”),
            // navegamos y no abrimos el drawer.
            const href = (threadsBtn.getAttribute && threadsBtn.getAttribute('data-href')) ? String(threadsBtn.getAttribute('data-href') || '').trim() : '';
            if (href !== '') {
                try { ev.preventDefault(); } catch (e) {}
                window.location.href = href;
                return;
            }
            if (!threadsDrawer || threadsDrawer.hidden) openThreadsDrawer();
            else closeThreadsDrawer();
        });
    }
    if (threadsDrawer) {
        threadsDrawer.addEventListener('click', function (ev) {
            const t = ev.target;
            if (!t) return;
            if (t && t.getAttribute && t.getAttribute('data-action') === 'close') closeThreadsDrawer();
        });
    }
    if (threadsSearch) {
        threadsSearch.addEventListener('input', function () {
            threadsQuery = String(threadsSearch.value || '');
            renderThreadsList();
        });
    }
    if (closeThreadsBtn) {
        closeThreadsBtn.addEventListener('click', closeThreadsDrawer);
    }
    if (newThreadBtn) {
        newThreadBtn.addEventListener('click', function () {
            createNewThread();
            closeThreadsDrawer();
        });
    }
    if (recentsBtn) {
        recentsBtn.addEventListener('click', function () {
            openThreadsDrawer();
        });
    }
    const menuNew = document.getElementById('ventasChatMenuNew');
    const menuClear = document.getElementById('ventasChatMenuClear');
    const menuPrefs = document.getElementById('ventasChatMenuPrefs');
    if (menuNew) {
        menuNew.addEventListener('click', function () {
            closeHeadMenu();
            createNewThread();
            closeThreadsDrawer();
            if (input) input.focus();
        });
    }
    if (menuClear) {
        menuClear.addEventListener('click', function () {
            closeHeadMenu();
            clearActiveConversationMaybeConfirm();
        });
    }
    if (menuPrefs) {
        menuPrefs.addEventListener('click', function () {
            closeHeadMenu();
            openPrefsDialog();
        });
    }
    const menuClearLocal = document.getElementById('ventasChatMenuClearLocal');
    const menuPurgeAll = document.getElementById('ventasChatMenuPurgeAll');
    if (menuClearLocal) {
        menuClearLocal.addEventListener('click', function () {
            clearLocalAssistantCacheAndReload();
        });
    }
    if (menuPurgeAll) {
        menuPurgeAll.addEventListener('click', function () {
            purgeServerThreadsAndLocalThenReload();
        });
    }
    document.addEventListener('click', function (ev) {
        const hm = document.getElementById('ventasChatHeadMenu');
        if (!hm || !hm.hasAttribute('open')) return;
        const t = ev.target;
        if (t && hm.contains(t)) return;
        hm.removeAttribute('open');
    });

    // Guardar como "Mis frecuentes" con Alt+Enter (o Ctrl/Cmd+S ya soportado abajo)
    if (input) {
        input.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && e.altKey) {
                e.preventDefault();
                addFavFromInput();
            }
        });
    }

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            const dlg = document.getElementById('ventasChatPrefsDialog');
            if (dlg && dlg.open) {
                e.preventDefault();
                dlg.close();
                return;
            }
            const hm = document.getElementById('ventasChatHeadMenu');
            if (hm && hm.hasAttribute('open')) {
                e.preventDefault();
                hm.removeAttribute('open');
                return;
            }
        }
        if (e.key === 'Escape' && panel && !panel.hidden) {
            if (isFull) {
                return;
            }
            closePanel();
        }
        if (e.key === 'Escape' && threadsDrawer && !threadsDrawer.hidden) {
            closeThreadsDrawer();
        }
    });

    loadHistory();
    applyShortcutsVisibility();
    if (isFull) {
        syncFullPageHero();
    }
    renderVentasFaqSelect();
    // Dictado por voz (si está disponible)
    (function setupDictation() {
        if (!micBtn) return;
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SR) {
            micBtn.hidden = true;
            return;
        }
        let recog = null;
        let listening = false;
        let baseBeforeDictation = '';
        let finalDictated = '';

        function setListening(on) {
            listening = !!on;
            micBtn.setAttribute('aria-pressed', listening ? 'true' : 'false');
            micBtn.title = listening ? 'Detener dictado' : 'Dictado por voz';
        }

        function ensure() {
            if (recog) return recog;
            recog = new SR();
            recog.lang = 'es-PE';
            recog.interimResults = true;
            recog.continuous = false;
            recog.maxAlternatives = 1;
            recog.onresult = function (ev) {
                try {
                    if (!input) return;
                    // Evita duplicados: SpeechRecognition emite resultados parciales acumulativos.
                    // Construimos "final" + "interim" y actualizamos el input sin concatenar cada evento.
                    let interim = '';
                    for (let i = ev.resultIndex; i < ev.results.length; i++) {
                        const r = ev.results[i];
                        const t = (r && r[0] && r[0].transcript) ? String(r[0].transcript) : '';
                        if (!t) continue;
                        if (r.isFinal) {
                            finalDictated = (finalDictated + ' ' + t).replace(/\s+/g, ' ').trim();
                        } else {
                            interim += t;
                        }
                    }
                    interim = String(interim || '').replace(/\s+/g, ' ').trim();
                    const base = String(baseBeforeDictation || '').trim();
                    const composed = (base + ' ' + finalDictated + ' ' + interim).replace(/\s+/g, ' ').trim();
                    input.value = composed;
                    autosizeInput();
                } catch (e) { /* ignore */ }
            };
            recog.onerror = function () { setListening(false); };
            recog.onend = function () { setListening(false); };
            return recog;
        }

        micBtn.addEventListener('click', function () {
            try {
                const r = ensure();
                if (!listening) {
                    baseBeforeDictation = String(input && input.value ? input.value : '').trim();
                    finalDictated = '';
                    setListening(true);
                    r.start();
                    if (input) input.focus();
                } else {
                    setListening(false);
                    r.stop();
                }
            } catch (e) {
                setListening(false);
            }
        });
    })();

    // Guardar favorito con Ctrl/Cmd+S en el input (rápido)
    if (input) {
        input.addEventListener('keydown', function (e) {
            const isSave = (e.key === 's' || e.key === 'S') && (e.ctrlKey || e.metaKey);
            if (isSave) {
                e.preventDefault();
                addFavFromInput();
            }
        });
    }
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

        async function callChatApiOnce() {
            const res = await fetch(CHAT_API, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(buildChatRequestBody()),
                credentials: 'same-origin',
            });
            const ct = (res.headers && res.headers.get) ? (res.headers.get('content-type') || '') : '';
            const raw = await res.text().catch(() => '');
            let data = {};
            if (ct.toLowerCase().includes('application/json')) {
                data = safeJsonParse(raw) || {};
            } else {
                // Si el servidor devolvió HTML (login/error), lo registramos para debug rápido.
                data = { ok: false, error: 'Respuesta no-JSON (posible sesión/redirect)' };
            }
            if (!res.ok || data.ok === false) {
                const msg = (data && data.error) ? String(data.error) : ('HTTP ' + res.status);
                const err = new Error(msg);
                err.status = res.status;
                err.nonJson = !ct.toLowerCase().includes('application/json');
                err.raw = raw;
                throw err;
            }
            return String(data.reply || '');
        }

        try {
            let reply = '';
            try {
                reply = await callChatApiOnce();
            } catch (e1) {
                // Reintento único: a veces el primer request falla por redirect/cold-start.
                const isRetryable = (e1 && (e1.nonJson || e1.status === 429 || e1.status === 500 || e1.status === 502 || e1.status === 503));
                if (!isRetryable) throw e1;
                await new Promise(r => setTimeout(r, 650));
                reply = await callChatApiOnce();
            }

            // Solo guardar en history si no es una respuesta hallucinated (Cliente 1/2/3…).
            // De esta forma no contamina el contexto de la siguiente consulta.
            if (!hasGenericClienteLabels(reply)) {
                history.push({ role: 'assistant', content: reply });
            }
            saveHistory();
            if (!trimHistory()) {
                append('assistant', reply, { streamAssistant: true });
            }
        } catch (e) {
            const errMsg = String(e.message || e).toLowerCase();
            const friendly = (errMsg.includes('no-json') || errMsg.includes('respuesta no-json') || errMsg.includes('sesión') || errMsg.includes('redirect'))
                ? 'Tu sesión parece haber cambiado o el servidor respondió algo inesperado. Recarga la página e intentá de nuevo.'
                : (errMsg.includes('token') || errMsg.includes('rate limit') || errMsg.includes('tpd') || errMsg.includes('diario'))
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
