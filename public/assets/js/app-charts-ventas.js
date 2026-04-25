(function () {
    'use strict';

    if (typeof Chart === 'undefined') return;

    var chartDaily;
    var chartZonas;

    var LAB_BARRAS_RGBA = [
        { f: 0.8, b: 1, rgb: [54, 162, 235] },
        { f: 0.8, b: 1, rgb: [75, 192, 192] },
        { f: 0.8, b: 1, rgb: [153, 102, 255] },
        { f: 0.8, b: 1, rgb: [255, 99, 132] },
        { f: 0.8, b: 1, rgb: [255, 159, 64] },
        { f: 0.8, b: 1, rgb: [255, 205, 86] },
        { f: 0.8, b: 1, rgb: [201, 203, 207] },
    ];

    function rgba(c, a) {
        return 'rgba(' + c.rgb[0] + ', ' + c.rgb[1] + ', ' + c.rgb[2] + ', ' + a + ')';
    }

    function styleByIndex(i) {
        var c = LAB_BARRAS_RGBA[i % LAB_BARRAS_RGBA.length];
        return { bg: rgba(c, c.f), border: rgba(c, c.b) };
    }

    function syncDefaults() {
        var dark = document.documentElement.getAttribute('data-theme') === 'dark';
        Chart.defaults.color = dark ? '#a1a1aa' : '#64748b';
        Chart.defaults.borderColor = dark ? '#3f3f46' : '#e5e7eb';
    }

    async function loadJson(params) {
        var u = 'api/stats.php?' + new URLSearchParams(params).toString();
        var r = await fetch(u);
        var j = await r.json();
        if (!j.ok) throw new Error(j.error || 'Error API');
        return j;
    }

    function destroyCharts() {
        if (chartDaily) {
            chartDaily.destroy();
            chartDaily = null;
        }
        if (chartZonas) {
            chartZonas.destroy();
            chartZonas = null;
        }
    }

    function runAfterLayout(fn) {
        requestAnimationFrame(function () {
            requestAnimationFrame(fn);
        });
    }

    function defaultRange() {
        var now = new Date();
        var hasta = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        var desde = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 30);
        function ymd(d) {
            return (
                d.getFullYear() +
                '-' +
                String(d.getMonth() + 1).padStart(2, '0') +
                '-' +
                String(d.getDate()).padStart(2, '0')
            );
        }
        return { desde: ymd(desde), hasta: ymd(hasta) };
    }

    async function build() {
        var c1 = document.getElementById('chartVentasDiarias');
        var c2 = document.getElementById('chartZonas');
        if (!c1 || !c2) return;

        destroyCharts();
        syncDefaults();

        var r = defaultRange();
        var daily = await loadJson({ type: 'vg_daily', desde: r.desde, hasta: r.hasta });
        var zonas = await loadJson({ type: 'vg_zonas', desde: r.desde, hasta: r.hasta, limit: 12 });

        var labelsDaily = daily.series.map(function (x) {
            return x.dia;
        });
        var valuesDaily = daily.series.map(function (x) {
            return Number(x.suma_valor) || 0;
        });

        var labelsZ = zonas.series.map(function (x) {
            return x.zona;
        });
        var valuesZ = zonas.series.map(function (x) {
            return Number(x.suma_valor) || 0;
        });

        var bgZ = [];
        var brZ = [];
        for (var i = 0; i < valuesZ.length; i++) {
            var st = styleByIndex(i);
            bgZ.push(st.bg);
            brZ.push(st.border);
        }

        chartDaily = new Chart(c1, {
            type: 'line',
            data: {
                labels: labelsDaily,
                datasets: [
                    {
                        label: 'Suma Valor',
                        data: valuesDaily.map(function () {
                            return 0;
                        }),
                        borderColor: rgba(LAB_BARRAS_RGBA[0], 1),
                        backgroundColor: rgba(LAB_BARRAS_RGBA[0], 0.18),
                        pointRadius: 0,
                        tension: 0.25,
                        fill: true,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                animation: { duration: 1500, easing: 'easeOutCubic' },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: 'rgba(15, 23, 42, 0.92)',
                        padding: 12,
                        cornerRadius: 8,
                    },
                },
                scales: {
                    x: {
                        ticks: { minRotation: 45, maxRotation: 45, autoSkip: true },
                        grid: { display: false },
                    },
                    y: { beginAtZero: true, grid: { color: Chart.defaults.borderColor } },
                },
            },
        });

        chartZonas = new Chart(c2, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Suma Valor',
                        data: [],
                        backgroundColor: bgZ,
                        borderColor: brZ,
                        borderWidth: 1,
                        maxBarThickness: 48,
                    },
                ],
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    duration: 1500,
                    easing: 'easeOutCubic',
                    delay: function (context) {
                        if (context.type === 'data' && context.mode === 'default') {
                            return (context.dataIndex || 0) * 125;
                        }
                        return 0;
                    },
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: 'rgba(15, 23, 42, 0.92)',
                        padding: 12,
                        cornerRadius: 8,
                    },
                },
                scales: {
                    x: { beginAtZero: true, grid: { color: Chart.defaults.borderColor } },
                    y: { grid: { display: false } },
                },
            },
        });

        runAfterLayout(function () {
            if (chartDaily) {
                chartDaily.data.datasets[0].data = valuesDaily;
                chartDaily.update();
            }
            if (chartZonas) {
                chartZonas.data.labels = labelsZ;
                chartZonas.data.datasets[0].data = valuesZ;
                chartZonas.update();
            }
        });
    }

    function boot() {
        build().catch(function (e) {
            // Silenciar en UI: si falla API, al menos no rompe layout.
            console.error(e);
        });
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
    else boot();

    window.addEventListener('app-theme-change', function () {
        boot();
    });
})();

