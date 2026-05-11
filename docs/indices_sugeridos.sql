-- ============================================================================
-- Índices recomendados para la base de datos del chatbot.
-- IMPORTANTE: estos índices NO se crean automáticamente. Ejecutarlos en una
-- ventana de mantenimiento; en una tabla grande (varios cientos de miles de
-- filas o más) el ALTER puede tardar varios minutos y bloquear escrituras.
--
-- Validar antes con: SHOW INDEX FROM <tabla>;
-- Y luego revisar con: EXPLAIN <tu SELECT>;
-- ============================================================================


-- ----------------------------------------------------------------------------
-- Tabla: ventasgeneral2  (fuente principal de los reportes de "línea comercial")
-- Actualmente NO tiene índices y todos los filtros hacen FULL TABLE SCAN.
-- Esto explica la lentitud de los reportes "Resumen / Diario / Precio por día".
-- ----------------------------------------------------------------------------

-- 1) Filtro principal por fecha contable + línea comercial.
--    Cubre el WHERE base de todos los reportes cuando tipo_fecha = "contable".
ALTER TABLE ventasgeneral2
  ADD INDEX idx_vg2_fcont_linea (FechaContable, CodigoLineaComercial);

-- 2) Filtro por día de proceso (cuando tipo_fecha = "proceso").
ALTER TABLE ventasgeneral2
  ADD INDEX idx_vg2_fproc (fechaProceso);

-- 3) Cascada de filtros / multi-select de cliente.
ALTER TABLE ventasgeneral2
  ADD INDEX idx_vg2_cliente (CodigoCliente);

-- 4) Filtros y agrupaciones por provincia y corporativo.
ALTER TABLE ventasgeneral2
  ADD INDEX idx_vg2_provincia (Provincia);
ALTER TABLE ventasgeneral2
  ADD INDEX idx_vg2_corp (NombreCoorporativo(64));

-- 5) Filtros por tipo de documento (los reportes restringen a '01','03').
ALTER TABLE ventasgeneral2
  ADD INDEX idx_vg2_coddoc (CodigoDocumento);

-- (Opcional) Si se filtra mucho por código de item:
-- ALTER TABLE ventasgeneral2 ADD INDEX idx_vg2_coditem (CodigoItem);


-- ----------------------------------------------------------------------------
-- Tabla: ventasgeneral  (fuente legacy del chatbot)
-- El dump original solo declara PRIMARY KEY (`id`).
-- ----------------------------------------------------------------------------
-- ALTER TABLE ventasgeneral ADD INDEX idx_fechacont (FechaCont);
-- ALTER TABLE ventasgeneral ADD INDEX idx_cliente_fecha (CodCliente, FechaCont);
-- ALTER TABLE ventasgeneral ADD INDEX idx_numdoc (NumeroDoc);


-- ----------------------------------------------------------------------------
-- Tabla: sale  (ya incluye índices en tfecfac, tprocli, tfectra, tcodigo,
-- (tdoc, tnumfac)). Opcional si filtran mucho por centro de costo:
-- ----------------------------------------------------------------------------
-- ALTER TABLE sale ADD INDEX idx_tcencos (tcencos);
