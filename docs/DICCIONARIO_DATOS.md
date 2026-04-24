# Diccionario mínimo de datos — ventas avícolas

Fuentes: tablas `sale` y `ventasgeneral` (MySQL, MyISAM, sin `FOREIGN KEY`). Las relaciones con maestros de cliente/producto son **lógicas** (no están en los dumps actuales).

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
| `tcencos` | Centro de costos | Código de centro de costos del ERP/plan contable; **la nomenclatura es la definida por la empresa** (no asumir partición fija tipo “3+3” sin tabla de equivalencias). |
| `tventa`, `tproce` | Catálogo | Canal / “venta a” y origen / “procede”. |
| `placa` | Logística | Placa vehículo. |
| `tfchlot`, `tnumlot` | Lote | Fecha/número lote. |
| `tdepart` | Zona | Posible zona/departamento (validar catálogo). |

## Tabla `ventasgeneral` (líneas enriquecidas / ETL)

| Campo | Uso |
|-------|-----|
| `id` | PK autoincremental. |
| `FechaCont` | Fecha para reportes (contable/operativa; validar con negocio). |
| `CodCliente`, `NombreCliente` | Cliente final; `CodCliente` suele alinearse con **DNI/RUC** como en `sale.tprocli`. |
| `CodCoorporativo`, `NombreCoorporativo` | Agrupación corporativa. |
| `TDoc`, `Serie`, `Numero`, `NumeroDoc` | Comprobante. |
| `CodItem`, `Glosa` | Producto y descripción. |
| `Cantidad`, `Peso`, `Valor` | Métricas por línea. |
| `CodZonaDistribucion`, `DescriZonaDistribucion` | Zona distribución. |
| `CodZonaPrecio`, `DescriZonaPrecio` | Zona precio. |
| `ZonaComercial`, `RutaComercial` | Jerarquía comercial. |
| `CodDescuento`, `DescriDescuento` | Descuento aplicado. |
| `CodMotivoDevolucion`, `DescriDevolucion` | Devoluciones. |
| `nom_db`, `usuarioRegistro`, `fechaHoraRegistro` | Traza ETL. |

## Cuándo usar cada tabla

- **`sale`:** granularidad ERP, `tcencos`, `tventa`/`tproce`, vendedor, fechas `tfecfac`/`tfectra`.
- **`ventasgeneral`:** respuestas con **nombre de cliente** y **zonas/rutas** sin unir a maestros.
