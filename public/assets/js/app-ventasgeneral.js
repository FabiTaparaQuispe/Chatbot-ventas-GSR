(function ($) {
    'use strict';

    var DT_LANG = {
        processing: 'Procesando…',
        search: 'Buscar:',
        lengthMenu: 'Mostrar _MENU_ registros',
        info: 'Mostrando _START_ a _END_ de _TOTAL_ registros',
        infoEmpty: 'Mostrando 0 a 0 de 0 registros',
        infoFiltered: '(filtrado de _MAX_ registros totales)',
        loadingRecords: 'Cargando…',
        zeroRecords: 'No se encontraron registros',
        emptyTable: 'Sin datos en la tabla',
        paginate: { first: 'Primero', previous: 'Anterior', next: 'Siguiente', last: 'Último' },
    };

    function ymd(d) {
        var y = d.getFullYear();
        var m = String(d.getMonth() + 1).padStart(2, '0');
        var da = String(d.getDate()).padStart(2, '0');
        return y + '-' + m + '-' + da;
    }

    function defaultRange() {
        // Por defecto: sin filtro de fechas (como la tabla original).
        return { desde: '', hasta: '' };
    }

    /** YYYY-MM → último día del mes (YYYY-MM-DD) */
    function lastDayOfCalendarMonth(ym) {
        var s = String(ym || '').trim();
        if (!/^\d{4}-\d{2}$/.test(s)) return '';
        var parts = s.split('-');
        var y = parseInt(parts[0], 10);
        var mo = parseInt(parts[1], 10);
        var last = new Date(y, mo, 0).getDate();
        return s + '-' + String(last).padStart(2, '0');
    }

    function syncPeriodoUI() {
        var mode = String($('#vgPeriodo').val() || 'todos').trim();
        $('#vgWrapDesde, #vgWrapHasta, #vgWrapMes, #vgWrapMesDesde, #vgWrapMesHasta').addClass('hidden');
        if (mode === 'todos') {
            return;
        }
        if (mode === 'por_fecha') {
            $('#vgWrapDesde').removeClass('hidden');
            $('#lblVgDesde').text('Fecha');
            return;
        }
        if (mode === 'entre_fechas') {
            $('#vgWrapDesde, #vgWrapHasta').removeClass('hidden');
            $('#lblVgDesde').text('Desde');
            return;
        }
        if (mode === 'por_mes') {
            $('#vgWrapMes').removeClass('hidden');
            return;
        }
        if (mode === 'entre_meses') {
            $('#vgWrapMesDesde, #vgWrapMesHasta').removeClass('hidden');
        }
    }

    /** Convierte el modo Período + inputs visibles en desde/hasta para la API */
    function resolvedDateFilter() {
        var mode = String($('#vgPeriodo').val() || 'todos').trim();
        var dDesde = String($('#vgDesde').val() || '').trim();
        var dHasta = String($('#vgHasta').val() || '').trim();
        var mes = String($('#vgMes').val() || '').trim();
        var mesDesde = String($('#vgMesDesde').val() || '').trim();
        var mesHasta = String($('#vgMesHasta').val() || '').trim();

        if (mode === 'todos') {
            return { desde: '', hasta: '' };
        }
        if (mode === 'por_fecha') {
            if (!dDesde) return { desde: '', hasta: '' };
            return { desde: dDesde, hasta: dDesde };
        }
        if (mode === 'entre_fechas') {
            if (dDesde && dHasta && dDesde > dHasta) {
                return { desde: dHasta, hasta: dDesde };
            }
            return { desde: dDesde, hasta: dHasta };
        }
        if (mode === 'por_mes') {
            if (!mes) return { desde: '', hasta: '' };
            return { desde: mes + '-01', hasta: lastDayOfCalendarMonth(mes) };
        }
        if (mode === 'entre_meses') {
            if (!mesDesde || !mesHasta) return { desde: '', hasta: '' };
            var a = mesDesde;
            var b = mesHasta;
            if (a > b) {
                var t = a;
                a = b;
                b = t;
            }
            return { desde: a + '-01', hasta: lastDayOfCalendarMonth(b) };
        }
        return { desde: dDesde, hasta: dHasta };
    }

    function toggleFiltros() {
        var contenido = document.getElementById('contenidoFiltrosDemo');
        var icono = document.getElementById('iconoFiltrosDemo');
        var btn = document.getElementById('btnToggleFiltrosDemo');
        if (!contenido || !icono) return;
        contenido.classList.toggle('hidden');
        var open = !contenido.classList.contains('hidden');
        icono.classList.toggle('card-filtros-demo__chev--open', open);
        if (btn) btn.setAttribute('aria-expanded', open ? 'true' : 'false');
        if (table) {
            try {
                table.columns.adjust();
            } catch (e) {}
        }
    }

    var table;
    var ventasSearchTimer = null;
    var iconosBound = false;

    function currentFiltros() {
        var dr = resolvedDateFilter();
        return {
            desde: dr.desde,
            hasta: dr.hasta,
            nombre: ($('#vgNombre').val() || '').trim(),
            numero_doc: ($('#vgDoc').val() || '').trim(),
            tipo_documento: ($('#vgTipoDoc').val() || '').trim(),
            provincia: ($('#vgProvincia').val() || '').trim(),
        };
    }

    function escapeHtml(s) {
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function rebuildCards() {
        if (!table) return;
        var $c = $('#cardsContainer');
        $c.empty();
        var info = table.page.info();
        var rows = table.rows({ page: 'current' }).data().toArray();
        rows.forEach(function (row, idx) {
            var num = info.start + idx + 1;
            var nro = row[0] != null ? String(row[0]) : '';
            var fecha = row[1] != null ? String(row[1]) : '';
            var codCliente = row[2] != null ? String(row[2]) : '';
            var cliente = row[3] != null ? String(row[3]) : '';
            var doc = row[4] != null ? String(row[4]) : '';
            var item = row[5] != null ? String(row[5]) : '';
            var glosa = row[6] != null ? String(row[6]) : '';
            var cant = row[7] != null ? String(row[7]) : '';
            var valor = row[8] != null ? String(row[8]) : '';
            var zona = row[9] != null ? String(row[9]) : '';
            var tipoDoc = row[10] != null ? String(row[10]) : '';
            var provincia = row[11] != null ? String(row[11]) : '';
            var linea = row[12] != null ? String(row[12]) : '';

            var h =
                '<article class="card-item prod-card">' +
                '<div class="card-numero-row">#' +
                num +
                '</div>' +
                '<div class="card-campos">' +
                '<div class="card-row"><span class="label">N°</span><span>' +
                escapeHtml(nro) +
                '</span></div>' +
                '<div class="card-row"><span class="label">Fecha contable</span><span>' +
                escapeHtml(fecha) +
                '</span></div>' +
                '<div class="card-row"><span class="label">Código cliente</span><span>' +
                escapeHtml(codCliente) +
                '</span></div>' +
                '<div class="card-row"><span class="label">Nombre cliente</span><span>' +
                escapeHtml(cliente) +
                '</span></div>' +
                '<div class="card-row"><span class="label">Nº documento</span><span>' +
                escapeHtml(doc) +
                '</span></div>' +
                '<div class="card-row"><span class="label">Código ítem</span><span>' +
                escapeHtml(item) +
                '</span></div>' +
                '<div class="card-row"><span class="label">Cantidad</span><span>' +
                escapeHtml(cant) +
                '</span></div>' +
                '<div class="card-row"><span class="label">Importe</span><span>' +
                escapeHtml(valor) +
                '</span></div>' +
                '<div class="card-row"><span class="label">Zona comercial</span><span>' +
                escapeHtml(zona) +
                '</span></div>' +
                '<div class="card-row"><span class="label">Tipo documento</span><span>' +
                escapeHtml(tipoDoc) +
                '</span></div>' +
                '<div class="card-row"><span class="label">Provincia</span><span>' +
                escapeHtml(provincia) +
                '</span></div>' +
                '<div class="card-row"><span class="label">Línea comercial</span><span>' +
                escapeHtml(linea) +
                '</span></div>' +
                '</div>' +
                '<div class="prod-card-meta">' +
                escapeHtml(glosa) +
                '</div>' +
                '</article>';
            $c.append(h);
        });
    }

    function renderIconosControls() {
        if (!table) return;
        if (!$('#productosIconosControls').is(':visible')) return;
        var $c = $('#productosIconosControls');
        if (!$c.length) return;
        if (!$c.find('.productos-iconos-toolbar-row').length) {
            var html =
                '<div class="productos-iconos-toolbar-row iconos-toolbar-row">' +
                '<div class="dataTables_length"><label>Mostrar ' +
                '<select class="js-len dt-toolbar-length-select cards-length-select">' +
                '<option value="20">20</option><option value="25">25</option><option value="50">50</option><option value="100">100</option>' +
                '</select> registros</label></div>' +
                '<div class="dataTables_filter"><label>Buscar <input type="search" class="js-search" placeholder=""></label></div>' +
                '</div>';
            $c.html(html);
        }
        if (!iconosBound) {
            $c.on('change.ventas', '.js-len', function () {
                var val = parseInt($(this).val(), 10);
                if (table && !isNaN(val)) table.page.len(val).draw(false);
            });
            $c.on('input.ventas', '.js-search', function () {
                var val = ($(this).val() || '').toString();
                if (ventasSearchTimer) clearTimeout(ventasSearchTimer);
                ventasSearchTimer = setTimeout(function () {
                    if (table && table.search() !== val) table.search(val).draw();
                }, 220);
            });
            iconosBound = true;
        }
        var len = String(table.page.len());
        var search = table.search() || '';
        var $len = $c.find('.js-len');
        var $search = $c.find('.js-search');
        if ($len.length && $len.val() !== len) $len.val(len);
        if ($search.length && !$search.is(':focus') && $search.val() !== search) $search.val(search);
    }

    function updateCardsPagination() {
        if (!table || typeof window.buildPaginationIconos !== 'function') return;
        var vista = $('#tablaVentasWrapper').attr('data-vista') || 'lista';
        if (vista !== 'iconos') return;
        var info = table.page.info();
        $('#cardsControlsTopProductos').empty();
        $('#cardsPagination').html(window.buildPaginationIconos(info));
    }

    function syncVistaLayout() {
        var lista = $('#tablaVentasWrapper').attr('data-vista') === 'lista';
        $('#btnViewLista').toggleClass('active', lista);
        $('#btnViewIconos').toggleClass('active', !lista);
        if (lista) {
            $('#productosDtControls').show();
            $('#productosIconosControls').hide();
        } else {
            $('#productosDtControls').hide();
            $('#productosIconosControls').show();
            renderIconosControls();
        }
        if (table) {
            try {
                table.columns.adjust();
            } catch (e) {}
            rebuildCards();
            updateCardsPagination();
        }
    }

    function applyAndReload(resetPage) {
        if (!table) return;
        if (resetPage !== false) table.page('first');
        table.ajax.reload(null, false);
    }

    function initTable() {
        table = $('#tablaVentasGeneral').DataTable({
            language: DT_LANG,
            serverSide: true,
            processing: true,
            searching: true,
            ordering: false,
            scrollX: true,
            scrollCollapse: true,
            pageLength: 20,
            lengthMenu: [
                [20, 25, 50, 100],
                [20, 25, 50, 100],
            ],
            dom: '<"dt-top-row"lf>rt<"dt-bottom-row"ip>',
            // Evita parámetros con corchetes (search[value]) que en algunos XAMPP/Apache causan 400.
            ajax: function (dtReq, callback) {
                var f = currentFiltros();
                var params = {
                    draw: dtReq.draw,
                    start: dtReq.start,
                    length: dtReq.length,
                    search: dtReq.search && dtReq.search.value ? dtReq.search.value : '',
                    desde: f.desde,
                    hasta: f.hasta,
                    nombre: f.nombre,
                    numero_doc: f.numero_doc,
                    tipo_documento: f.tipo_documento,
                    provincia: f.provincia,
                };
                $.ajax({
                    url: 'api/ventasgeneral_dt.php',
                    type: 'GET',
                    dataType: 'json',
                    data: params,
                    success: function (json) {
                        callback(json);
                    },
                    error: function (xhr) {
                        try {
                            // Si el server devolvió HTML (login/error), lo registramos para debug rápido.
                            var t = (xhr && xhr.responseText ? String(xhr.responseText) : '').slice(0, 200);
                            if (t) console.warn('ventasgeneral_dt no-JSON:', t);
                        } catch (e) {}
                        callback({
                            draw: dtReq.draw,
                            recordsTotal: 0,
                            recordsFiltered: 0,
                            data: [],
                            error: 'HTTP ' + (xhr && xhr.status ? xhr.status : 'error'),
                        });
                    },
                });
            },
            columns: [
                { data: 0 },
                { data: 1 },
                { data: 2 },
                { data: 3 },
                { data: 4 },
                { data: 5 },
                { data: 6 },
                { data: 7 },
                { data: 8 },
                { data: 9 },
                { data: 10 },
                { data: 11 },
                { data: 12 },
            ],
            drawCallback: function () {
                rebuildCards();
                renderIconosControls();
                updateCardsPagination();
            },
            initComplete: function () {
                var $w = $('#tablaVentasGeneral').closest('.dataTables_wrapper');
                var $len = $w.find('.dataTables_length').first();
                var $filter = $w.find('.dataTables_filter').first();
                $('#productosDtControls').empty().append($len).append($filter);
                var vista = $('#tablaVentasWrapper').attr('data-vista') || 'lista';
                $('#productosDtControls').toggle(vista === 'lista');
                $('#productosIconosControls').toggle(vista === 'iconos');
                if (vista === 'iconos') {
                    renderIconosControls();
                }
                try { table.columns.adjust(); } catch (e) {}
            },
        });
    }

    $(function () {
        var r = defaultRange();
        $('#vgDesde').val(r.desde);
        $('#vgHasta').val(r.hasta);
        $('#vgPeriodo').val('todos');
        $('#vgMes').val('');
        $('#vgMesDesde').val('');
        $('#vgMesHasta').val('');
        syncPeriodoUI();
        $('#vgPeriodo').on('change', function () {
            syncPeriodoUI();
        });

        $('#btnToggleFiltrosDemo').on('click', toggleFiltros);
        $('#btnFiltrarVentas').on('click', function () {
            applyAndReload(true);
        });
        $('#btnLimpiarVentas').on('click', function () {
            $('#vgPeriodo').val('todos');
            $('#vgDesde').val('');
            $('#vgHasta').val('');
            $('#vgMes').val('');
            $('#vgMesDesde').val('');
            $('#vgMesHasta').val('');
            $('#vgNombre').val('');
            $('#vgDoc').val('');
            $('#vgTipoDoc').val('');
            $('#vgProvincia').val('');
            syncPeriodoUI();
            applyAndReload(true);
        });

        $('#btnViewLista').on('click', function () {
            $('#tablaVentasWrapper').attr('data-vista', 'lista');
            syncVistaLayout();
        });
        $('#btnViewIconos').on('click', function () {
            $('#tablaVentasWrapper').attr('data-vista', 'iconos');
            syncVistaLayout();
        });

        if ($(window).width() < 768) {
            $('#tablaVentasWrapper').attr('data-vista', 'iconos');
        }

        initTable();
        syncVistaLayout();
    });
})(jQuery);

