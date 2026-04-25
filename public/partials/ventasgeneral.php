<?php
declare(strict_types=1);
?>

<div class="page-head">
    <h1>Ventas general</h1>
</div>

<div class="card-filtros-demo">
    <button type="button" class="card-filtros-demo__head" id="btnToggleFiltrosDemo" aria-expanded="false" aria-controls="contenidoFiltrosDemo">
        <div class="card-filtros-demo__head-left">
            <span class="card-filtros-demo__title">Filtros de búsqueda</span>
        </div>
        <svg id="iconoFiltrosDemo" class="card-filtros-demo__chev" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
    </button>
    <div id="contenidoFiltrosDemo" class="card-filtros-demo__body hidden">
        <div class="filters-block filters-block--inner">
            <div class="filter-row">
                <div class="filter-field">
                    <label for="vgDesde">Desde</label>
                    <input type="date" id="vgDesde" />
                </div>
                <div class="filter-field">
                    <label for="vgHasta">Hasta</label>
                    <input type="date" id="vgHasta" />
                </div>
                <div class="filter-field">
                    <label for="vgNombre">Nombre cliente</label>
                    <input type="text" id="vgNombre" placeholder="Ingrese su nombre" />
                </div>
                <div class="filter-field">
                    <label for="vgDoc">Nº doc</label>
                    <input type="text" id="vgDoc" />
                </div>
            </div>
            <div class="filter-actions">
                <button type="button" class="btn btn-primary" id="btnFiltrarVentas"><i class="fas fa-filter"></i> Filtrar</button>
                <button type="button" class="btn btn-ghost" id="btnLimpiarVentas">Limpiar</button>
            </div>
        </div>
    </div>
</div>

<div class="tabla-listado-wrapper" id="tablaVentasWrapper" data-vista-tabla-iconos data-vista="lista">
    <div class="reportes-toolbar-row" id="ventasToolbarRow">
        <div class="view-toggle-group" id="viewToggleGroupVentas">
            <button type="button" class="view-toggle-btn active" id="btnViewLista" title="Lista">
                <i class="fas fa-list" aria-hidden="true"></i> Lista
            </button>
            <button type="button" class="view-toggle-btn" id="btnViewIconos" title="Iconos">
                <i class="fas fa-th" aria-hidden="true"></i> Iconos
            </button>
        </div>
        <div class="productos-dt-toolbar-slot" id="productosDtControls"></div>
        <div class="productos-dt-toolbar-slot" id="productosIconosControls" style="display: none;"></div>
    </div>

    <div class="view-tarjetas-wrap" id="viewTarjetas">
        <div id="cardsControlsTopProductos" class="productos-cards-controls-top" aria-hidden="true"></div>
        <div id="cardsContainer" class="cards-grid cards-grid-iconos" data-vista-cards="iconos"></div>
        <div id="cardsPagination" data-table="#tablaVentasGeneral" data-vista="iconos"></div>
    </div>

    <div class="view-lista-wrap productos-dt-skin" id="viewLista">
        <div class="table-wrapper overflow-x-auto">
            <table id="tablaVentasGeneral" class="data-table config-table display stripe nowrap" style="width:100%">
                <thead>
                    <tr>
                        <th>id</th>
                        <th>Fecha</th>
                        <th>CodCliente</th>
                        <th>Cliente</th>
                        <th>Doc</th>
                        <th>Ítem</th>
                        <th>Glosa</th>
                        <th>Cant</th>
                        <th>Valor</th>
                        <th>Zona</th>
                    </tr>
                </thead>
                <tbody></tbody>
            </table>
        </div>
    </div>
</div>

