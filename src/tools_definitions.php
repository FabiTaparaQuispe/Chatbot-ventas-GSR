<?php

declare(strict_types=1);

/**
 * Definiciones compactas (menos tokens Groq). Parámetros: fechas YYYY-MM-DD salvo indicación.
 *
 * @return list<array<string, mixed>>
 */
function ventas_tool_definitions(): array
{
    $d = ['type' => 'string'];
    $dn = ['anyOf' => [['type' => 'integer'], ['type' => 'string']]];

    return [
        ['type' => 'function', 'function' => [
            'name' => 'ventasgeneral_resumen',
            'description' => 'Agregados ventasgeneral (filas, suma Valor/Cantidad/Peso). Opc: zona_comercial, cod_cliente, prefijo_descri_zona_precio, provincia, tipo_documento. reporte_url=ventasgeneral_resumen_tabla.php',
            'parameters' => ['type' => 'object', 'properties' => [
                'fecha_desde' => $d, 'fecha_hasta' => $d,
                'zona_comercial' => $d, 'cod_cliente' => $d, 'prefijo_descri_zona_precio' => $d,
                'provincia' => $d, 'tipo_documento' => $d,
            ], 'required' => ['fecha_desde', 'fecha_hasta']],
        ]],
        ['type' => 'function', 'function' => [
            'name' => 'ventasgeneral_buscar',
            'description' => 'Filas ventasgeneral (máx 100). prefijo_descri_zona_precio para mercado. Opc: provincia, tipo_documento. reporte_url=ventasgeneral_buscar_tabla.php',
            'parameters' => ['type' => 'object', 'properties' => [
                'nombre_cliente' => $d, 'numero_doc' => $d, 'cod_item' => $d, 'tdoc' => $d,
                'prefijo_descri_zona_precio' => $d, 'fecha_desde' => $d, 'fecha_hasta' => $d,
                'provincia' => $d, 'tipo_documento' => $d,
                'limit' => $dn, 'offset' => $dn,
            ], 'required' => []],
        ]],
        ['type' => 'function', 'function' => [
            'name' => 'ventasgeneral_pareto_nc_zonaprecio',
            'description' => 'Pareto NC TDoc=07 por DescripcionZonaPrecio (por zona). reporte_url=pareto_nc_zona.php',
            'parameters' => ['type' => 'object', 'properties' => [
                'fecha_desde' => $d, 'fecha_hasta' => $d, 'max_zonas' => $dn,
            ], 'required' => ['fecha_desde', 'fecha_hasta']],
        ]],
        ['type' => 'function', 'function' => [
            'name' => 'ventasgeneral_top_clientes_zona_precio',
            'description' => 'Top clientes SUM(Valor) con prefijo DescripcionZonaPrecio. reporte_url=pareto_clientes_zona.php',
            'parameters' => ['type' => 'object', 'properties' => [
                'fecha_desde' => $d, 'fecha_hasta' => $d, 'prefijo_descri_zona_precio' => $d, 'top_n' => $dn,
            ], 'required' => ['fecha_desde', 'fecha_hasta', 'prefijo_descri_zona_precio']],
        ]],
        ['type' => 'function', 'function' => [
            'name' => 'ventasgeneral_barras_ventas_dimension',
            'description' => 'Barras SUM(Valor): dimension=precio|comercial. reporte_url=ventas_barras_dimension.php',
            'parameters' => ['type' => 'object', 'properties' => [
                'fecha_desde' => $d, 'fecha_hasta' => $d, 'dimension' => $d, 'top_n' => $dn,
            ], 'required' => ['fecha_desde', 'fecha_hasta']],
        ]],
        ['type' => 'function', 'function' => [
            'name' => 'ventasgeneral_comparativo_periodos',
            'description' => 'Compara dos rangos misma dimension precio|comercial. reporte_url=ventas_comparativo.php (a_desde,a_hasta,b_desde,b_hasta)',
            'parameters' => ['type' => 'object', 'properties' => [
                'fecha_desde_a' => $d, 'fecha_hasta_a' => $d, 'fecha_desde_b' => $d, 'fecha_hasta_b' => $d, 'dimension' => $d, 'top_n' => $dn,
            ], 'required' => ['fecha_desde_a', 'fecha_hasta_a', 'fecha_desde_b', 'fecha_hasta_b']],
        ]],
        ['type' => 'function', 'function' => [
            'name' => 'ventasgeneral_top_productos',
            'description' => 'Top productos SUM(Valor). reporte_url=ventas_top_productos.php',
            'parameters' => ['type' => 'object', 'properties' => [
                'fecha_desde' => $d, 'fecha_hasta' => $d, 'top_n' => $dn,
            ], 'required' => ['fecha_desde', 'fecha_hasta']],
        ]],
        ['type' => 'function', 'function' => [
            'name' => 'ventasgeneral_top_clientes_globales',
            'description' => 'Top clientes global SUM(Valor). reporte_url=ventas_top_clientes_global.php',
            'parameters' => ['type' => 'object', 'properties' => [
                'fecha_desde' => $d, 'fecha_hasta' => $d, 'top_n' => $dn,
            ], 'required' => ['fecha_desde', 'fecha_hasta']],
        ]],
        ['type' => 'function', 'function' => [
            'name' => 'ventasgeneral_top_clientes_nota_credito',
            'description' => 'Top clientes por cantidad líneas TDoc=07 (NC). reporte_url=ventas_top_clientes_nc.php',
            'parameters' => ['type' => 'object', 'properties' => [
                'fecha_desde' => $d, 'fecha_hasta' => $d, 'top_n' => $dn,
            ], 'required' => ['fecha_desde', 'fecha_hasta']],
        ]],
        ['type' => 'function', 'function' => [
            'name' => 'ventasgeneral_mix_tdoc',
            'description' => 'Mix SUM(Valor) por TDoc. reporte_url=ventas_mix_tdoc.php',
            'parameters' => ['type' => 'object', 'properties' => [
                'fecha_desde' => $d, 'fecha_hasta' => $d,
            ], 'required' => ['fecha_desde', 'fecha_hasta']],
        ]],
        ['type' => 'function', 'function' => [
            'name' => 'ventasgeneral_barras_ruta_comercial',
            'description' => 'Barras por RutaComercial. reporte_url=ventas_barras_ruta.php',
            'parameters' => ['type' => 'object', 'properties' => [
                'fecha_desde' => $d, 'fecha_hasta' => $d, 'top_n' => $dn,
            ], 'required' => ['fecha_desde', 'fecha_hasta']],
        ]],
        ['type' => 'function', 'function' => [
            'name' => 'ventasgeneral_barras_corporativo',
            'description' => 'Barras por NombreCoorporativo. reporte_url=ventas_barras_corporativo.php',
            'parameters' => ['type' => 'object', 'properties' => [
                'fecha_desde' => $d, 'fecha_hasta' => $d, 'top_n' => $dn,
            ], 'required' => ['fecha_desde', 'fecha_hasta']],
        ]],
        ['type' => 'function', 'function' => [
            'name' => 'ventasgeneral_serie_mensual_valor',
            'description' => 'Serie mensual SUM(Valor). reporte_url=ventas_serie_mensual.php',
            'parameters' => ['type' => 'object', 'properties' => [
                'fecha_desde' => $d, 'fecha_hasta' => $d,
            ], 'required' => ['fecha_desde', 'fecha_hasta']],
        ]],
        ['type' => 'function', 'function' => [
            'name' => 'ventasgeneral_proyeccion_ventas',
            'description' => 'Proyección de ventas futuras basada en serie mensual histórica. Usa regresión lineal simple para estimar tendencia.',
            'parameters' => ['type' => 'object', 'properties' => [
                'fecha_desde' => $d, 'fecha_hasta' => $d, 'meses_a_proyectar' => ['type' => 'integer', 'default' => 3],
            ], 'required' => ['fecha_desde', 'fecha_hasta']],
        ]],
    ];
}
