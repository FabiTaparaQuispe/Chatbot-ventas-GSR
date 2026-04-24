-- Índices sugeridos para `ventasgeneral` si se usa como fuente principal del chatbot.
-- El dump original solo declara PRIMARY KEY (`id`). Ejecutar tras revisar volumen y EXPLAIN.

-- ALTER TABLE ventasgeneral ADD INDEX idx_fechacont (FechaCont);
-- ALTER TABLE ventasgeneral ADD INDEX idx_cliente_fecha (CodCliente, FechaCont);
-- ALTER TABLE ventasgeneral ADD INDEX idx_numdoc (NumeroDoc);

-- Tabla `sale` ya incluye índices en tfecfac, tprocli, tfectra, tcodigo, (tdoc, tnumfac).
-- Opcional si filtran mucho por tcencos:
-- ALTER TABLE sale ADD INDEX idx_tcencos (tcencos);
