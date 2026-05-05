function ventasBindPdfDownload(buttonId, rootId, filename, opts) {
    var btn = document.getElementById(buttonId);
    var root = document.getElementById(rootId);
    if (!btn || !root || !window.jspdf || !window.jspdf.jsPDF) return;
    opts = opts || {};

    var DEFAULT_COMPANY = 'GRANJA RINCONADA DEL SUR S.A.';
    var DEFAULT_LOGO_URLS = ['/assets/img/empresa-logo.png', '/assets/img/empresa-logo.svg'];

    function pad2(n) { return String(n).padStart(2, '0'); }
    function nowStamp() {
        var d = new Date();
        return pad2(d.getDate()) + '/' + pad2(d.getMonth()+1) + '/' + d.getFullYear() + ' ' + pad2(d.getHours()) + ':' + pad2(d.getMinutes());
    }
    function safeText(s) { return String(s == null ? '' : s).replace(/\s+/g, ' ').trim(); }

    function companyName() {
        if (opts && opts.company) return String(opts.company);
        try {
            var v = document.body && document.body.getAttribute('data-app-company');
            if (v) return v;
        } catch (e) {}
        return DEFAULT_COMPANY;
    }

    function logoUrlList() {
        if (opts && opts.logoUrl) return [String(opts.logoUrl)];
        try {
            var one = document.body && document.body.getAttribute('data-pdf-logo');
            if (one) return [one].concat(DEFAULT_LOGO_URLS.filter(function (u) { return u !== one; }));
        } catch (e2) {}
        return DEFAULT_LOGO_URLS.slice();
    }

    /** Convierte una imagen ya cargada a PNG data URL (jsPDF). */
    function imageToPngDataUrl(img, maxW, maxH) {
        var nw = img.naturalWidth || img.width || 1;
        var nh = img.naturalHeight || img.height || 1;
        var scale = Math.min(maxW / nw, maxH / nh, 1);
        var cw = Math.max(1, Math.round(nw * scale));
        var ch = Math.max(1, Math.round(nh * scale));
        var c = document.createElement('canvas');
        c.width = cw;
        c.height = ch;
        var ctx = c.getContext('2d');
        ctx.clearRect(0, 0, cw, ch);
        ctx.drawImage(img, 0, 0, cw, ch);
        return c.toDataURL('image/png');
    }

    function rasterizeSvgDataUrl(svgDataUrl, maxW, maxH, cb) {
        var img = new Image();
        img.onload = function () {
            try { cb(imageToPngDataUrl(img, maxW, maxH)); } catch (e) { cb(null); }
        };
        img.onerror = function () { cb(null); };
        img.src = svgDataUrl;
    }

    /** Obtiene PNG data URL para el encabezado (intenta PNG/SVG del servidor; si falla, marca por defecto). */
    function loadLogoPng(cb) {
        var urls = logoUrlList();
        var fallbackSvg = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(
            '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="80" viewBox="0 0 200 80">' +
            '<rect width="200" height="80" rx="12" fill="#ffffff"/>' +
            '<rect x="14" y="14" width="52" height="52" rx="10" fill="#2563eb" opacity="0.12"/>' +
            '<path d="M40 22l18 8v12c0 12-8 22-18 25-10-3-18-13-18-25V30l18-8z" fill="#2563eb"/>' +
            '</svg>'
        );
        var maxRaster = 320;

        function finishTry(i) {
            if (i >= urls.length) {
                rasterizeSvgDataUrl(fallbackSvg, maxRaster, maxRaster, function (png) { cb(png); });
                return;
            }
            var url = urls[i];
            var im = new Image();
            im.crossOrigin = 'anonymous';
            im.onload = function () {
                try {
                    cb(imageToPngDataUrl(im, maxRaster, maxRaster));
                } catch (e) {
                    finishTry(i + 1);
                }
            };
            im.onerror = function () { finishTry(i + 1); };
            im.src = url;
        }
        finishTry(0);
    }

    function collectTable() {
        var h2 = root.querySelector('h2');
        var meta = root.querySelector('.pdf-meta') || root.querySelector('.reporte-informe-meta');
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
        if (head.length > 0) {
            var h0 = String(head[0] || '').toLowerCase().replace(/\./g, '').trim();
            var hasN = h0 === 'n°' || h0 === 'nº' || h0 === 'no' || h0 === 'nro' || h0 === 'numero' || h0 === 'n';
            if (!hasN) {
                head.unshift('N°');
                rows = rows.map(function (r, idx) {
                    var rr = r.slice(0);
                    rr.unshift(String(idx + 1));
                    return rr;
                });
            }
        }
        return { title: title, meta: metaText, head: head, rows: rows };
    }

    btn.addEventListener('click', function () {
        var data = collectTable();
        var COMPANY_NAME = companyName();

        loadLogoPng(function (logoPng) {
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

                var x0 = mL + 1.4;
                var logoW = 12;
                var logoH = 10;
                var yLogo = y + (hCab - logoH) / 2;
                if (logoPng) {
                    try {
                        doc.addImage(logoPng, 'PNG', x0, yLogo, logoW, logoH);
                    } catch (e1) {}
                }

                doc.setFont('helvetica', 'bold');
                doc.setFontSize(8.2);
                doc.setTextColor(15, 23, 42);
                var textX = x0 + logoW + 2;
                var txtW = Math.max(8, mL + w1 - textX - 1.5);
                var lines = doc.splitTextToSize(COMPANY_NAME, txtW);
                if (lines.length > 2) lines = lines.slice(0, 2);
                var lineGap = 3.3;
                var blockH = lines.length * lineGap;
                var yText0 = y + (hCab - blockH) / 2 + lineGap * 0.65;
                doc.text(lines, textX, yText0);

                doc.setFont('helvetica', 'bold');
                doc.setFontSize(12);
                doc.setTextColor(255, 255, 255);
                var rawT = String(data.title || 'REPORTE').trim();
                var tit = (/^reporte\b/i.test(rawT) ? rawT : ('REPORTE: ' + rawT));
                doc.text(tit, mL + w1 + w2 / 2, y + 8.2, { align: 'center' });

                doc.setFont('helvetica', 'normal');
                doc.setFontSize(9);
                doc.setTextColor(71, 85, 105);
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

            drawHeaderBand();

            var n = Math.max(1, data.head.length || 1);
            var colW = [];
            for (var i = 0; i < n; i++) colW.push(contentW / n);
            var colX = [mL];
            for (var k = 0; k < n; k++) colX.push(colX[k] + colW[k]);

            drawThead(data.head, colX, colW);
            for (var r = 0; r < data.rows.length; r++) {
                drawRow(data.rows[r], colX, colW);
            }

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
    });
}
