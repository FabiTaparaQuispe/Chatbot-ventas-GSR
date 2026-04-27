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
    .reporte-toolbar .btn-pdf { background: #b91c1c; border-color: #991b1b; color: #fff; }
    .reporte-toolbar .btn-pdf:hover { background: #dc2626; border-color: #b91c1c; }
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
<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js" crossorigin="anonymous"></script>
<script>
function ventasBindPdfDownload(buttonId, rootId, filename, opts) {
    var btn = document.getElementById(buttonId);
    var root = document.getElementById(rootId);
    if (!btn || !root || !window.jspdf || !window.jspdf.jsPDF) return;
    opts = opts || {};

    function pad2(n) { return String(n).padStart(2, '0'); }
    function nowStamp() {
        var d = new Date();
        return pad2(d.getDate()) + '/' + pad2(d.getMonth()+1) + '/' + d.getFullYear() + ' ' + pad2(d.getHours()) + ':' + pad2(d.getMinutes());
    }
    function safeText(s) { return String(s == null ? '' : s).replace(/\s+/g, ' ').trim(); }

    // Logo simple (SVG embebido) ya que el proyecto de referencia no trae PNG en disco.
    var LOGO_SVG = "data:image/svg+xml;base64," + btoa(unescape(encodeURIComponent(
        '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="60" viewBox="0 0 120 60">' +
        '<rect x="0" y="0" width="120" height="60" rx="10" fill="#ffffff"/>' +
        '<rect x="10" y="10" width="40" height="40" rx="10" fill="#2563eb" opacity="0.12"/>' +
        '<path d="M30 14l14 6v10c0 10-6 18-14 20-8-2-14-10-14-20V20l14-6z" fill="#2563eb"/>' +
        '</svg>'
    )));
    var COMPANY_NAME = (opts && opts.company) ? String(opts.company) : 'GRANJA RINCONADA DEL SUR S.A.';

    function collectTable() {
        var h2 = root.querySelector('h2');
        var meta = root.querySelector('.pdf-meta');
        var table = root.querySelector('table');
        var title = safeText(h2 ? h2.textContent : (opts.title || 'REPORTE'));
        var metaText = safeText(meta ? meta.textContent : '');
        if (!table) return { title: title, meta: metaText, head: [], rows: [] };
        var head = [];
        table.querySelectorAll('thead th').forEach(function(th){ head.push(safeText(th.textContent)); });
        var rows = [];
        table.querySelectorAll('tbody tr').forEach(function(tr){
            var r = [];
            tr.querySelectorAll('td').forEach(function(td){ r.push(safeText(td.textContent)); });
            if (r.length) rows.push(r);
        });
        // Columna contador N° (si no existe ya)
        if (head.length > 0) {
            var h0 = String(head[0] || '').toLowerCase().replace(/\./g, '').trim();
            var hasN = h0 === 'n°' || h0 === 'nº' || h0 === 'no' || h0 === 'nro' || h0 === 'numero' || h0 === 'n';
            if (!hasN) {
                head.unshift('N°');
                rows = rows.map(function (r, i) {
                    var rr = r.slice(0);
                    rr.unshift(String(i + 1));
                    return rr;
                });
            }
        }
        return { title: title, meta: metaText, head: head, rows: rows };
    }

    btn.addEventListener('click', function () {
        var data = collectTable();
        var doc = new window.jspdf.jsPDF({ unit: 'mm', format: 'a4', orientation: 'landscape' });

        var mL = 10, mR = 10, mT = 12, mB = 18;
        var pageW = doc.internal.pageSize.getWidth();
        var pageH = doc.internal.pageSize.getHeight();
        var contentW = pageW - mL - mR;
        var y = mT;

        var azul = [37, 99, 235];
        var bordeExt = 100;
        var bordeCel = 203;

        function drawHeaderBand() {
            var w1 = contentW * 0.2;
            var w2 = contentW * 0.6;
            var w3 = contentW * 0.2;
            var hCab = 14;

            doc.setLineWidth(0.25);
            doc.setDrawColor(bordeExt, bordeExt, bordeExt);

            doc.setFillColor(255, 255, 255);
            doc.rect(mL, y, w1, hCab, 'FD');
            doc.setFillColor(azul[0], azul[1], azul[2]);
            doc.rect(mL + w1, y, w2, hCab, 'F');
            doc.setFillColor(255, 255, 255);
            doc.rect(mL + w1 + w2, y, w3, hCab, 'FD');

            doc.setDrawColor(bordeExt, bordeExt, bordeExt);
            doc.rect(mL, y, contentW, hCab, 'S');
            doc.line(mL + w1, y, mL + w1, y + hCab);
            doc.line(mL + w1 + w2, y, mL + w1 + w2, y + hCab);

            // Izquierda: logo + empresa
            try {
                doc.addImage(LOGO_SVG, 'PNG', mL + 1.2, y + 2.2, 16.5, 9.6);
            } catch (e) {}
            try {
                doc.setFont('helvetica', 'bold');
                doc.setFontSize(8.2);
                doc.setTextColor(15, 23, 42);
                var txtW = Math.max(10, w1 - 20);
                var lines = doc.splitTextToSize(COMPANY_NAME, txtW);
                if (lines.length > 2) lines = lines.slice(0, 2);
                doc.text(lines, mL + 18.6, y + 5.2);
            } catch (e2) {}

            doc.setFont('helvetica', 'bold');
            doc.setFontSize(12);
            doc.setTextColor(255, 255, 255);
            var rawT = String(data.title || 'REPORTE').trim();
            var tit = (/^reporte\b/i.test(rawT) ? rawT : ('REPORTE: ' + rawT));
            doc.text(tit, mL + w1 + w2 / 2, y + 8.2, { align: 'center' });

            doc.setFont('helvetica', 'normal');
            doc.setFontSize(9);
            doc.setTextColor(71, 85, 105);
            // Derecha: fecha/hora centrada
            doc.text(nowStamp(), mL + w1 + w2 + w3 / 2, y + 7.2, { align: 'center' });

            y = y + hCab + 3;
        }

        function yMax() { return pageH - mB - 2; }

        function drawThead(head, colX, colW) {
            var hTh = 6;
            doc.setLineWidth(0.15);
            doc.setFont('helvetica', 'bold');
            doc.setFontSize(7.5);
            for (var t = 0; t < head.length; t++) {
                doc.setDrawColor(bordeCel, bordeCel, bordeCel);
                doc.setFillColor(azul[0], azul[1], azul[2]);
                doc.rect(colX[t], y, colW[t], hTh, 'F');
                doc.setDrawColor(bordeCel, bordeCel, bordeCel);
                doc.rect(colX[t], y, colW[t], hTh, 'S');
                doc.setTextColor(255, 255, 255);
                doc.text(String(head[t] || ''), colX[t] + 0.6, y + 4.2);
            }
            y += hTh;
        }

        function drawRow(cells, colX, colW) {
            var hTd = 4.5;
            if (y + hTd > yMax()) {
                doc.addPage();
                pageW = doc.internal.pageSize.getWidth();
                pageH = doc.internal.pageSize.getHeight();
                y = mT;
                drawThead(data.head, colX, colW);
            }
            doc.setFont('helvetica', 'normal');
            doc.setFontSize(7);
            doc.setTextColor(30, 41, 59);
            for (var c = 0; c < cells.length; c++) {
                doc.setDrawColor(bordeCel, bordeCel, bordeCel);
                doc.setFillColor(255, 255, 255);
                doc.rect(colX[c], y, colW[c], hTd, 'FD');
                var raw = String(cells[c] != null ? cells[c] : '');
                if (raw.length > 60) raw = raw.slice(0, 58) + '…';
                doc.text(doc.splitTextToSize(raw, colW[c] - 1.2)[0] || ' ', colX[c] + 0.5, y + 3.2);
            }
            y += hTd;
        }

        // Page 1
        drawHeaderBand();

        // Column widths: proporcionales a cantidad de columnas
        var n = Math.max(1, data.head.length || 1);
        var colW = [];
        for (var i = 0; i < n; i++) colW.push(contentW / n);
        var colX = [mL];
        for (var k = 0; k < n; k++) colX.push(colX[k] + colW[k]);

        drawThead(data.head, colX, colW);
        for (var r = 0; r < data.rows.length; r++) {
            drawRow(data.rows[r], colX, colW);
        }

        // Paginación
        var totalP = doc.internal.getNumberOfPages();
        for (var pi = 1; pi <= totalP; pi++) {
            doc.setPage(pi);
            doc.setFont('helvetica', 'normal');
            doc.setFontSize(9);
            doc.setTextColor(30, 41, 59);
            var pw0 = doc.internal.pageSize.getWidth();
            var ph0 = doc.internal.pageSize.getHeight();
            doc.text(String(pi) + ' de ' + String(totalP), pw0 / 2, ph0 - 6, { align: 'center' });
        }

        doc.save(filename || 'reporte.pdf');
    });
}
</script>
HTML;
}
