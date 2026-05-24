(function () {
    var _cfg = window.__VENTAS_CHAT || {};
    const CHAT_API = _cfg.chatApi || '/api/chat';
    const VENTAS_PUBLIC_BASE = _cfg.publicBase || '/';
    const VENTAS_MODULES_WEB_BASE = _cfg.modulesBase || '/modules/';
    const USER_KEY_RAW = _cfg.userKey || 'anon';
    const USER_KEY = String(USER_KEY_RAW || 'anon')
        .toLowerCase()
        .replace(/\s+/g, '')
        .replace(/[^a-z0-9@._-]+/g, '_')
        .slice(0, 80) || 'anon';
    const NS = 'ventasChatbot:' + USER_KEY + ':';
    const LS_HISTORY = NS + 'history_v1';
    const LS_THREADS = NS + 'threads_v1';
    const LS_ACTIVE_THREAD = NS + 'active_thread_v1';
    const LS_DRAFT = NS + 'draft_v1';
    const LS_FAVS = NS + 'favs_v1';
    const LS_PREFS_CONTEXT = NS + 'prefs_context_v1';
    const LS_HIDE_TIPS = NS + 'hide_consejos_v1';
    const LS_PIP = NS + 'chatbot_pip_v1';
    const MAX_LOCAL_MESSAGES = 120;
    const MAX_THREADS = 40;
    const isFull = typeof window !== 'undefined' && window.VENTAS_CHAT_FULL === true;
    const THREADS_API = (_cfg.threadsApi != null && _cfg.threadsApi !== '') ? _cfg.threadsApi : (String(VENTAS_PUBLIC_BASE || '') + 'api/chat_threads');


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
    const pipBackdrop = document.getElementById('ventasChatPipBackdrop');
    const pipToggle = document.getElementById('ventasChatPipToggle');

    let faqTemplatesCache = [];
    const history = [];
    let threads = [];
    let activeThreadId = '';
    let threadsQuery = '';
    let lastResult = null;  // último resultado de herramienta (encadenamiento secuencial)

    const CHATBOT_PAGE_BASE = (_cfg.chatbotPage != null && String(_cfg.chatbotPage).trim() !== '')
        ? String(_cfg.chatbotPage).trim()
        : '/?page=chatbot';

    function buildChatbotFullUrl() {
        let base = CHATBOT_PAGE_BASE;
        let tid = '';
        try {
            tid = (activeThreadId || '').trim() || (localStorage.getItem(LS_ACTIVE_THREAD) || '').trim();
        } catch (e1) { /* ignore */ }
        if (!tid) return base;
        const sep = base.indexOf('?') >= 0 ? '&' : '?';
        return base + sep + 'thread=' + encodeURIComponent(tid);
    }
    function syncOpenFullHref() {
        if (isFull) return;
        const el = document.getElementById('ventasChatOpenFull');
        if (!el) return;
        el.setAttribute('href', buildChatbotFullUrl());
    }

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
        syncOpenFullHref();
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
        if (lastResult !== null) body.prev_result = lastResult;
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
        lastResult = null;
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
                // Además, limpiar bloques SQL del historial guardado para no desperdiciar tokens.
                const isStale = m.role === 'assistant' && hasGenericClienteLabels(m.content || '');
                if (!isStale) {
                    const content = m.role === 'assistant'
                        ? (splitAssistantAnswerAndSql(m.content || '').head || m.content)
                        : m.content;
                    history.push({ role: m.role, content: content });
                }
                append(m.role, m.content);
            }
            // Scroll al último mensaje tras renderizar todos (incluyendo tablas)
            if (log) {
                window.setTimeout(function () { log.scrollTop = log.scrollHeight; }, 80);
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

    function setChatbotPipMode(active, persist) {
        if (!isFull || !panel) return;
        const on = !!active;
        document.body.classList.toggle('chatbot-pip-active', on);
        panel.classList.toggle('chatbot-page--pip', on);
        if (pipBackdrop) {
            if (on) {
                pipBackdrop.hidden = false;
                pipBackdrop.setAttribute('aria-hidden', 'false');
            } else {
                pipBackdrop.hidden = true;
                pipBackdrop.setAttribute('aria-hidden', 'true');
            }
        }
        if (pipToggle) {
            pipToggle.setAttribute('aria-pressed', on ? 'true' : 'false');
            pipToggle.title = on ? 'Volver a vista página completa' : 'Vista compacta (ventana flotante en esta página)';
            pipToggle.setAttribute('aria-label', on ? 'Volver a vista página completa' : 'Vista compacta flotante');
            const ic = pipToggle.querySelector('i');
            if (ic) {
                ic.className = on ? 'fas fa-expand' : 'fas fa-compress';
            }
        }
        if (persist) {
            try { localStorage.setItem(LS_PIP, on ? '1' : '0'); } catch (e) { /* ignore */ }
        }
        if (on && log) {
            try { log.scrollTop = log.scrollHeight; } catch (e1) { /* ignore */ }
        }
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
        // Proyección: usa últimos 6 meses completos como historial (mínimo 2 meses requeridos).
        const now = new Date();
        const projDesde = toYmd(new Date(now.getFullYear(), now.getMonth() - 7, 1));
        const projHasta = toYmd(new Date(now.getFullYear(), now.getMonth(), 0));
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
            { label: 'Proyección próximos 3 meses', text: 'Del ' + projDesde + ' al ' + projHasta + ', proyectá las ventas para los próximos 3 meses basándote en la tendencia histórica.' },
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

    /** Limpia comillas y markdown típico del modelo en celdas de tabla. */
    function _sanitizeCellDisplay(s) {
        let t = String(s || '').trim();
        t = t.replace(/^[\s"'“”‘’]+|[\s"'“”‘’]+$/g, '');
        t = t.replace(/\*\*([^*]+)\*\*/g, '$1');
        t = t.replace(/\*([^*]+)\*/g, '$1');
        t = t.replace(/`([^`]+)`/g, '$1');
        return t.replace(/\s+/g, ' ').trim();
    }

    function hasGenericClienteLabels(text) {
        return /^\d+\.\s*Cliente\s+\d+/mi.test(String(text));
    }

    function stripTrailingUrlJunk(url) {
        return String(url).replace(/[),.;'\]}>*`]+$/g, '');
    }

    function normalizeTextForLinkify(s) {
        return String(s)
            .replace(/[\u200b-\u200d\ufeff\u00a0]/g, '')
            .replace(/\/modulos\//gi, '/modules/');
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
        return String(text)
            .replace(/`([^`\n]*\.php\?[^`\n]*)`/gi, '$1')
            .replace(/`([^`\n]*\/modules\/[^\s`?]+\?[^`\n]*)`/gi, '$1');
    }

    function collapseMultilineQueryUrls(text) {
        let t = String(text);
        let prev;
        const blocks = [
            /(\/modules\/(?:ventasgeneral\/[^\s?\n\r]+|reports\/[^\s?\n\r]+)\?[^\n\r]*)\r?\n\s*&/gi,
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
            .replace(/ventasgeneral_resumen_tabla\.php\?/gi, '/modules/ventasgeneral/resumen-tabla?')
            .replace(/ventasgeneral_buscar_tabla\.php\?/gi, '/modules/ventasgeneral/buscar-tabla?')
            .replace(/ventasgeneral_resumen\.php\?/gi, '/modules/ventasgeneral/resumen-tabla?')
            .replace(/ventasgeneral_buscar\.php\?/gi, '/modules/ventasgeneral/buscar-tabla?')
            .replace(/ventasgeneral_top_clientes_nc\.php\?/gi, '/modules/reports/ventas-top-clientes-nc?')
            .replace(/ventas_top_clientes_nc\.php\?/gi, '/modules/reports/ventas-top-clientes-nc?')
            .replace(/ventasgeneral_pareto_nc[^?]*\.php\?/gi, '/modules/reports/pareto-nc-zona?')
            .replace(/pareto_nc_zona\.php\?/gi, '/modules/reports/pareto-nc-zona?')
            .replace(/pareto_nc_zonaprecio\.php\?/gi, '/modules/reports/pareto-nc-zona?')
            .replace(/ventasgeneral_top_clientes_zona_precio\.php\?/gi, '/modules/reports/pareto-clientes-zona?')
            .replace(/pareto_clientes_zona\.php\?/gi, '/modules/reports/pareto-clientes-zona?')
            .replace(/ventas_barras_dimension\.php\?/gi, '/modules/reports/ventas-barras-dimension?')
            .replace(/ventas_comparativo\.php\?/gi, '/modules/reports/ventas-comparativo?')
            .replace(/ventas_top_productos\.php\?/gi, '/modules/reports/ventas-top-productos?')
            .replace(/ventas_top_clientes_global\.php\?/gi, '/modules/reports/ventas-top-clientes-global?')
            .replace(/ventas_mix_tdoc\.php\?/gi, '/modules/reports/ventas-mix-tdoc?')
            .replace(/ventas_barras_ruta\.php\?/gi, '/modules/reports/ventas-barras-ruta?')
            .replace(/ventas_barras_corporativo\.php\?/gi, '/modules/reports/ventas-barras-corporativo?')
            .replace(/ventas_serie_mensual\.php\?/gi, '/modules/reports/ventas-serie-mensual?');
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

    function _useVerReporteLabelForHref(resolved) {
        const u = String(resolved || '');
        return /^\/modules\/(reports|ventasgeneral)\b/i.test(u);
    }

    /** Formatea número con separador de miles (es-PE). No reformatea si ya trae comas. */
    function _formatNumberToken(numStr, fixedDecimals) {
        const raw = String(numStr || '').trim();
        if (!raw || raw.indexOf(',') >= 0) return raw;
        const clean = raw.replace(/,/g, '');
        if (!/^-?\d+(\.\d+)?$/.test(clean)) return raw;
        const n = parseFloat(clean);
        if (!isFinite(n)) return raw;
        if (fixedDecimals != null) {
            return n.toLocaleString('es-PE', {
                minimumFractionDigits: fixedDecimals,
                maximumFractionDigits: fixedDecimals,
            });
        }
        if (clean.indexOf('.') >= 0) {
            const dec = clean.split('.')[1].length;
            return n.toLocaleString('es-PE', { minimumFractionDigits: dec, maximumFractionDigits: dec });
        }
        return n.toLocaleString('es-PE', { maximumFractionDigits: 0 });
    }

    /** Montos S/, unidades, kg, líneas y otros números grandes en texto del asistente. */
    function formatChatDisplayNumbers(text) {
        let s = String(text || '');
        // $ → S/ (evita tocar http://…)
        s = s.replace(/\$\s*([\d]{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)/g, 'S/ $1');
        // S/ 1234567.89 → S/ 1,234,567.89
        s = s.replace(/\bS\/\s*(\d+(?:\.\d+)?)\b/g, function (_, n) {
            return 'S/ ' + _formatNumberToken(n, String(n).indexOf('.') >= 0 ? 2 : null);
        });
        s = s.replace(/(\d+(?:\.\d+)?)\s+unidades\b/gi, function (_, n) {
            return _formatNumberToken(n) + ' unidades';
        });
        s = s.replace(/(\d+(?:\.\d+)?)\s+kg\b/gi, function (_, n) {
            return _formatNumberToken(n) + ' kg';
        });
        s = s.replace(/(\d+(?:\.\d+)?)\s+líneas\b/gi, function (_, n) {
            return _formatNumberToken(n) + ' líneas';
        });
        s = s.replace(/(\d+(?:\.\d+)?)\s+notas de crédito\b/gi, function (_, n) {
            return _formatNumberToken(n) + ' notas de crédito';
        });
        return s;
    }

    /** @deprecated alias */
    function formatImportesSoles(text) {
        return formatChatDisplayNumbers(text);
    }

    /** Mismo criterio que formatChatDisplayNumbers, para celdas de tablas HTML del chat. */
    function formatCellDisplayNumbers(text) {
        return formatChatDisplayNumbers(text);
    }

    function linkifyAssistant(text) {
        let t = normalizeTextForLinkify(text);
        t = unwrapBackticksAroundPhpUrls(t);
        t = collapseDateLineBreaks(t);
        t = collapseMultilineQueryUrls(t);
        /** reporte_url: … → enlace "ver reporte" (href resuelto; sin mostrar URL larga). */
        const reportHrefs = [];
        t = t.replace(/\breporte_url\s*:\s*([^\s<]+)/gi, function (full, rawU) {
            const url = stripTrailingUrlJunk(rawU);
            const ok = /^\/modules\//i.test(url) || /^ventas-[^\s]+\?/i.test(url) || /\.php\?/i.test(url);
            if (!ok) return full;
            const ix = reportHrefs.length;
            reportHrefs.push(url);
            return '@@@CHAT_REPORT_' + ix + '@@@';
        });
        t = formatImportesSoles(t);
        const re = /(https?:\/\/[^\s<]+|\/modules\/(?:reports|ventasgeneral)\/[^\s<]+|\/modules\/[^\s<]+\?[^\s<]+|sql_texto\.php\?[^\s<]+|(?:pareto_nc_zona|pareto_clientes_zona)(?:_tabla)?\.php\?[^\s<]+|ventasgeneral_top_clientes_nc\.php\?[^\s<]+|ventasgeneral_top_clientes_zona_precio\.php\?[^\s<]+|ventas_(?:barras_dimension|comparativo|top_productos|top_clientes_global|top_clientes_nc|mix_tdoc|barras_ruta|barras_corporativo|serie_mensual)\.php\?[^\s<]+|ventasgeneral_(?:buscar|resumen)(?:_tabla)?\.php\?[^\s<]+)/gi;
        const out = [];
        let last = 0;
        let m;
        re.lastIndex = 0;
        while ((m = re.exec(t)) !== null) {
            out.push(escapeHtml(t.slice(last, m.index)));
            const raw = stripTrailingUrlJunk(m[0]);
            const hrefResolved = resolveAssistantHref(raw);
            const href = escapeHtml(hrefResolved);
            const shortRep = _useVerReporteLabelForHref(hrefResolved);
            const label = shortRep ? escapeHtml('ver reporte') : escapeHtml(raw);
            out.push('<a class="ventas-chat-link' + (shortRep ? ' ventas-chat-report-link' : '') + '" href="' + href + '" target="_blank" rel="noopener noreferrer">' + label + '</a>');
            last = m.index + m[0].length;
        }
        out.push(escapeHtml(t.slice(last)));
        let result = out.join('');
        for (let ix = 0; ix < reportHrefs.length; ix++) {
            const ph = '@@@CHAT_REPORT_' + ix + '@@@';
            const raw = reportHrefs[ix];
            const hrefResolved = resolveAssistantHref(raw);
            const href = escapeHtml(hrefResolved);
            const link = '<a class="ventas-chat-link ventas-chat-report-link" href="' + href + '" target="_blank" rel="noopener noreferrer">ver reporte</a>';
            result = result.split(ph).join(link);
        }
        return result;
    }

    /** Convierte 2+ líneas con viñeta (- * •) en tabla HTML (ej. provincia : detalle). */
    function _bulletLinesToTable(lines) {
        const rows = [];
        lines.forEach(function (line) {
            const m = String(line).trim().match(/^[-*•]\s+(.+)$/);
            if (!m) return;
            const inner = m[1].trim();
            const colonIdx = inner.indexOf(':');
            var k, v;
            if (colonIdx > 0 && colonIdx < inner.length - 1) {
                k = inner.slice(0, colonIdx).replace(/\*\*/g, '').trim();
                v = inner.slice(colonIdx + 1).trim();
            } else {
                k = '—';
                v = inner;
            }
            rows.push({
                k: _sanitizeCellDisplay(k),
                v: formatCellDisplayNumbers(_sanitizeCellDisplay(v)),
            });
        });
        if (rows.length < 2) return null;
        var h = '<div class="ventas-chat-inline-table-wrap"><table class="ventas-chat-simple-table"><thead><tr><th>Concepto</th><th>Detalle</th></tr></thead><tbody>';
        rows.forEach(function (r) {
            h += '<tr><td>' + escapeHtml(r.k) + '</td><td>' + escapeHtml(r.v) + '</td></tr>';
        });
        h += '</tbody></table></div>';
        return h;
    }

    function _splitSegmentForBullets(seg) {
        const lines = String(seg).split(/\r?\n/);
        const chunks = [];
        var buf = [];
        function flushBuf() {
            if (buf.length) {
                chunks.push({ type: 'text', text: buf.join('\n') });
                buf = [];
            }
        }
        var i = 0;
        while (i < lines.length) {
            if (/^\s*[-*•]\s+/.test(lines[i])) {
                var j = i;
                while (j < lines.length && /^\s*[-*•]\s+/.test(lines[j])) j++;
                if (j - i >= 2) {
                    flushBuf();
                    var tbl = _bulletLinesToTable(lines.slice(i, j));
                    if (tbl) chunks.push({ type: 'html', html: tbl });
                    else {
                        for (var k = i; k < j; k++) buf.push(lines[k]);
                    }
                    i = j;
                } else {
                    buf.push(lines[i]);
                    i++;
                }
            } else {
                buf.push(lines[i]);
                i++;
            }
        }
        flushBuf();
        return chunks;
    }

    function _segmentWithBulletsAndLinkify(seg) {
        const parts = _splitSegmentForBullets(seg);
        return parts.map(function (p) {
            if (p.type === 'html') return p.html;
            return '<span class="chat-text-seg">' + linkifyAssistant(p.text) + '</span>';
        }).join('');
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

    // ─── CHAT TABLE WIDGET ─────────────────────────────────────────────────────
    var _ctSeq = 0;
    function _ctId() { return 'ct' + (++_ctSeq); }

    function _ctAttr(s) {
        return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    function _ctCap(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : ''; }

    function _ctColHeader(v) {
        var s = _sanitizeCellDisplay(String(v || '').trim());
        if (/^S\/\s/.test(s) || /^-?S\/\s/.test(s)) return 'Importe';
        if (/líneas?\s+NC/i.test(s)) return 'Líneas NC';
        if (/líneas?/i.test(s) && /^\d/.test(s)) return 'Líneas';
        if (/kg/i.test(s) && /^\d/.test(s)) return 'Peso (kg)';
        if (/^\d[\d,.]+%$/.test(s)) return '% total';
        if (/acumulado/i.test(s)) return '% acum.';
        var mPer = s.match(/^(periodo\s+[A-Z])\s+S\//i);
        if (mPer) return _ctCap(mPer[1]);
        if (/^precio\b/i.test(s)) return 'Precio/kg';
        var mLbl = s.match(/^([a-záéíóúüñ ]+?)\s+S\//i);
        if (mLbl) return _ctCap(mLbl[1].trim());
        var mNum = s.match(/^-?[\d,.]+\s+(.+)$/);
        if (mNum) return _ctCap(mNum[1].trim());
        var mPct = s.match(/^[\d,.]+%\s+(.+)$/);
        if (mPct) return _ctCap(mPct[1].trim());
        if (/^[\d,.]+%$/.test(s)) return '% del total';
        return _ctCap(s);
    }

    /** Divide una cadena de valores por ", " respetando paréntesis y números con coma (S/ 1,234.56). */
    function _ctSplitVals(s) {
        var vals = [], cur = '', depth = 0;
        for (var i = 0; i < s.length; i++) {
            var c = s[i];
            if (c === '(') { depth++; cur += c; continue; }
            if (c === ')') { depth--; cur += c; continue; }
            // Coma dentro de paréntesis o en número (dígito antes Y después de ",")
            if (c === ',' && depth === 0) {
                var prev = cur.trimEnd().slice(-1);
                var next = s[i + 1];
                var afterNext = s[i + 2] || '';
                var numAfter = next === ' ' && /\d/.test(afterNext) && /\d/.test(prev);
                if (next === ' ' && !numAfter) {
                    vals.push(_sanitizeCellDisplay(cur.trim()));
                    cur = ''; i++; continue;
                }
            }
            cur += c;
        }
        if (cur.trim()) vals.push(_sanitizeCellDisplay(cur.trim()));
        return vals.length ? vals : [_sanitizeCellDisplay(s)];
    }

    function _ctParseItem(raw) {
        // Intenta separador ": "
        var ci = raw.indexOf(': ');
        // Intenta separador " - " (usado por el LLM en algunos formatos)
        var di = raw.indexOf(' - ');
        var sep = -1, sepLen = 0;
        if (ci >= 0 && (di < 0 || ci <= di)) { sep = ci; sepLen = 2; }
        else if (di >= 0) { sep = di; sepLen = 3; }

        if (sep < 0) return { name: _sanitizeCellDisplay(raw), extra: '', vals: [_sanitizeCellDisplay(raw)] };

        var name = _sanitizeCellDisplay(raw.slice(0, sep).replace(/\*\*/g, '').trim());
        var rest = raw.slice(sep + sepLen).trim();
        var vals = _ctSplitVals(rest).map(function (v) { return formatCellDisplayNumbers(v); });
        var nm = name.match(/^(.*?)\s*\(([^)]+)\)$/);
        if (nm) return { name: _sanitizeCellDisplay(nm[1].trim()), extra: _sanitizeCellDisplay(nm[2].trim()), vals: vals };
        return { name: name, extra: '', vals: vals };
    }

    function _ctParseBlocks(text) {
        var lines = text.split('\n');
        var blocks = [], block = null, next = 1;
        for (var i = 0; i < lines.length; i++) {
            var t = lines[i].trim();
            var m = t.match(/^(\d+)\.\s+(.+)$/);
            if (m && parseInt(m[1], 10) === next && !m[2].startsWith('(+')) {
                if (!block) block = { start: i, end: i, items: [] };
                block.items.push({ num: parseInt(m[1], 10), raw: m[2] });
                block.end = i; next++;
            } else {
                if (block && block.items.length >= 2) blocks.push(block);
                block = null; next = 1;
                var m1 = t.match(/^1\.\s+(.+)$/);
                if (m1 && !m1[1].startsWith('(+')) {
                    block = { start: i, end: i, items: [{ num: 1, raw: m1[1] }] };
                    next = 2;
                }
            }
        }
        if (block && block.items.length >= 2) blocks.push(block);
        return blocks;
    }

    function _ctBuildPagination(page, total) {
        if (total <= 1) return '';
        var h = '<span class="paginate_button previous chat-paginate-btn' + (page === 0 ? ' disabled' : '') + '" data-ctp="prev">Anterior</span>';
        var s = Math.max(0, page - 2), e = Math.min(total - 1, s + 4);
        if (e - s < 4) s = Math.max(0, e - 4);
        for (var p = s; p <= e; p++) {
            h += '<span class="paginate_button chat-paginate-btn' + (p === page ? ' current' : '') + '" data-ctp="' + p + '">' + (p + 1) + '</span>';
        }
        h += '<span class="paginate_button next chat-paginate-btn' + (page === total - 1 ? ' disabled' : '') + '" data-ctp="next">Siguiente</span>';
        return h;
    }

    function _ctIsNumericCol(header) {
        return /^(Importe|Líneas|Peso|Unidades|Precio|%|N°$)/.test(header);
    }

    function _ctBuildWidget(items) {
        var parsed = items.map(function(it) { return _ctParseItem(it.raw); });
        var hasExtra = parsed.some(function(p) { return p.extra !== ''; });
        var cols = ['N°', 'Nombre'];
        if (hasExtra) cols.push('Extra');
        var firstVals = parsed[0].vals;
        for (var vi = 0; vi < firstVals.length; vi++) cols.push(_ctColHeader(firstVals[vi]));

        var rows = items.map(function(it, idx) {
            var p = parsed[idx];
            var row = [String(it.num), p.name];
            if (hasExtra) row.push(p.extra);
            for (var i = 0; i < p.vals.length; i++) row.push(p.vals[i]);
            while (row.length < cols.length) row.push('');
            return row;
        });

        var pp = 30, total = Math.max(1, Math.ceil(rows.length / pp));
        var initRows = rows.slice(0, pp), endIdx = Math.min(pp, rows.length);
        var infoText = rows.length > 0 ? 'Mostrando 1 a ' + endIdx + ' de ' + rows.length + ' registros' : 'Sin resultados';
        var thead = cols.map(function(c) {
            var align = _ctIsNumericCol(c) ? ' style="text-align:right"' : '';
            return '<th' + align + '>' + escapeHtml(c) + '</th>';
        }).join('');
        var tbody = initRows.map(function(row) {
            return '<tr>' + row.map(function(c, ci) {
                var align = _ctIsNumericCol(cols[ci]) ? ' style="text-align:right"' : '';
                return '<td' + align + '>' + escapeHtml(String(c)) + '</td>';
            }).join('') + '</tr>';
        }).join('');
        var initCards = initRows.map(function(row) {
            var fields = cols.slice(1).map(function(col, ci) {
                return '<div class="card-row"><span class="label">' + escapeHtml(col) + '</span><span>' + escapeHtml(String(row[ci + 1] || '')) + '</span></div>';
            }).join('');
            return '<article class="card-item prod-card"><div class="card-numero-row">#' + escapeHtml(String(row[0])) + '</div><div class="card-campos">' + fields + '</div></article>';
        }).join('');
        var pag = _ctBuildPagination(0, total);
        var tid = _ctId();

        return '<div class="ventas-chat-table-widget productos-dt-skin" data-ct-id="' + tid + '"'
            + ' data-ct-rows="' + _ctAttr(JSON.stringify(rows)) + '"'
            + ' data-ct-cols="' + _ctAttr(JSON.stringify(cols)) + '"'
            + ' data-ct-pp="30" data-ct-page="0" data-ct-q="" data-ct-view="lista" data-ct-total="' + total + '">'
            + '<div class="ventas-chat-table-toolbar reportes-toolbar-row">'
            + '<div class="view-toggle-group">'
            + '<button type="button" class="view-toggle-btn active" data-ct-v="lista" title="Lista"><i class="fas fa-list" aria-hidden="true"></i> Lista</button>'
            + '<button type="button" class="view-toggle-btn" data-ct-v="iconos" title="Iconos"><i class="fas fa-th" aria-hidden="true"></i> Iconos</button>'
            + '</div>'
            + '<div class="ventas-chat-table-controls">'
            + '<div class="dataTables_length"><label>Mostrar <select class="chat-ct-pp"><option value="10">10</option><option value="20">20</option><option value="30" selected>30</option><option value="50">50</option><option value="100">100</option></select> registros</label></div>'
            + '<div class="dataTables_filter"><label>Buscar <input type="search" class="chat-ct-q" placeholder=""></label></div>'
            + '</div></div>'
            + '<div class="view-lista-wrap" data-ct-pane="lista"><div class="table-wrapper overflow-x-auto">'
            + '<table class="data-table display stripe nowrap" style="width:100%"><thead><tr>' + thead + '</tr></thead><tbody>' + tbody + '</tbody></table>'
            + '</div></div>'
            + '<div class="view-tarjetas-wrap" data-ct-pane="iconos" style="display:none">'
            + '<div class="cards-grid cards-grid-iconos" data-vista-cards="iconos">' + initCards + '</div></div>'
            + '<div class="dt-bottom-row">'
            + '<div class="dataTables_info chat-ct-info">' + escapeHtml(infoText) + '</div>'
            + '<div class="dataTables_paginate paginate_button_wrap chat-ct-pag">' + pag + '</div>'
            + '</div></div>';
    }

    function _ctRender(widget) {
        var rows, cols;
        try { rows = JSON.parse(widget.dataset.ctRows || '[]'); cols = JSON.parse(widget.dataset.ctCols || '[]'); } catch(e) { return; }
        var pp = parseInt(widget.dataset.ctPp || '30');
        var page = parseInt(widget.dataset.ctPage || '0');
        var q = (widget.dataset.ctQ || '').toLowerCase();
        var view = widget.dataset.ctView || 'lista';
        var filtered = q ? rows.filter(function(row) { return row.some(function(c) { return String(c).toLowerCase().indexOf(q) >= 0; }); }) : rows;
        var total = Math.max(1, Math.ceil(filtered.length / pp));
        page = Math.min(page, total - 1);
        widget.dataset.ctPage = String(page); widget.dataset.ctTotal = String(total);
        var start = page * pp, end = Math.min(start + pp, filtered.length);
        var pageRows = filtered.slice(start, end);

        var infoEl = widget.querySelector('.chat-ct-info');
        if (infoEl) infoEl.textContent = filtered.length === 0 ? 'Sin resultados'
            : 'Mostrando ' + (start + 1) + ' a ' + end + ' de ' + filtered.length + ' registros'
              + (filtered.length < rows.length ? ' (filtrados de ' + rows.length + ' total)' : '');

        var pagEl = widget.querySelector('.chat-ct-pag');
        if (pagEl) pagEl.innerHTML = _ctBuildPagination(page, total);

        var listaPane = widget.querySelector('[data-ct-pane="lista"]');
        var iconosPane = widget.querySelector('[data-ct-pane="iconos"]');

        if (view === 'lista') {
            if (listaPane) listaPane.style.display = '';
            if (iconosPane) iconosPane.style.display = 'none';
            var tbody = widget.querySelector('tbody');
            if (tbody) tbody.innerHTML = pageRows.map(function(row) {
                return '<tr>' + row.map(function(c) { return '<td>' + escapeHtml(String(c)) + '</td>'; }).join('') + '</tr>';
            }).join('');
        } else {
            if (listaPane) listaPane.style.display = 'none';
            if (iconosPane) iconosPane.style.display = '';
            var cardsEl = widget.querySelector('.cards-grid');
            if (cardsEl) cardsEl.innerHTML = pageRows.map(function(row) {
                var fields = cols.slice(1).map(function(col, ci) {
                    return '<div class="card-row"><span class="label">' + escapeHtml(col) + '</span><span>' + escapeHtml(String(row[ci + 1] || '')) + '</span></div>';
                }).join('');
                return '<article class="card-item prod-card"><div class="card-numero-row">#' + escapeHtml(String(row[0])) + '</div><div class="card-campos">' + fields + '</div></article>';
            }).join('');
        }
    }

    function _ctInitDelegation() {
        if (!log || log._ctDel) return;
        log._ctDel = true;
        log.addEventListener('change', function(e) {
            if (e.target.classList.contains('chat-ct-pp')) {
                var w = e.target.closest('.ventas-chat-table-widget');
                if (w) { w.dataset.ctPp = e.target.value; w.dataset.ctPage = '0'; _ctRender(w); }
            }
        });
        var _ctTimer;
        log.addEventListener('input', function(e) {
            if (e.target.classList.contains('chat-ct-q')) {
                var w = e.target.closest('.ventas-chat-table-widget');
                if (w) { clearTimeout(_ctTimer); _ctTimer = setTimeout(function() { w.dataset.ctQ = e.target.value.toLowerCase(); w.dataset.ctPage = '0'; _ctRender(w); }, 250); }
            }
        });
        log.addEventListener('click', function(e) {
            var btn = e.target.closest('[data-ct-v]');
            if (btn) {
                var w = btn.closest('.ventas-chat-table-widget');
                if (w) {
                    var v = btn.dataset.ctV; w.dataset.ctView = v;
                    w.querySelectorAll('[data-ct-v]').forEach(function(b) { b.classList.toggle('active', b.dataset.ctV === v); });
                    _ctRender(w); return;
                }
            }
            var pb = e.target.closest('.chat-paginate-btn');
            if (pb && !pb.classList.contains('disabled')) {
                var w = pb.closest('.ventas-chat-table-widget');
                if (w) {
                    var action = pb.dataset.ctp, tot = parseInt(w.dataset.ctTotal || '1'), page = parseInt(w.dataset.ctPage || '0');
                    if (action === 'prev') page = Math.max(0, page - 1);
                    else if (action === 'next') page = Math.min(tot - 1, page + 1);
                    else { var n = parseInt(action, 10); if (!isNaN(n)) page = Math.max(0, Math.min(tot - 1, n)); }
                    w.dataset.ctPage = String(page); _ctRender(w);
                }
            }
        });
    }

    function _mdIsTableSeparatorLine(line) {
        const t = String(line || '').trim();
        if (!t || !/\|/.test(t)) return false;
        return /^[|\s:\-]+$/.test(t) && /-/.test(t);
    }

    function _mdLooksTableRow(line) {
        const t = String(line || '').trim();
        return t.length > 0 && /\|/.test(t) && !_mdIsTableSeparatorLine(t);
    }

    function _mdSplitPipeRow(line) {
        let cells = String(line).trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(function (c) {
            return _sanitizeCellDisplay(c);
        });
        while (cells.length && cells[0] === '') cells.shift();
        while (cells.length && cells[cells.length - 1] === '') cells.pop();
        return cells;
    }

    function _mdBuildGfmTableHtml(slice) {
        if (!slice || slice.length < 3) return '';
        const headerCells = _mdSplitPipeRow(slice[0]);
        if (!headerCells.length) return '';
        const bodyRows = [];
        for (let r = 2; r < slice.length; r++) {
            const cells = _mdSplitPipeRow(slice[r]);
            if (!cells.length) continue;
            bodyRows.push(cells);
        }
        if (!bodyRows.length) return '';
        let thead = '<thead><tr>';
        headerCells.forEach(function (h) {
            thead += '<th>' + escapeHtml(h) + '</th>';
        });
        thead += '</tr></thead>';
        let tbody = '<tbody>';
        bodyRows.forEach(function (row) {
            tbody += '<tr>';
            for (let c = 0; c < headerCells.length; c++) {
                var cell = row[c] != null ? row[c] : '';
                tbody += '<td>' + escapeHtml(formatCellDisplayNumbers(cell)) + '</td>';
            }
            tbody += '</tr>';
        });
        tbody += '</tbody>';
        return '<div class="ventas-chat-inline-table-wrap ventas-chat-mdtable-wrap"><table class="ventas-chat-simple-table">' + thead + tbody + '</table></div>';
    }

    function _splitByMarkdownTables(text) {
        const lines = String(text || '').split(/\r?\n/);
        const parts = [];
        const buf = [];
        function flush() {
            if (buf.length) {
                parts.push({ type: 'text', text: buf.join('\n') });
                buf.length = 0;
            }
        }
        let i = 0;
        while (i < lines.length) {
            if (i + 1 < lines.length && _mdLooksTableRow(lines[i]) && _mdIsTableSeparatorLine(lines[i + 1])) {
                flush();
                let end = i + 2;
                while (end < lines.length && _mdLooksTableRow(lines[end])) end++;
                const html = _mdBuildGfmTableHtml(lines.slice(i, end));
                if (html) {
                    parts.push({ type: 'html', html: html });
                    i = end;
                    if (i < lines.length && String(lines[i]).trim() === '') i++;
                    continue;
                }
            }
            buf.push(lines[i]);
            i++;
        }
        flush();
        return parts;
    }

    function _chatTextToHtmlInner(text) {
        var blocks = _ctParseBlocks(text);
        if (!blocks.length) return _segmentWithBulletsAndLinkify(text);
        var lines = text.split('\n');
        var lineBlock = new Array(lines.length).fill(-1);
        blocks.forEach(function(b, bi) { for (var ii = b.start; ii <= b.end; ii++) lineBlock[ii] = bi; });
        var parts = [], ii = 0;
        while (ii < lines.length) {
            var bi = lineBlock[ii];
            if (bi >= 0) {
                parts.push(_ctBuildWidget(blocks[bi].items));
                ii = blocks[bi].end + 1;
            } else {
                var j = ii;
                while (j < lines.length && lineBlock[j] < 0) j++;
                var seg = lines.slice(ii, j).join('\n');
                if (seg.trim()) parts.push(_segmentWithBulletsAndLinkify(seg));
                ii = j;
            }
        }
        return parts.join('');
    }

    function _chatTextToHtml(text) {
        const chunks = _splitByMarkdownTables(String(text || ''));
        if (!chunks.length) return _chatTextToHtmlInner(String(text || ''));
        return chunks.map(function (part) {
            if (part.type === 'html') return part.html;
            const seg = String(part.text || '');
            if (!seg.trim()) return '';
            return _chatTextToHtmlInner(seg);
        }).join('');
    }
    // ───────────────────────────────────────────────────────────────────────────

    function _userIsAdmin() {
        var r = (window.__VENTAS_CHAT && window.__VENTAS_CHAT.userRole || '').toLowerCase();
        return r === 'admin' || r === 'administrador';
    }

    function renderAssistantHtml(fullText) {
        const parts = splitAssistantAnswerAndSql(fullText);
        if (!parts.tail) return _chatTextToHtml(parts.head);
        var html = _chatTextToHtml(parts.head);
        if (_userIsAdmin()) {
            html += '\n\n<details class="ventas-chat-sql-fold"><summary class="ventas-chat-sql-fold-summary">Detalle técnico (SQL)</summary>'
                  + '<pre class="ventas-chat-sql-pre">' + escapeHtml(parts.tail) + '</pre></details>';
        }
        return html;
    }

    function _assistantBodyHasWideTable(html) {
        return String(html || '').indexOf('ventas-chat-table-widget') >= 0
            || String(html || '').indexOf('ventas-chat-simple-table') >= 0
            || String(html || '').indexOf('ventas-chat-mdtable-wrap') >= 0;
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
                if (outerDiv && _assistantBodyHasWideTable(bodyEl.innerHTML)) outerDiv.classList.add('has-table');
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
            if (_assistantBodyHasWideTable(body.innerHTML)) el.classList.add('has-table');
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
                if (_assistantBodyHasWideTable(body.innerHTML)) div.classList.add('has-table');
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
        if (panel) {
            panel.removeAttribute('hidden');
            panel.style.display = 'flex';
        }
        if (fab) {
            fab.setAttribute('hidden', '');
            fab.setAttribute('aria-expanded', 'true');
        }
        if (errEl) errEl.hidden = true;
        renderVentasFaqSelect();
        loadDraft();
        autosizeInput();
        applyShortcutsVisibility();
        if (input) input.focus();
        syncOpenFullHref();
        // Al abrir el panel, posicionar en el último mensaje
        if (log) window.setTimeout(function () { log.scrollTop = log.scrollHeight; }, 60);
    }

    function closePanel() {
        if (isFull) return;
        saveDraft();
        if (panel) {
            panel.setAttribute('hidden', '');
            panel.style.display = '';
        }
        if (fab) {
            fab.removeAttribute('hidden');
            fab.setAttribute('aria-expanded', 'false');
            fab.focus();
        }
    }

    if (fab) {
        fab.addEventListener('click', openPanel);
    }
    const openFullEl = document.getElementById('ventasChatOpenFull');
    if (openFullEl && !isFull) {
        syncOpenFullHref();
        openFullEl.addEventListener('pointerdown', syncOpenFullHref);
        openFullEl.addEventListener('focus', syncOpenFullHref);
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
            if (isFull && document.body.classList.contains('chatbot-pip-active')) {
                e.preventDefault();
                setChatbotPipMode(false, true);
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
        if (pipToggle && panel) {
            try {
                if (localStorage.getItem(LS_PIP) === '1') setChatbotPipMode(true, false);
            } catch (e) { /* ignore */ }
            pipToggle.addEventListener('click', function () {
                setChatbotPipMode(!document.body.classList.contains('chatbot-pip-active'), true);
            });
            if (pipBackdrop) {
                pipBackdrop.addEventListener('click', function () {
                    setChatbotPipMode(false, true);
                });
            }
        }
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

    // ── Indicador de escritura (●●●) ──────────────────────────────────────────
    let _typingBubble = null;

    function showTypingIndicator(statusText) {
        if (!log) return;
        if (!_typingBubble) {
            const div = document.createElement('div');
            div.className = 'ventas-chat-msg assistant';
            div.setAttribute('data-typing', '1');
            const label = document.createElement('div');
            label.className = 'ventas-chat-label';
            label.textContent = 'Asistente';
            const body = document.createElement('div');
            body.className = 'ventas-chat-msg-body ventas-chat-typing';
            body.innerHTML = '<span class="ventas-dot"></span><span class="ventas-dot"></span><span class="ventas-dot"></span>';
            div.appendChild(label);
            div.appendChild(body);
            log.appendChild(div);
            _typingBubble = div;
        }
        const body = _typingBubble.querySelector('.ventas-chat-msg-body');
        if (body && statusText) {
            body.innerHTML = '<span class="ventas-dot"></span><span class="ventas-dot"></span><span class="ventas-dot"></span>'
                + '<span style="margin-left:6px;font-size:.85em;opacity:.7">' + statusText + '</span>';
        }
        log.scrollTop = log.scrollHeight;
    }

    function removeTypingIndicator() {
        if (_typingBubble && _typingBubble.parentNode) {
            _typingBubble.parentNode.removeChild(_typingBubble);
        }
        _typingBubble = null;
    }

    // ── Bubble de streaming en tiempo real ────────────────────────────────────
    let _streamBubble = null;
    let _streamBody = null;
    let _streamRaw = '';

    function createStreamBubble() {
        removeTypingIndicator();
        if (!log) return;
        const div = document.createElement('div');
        div.className = 'ventas-chat-msg assistant ventas-chat-msg--streaming';
        const label = document.createElement('div');
        label.className = 'ventas-chat-label';
        label.textContent = 'Asistente';
        const body = document.createElement('div');
        body.className = 'ventas-chat-msg-body';
        div.appendChild(label);
        div.appendChild(body);
        log.appendChild(div);
        _streamBubble = div;
        _streamBody = body;
        _streamRaw = '';
    }

    function appendStreamToken(token) {
        if (!_streamBody) createStreamBubble();
        _streamRaw += token;
        _streamBody.textContent = _streamRaw;
        if (log) log.scrollTop = log.scrollHeight;
    }

    function finalizeStreamBubble(fullReply) {
        if (_streamBubble) {
            if (_streamBody) {
                _streamBody.innerHTML = renderAssistantHtml(fullReply);
                if (_assistantBodyHasWideTable(_streamBody.innerHTML)) _streamBubble.classList.add('has-table');
            }
            _streamBubble.classList.remove('ventas-chat-msg--streaming');
            if (log) log.scrollTop = log.scrollHeight;
        }
        _streamBubble = null;
        _streamBody = null;
        _streamRaw = '';
    }

    function clearStreamBubble() {
        if (_streamBubble && _streamBubble.parentNode) {
            _streamBubble.parentNode.removeChild(_streamBubble);
        }
        _streamBubble = null;
        _streamBody = null;
        _streamRaw = '';
    }

    // ── API calls ─────────────────────────────────────────────────────────────
    const CHAT_STREAM_API = CHAT_API + '/stream';

    async function callChatApiStream(signal) {
        const res = await fetch(CHAT_STREAM_API, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(buildChatRequestBody()),
            credentials: 'same-origin',
            signal: signal || null,
        });
        if (!res.ok) {
            const raw = await res.text().catch(() => '');
            const data = safeJsonParse(raw) || {};
            const msg = (data && data.error) ? String(data.error) : ('HTTP ' + res.status);
            const err = new Error(msg);
            err.status = res.status;
            throw err;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let finalReply = '';
        let finalLastResult = null;
        let hasTokens = false;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();
            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                let event;
                try { event = JSON.parse(line.slice(6)); } catch { continue; }
                if (event.type === 'status') {
                    if (!hasTokens) showTypingIndicator(event.text);
                } else if (event.type === 'token') {
                    hasTokens = true;
                    appendStreamToken(event.text);
                } else if (event.type === 'reply') {
                    finalReply = event.text;
                } else if (event.type === 'done') {
                    if (event.reply) finalReply = event.reply;
                    finalLastResult = event.last_result || null;
                } else if (event.type === 'error') {
                    const err = new Error(event.text || 'Error del servidor');
                    err.status = 500;
                    throw err;
                }
            }
        }

        // Si llegaron tokens pero no un reply enriquecido, usar el texto acumulado
        if (!finalReply && _streamRaw) finalReply = _streamRaw;
        return { reply: finalReply, lastResult: finalLastResult, usedStream: hasTokens };
    }

    async function callChatApiOnce(signal) {
        const res = await fetch(CHAT_API, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(buildChatRequestBody()),
            credentials: 'same-origin',
            signal: signal || null,
        });
        const ct = (res.headers && res.headers.get) ? (res.headers.get('content-type') || '') : '';
        const raw = await res.text().catch(() => '');
        let data = {};
        if (ct.toLowerCase().includes('application/json')) {
            data = safeJsonParse(raw) || {};
        } else {
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
        lastResult = (data.last_result !== undefined && data.last_result !== null) ? data.last_result : null;
        return String(data.reply || '');
    }

    let sendInFlight = false;
    let _abortCtrl = null;

    function _getStopBtn() {
        return document.getElementById('ventasChatStop');
    }
    function _showStopBtn() {
        const btn = _getStopBtn();
        if (btn) { btn.hidden = false; btn.disabled = false; }
        if (send) send.hidden = true;
    }
    function _hideStopBtn() {
        const btn = _getStopBtn();
        if (btn) btn.hidden = true;
        if (send) send.hidden = false;
    }
    document.addEventListener('click', function (e) {
        if (e.target && e.target.id === 'ventasChatStop') {
            const btn = e.target;
            btn.disabled = true;
            if (_abortCtrl) _abortCtrl.abort();
        }
    }, true);

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
        _abortCtrl = new AbortController();
        _showStopBtn();
        showTypingIndicator('');

        try {
            let reply = '';
            let usedStream = false;

            // Intentar streaming primero; fallback al endpoint clásico
            try {
                const result = await callChatApiStream(_abortCtrl.signal);
                reply = result.reply;
                usedStream = result.usedStream;
                lastResult = result.lastResult;
            } catch (e1) {
                if (e1 && e1.name === 'AbortError') {
                    // Usuario detuvo — mostrar lo que llegó hasta ahora
                    removeTypingIndicator();
                    const partial = _streamRaw || '';
                    if (partial) {
                        finalizeStreamBubble(partial);
                        history.push({ role: 'assistant', content: partial });
                        saveHistory();
                    } else {
                        clearStreamBubble();
                    }
                    return;
                }
                clearStreamBubble();
                removeTypingIndicator();
                const isRetryable = (e1 && (e1.status === 500 || e1.status === 502 || e1.status === 503));
                if (!isRetryable) throw e1;
                // Fallback al endpoint clásico
                showTypingIndicator('');
                try {
                    reply = await callChatApiOnce(_abortCtrl ? _abortCtrl.signal : null);
                } catch (e2) {
                    if (e2 && (e2.status === 500 || e2.status === 502 || e2.status === 503)) {
                        await new Promise(r => setTimeout(r, 650));
                        reply = await callChatApiOnce(_abortCtrl ? _abortCtrl.signal : null);
                    } else {
                        throw e2;
                    }
                }
            }

            removeTypingIndicator();

            if (!hasGenericClienteLabels(reply)) {
                const cleanContent = splitAssistantAnswerAndSql(reply).head || reply;
                history.push({ role: 'assistant', content: cleanContent });
            }
            saveHistory();

            if (!trimHistory()) {
                if (usedStream) {
                    // Los tokens ya se mostraron en tiempo real; ahora renderizar markdown completo
                    finalizeStreamBubble(reply);
                } else {
                    removeTypingIndicator();
                    append('assistant', reply, { streamAssistant: true });
                }
            } else {
                clearStreamBubble();
            }
        } catch (e) {
            removeTypingIndicator();
            clearStreamBubble();
            const errMsg = String(e.message || e).toLowerCase();
            const serverMsg = String(e.message || '');
            const isRateLimit = (e && e.status === 429) || errMsg.includes('rate limit') || errMsg.includes('rate_limit') || errMsg.includes('too many requests') || errMsg.includes('tokens per day') || errMsg.includes('tpd') || errMsg.includes('límite') || errMsg.includes('limite') || errMsg.includes('intentá de nuevo');
            const friendly = (errMsg.includes('no-json') || errMsg.includes('respuesta no-json') || errMsg.includes('sesión') || errMsg.includes('redirect'))
                ? 'Tu sesión parece haber cambiado o el servidor respondió algo inesperado. Recarga la página e intentá de nuevo.'
                : isRateLimit
                ? (serverMsg && (serverMsg.toLowerCase().startsWith('límite') || serverMsg.toLowerCase().startsWith('intentá')) ? serverMsg : 'Se alcanzó el límite de consultas. Intentá de nuevo en unos minutos.')
                : (serverMsg && serverMsg.length > 0 && serverMsg.length < 900 && !errMsg.includes('no-json'))
                ? serverMsg
                : 'Hubo un inconveniente. Por favor intentá de nuevo.';
            append('assistant', friendly);
            history.pop();
            input.value = text;
            saveDraft();
            saveHistory();
            if (errEl) errEl.hidden = true;
        } finally {
            send.disabled = false;
            sendInFlight = false;
            _abortCtrl = null;
            _hideStopBtn();
        }
    }

    _ctInitDelegation();

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