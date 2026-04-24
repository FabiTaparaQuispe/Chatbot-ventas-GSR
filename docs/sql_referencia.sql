-- Consultas de referencia (agregados). Ajustar fechas y campos de fecha tras validación con negocio.
-- Siempre filtrar por rango de fechas; usar LIMIT en listados.

-- 1) Top clientes por importe (ventasgeneral)
-- SELECT CodCliente, NombreCliente, SUM(Valor) AS total_valor, SUM(Cantidad) AS total_cant, SUM(Peso) AS total_peso
-- FROM ventasgeneral
-- WHERE FechaCont BETWEEN '2026-01-01' AND '2026-01-31'
-- GROUP BY CodCliente, NombreCliente
-- ORDER BY total_valor DESC
-- LIMIT 20;

-- 2) Compras de un cliente en un periodo (ventasgeneral)
-- SELECT FechaCont, NumeroDoc, Glosa, Cantidad, Peso, Valor
-- FROM ventasgeneral
-- WHERE CodCliente = '29413198'
--   AND FechaCont BETWEEN '2026-01-01' AND '2026-01-31'
-- ORDER BY FechaCont DESC
-- LIMIT 500;

-- 3) Serie temporal mensual (ventasgeneral)
-- SELECT DATE_FORMAT(FechaCont, '%Y-%m') AS mes, SUM(Valor) AS total_valor, SUM(Cantidad) AS total_cant, SUM(Peso) AS total_peso
-- FROM ventasgeneral
-- WHERE FechaCont BETWEEN '2025-01-01' AND '2026-04-30'
-- GROUP BY DATE_FORMAT(FechaCont, '%Y-%m')
-- ORDER BY mes;

-- 4) Top clientes por importe (sale)
-- SELECT tprocli AS cod_cliente, SUM(timport) AS total_importe, SUM(tcantid) AS total_cantidad
-- FROM sale
-- WHERE tfecfac BETWEEN '2026-01-01' AND '2026-01-31'
--   AND tlib = 'RV'
-- GROUP BY tprocli
-- ORDER BY total_importe DESC
-- LIMIT 20;

-- 5) Ventas por centro de costos (codigo completo tcencos) — solo sale
-- SELECT TRIM(tcencos) AS centro_costo, SUM(timport) AS total_importe, SUM(tcantid) AS total_cantidad
-- FROM sale
-- WHERE tfecfac BETWEEN '2026-01-01' AND '2026-01-31' AND tlib = 'RV'
--   AND tcencos IS NOT NULL AND TRIM(tcencos) <> ''
-- GROUP BY TRIM(tcencos)
-- ORDER BY total_importe DESC
-- LIMIT 50;

-- 6) Comparativo dos periodos (ejemplo ventasgeneral — dos rangos en subconsultas)
-- Ver implementación en aplicación o CTE según versión MySQL.
