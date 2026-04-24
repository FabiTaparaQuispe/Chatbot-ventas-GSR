# Validación con negocio (checklist)

Este documento lista lo que debe confirmar quien opera el ERP o el data mart antes de usar las consultas en producción o el chatbot. Marque cada ítem cuando esté validado.

## Fechas: cuál es la “fecha de venta” oficial

| Pregunta | Opciones típicas | Tabla `sale` | Tabla `ventasgeneral` |
|----------|------------------|--------------|------------------------|
| ¿Para reportes de facturación se usa la fecha del comprobante o la de registro en sistema? | Comprobante vs operación | `tfecfac` vs `tfectra` / `tdate` | `FechaCont` (confirmar si es contable u operativa) |
| ¿Los reportes históricos del BI usan la misma fecha que el chatbot? | Sí / No | — | Alinear criterio |

**Recomendación técnica:** hasta validar, el SQL de referencia usa `tfecfac` en `sale` y `FechaCont` en `ventasgeneral`; cambiar en un solo lugar (`ToolRegistry` / consultas) si negocio indica otro campo.

## `treg` y `sw` en `sale`

- ¿`treg` identifica un movimiento único y `sw` la línea dentro del movimiento?
- ¿Existen anulaciones o notas de crédito que dupliquen `treg` o requieran filtrar por `toperacion`, `swd` u otro flag?
- ¿Algún reporte oficial excluye ciertos valores de `tlib` (por ejemplo solo `RV`)?

## Origen y correspondencia `ventasgeneral` vs `sale`

- ¿`ventasgeneral` se alimenta desde la misma base que `sale`, de otra instancia, o de ETL externo?
- ¿Puede haber líneas en una tabla que no existan en la otra?
- ¿El vínculo entre ambas es documento (`TDoc`+`Serie`+`Numero` ≈ `tdoc`+`tserie`+`tnumfac`) más cliente e ítem, o hay otra clave?

## Campos de canal y logística

- Catálogo de valores de `tventa` y `tproce` (venta a / procede).
- Significado exacto de `trp` / `trpsol` (jabas vs otros importes).

## Centro de costos `tcencos`

- Documentar la **nomenclatura oficial** (estructura del código, longitud, significado de cada parte) según plan de cuentas / ERP.
- ¿Hay tabla o catálogo maestro de centros de costo para traducir código → nombre (granja, campaña, etc.)?
- ¿Líneas con `tcencos` vacío o nulo se excluyen de ciertos reportes?

## Firmas

- Validado por: _________________  
- Fecha: _________________
