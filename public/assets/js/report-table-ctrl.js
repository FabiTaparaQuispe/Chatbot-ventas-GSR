/* Controles de tabla para páginas de reportes: búsqueda, filtro provincia,
   ordenamiento por columna, registros/página, paginación y vista Lista / Iconos.
   Se activa en cualquier <table class="rct-auto">. */
(function () {
    'use strict';

    var DEFAULT_PP = 30;

    /* Inyectar estilos de ordenamiento y tarjetas una sola vez */
    if (!document.getElementById('rct-sort-styles')) {
        var style = document.createElement('style');
        style.id = 'rct-sort-styles';
        style.textContent =
            /* Cabeceras ordenables */
            '.rct-sortable{cursor:pointer;user-select:none;white-space:nowrap}'
            + '.rct-sortable::after{content:" ⇅";opacity:.3;font-size:.78em}'
            + '.rct-sort-asc::after{content:" ↑";opacity:1}'
            + '.rct-sort-desc::after{content:" ↓";opacity:1}'
            /* Tarjeta: layout completo una columna por campo */
            + '.rct-wrap .card-item{overflow-wrap:normal}'
            + '.rct-wrap .card-campos{grid-template-columns:1fr!important;gap:.22rem 0!important;padding:.75rem!important}'
            + '.rct-wrap .card-row{display:grid!important;grid-template-columns:minmax(7rem,44%) 1fr!important;gap:.25rem .6rem!important;align-items:baseline!important}'
            + '.rct-wrap .card-row .label{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}'
            + '.rct-wrap .card-row span:not(.label){overflow:visible!important;text-overflow:unset!important;word-break:break-word}'
            /* Grid de tarjetas multi-columna */
            + '@media(min-width:640px){.rct-wrap .cards-grid-iconos{grid-template-columns:repeat(2,minmax(0,1fr))!important}}'
            + '@media(min-width:1100px){.rct-wrap .cards-grid-iconos{grid-template-columns:repeat(3,minmax(0,1fr))!important}}'
            /* Fila de totales en tfoot */
            + '.rct-totals-row td{border-top:2px solid #94a3b8!important;background:#f1f5f9!important;font-weight:700!important;font-size:.88em;padding:.45rem .75rem!important;white-space:nowrap}'
            + 'html[data-theme="dark"] .rct-totals-row td{background:#1e293b!important;border-color:#475569!important;color:#e2e8f0!important}';
        document.head.appendChild(style);
    }

    function escH(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function buildPag(page, total) {
        if (total <= 1) return '';
        var h = '<span class="paginate_button previous rct-pg-btn' + (page === 0 ? ' disabled' : '') + '" data-rp="prev">Anterior</span>';
        var s = Math.max(0, page - 2), e = Math.min(total - 1, s + 4);
        if (e - s < 4) s = Math.max(0, e - 4);
        for (var p = s; p <= e; p++) {
            h += '<span class="paginate_button rct-pg-btn' + (p === page ? ' current' : '') + '" data-rp="' + p + '">' + (p + 1) + '</span>';
        }
        h += '<span class="paginate_button next rct-pg-btn' + (page === total - 1 ? ' disabled' : '') + '" data-rp="next">Siguiente</span>';
        return h;
    }

    function parseNum(s) {
        var n = parseFloat(String(s).replace(/[^\d.\-]/g, ''));
        return isNaN(n) ? null : n;
    }

    function normKey(s) {
        return String(s == null ? '' : s).trim().toUpperCase();
    }

    function initTableCtrl(tableEl) {
        var tbody = tableEl.querySelector('tbody');
        if (!tbody) return;
        var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
        if (rows.length < 2) return;

        var ths = Array.prototype.slice.call(tableEl.querySelectorAll('thead th'));
        var cols = ths.map(function (th) { return th.textContent.trim(); });

        /* Fuente de verdad inmutable */
        var origRows = rows.slice();
        var origData = rows.map(function (tr) {
            return Array.prototype.slice.call(tr.querySelectorAll('td')).map(function (td) { return td.textContent.trim(); });
        });
        /* Índices ordenados (puede reordenarse al hacer click en columna) */
        var sortedIndices = origRows.map(function (_, i) { return i; });

        /* Detectar columnas filtrables */
        var provIdx = -1;
        var corpIdx = -1;
        for (var ci = 0; ci < cols.length; ci++) {
            if (cols[ci].toLowerCase() === 'provincia') provIdx = ci;
            if (/corporativo/i.test(cols[ci])) corpIdx = ci;
        }

        var tableWrap = tableEl.closest('.table-wrapper') || tableEl.parentElement;
        var parent = tableWrap.parentElement;

        var wrap = document.createElement('div');
        wrap.className = 'rct-wrap productos-dt-skin';
        parent.insertBefore(wrap, tableWrap);

        /* Dropdown de provincias */
        var provHTML = '';
        if (provIdx >= 0) {
            var provinces = [];
            var seenProv = {};
            origData.forEach(function (row) {
                var p = row[provIdx] || '';
                var k = normKey(p);
                if (k && !seenProv[k]) {
                    seenProv[k] = String(p).trim();
                    provinces.push(seenProv[k]);
                }
            });
            provinces.sort(function (a, b) { return a.localeCompare(b, 'es'); });
            provHTML = '<div class="dataTables_filter"><label>Provincia '
                + '<select class="rct-prov chat-ct-pp"><option value="">Todas</option>'
                + provinces.map(function (p) { return '<option value="' + escH(p) + '">' + escH(p) + '</option>'; }).join('')
                + '</select></label></div>';
        }

        /* Dropdown de corporativos */
        var corpHTML = '';
        if (corpIdx >= 0) {
            var corps = [];
            var seenCorp = {};
            origData.forEach(function (row) {
                var c = row[corpIdx] || '';
                var k = normKey(c);
                if (k && !seenCorp[k]) {
                    seenCorp[k] = String(c).trim();
                    corps.push(seenCorp[k]);
                }
            });
            corps.sort(function (a, b) { return a.localeCompare(b, 'es'); });
            corpHTML = '<div class="dataTables_filter"><label>Corporativo '
                + '<select class="rct-corp chat-ct-pp"><option value="">Todos</option>'
                + corps.map(function (c) { return '<option value="' + escH(c) + '">' + escH(c) + '</option>'; }).join('')
                + '</select></label></div>';
        }

        /* Toolbar */
        var toolbar = document.createElement('div');
        toolbar.className = 'reportes-toolbar-row rct-toolbar';
        toolbar.innerHTML =
            '<div class="view-toggle-group">'
            + '<button type="button" class="view-toggle-btn active" data-rct-v="lista" title="Vista lista">'
            + '<i class="fas fa-list" aria-hidden="true"></i> Lista</button>'
            + '<button type="button" class="view-toggle-btn" data-rct-v="iconos" title="Vista iconos">'
            + '<i class="fas fa-th" aria-hidden="true"></i> Iconos</button>'
            + '</div>'
            + '<div class="ventas-chat-table-controls">'
            + provHTML
            + corpHTML
            + '<div class="dataTables_length"><label>Mostrar '
            + '<select class="rct-pp chat-ct-pp">'
            + '<option value="10">10</option><option value="20">20</option>'
            + '<option value="30" selected>30</option><option value="50">50</option>'
            + '<option value="100">100</option><option value="0">Todos</option>'
            + '</select> registros</label></div>'
            + '<div class="dataTables_filter"><label>Buscar '
            + '<input type="search" class="rct-q chat-ct-q" placeholder=""></label></div>'
            + '</div>';

        /* Vista tarjetas */
        var cardsWrap = document.createElement('div');
        cardsWrap.className = 'view-tarjetas-wrap rct-cards-wrap';
        cardsWrap.style.display = 'none';
        cardsWrap.innerHTML = '<div class="cards-grid cards-grid-iconos" data-vista-cards="iconos"></div>';

        /* Fila inferior: info + paginación */
        var bottomRow = document.createElement('div');
        bottomRow.className = 'dt-bottom-row';
        bottomRow.innerHTML =
            '<div class="dataTables_info rct-info"></div>'
            + '<div class="dataTables_paginate paginate_button_wrap rct-pag"></div>';

        wrap.appendChild(toolbar);
        wrap.appendChild(tableWrap);
        wrap.appendChild(cardsWrap);
        wrap.appendChild(bottomRow);

        /* Estado */
        var st = { page: 0, pp: DEFAULT_PP, q: '', prov: '', corp: '', view: 'lista' };
        var sortState = { col: -1, dir: 'asc' };

        /* Cabeceras ordenables */
        ths.forEach(function (th, idx) {
            th.classList.add('rct-sortable');
            th.setAttribute('title', 'Ordenar por ' + (cols[idx] || 'columna'));
            th.addEventListener('click', function () {
                if (sortState.col === idx) {
                    sortState.dir = sortState.dir === 'asc' ? 'desc' : 'asc';
                } else {
                    sortState.col = idx;
                    sortState.dir = 'asc';
                }
                /* Detectar si la columna es numérica */
                var isNumeric = origData.some(function (row) {
                    return row[idx] !== undefined && parseNum(row[idx]) !== null;
                });
                sortedIndices.sort(function (a, b) {
                    var va = origData[a][idx] || '';
                    var vb = origData[b][idx] || '';
                    var cmp;
                    if (isNumeric) {
                        var na = parseNum(va), nb = parseNum(vb);
                        cmp = (na === null ? -Infinity : na) - (nb === null ? -Infinity : nb);
                    } else {
                        cmp = va.localeCompare(vb, 'es');
                    }
                    return sortState.dir === 'asc' ? cmp : -cmp;
                });
                ths.forEach(function (h, i) {
                    h.classList.remove('rct-sort-asc', 'rct-sort-desc');
                    if (i === sortState.col) h.classList.add(sortState.dir === 'asc' ? 'rct-sort-asc' : 'rct-sort-desc');
                });
                st.page = 0;
                render();
            });
        });

        /* --- Fila de totales en tfoot --- */
        var sumColIndices = [];
        var precioKgColIdx = -1, pesoColIdx = -1, valorColIdx = -1;
        var cumplColIdx = -1, pedidoColIdx = -1, vendidoColIdx = -1;

        ths.forEach(function (th, idx) {
            if (/text-align\s*:\s*right/i.test(th.getAttribute('style') || '')) {
                sumColIndices.push(idx);
            }
            var name = (cols[idx] || '').toLowerCase();
            if (/precio.*kg|precio_kg/i.test(name)) precioKgColIdx = idx;
            else if (/\bpeso\b/i.test(name)) pesoColIdx = idx;
            else if (/\bvalor\b/i.test(name)) valorColIdx = idx;
            if (/cumplimiento/i.test(name)) cumplColIdx = idx;
            else if (/pedido/i.test(name)) pedidoColIdx = idx;
            else if (/vendido/i.test(name)) vendidoColIdx = idx;
        });
        /* precio/kg se calcula como promedio ponderado, no se suma directamente */
        if (precioKgColIdx >= 0) {
            var pkPos = sumColIndices.indexOf(precioKgColIdx);
            if (pkPos >= 0) sumColIndices.splice(pkPos, 1);
        }
        /* cumplimiento es un % — se muestra ponderado (vendido/pedido), no se suma */
        if (cumplColIdx >= 0) {
            var cPos = sumColIndices.indexOf(cumplColIdx);
            if (cPos >= 0) sumColIndices.splice(cPos, 1);
        }

        var tfootCells = null;
        if (sumColIndices.length > 0) {
            var tfoot = tableEl.querySelector('tfoot') || tableEl.appendChild(document.createElement('tfoot'));
            /* Eliminar fila de totales preexistente del servidor para no duplicar */
            var existingTr = tfoot.querySelector('.rct-totals-row');
            if (existingTr) tfoot.removeChild(existingTr);
            var tfootTr = document.createElement('tr');
            tfootTr.className = 'rct-totals-row';
            tfoot.appendChild(tfootTr);
            tfootCells = ths.map(function (th, idx) {
                var td = document.createElement('td');
                if (sumColIndices.indexOf(idx) >= 0 || idx === precioKgColIdx) td.style.textAlign = 'right';
                tfootTr.appendChild(td);
                return td;
            });
        }

        function fmtSum(n, dec) {
            return n.toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec });
        }

        function renderTotals(fi) {
            if (!tfootCells) return;
            if (fi.length === 0) {
                tfootCells.forEach(function (td) { td.textContent = ''; });
                return;
            }
            var sums = {};
            sumColIndices.forEach(function (idx) { sums[idx] = 0; });
            if (pesoColIdx >= 0) sums[pesoColIdx] = sums[pesoColIdx] || 0;
            if (valorColIdx >= 0) sums[valorColIdx] = sums[valorColIdx] || 0;
            fi.forEach(function (i) {
                sumColIndices.forEach(function (idx) {
                    var n = parseNum(origData[i][idx]);
                    if (n !== null) sums[idx] += n;
                });
                /* También acumular peso y valor aunque no estén en sumColIndices (para precio/kg) */
                if (precioKgColIdx >= 0) {
                    if (pesoColIdx >= 0 && sumColIndices.indexOf(pesoColIdx) < 0) {
                        var np = parseNum(origData[i][pesoColIdx]); if (np !== null) sums[pesoColIdx] = (sums[pesoColIdx] || 0) + np;
                    }
                    if (valorColIdx >= 0 && sumColIndices.indexOf(valorColIdx) < 0) {
                        var nv = parseNum(origData[i][valorColIdx]); if (nv !== null) sums[valorColIdx] = (sums[valorColIdx] || 0) + nv;
                    }
                }
            });
            tfootCells.forEach(function (td, idx) {
                if (idx === 0) {
                    td.textContent = 'Totales (' + fi.length + ' filas)';
                    td.style.fontStyle = 'italic';
                } else if (idx === precioKgColIdx) {
                    var p = sums[pesoColIdx] || 0, v = sums[valorColIdx] || 0;
                    td.textContent = p > 0 ? fmtSum(v / p, 4) : '—';
                } else if (idx === cumplColIdx) {
                    var tp = sums[pedidoColIdx] || 0, tv = sums[vendidoColIdx] || 0;
                    td.textContent = tp > 0 ? fmtSum(tv / tp * 100, 1) + '%' : '—';
                } else if (sumColIndices.indexOf(idx) >= 0) {
                    td.textContent = fmtSum(sums[idx], 2);
                } else {
                    td.textContent = '';
                }
            });
        }

        function getFiltered() {
            var q = st.q;
            var prov = st.prov;
            var corp = st.corp;
            var provK = prov ? normKey(prov) : '';
            var corpK = corp ? normKey(corp) : '';
            return sortedIndices.filter(function (i) {
                var row = origData[i];
                if (prov && provIdx >= 0 && normKey(row[provIdx] || '') !== provK) return false;
                if (corp && corpIdx >= 0 && normKey(row[corpIdx] || '') !== corpK) return false;
                if (q && !row.some(function (c) { return c.toLowerCase().indexOf(q) >= 0; })) return false;
                return true;
            });
        }

        /* Exponer API mínima para que scripts de gráficas reaccionen a filtros client-side */
        tableEl.__rct = tableEl.__rct || {};
        tableEl.__rct.cols = cols;
        tableEl.__rct.origData = origData;
        tableEl.__rct.getFilteredIndices = getFiltered;

        function render() {
            var fi = getFiltered();
            var pp = st.pp;
            var total = pp === 0 ? 1 : Math.max(1, Math.ceil(fi.length / pp));
            st.page = Math.min(st.page, total - 1);
            var start = pp === 0 ? 0 : st.page * pp;
            var end = pp === 0 ? fi.length : Math.min(start + pp, fi.length);
            var pageIndices = fi.slice(start, end);

            var infoEl = bottomRow.querySelector('.rct-info');
            if (infoEl) {
                infoEl.textContent = fi.length === 0 ? 'Sin resultados'
                    : 'Mostrando ' + (start + 1) + ' a ' + end + ' de ' + fi.length + ' registros'
                      + (fi.length < origRows.length ? ' (filtrados de ' + origRows.length + ' total)' : '');
            }

            var pagEl = bottomRow.querySelector('.rct-pag');
            if (pagEl) pagEl.innerHTML = buildPag(st.page, total);

            renderTotals(fi);

            try {
                tableEl.__rct.filteredIndices = fi.slice();
                tableEl.__rct.filters = { prov: st.prov, corp: st.corp, q: st.q };
                tableEl.dispatchEvent(new CustomEvent('rct:filtered', {
                    detail: { filteredIndices: tableEl.__rct.filteredIndices, filters: tableEl.__rct.filters }
                }));
            } catch (e) { /* no-op */ }

            if (st.view === 'lista') {
                tableWrap.style.display = '';
                cardsWrap.style.display = 'none';
                /* Reordenar físicamente las filas en el DOM según el orden actual de sortedIndices */
                var visibleSet = {};
                pageIndices.forEach(function (i) { visibleSet[i] = true; });
                sortedIndices.forEach(function (i) {
                    origRows[i].style.display = visibleSet[i] ? '' : 'none';
                    tbody.appendChild(origRows[i]);
                });
            } else {
                tableWrap.style.display = 'none';
                cardsWrap.style.display = 'block';
                var grid = cardsWrap.querySelector('.cards-grid');
                if (grid) {
                    grid.innerHTML = pageIndices.map(function (i) {
                        var row = origData[i];
                        var fields = cols.slice(1).map(function (col, ci) {
                            return '<div class="card-row"><span class="label">' + escH(col) + '</span>'
                                + '<span>' + escH(row[ci + 1] || '') + '</span></div>';
                        }).join('');
                        return '<article class="card-item prod-card">'
                            + '<div class="card-numero-row">#' + escH(row[0] || '') + '</div>'
                            + '<div class="card-campos">' + fields + '</div></article>';
                    }).join('');
                }
            }
        }

        /* Eventos toolbar */
        toolbar.addEventListener('click', function (e) {
            var btn = e.target.closest('[data-rct-v]');
            if (!btn) return;
            st.view = btn.getAttribute('data-rct-v');
            Array.prototype.forEach.call(toolbar.querySelectorAll('[data-rct-v]'), function (b) {
                b.classList.toggle('active', b.getAttribute('data-rct-v') === st.view);
            });
            render();
        });

        toolbar.addEventListener('change', function (e) {
            if (e.target.classList.contains('rct-pp')) {
                st.pp = parseInt(e.target.value, 10);
                st.page = 0;
                render();
            }
            if (e.target.classList.contains('rct-prov')) {
                st.prov = e.target.value;
                st.page = 0;
                render();
            }
            if (e.target.classList.contains('rct-corp')) {
                st.corp = e.target.value;
                st.page = 0;
                render();
            }
        });

        var _qt;
        toolbar.addEventListener('input', function (e) {
            if (e.target.classList.contains('rct-q')) {
                clearTimeout(_qt);
                _qt = setTimeout(function () {
                    st.q = e.target.value.toLowerCase().trim();
                    st.page = 0;
                    render();
                }, 250);
            }
        });

        bottomRow.addEventListener('click', function (e) {
            var pb = e.target.closest('.rct-pg-btn');
            if (!pb || pb.classList.contains('disabled')) return;
            var action = pb.getAttribute('data-rp');
            var fi2 = getFiltered();
            var pp = st.pp;
            var total = pp === 0 ? 1 : Math.max(1, Math.ceil(fi2.length / pp));
            if (action === 'prev') st.page = Math.max(0, st.page - 1);
            else if (action === 'next') st.page = Math.min(total - 1, st.page + 1);
            else { var n = parseInt(action, 10); if (!isNaN(n)) st.page = Math.max(0, Math.min(total - 1, n)); }
            render();
        });

        render();
    }

    function autoInit() {
        var tables = document.querySelectorAll('table.rct-auto');
        Array.prototype.forEach.call(tables, function (t) { initTableCtrl(t); });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', autoInit);
    } else {
        autoInit();
    }
})();
