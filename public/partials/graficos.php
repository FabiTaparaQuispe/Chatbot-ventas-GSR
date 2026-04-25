<?php
declare(strict_types=1);
?>

<div class="graficos-page">
    <h1 class="graficos-page-heading">Gráficos</h1>
    <div class="graficos-grid">
        <div class="graficos-card graficos-card--donut">
            <div class="graficos-card-head">
                <span class="graficos-card-icon" aria-hidden="true"><i class="fas fa-chart-line"></i></span>
                <div>
                    <h2 class="graficos-card-title">Ventas por día (Valor)</h2>
                </div>
            </div>
            <div class="graficos-canvas-shell">
                <canvas id="chartVentasDiarias" aria-label="Gráfico línea de ventas por día"></canvas>
            </div>
        </div>

        <div class="graficos-card graficos-card--bar">
            <div class="graficos-card-head">
                <span class="graficos-card-icon graficos-card-icon--alt" aria-hidden="true"><i class="fas fa-chart-column"></i></span>
                <div>
                    <h2 class="graficos-card-title">Top zonas (Valor)</h2>
                </div>
            </div>
            <div class="graficos-canvas-shell">
                <canvas id="chartZonas" aria-label="Gráfico barras top zonas"></canvas>
            </div>
        </div>
    </div>
</div>

