<?php
declare(strict_types=1);
$defaultHasta = (new DateTimeImmutable('today'))->format('Y-m-d');
$defaultDesde = (new DateTimeImmutable('today'))->modify('-30 days')->format('Y-m-d');
?>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Gráficos · ventas</title>
    <link rel="stylesheet" href="style.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js" crossorigin="anonymous"></script>
</head>
<body>
    <div class="wrap">
        <header class="top">
            <h1>Gráficos</h1>
            <nav><a href="ventasgeneral_table.php">Ventas general</a></nav>
        </header>

        <form id="f" class="card">
            <label>Desde <input type="date" name="desde" id="desde" value="<?= htmlspecialchars($defaultDesde, ENT_QUOTES, 'UTF-8') ?>"></label>
            <label>Hasta <input type="date" name="hasta" id="hasta" value="<?= htmlspecialchars($defaultHasta, ENT_QUOTES, 'UTF-8') ?>"></label>
            <label>sale por fecha
                <select id="campo_sale">
                    <option value="tfecfac">tfecfac</option>
                    <option value="tfectra">tfectra</option>
                </select>
            </label>
            <button type="submit">Cargar</button>
        </form>

        <section class="card">
            <h2>ventasgeneral — Valor por día</h2>
            <div class="chart-wrap"><canvas id="c1"></canvas></div>
        </section>
        <section class="card">
            <h2>ventasgeneral — Top zonas (suma Valor)</h2>
            <div class="chart-wrap"><canvas id="c2"></canvas></div>
        </section>
        <section class="card">
            <h2>sale — Importe (timport) por día</h2>
            <div class="chart-wrap"><canvas id="c3"></canvas></div>
        </section>
        <p id="err" class="error" hidden></p>
    </div>
    <script>
    (function () {
        const base = '../api/stats.php';
        let ch1, ch2, ch3;

        async function loadJson(params) {
            const u = base + '?' + new URLSearchParams(params).toString();
            const r = await fetch(u);
            const j = await r.json();
            if (!j.ok) throw new Error(j.error || 'Error API');
            return j;
        }

        function destroyChart(c) {
            if (c) c.destroy();
        }

        document.getElementById('f').addEventListener('submit', async function (e) {
            e.preventDefault();
            const err = document.getElementById('err');
            err.hidden = true;
            const desde = document.getElementById('desde').value;
            const hasta = document.getElementById('hasta').value;
            const campo = document.getElementById('campo_sale').value;
            try {
                const [vgd, vgz, sd] = await Promise.all([
                    loadJson({ type: 'vg_daily', desde, hasta }),
                    loadJson({ type: 'vg_zonas', desde, hasta, limit: 12 }),
                    loadJson({ type: 'sale_daily', desde, hasta, campo }),
                ]);

                const labels1 = vgd.series.map(x => x.dia);
                const data1 = vgd.series.map(x => parseFloat(x.suma_valor) || 0);
                destroyChart(ch1);
                ch1 = new Chart(document.getElementById('c1'), {
                    type: 'line',
                    data: { labels: labels1, datasets: [{ label: 'Suma Valor', data: data1, borderColor: '#3b82f6', tension: 0.2 }] },
                    options: { responsive: true, maintainAspectRatio: false, scales: { x: { ticks: { maxRotation: 45 } } } }
                });

                const labels2 = vgz.series.map(x => x.zona);
                const data2 = vgz.series.map(x => parseFloat(x.suma_valor) || 0);
                destroyChart(ch2);
                ch2 = new Chart(document.getElementById('c2'), {
                    type: 'bar',
                    data: { labels: labels2, datasets: [{ label: 'Suma Valor', data: data2, backgroundColor: '#2563eb' }] },
                    options: { responsive: true, maintainAspectRatio: false, indexAxis: 'y' }
                });

                const labels3 = sd.series.map(x => x.dia);
                const data3 = sd.series.map(x => parseFloat(x.suma_importe) || 0);
                destroyChart(ch3);
                ch3 = new Chart(document.getElementById('c3'), {
                    type: 'bar',
                    data: { labels: labels3, datasets: [{ label: 'Suma timport', data: data3, backgroundColor: '#22c55e' }] },
                    options: { responsive: true, maintainAspectRatio: false, scales: { x: { ticks: { maxRotation: 45 } } } }
                });
            } catch (ex) {
                err.textContent = String(ex.message || ex);
                err.hidden = false;
            }
        });

        document.getElementById('f').dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
    })();
    </script>
</body>
</html>
