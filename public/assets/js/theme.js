/**
 * Tema claro/oscuro — cookie ix2-theme + localStorage (alineado a SIP).
 */
(function () {
    function readCookieTheme() {
        try {
            var m = document.cookie.match(/(?:^|; )ix2-theme=([^;]*)/);
            return m ? decodeURIComponent(m[1]).toLowerCase().trim() : '';
        } catch (e) {
            return '';
        }
    }

    function writeCookieTheme(mode) {
        try {
            document.cookie =
                'ix2-theme=' +
                encodeURIComponent(mode) +
                ';path=/;max-age=' +
                60 * 60 * 24 * 365 +
                ';SameSite=Lax';
        } catch (e) {}
    }

    function syncIcons(mode) {
        var dark = mode === 'dark';
        document.querySelectorAll('.app-theme-sun').forEach(function (el) {
            el.classList.toggle('hidden', dark);
        });
        document.querySelectorAll('.app-theme-moon').forEach(function (el) {
            el.classList.toggle('hidden', !dark);
        });
    }

    /** Réplica del tema en nodos marcados (p. ej. tarjetas Iconos) para CSS con máxima fiabilidad */
    function syncThemeNodes(mode) {
        try {
            document.querySelectorAll('[data-sync-app-theme]').forEach(function (el) {
                el.setAttribute('data-app-theme', mode);
            });
        } catch (e) {}
    }

    window.appSetTheme = function (mode) {
        if (mode !== 'dark' && mode !== 'light') return;
        var d = document.documentElement;
        d.setAttribute('data-theme', mode);
        d.style.colorScheme = mode === 'dark' ? 'dark' : 'light';
        try {
            localStorage.setItem('ix2-theme', mode);
        } catch (e) {}
        writeCookieTheme(mode);
        syncIcons(mode);
        syncThemeNodes(mode);
        window.dispatchEvent(new CustomEvent('app-theme-change', { detail: { theme: mode } }));
    };

    window.appToggleTheme = function () {
        var cur = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
        appSetTheme(cur === 'dark' ? 'light' : 'dark');
    };

    var initial = document.documentElement.getAttribute('data-theme') || 'light';
    syncIcons(initial);
    syncThemeNodes(initial);
})();

