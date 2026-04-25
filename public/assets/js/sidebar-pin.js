(function () {
    var PIN_KEY = 'app-sidebar-pinned';

    function getCol() {
        return document.getElementById('appSidebarCol');
    }

    function setPinIcon(pinned) {
        var ic = document.querySelector('.app-sidebar-pin-icon');
        if (!ic) return;
        ic.classList.remove('fa-lock', 'fa-lock-open');
        ic.classList.add(pinned ? 'fa-lock' : 'fa-lock-open');
        var btn = document.getElementById('appBtnSidebarPin');
        if (btn) btn.setAttribute('aria-pressed', pinned ? 'true' : 'false');
    }

    window.appToggleSidebarPin = function () {
        var col = getCol();
        if (!col) return;
        var pinned = !col.classList.contains('app-sidebar-pin-open');
        col.classList.toggle('app-sidebar-pin-open', pinned);
        try {
            localStorage.setItem(PIN_KEY, pinned ? '1' : '0');
        } catch (e) {}
        setPinIcon(pinned);
    };

    try {
        var col = getCol();
        if (col && localStorage.getItem(PIN_KEY) === '1') {
            col.classList.add('app-sidebar-pin-open');
            setPinIcon(true);
        } else {
            setPinIcon(false);
        }
    } catch (e) {
        var col2 = getCol();
        setPinIcon(!!(col2 && col2.classList.contains('app-sidebar-pin-open')));
    }

    function closeMobileSidebar() {
        document.body.classList.remove('app-sidebar-open');
    }

    function openMobileSidebar() {
        document.body.classList.add('app-sidebar-open');
    }

    var bd = document.getElementById('appSidebarBackdrop');
    if (bd) bd.addEventListener('click', closeMobileSidebar);
    var openBtn = document.getElementById('appOpenSidebar');
    if (openBtn) openBtn.addEventListener('click', openMobileSidebar);

    document.querySelectorAll('.app-nav-link').forEach(function (a) {
        a.addEventListener('click', function () {
            if (window.matchMedia && matchMedia('(max-width: 900px)').matches) {
                closeMobileSidebar();
            }
        });
    });
})();

