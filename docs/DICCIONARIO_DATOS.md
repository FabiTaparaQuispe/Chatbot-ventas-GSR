# Diccionario mínimo de datos — ventas avícolas

Fuentes: tablas `sale` y `ventasgeneral2` (MySQL, MyISAM, sin `FOREIGN KEY`). Las relaciones con maestros de cliente/producto son **lógicas** (no están en los dumps actuales).

## Tabla `sale` (detalle operativo / ERP)

| Campo | Tipo lógico | Uso |
|-------|-------------|-----|
| `treg`, `sw` | PK compuesta | Identifican línea dentro de un registro/movimiento. |
| `tasi` | Día del mes | Número del día del mes de la operación (ej. 1 de enero → `1`). |
| `tlib` | Libro | Ej. `RV` = registro de ventas. |
| `talm` | Almacén | Código almacén. |
| `tfectra` | Fecha | Fecha de operación/traslado en sistema. |
| `tfecfac` | Fecha | Fecha del comprobante (factura/boleta). |
| `tprocli` | Documento cliente | **DNI o RUC** del cliente (Perú), como texto. |
| `mprocli` | Texto | Mnemónico / referencia corta del cliente. |
| `tdoc`, `tserie`, `tnumfac` | Documento | Tipo, serie y número de comprobante. |
| `tcodven`, `tvended` | Vendedor | Código vendedor (duplicidad semántica; unificar criterio). |
| `tcodigo` | Producto | Código artículo. |
| `tglosa` | Texto | Descripción de línea. |
| `tcantid` | Cantidad | Unidades. |
| `timport` | Importe | Valor de línea en la moneda indicada en `tmon`. |
| `tmon` | Moneda | Tipo o símbolo de moneda del importe (ej. `S/.`). |
| `tigv`, `tpreuni`, `tpreuniigv` | Montos | IGV y precios. |
| `tcencos` | Centro de costos | Código de centro de costos del ERP/plan contable; **la nomenclatura es la definida por la empresa** (no asumir partición fija tipo "3+3" sin tabla de equivalencias). |
| `tventa`, `tproce` | Catálogo | Canal / "venta a" y origen / "procede". |
| `placa` | Logística | Placa vehículo. |
| `tfchlot`, `tnumlot` | Lote | Fecha/número lote. |
| `tdepart` | Zona | Posible zona/departamento (validar catálogo). |

## Tabla `ventasgeneral2` (líneas enriquecidas / ETL)

| Campo | Uso |
|-------|-----|
| `id` | PK autoincremental. |
| `FechaContable` | Fecha contable para reportes (base de todos los filtros por período). |
| `CodigoCliente`, `NombreCliente` | Cliente final; `CodigoCliente` suele alinearse con **DNI/RUC** como en `sale.tprocli`. |
| `CodigoCoorporativo`, `NombreCoorporativo` | Agrupación corporativa (cadenas, grupos empresariales). |
| `CodigoDocumento` | Código interno del tipo de comprobante (ej. `07` = Nota de Crédito). |
| `TipoDocumento` | Descripción del tipo de comprobante (ej. `Boleta de Venta`, `Factura`). |
| `SerieDocumento` | Serie del comprobante. |
| `NumeroDocumento` | Número correlativo del comprobante. |
| `NumeroFactura` | Número de factura/comprobante legible (usado en búsquedas y filtros). |
| `CodigoItem` | Código de producto/artículo. |
| `GlosaDetalle` | Descripción de línea / glosa del artículo. |
| `Cantidad` | Unidades vendidas por línea. |
| `Peso` | Peso por línea (kg). |
| `Valor` | Importe de la línea en soles (S/). |
| `ZonaComercial` | Zona comercial asignada al cliente. |
| `DescripcionZonaPrecio` | Zona de precio (mercado); usado con prefijo para filtrar ciudad/región (AQP, TACNA, MOQUEGUA, LAJOYA, etc.). |
| `DescripcionZonaDistribucion` | Zona de distribución logística. |
| `RutaComercial` | Ruta comercial de visita/despacho. |
| `LineaComercial` | Línea de negocio o familia comercial del producto. |
| `Provincia` | Provincia del cliente o destino de la venta (ej. `AREQUIPA`, `TACNA`). |

## Cuándo usar cada tabla

- **`sale`:** granularidad ERP, `tcencos`, `tventa`/`tproce`, vendedor, fechas `tfecfac`/`tfectra`.
- **`ventasgeneral2`:** respuestas con **nombre de cliente**, **zonas/rutas**, **provincia**, **tipo de documento** y métricas (Valor, Cantidad, Peso) sin unir a maestros.

## Filtros disponibles en el chatbot

| Parámetro chatbot | Campo SQL | Herramientas |
|-------------------|-----------|--------------|
| `fecha_desde` / `fecha_hasta` | `FechaContable` | todas |
| `nombre_cliente` | `NombreCliente` LIKE | `ventasgeneral_buscar` |
| `numero_doc` | `NumeroFactura` LIKE | `ventasgeneral_buscar` |
| `cod_item` | `CodigoItem` = | `ventasgeneral_buscar` |
| `tdoc` | `CodigoDocumento` = | `ventasgeneral_buscar` |
| `prefijo_descri_zona_precio` | `DescripcionZonaPrecio` LIKE prefijo% | `ventasgeneral_buscar`, `ventasgeneral_resumen`, `ventasgeneral_top_clientes_zona_precio` |
| `zona_comercial` | `ZonaComercial` = | `ventasgeneral_resumen` |
| `cod_cliente` | `CodigoCliente` = | `ventasgeneral_resumen` |
| `provincia` | `Provincia` LIKE | `ventasgeneral_buscar`, `ventasgeneral_resumen` |
| `tipo_documento` | `TipoDocumento` LIKE | `ventasgeneral_buscar`, `ventasgeneral_resumen` |
