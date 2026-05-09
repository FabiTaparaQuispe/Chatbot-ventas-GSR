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

    /* clip: true evita que las etiquetas se dibujen sobre la leyenda u otros márgenes */
    var base = {
        clamp: true,
        clip: true,
        backgroundColor: null,
        borderRadius: 0,
        padding: 0,
        font: { size: 9, weight: '600' },
    };

    global.VENTAS_CHART_DATALABELS = {
        linePesoKg: Object.assign({}, base, {
            color: dlThemeColor('#ecfdf5', '#14532d'),
            align: 'top',
            offset: 4,
            display: function (ctx) {
                return hasVal(ctx.dataset.data[ctx.dataIndex]);
            },
            formatter: function (value) {
                if (!hasVal(value)) return '';
                return Number(value).toLocaleString('es-PE', {
                    minimumFractionDigits: 0,
                    maximumFractionDigits: 2,
                });
            },
        }),

        lineValorSol: Object.assign({}, base, {
            color: dlThemeColor('#dbeafe', '#1e3a8a'),
            align: 'top',
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

        linePrecioKg: Object.assign({}, base, {
            color: dlThemeColor('#ffedd5', '#9a3412'),
            align: 'top',
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
                        maximumFractionDigits: 4,
                    }) +
                    '/kg'
                );
            },
        }),

        /** Línea multi-serie: offset por dataset; leyenda suele ir abajo para no solaparse */
        linePrecioKgMulti: Object.assign({}, base, {
            color: dlThemeColor('#f1f5f9', '#0f172a'),
            align: 'top',
            offset: function (ctx) {
                return 6 + (ctx.datasetIndex || 0) * 12;
            },
            display: function (ctx) {
                return hasVal(ctx.dataset.data[ctx.dataIndex]);
            },
            formatter: function (value) {
                if (!hasVal(value)) return '';
                return (
                    'S/ ' +
                    Number(value).toLocaleString('es-PE', {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 4,
                    }) +
                    '/kg'
                );
            },
        }),

        hbarPesoKg: Object.assign({}, base, {
            color: dlThemeColor('#dcfce7', '#14532d'),
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
            color: dlThemeColor('#dbeafe', '#1e40af'),
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
