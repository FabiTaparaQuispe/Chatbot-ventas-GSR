<?php

declare(strict_types=1);

/**
 * Estilos comunes para tablas de reporte (pantalla + PDF).
 */
function ventas_reporte_tabla_styles(): void
{
    echo <<<'CSS'
<style>
    .reporte-toolbar { display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center; margin: 0 0 1rem; }
    .reporte-toolbar a, .reporte-toolbar button {
        font: inherit; font-size: 0.875rem; padding: 0.45rem 0.85rem; border-radius: 8px; cursor: pointer;
        text-decoration: none; border: 1px solid #475569; background: #334155; color: #e2e8f0;
    }
    .reporte-toolbar a:hover, .reporte-toolbar button:hover { background: #3b82f6; border-color: #2563eb; color: #fff; }
    .reporte-toolbar .btn-pdf { background: #b45309; border-color: #d97706; color: #fff; }
    .reporte-toolbar .btn-pdf:hover { background: #ea580c; border-color: #f97316; }
    #reporte-pdf-root { background: #fff; color: #0f172a; padding: 1rem 1.25rem; border-radius: 8px; }
    #reporte-pdf-root h2.pdf-h2 { margin: 0 0 0.5rem; font-size: 1rem; color: #0f172a; }
    #reporte-pdf-root .pdf-meta { font-size: 0.8rem; color: #475569; margin-bottom: 0.75rem; }
    #reporte-pdf-root table { width: 100%; border-collapse: collapse; font-size: 0.75rem; }
    #reporte-pdf-root th, #reporte-pdf-root td { border: 1px solid #cbd5e1; padding: 0.35rem 0.45rem; text-align: left; vertical-align: top; }
    #reporte-pdf-root th { background: #e2e8f0; font-weight: 600; }
    #reporte-pdf-root tr:nth-child(even) { background: #f8fafc; }
</style>
CSS;
}

function ventas_reporte_tabs_styles(): void
{
    echo <<<'CSS'
<style>
    .reporte-tabs { background: #1e293b; border-radius: 12px; border: 1px solid #334155; overflow: hidden; }
    .reporte-tab-bar { display: flex; gap: 0; border-bottom: 1px solid #334155; background: #0f172a; }
    .reporte-tab {
        flex: 1; max-width: 220px; padding: 0.65rem 1rem; border: none; background: transparent; color: #94a3b8;
        cursor: pointer; font: inherit; font-size: 0.9rem; border-bottom: 3px solid transparent;
    }
    .reporte-tab:hover { color: #e2e8f0; }
    .reporte-tab.is-active { color: #fff; border-bottom-color: #3b82f6; background: #1e293b; }
    .reporte-tab-panel { display: none; padding: 1rem; }
    .reporte-tab-panel.is-active { display: block; }
    .reporte-tab-panel.chart-panel { min-height: 280px; }
    .chart-inner { position: relative; height: min(55vh, 420px); }
</style>
CSS;
}

function ventas_reporte_tabs_script(): void
{
    echo <<<'JS'
<script>
(function () {
    function init(root) {
        var tabs = [].slice.call(root.querySelectorAll('.reporte-tab'));
        var panels = [].slice.call(root.querySelectorAll('.reporte-tab-panel'));
        function show(i) {
            var n = tabs.length;
            if (n === 0) return;
            if (i < 0 || i >= n) i = 0;
            tabs.forEach(function (t, ix) { t.classList.toggle('is-active', ix === i); });
            panels.forEach(function (p, ix) { p.classList.toggle('is-active', ix === i); });
            try {
                root.dispatchEvent(new CustomEvent('ventas-reporte-tab', { detail: { index: i } }));
            } catch (e) {}
        }
        tabs.forEach(function (t, i) {
            t.addEventListener('click', function () { show(i); });
        });
        var start = 0;
        try {
            if (location.hash === '#grafico') start = 1;
            var sp = new URLSearchParams(location.search);
            if (sp.get('tab') === '1') start = 1;
        } catch (e) {}
        show(start);
    }
    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('[data-ventas-tabs]').forEach(init);
    });
})();
</script>
JS;
}

function ventas_reporte_pdf_script(): void
{
    echo <<<'HTML'
<script src="https://cdn.jsdelivr.net/npm/html2pdf.js@0.10.1/dist/html2pdf.bundle.min.js" crossorigin="anonymous"></script>
<script>
function ventasBindPdfDownload(buttonId, rootId, filename) {
    var btn = document.getElementById(buttonId);
    var el = document.getElementById(rootId);
    if (!btn || !el) return;
    btn.addEventListener('click', function () {
        if (!window.html2pdf) return;
        window.html2pdf().set({
            margin: [10, 10, 10, 10],
            filename: filename,
            image: { type: 'jpeg', quality: 0.93 },
            html2canvas: { scale: 2, useCORS: true, logging: false },
            jsPDF: { unit: 'mm', format: 'a4', orientation: 'landscape' },
            pagebreak: { mode: ['avoid-all', 'css', 'legacy'] }
        }).from(el).save();
    });
}
</script>
HTML;
}
