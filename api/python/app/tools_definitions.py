from __future__ import annotations

from typing import Any


def ventas_tool_definitions() -> list[dict[str, Any]]:
    d = {"type": "string"}
    d_opt = {"type": "string", "description": "YYYY-MM-DD"}
    dn: dict[str, Any] = {
        "anyOf": [{"type": "integer"}, {"type": "string"}],
        "description": "Entero positivo",
    }
    dn_top_linea_resumen: dict[str, Any] = {
        "anyOf": [{"type": "integer"}, {"type": "string"}],
        "description": "Opcional. Omitir para devolver todas las filas (sin LIMIT). Si se indica un entero >0, máximo ese número de filas (tope 100000).",
    }
    dim = {
        "type": "string",
        "enum": ["precio", "comercial"],
        "description": "precio=DescripcionZonaPrecio, comercial=ZonaComercial",
    }
    pref = {
        "type": "string",
        "description": "Prefijo de DescripcionZonaPrecio, ej. AQP, TACNA, MOQUEGUA, LAJOYA",
    }
    prov = {"type": "string", "description": "Valor de Provincia, ej. AREQUIPA, TACNA"}
    tdoc = {"type": "string", "description": 'Valor de TipoDocumento, ej. "Boleta de Venta", "Factura"'}

    return [
        {
            "type": "function",
            "function": {
                "name": "ventasgeneral_resumen",
                "description": "Totales ventasgeneral (filas, suma Valor/Cantidad/Peso) con filtros opcionales. reporte_url=ventasgeneral_resumen_tabla.php",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "fecha_desde": d_opt,
                        "fecha_hasta": d_opt,
                        "zona_comercial": d,
                        "cod_cliente": d,
                        "prefijo_descri_zona_precio": pref,
                        "provincia": prov,
                        "tipo_documento": tdoc,
                    },
                    "required": ["fecha_desde", "fecha_hasta"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "ventasgeneral_buscar",
                "description": "Filas individuales ventasgeneral (máx 100). Usar para buscar líneas concretas, no para totales. reporte_url=ventasgeneral_buscar_tabla.php",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "nombre_cliente": d,
                        "numero_doc": d,
                        "cod_item": d,
                        "tdoc": d,
                        "prefijo_descri_zona_precio": pref,
                        "fecha_desde": d_opt,
                        "fecha_hasta": d_opt,
                        "provincia": prov,
                        "tipo_documento": tdoc,
                        "limit": dn,
                        "offset": dn,
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "ventasgeneral_pareto_nc_zonaprecio",
                "description": "Pareto de notas de crédito (TDoc=07) agrupado por DescripcionZonaPrecio. reporte_url=pareto_nc_zona.php",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "fecha_desde": d_opt,
                        "fecha_hasta": d_opt,
                        "max_zonas": dn,
                    },
                    "required": ["fecha_desde", "fecha_hasta"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "ventasgeneral_top_clientes_zona_precio",
                "description": "Top clientes por SUM(Valor) dentro de una zona de precio (prefijo obligatorio). reporte_url=pareto_clientes_zona.php",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "fecha_desde": d_opt,
                        "fecha_hasta": d_opt,
                        "prefijo_descri_zona_precio": pref,
                        "top_n": dn,
                    },
                    "required": ["fecha_desde", "fecha_hasta", "prefijo_descri_zona_precio"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "ventasgeneral_barras_ventas_dimension",
                "description": "Ranking de zonas por SUM(Valor) en una dimensión. NO usar dos veces para comparar períodos — usar ventasgeneral_comparativo_periodos. reporte_url=ventas_barras_dimension.php",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "fecha_desde": d_opt,
                        "fecha_hasta": d_opt,
                        "dimension": dim,
                        "top_n": dn,
                    },
                    "required": ["fecha_desde", "fecha_hasta"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "ventasgeneral_comparativo_periodos",
                "description": "Compara SUM(Valor) entre dos períodos en la misma dimensión. Llamar UNA sola vez con los cuatro rangos. reporte_url=ventas_comparativo.php",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "fecha_desde_a": d_opt,
                        "fecha_hasta_a": d_opt,
                        "fecha_desde_b": d_opt,
                        "fecha_hasta_b": d_opt,
                        "dimension": dim,
                        "top_n": dn,
                    },
                    "required": ["fecha_desde_a", "fecha_hasta_a", "fecha_desde_b", "fecha_hasta_b"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "ventasgeneral_top_productos",
                "description": "Top productos por SUM(Valor). reporte_url=ventas_top_productos.php",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "fecha_desde": d_opt,
                        "fecha_hasta": d_opt,
                        "top_n": dn,
                    },
                    "required": ["fecha_desde", "fecha_hasta"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "ventasgeneral_top_clientes_globales",
                "description": "Top clientes global por SUM(Valor), sin filtro de zona. reporte_url=ventas_top_clientes_global.php",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "fecha_desde": d_opt,
                        "fecha_hasta": d_opt,
                        "top_n": dn,
                    },
                    "required": ["fecha_desde", "fecha_hasta"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "ventasgeneral_top_clientes_nota_credito",
                "description": "Top clientes por cantidad de líneas TDoc=07 (NC/devoluciones). Solo usar cuando el usuario pide explícitamente notas de crédito. reporte_url=ventas_top_clientes_nc.php",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "fecha_desde": d_opt,
                        "fecha_hasta": d_opt,
                        "top_n": dn,
                    },
                    "required": ["fecha_desde", "fecha_hasta"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "ventasgeneral_mix_tdoc",
                "description": "Mix de SUM(Valor) por tipo de documento (TDoc). reporte_url=ventas_mix_tdoc.php",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "fecha_desde": d_opt,
                        "fecha_hasta": d_opt,
                    },
                    "required": ["fecha_desde", "fecha_hasta"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "ventasgeneral_barras_ruta_comercial",
                "description": "Ranking de rutas comerciales por SUM(Valor). reporte_url=ventas_barras_ruta.php",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "fecha_desde": d_opt,
                        "fecha_hasta": d_opt,
                        "top_n": dn,
                    },
                    "required": ["fecha_desde", "fecha_hasta"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "ventasgeneral_barras_corporativo",
                "description": "Ranking de corporativos (NombreCoorporativo) por SUM(Valor). reporte_url=ventas_barras_corporativo.php",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "fecha_desde": d_opt,
                        "fecha_hasta": d_opt,
                        "top_n": dn,
                    },
                    "required": ["fecha_desde", "fecha_hasta"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "ventasgeneral_serie_mensual_valor",
                "description": "Serie de SUM(Valor) agrupada por mes. reporte_url=ventas_serie_mensual.php",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "fecha_desde": d_opt,
                        "fecha_hasta": d_opt,
                    },
                    "required": ["fecha_desde", "fecha_hasta"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "ventasgeneral_proyeccion_ventas",
                "description": "Proyección de ventas futuras con regresión lineal sobre la serie mensual histórica. Requiere ≥2 meses de historial.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "fecha_desde": d_opt,
                        "fecha_hasta": d_opt,
                        "meses_a_proyectar": {
                            "type": "integer",
                            "default": 3,
                            "description": "Meses futuros a proyectar (1-12)",
                        },
                    },
                    "required": ["fecha_desde", "fecha_hasta"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "ventasgeneral_linea_resumen_provincia",
                "description": "Resumen de ventas de una línea comercial agrupado por provincia y cliente: SUM(Cantidad), SUM(Peso), SUM(Valor), ordenado por peso DESC. Por defecto sin límite de filas (todas). Filtros opcionales: cod_item (producto, ej. 100=carne, 103=brasa) y mercado (prefijo DescripcionZonaPrecio, ej. TACNA, AQPMERCADO). reporte_url=ventas-linea-resumen-provincia",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "fecha_desde": d_opt,
                        "fecha_hasta": d_opt,
                        "linea_comercial": {"type": "string", "description": "Texto de LineaComercial, ej. 'Pollo Vivo'"},
                        "cod_item": {"type": "string", "description": "Código de producto, ej. 100 (carne), 103 (brasa)"},
                        "mercado": pref,
                        "top_n": dn_top_linea_resumen,
                    },
                    "required": ["fecha_desde", "fecha_hasta", "linea_comercial"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "ventasgeneral_linea_diario_provincia",
                "description": "Ventas diarias de una línea comercial por fecha, provincia y cliente. Filtros opcionales: cod_item (ej. 100=carne, 103=brasa) y mercado (prefijo zona precio). reporte_url=ventas-linea-diario-provincia",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "fecha_desde": d_opt,
                        "fecha_hasta": d_opt,
                        "linea_comercial": {"type": "string", "description": "Texto de LineaComercial, ej. 'Pollo Vivo'"},
                        "cod_item": {"type": "string", "description": "Código de producto, ej. 100 (carne), 103 (brasa)"},
                        "mercado": pref,
                        "top_n": dn,
                    },
                    "required": ["fecha_desde", "fecha_hasta", "linea_comercial"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "ventasgeneral_linea_precio_diario",
                "description": "Precio por día (precio_kg = Valor/Peso) de una línea comercial por fecha, provincia y cliente. Filtros opcionales: cod_item y mercado. reporte_url=ventas-linea-precio-diario",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "fecha_desde": d_opt,
                        "fecha_hasta": d_opt,
                        "linea_comercial": {"type": "string", "description": "Texto de LineaComercial, ej. 'Pollo Vivo'"},
                        "cod_item": {"type": "string", "description": "Código de producto, ej. 100 (carne), 103 (brasa)"},
                        "mercado": pref,
                        "top_n": dn,
                    },
                    "required": ["fecha_desde", "fecha_hasta", "linea_comercial"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "ventasgeneral_linea_mix_productos",
                "description": "Mix de productos dentro de una línea comercial: SUM(Cantidad), SUM(Peso), SUM(Valor), precio_kg y % del peso total por CodigoItem. Responde '¿cuánto carne vs brasa se vendió?'. Filtro opcional: mercado. reporte_url=ventas-linea-mix-productos",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "fecha_desde": d_opt,
                        "fecha_hasta": d_opt,
                        "linea_comercial": {"type": "string", "description": "Texto de LineaComercial, ej. 'Pollo Vivo'"},
                        "mercado": pref,
                    },
                    "required": ["fecha_desde", "fecha_hasta", "linea_comercial"],
                },
            },
        },
    ]
