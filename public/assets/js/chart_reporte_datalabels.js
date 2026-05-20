/**
 * Helpers comunes para reportes (leyenda legible por tema, animación).
 * Opcional: registra chartjs-plugin-datalabels y expone VENTAS_CHART_DATALABELS.
 * Orden: chart.umd.min.js → [chartjs-plugin-datalabels.min.js] → este archivo
 */
(function (global) {
    function themeIsDark() {
        try {
            var html = global.document && global.document.documentElement;
            return html && html.getAttribute('data-theme') === 'dark';
        } catch (e) {
            return false;
        }
    }

    function themeLegendColor() {
        try {
            /* Oscuro: casi blanco; claro: slate oscuro */
            return themeIsDark() ? '#f8fafc' : '#1e293b';
        } catch (e) {
            return '#1e293b';
        }
    }

    global.reporteChartLegendColor = themeLegendColor;

    /** Color de etiqueta de dato: claro en tema oscuro, oscuro en tema claro (sin fondo) */
    function dlThemeColor(onDarkHex, onLightHex) {
        return function () {
            return themeIsDark() ? onDarkHex : onLightHex;
        };
    }

    /** Animación al crear / refrescar datos (las actualizaciones con update('none') no animan) */
    global.reporteChartAnimate = {
        animation: {
            duration: 1000,
            easing: 'easeOutQuart',
        },
    };

    /**
     * Actualiza el color de la leyenda de todos los Chart.js del documento
     * (p. ej. al cambiar tema con appSetTheme / app-theme-change).
     */
    function reporteChartsApplyTheme() {
        if (typeof Chart === 'undefined' || typeof Chart.getChart !== 'function') return;
        var col = themeLegendColor();
        var doc = global.document;
        if (!doc || !doc.querySelectorAll) return;
        try {
            doc.querySelectorAll('canvas').forEach(function (canvas) {
                var ch = Chart.getChart(canvas);
                if (!ch) return;
                var opts = ch.options && ch.options.plugins;
                if (opts && opts.legend) {
                    if (!opts.legend.labels) opts.legend.labels = {};
                    opts.legend.labels.color = col;
                }
                /* Recalcula colores scriptables de datalabels al cambiar tema */
                ch.update('none');
            });
        } catch (e) {}
    }

    global.reporteChartsApplyTheme = reporteChartsApplyTheme;

    if (global.document && !global.__reporteChartThemeBound) {
        global.__reporteChartThemeBound = true;
        global.document.addEventListener('app-theme-change', reporteChartsApplyTheme);
    }

    if (typeof Chart === 'undefined') return;

    var CDL = global.ChartDataLabels;
    if (CDL) {
        try {
            Chart.register(CDL);
        } catch (e) {
            CDL = null;
        }
    }
    if (!CDL) {
        global.VENTAS_CHART_DATALABELS = null;
        return;
    }

    function hasVal(v) {
        return v != null && !isNaN(v);
    }

    /**
     * Para series largas (>30 puntos) solo muestra etiqueta en:
     * primer punto, último punto, valor mínimo y valor máximo.
     * Para series cortas muestra todos.
     */
    function dlDisplayKeyPoints(ctx) {
        var data = ctx.dataset.data;
        var i = ctx.dataIndex;
        if (!hasVal(data[i])) return false;
        var n = data.length;
        if (n <= 30) return true;
        // Siempre mostrar primero y último con valor
        var first = 0;
        while (first < n && !hasVal(data[first])) first++;
        var last = n - 1;
        while (last >= 0 && !hasVal(data[last])) last--;
        if (i === first || i === last) return true;
        // Mínimo y máximo globales
        var minVal = Infinity, maxVal = -Infinity, minIdx = -1, maxIdx = -1;
        for (var j = 0; j < n; j++) {
            if (!hasVal(data[j])) continue;
            var v = Number(data[j]);
            if (v < minVal) { minVal = v; minIdx = j; }
            if (v > maxVal) { maxVal = v; maxIdx = j; }
        }
        if (i === minIdx || i === maxIdx) return true;
        // Puntos de inflexión: cambio >= 0.5% respecto al punto anterior válido
        var prev = i - 1;
        while (prev >= 0 && !hasVal(data[prev])) prev--;
        if (prev >= 0) {
            var cur = Number(data[i]);
            var prevVal = Number(data[prev]);
            if (prevVal !== 0 && Math.abs(cur - prevVal) / Math.abs(prevVal) >= 0.005) return true;
        }
        return false;
    }

    /**
     * Devuelve el color de la serie/punto: borderColor (líneas) o backgroundColor
     * (barras, potencialmente arreglo por dato), para que la etiqueta tenga el mismo
     * color que su línea o barra y sea fácil identificar a qué corresponde.
     */
    function dlSeriesColor(ctx) {
        var ds = (ctx && ctx.dataset) || {};
        var idx = ctx && ctx.dataIndex;
        var c = ds.borderColor;
        if (Array.isArray(c)) c = c[idx];
        if (!c) {
            c = ds.backgroundColor;
            if (Array.isArray(c)) c = c[idx];
        }
        if (!c) c = ds.pointBackgroundColor;
        return c || themeLegendColor();
    }

    global.reporteChartDataLabelSeriesColor = dlSeriesColor;

    /* clip: true evita que las etiquetas se dibujen sobre la leyenda u otros márgenes */
    var base = {
        clamp: true,
        clip: true,
        backgroundColor: null,
        borderRadius: 0,
        padding: 0,
        font: { size: 12, weight: '700' },
    };

    global.VENTAS_CHART_DATALABELS = {
        linePesoKg: Object.assign({}, base, {
            color: dlSeriesColor,
            align: 'top',
            offset: 4,
            display: dlDisplayKeyPoints,
            formatter: function (value) {
                if (!hasVal(value)) return '';
                return Number(value).toLocaleString('es-PE', {
                    minimumFractionDigits: 0,
                    maximumFractionDigits: 2,
                });
            },
        }),

        lineValorSol: Object.assign({}, base, {
            color: dlSeriesColor,
            align: 'top',
            offset: 4,
            display: dlDisplayKeyPoints,
            formatter: function (value) {
                if (!hasVal(value)) return '';
                return (
                    'S/ ' +
                    Number(value).toLocaleString('es-PE', {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                    })
                );
            },
        }),

        linePrecioKg: Object.assign({}, base, {
            color: dlSeriesColor,
            align: 'top',
            offset: 4,
            display: dlDisplayKeyPoints,
            formatter: function (value) {
                if (!hasVal(value)) return '';
                return (
                    'S/ ' +
                    Number(value).toLocaleString('es-PE', {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                    })
                );
            },
        }),

        /** Línea multi-serie: offset por dataset; leyenda suele ir abajo para no solaparse */
        linePrecioKgMulti: Object.assign({}, base, {
            color: dlSeriesColor,
            align: 'top',
            offset: function (ctx) {
                return 6 + (ctx.datasetIndex || 0) * 12;
            },
            display: dlDisplayKeyPoints,
            formatter: function (value) {
                if (!hasVal(value)) return '';
                return (
                    'S/ ' +
                    Number(value).toLocaleString('es-PE', {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                    })
                );
            },
        }),

        hbarPesoKg: Object.assign({}, base, {
            color: dlSeriesColor,
            anchor: 'end',
            align: 'end',
            offset: 4,
            display: function (ctx) {
                return hasVal(ctx.dataset.data[ctx.dataIndex]);
            },
            formatter: function (value) {
                if (!hasVal(value)) return '';
                return (
                    Number(value).toLocaleString('es-PE', {
                        minimumFractionDigits: 0,
                        maximumFractionDigits: 2,
                    }) + ' kg'
                );
            },
        }),

        hbarValorSol: Object.assign({}, base, {
            color: dlSeriesColor,
            anchor: 'end',
            align: 'end',
            offset: 4,
            display: function (ctx) {
                return hasVal(ctx.dataset.data[ctx.dataIndex]);
            },
            formatter: function (value) {
                if (!hasVal(value)) return '';
                return (
                    'S/ ' +
                    Number(value).toLocaleString('es-PE', {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                    })
                );
            },
        }),
    };
})(typeof window !== 'undefined' ? window : this);
