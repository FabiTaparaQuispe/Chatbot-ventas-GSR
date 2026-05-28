from services.urlmap import (
    REPORT_SLUG_PARETO_CLIENTES_ZONA,
    REPORT_SLUG_PARETO_NC_ZONA,
    REPORT_SLUG_VENTAS_BARRAS_CORPORATIVO,
    REPORT_SLUG_VENTAS_BARRAS_DIMENSION,
    REPORT_SLUG_VENTAS_BARRAS_RUTA,
    REPORT_SLUG_VENTAS_COMPARATIVO,
    REPORT_SLUG_VENTAS_LINEA_DIARIO_PROVINCIA,
    REPORT_SLUG_VENTAS_LINEA_MIX_PRODUCTOS,
    REPORT_SLUG_VENTAS_LINEA_PRECIO_DIARIO,
    REPORT_SLUG_VENTAS_LINEA_PRECIO_RESUMEN_PROV,
    REPORT_SLUG_VENTAS_LINEA_RESUMEN_PROVINCIA,
    REPORT_SLUG_VENTAS_MIX_TDOC,
    REPORT_SLUG_VENTAS_RESUMEN_POR_LINEA,
    REPORT_SLUG_VENTAS_SERIE_MENSUAL,
    REPORT_SLUG_VENTAS_TOP_CLIENTES_GLOBAL,
    REPORT_SLUG_VENTAS_TOP_CLIENTES_NC,
    REPORT_SLUG_VENTAS_TOP_PRODUCTOS,
    REPORT_VENTASGENERAL_BUSCAR_TABLA,
    REPORT_VENTASGENERAL_RESUMEN_TABLA,
    REPORTS_PREFIX,
)


def ventas_tool_definitions():
    d = {'type': 'string'}
    d_opt = {'type': 'string', 'description': 'YYYY-MM-DD'}
    dn = {'anyOf': [{'type': 'integer'}, {'type': 'string'}], 'description': 'Entero positivo'}
    dim = {'type': 'string', 'enum': ['precio', 'comercial'], 'description': 'precio=DescripcionZonaPrecio, comercial=ZonaComercial'}
    pref = {'type': 'string', 'description': 'Prefijo de DescripcionZonaPrecio, ej. AQP, TACNA, MOQUEGUA, LAJOYA'}
    prov = {'type': 'string', 'description': 'Valor de Provincia, ej. AREQUIPA, TACNA'}
    tdoc = {'type': 'string', 'description': 'Valor de TipoDocumento, ej. "Boleta de Venta", "Factura"'}
    pagina = {
        'anyOf': [{'type': 'integer'}, {'type': 'string'}],
        'description': 'Página solicitada (entero ≥1). Default 1.',
    }
    por_pagina = {
        'anyOf': [{'type': 'integer'}, {'type': 'string'}],
        'description': 'Tamaño de página (entero 10-100). Default 50.',
    }

    return [
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_resumen',
            'description': f'Totales ventasgeneral (filas, suma Valor/Cantidad/Peso) con filtros opcionales. Para notas de crédito usar codigo_documento="07". Para filtrar por una línea comercial específica usar linea_comercial. Para ventas de UN cliente específico usar nombre_cliente. reporte_url={REPORT_VENTASGENERAL_RESUMEN_TABLA}?…',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt,
                'zona_comercial': d, 'cod_cliente': d,
                'nombre_cliente': {'type': 'string', 'description': 'Filtro parcial por NombreCliente (LIKE). Ej: "QUISPE VARGAS VICTOR"'},
                'nombre_corporativo': {'type': 'string', 'description': 'Filtro parcial por NombreCoorporativo (LIKE). Usar cuando el usuario menciona el corporativo, ej: "corporativo Huaypuna".'},
                'prefijo_descri_zona_precio': pref, 'provincia': prov, 'tipo_documento': tdoc,
                'codigo_documento': {'type': 'string', 'description': 'Código de tipo de documento: "07"=Nota de Crédito. Usar en vez de tipo_documento para filtrar NCs.'},
                'linea_comercial': {'type': 'string', 'description': "Filtra por línea comercial exacta, ej. 'Pollo Vivo', 'Embutidos'. Usar cuando el usuario pide totales de UNA línea específica sin desglose."},
                'excluir_nc': {'type': 'boolean', 'description': 'Si true, excluye Notas de Crédito (CodigoDocumento=07) del total. Usar cuando se quiere el total bruto de ventas (facturas+boletas) como denominador para calcular % de NCs.'},
            }, 'required': ['fecha_desde', 'fecha_hasta']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_buscar',
            'description': (
                f'Filas individuales ventasgeneral (paginado). Usar para buscar líneas concretas, '
                f'no para totales. También usar para "busca la factura X", "busca el documento X", '
                f'"muéstrame el número X". '
                f'numero_doc = número de factura/boleta (ej. "3750004023") → usa SIEMPRE para buscar por número de documento. '
                f'tdoc = código de 2 chars ("01"=Factura,"03"=Boleta,"07"=NC) — NUNCA pongas aquí un número largo. '
                f'tipo_documento = texto "Boleta de Venta","Factura","Nota de Crédito". '
                f'Usa pagina/por_pagina para navegar el resultado. reporte_url={REPORT_VENTASGENERAL_BUSCAR_TABLA}?…'
            ),
            'parameters': {'type': 'object', 'properties': {
                'nombre_cliente': d,
                'nombre_corporativo': {'type': 'string', 'description': 'Filtro parcial por NombreCoorporativo (LIKE). Usar cuando el usuario dice "corporativo X".'},
                'numero_doc': {'type': 'string', 'description': 'Número de factura/boleta (NumeroFactura). Ej: "3750004023". Usar para "busca la factura X", "documento número X".'},
                'cod_item': d,
                'tdoc': {'type': 'string', 'description': 'Código de documento de 2 chars: "01"=Factura, "03"=Boleta de Venta, "07"=Nota de Crédito. NUNCA poner un número de factura aquí.'},
                'prefijo_descri_zona_precio': pref, 'fecha_desde': d_opt, 'fecha_hasta': d_opt,
                'provincia': prov, 'tipo_documento': tdoc,
                'pagina': pagina, 'por_pagina': por_pagina,
            }, 'required': []},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_pareto_nc_zonaprecio',
            'description': f'Pareto de notas de crédito (TDoc=07) agrupado por DescripcionZonaPrecio. max_zonas acota el universo; pagina/por_pagina lo navegan. reporte_url={REPORTS_PREFIX}{REPORT_SLUG_PARETO_NC_ZONA}?…',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt, 'max_zonas': dn,
                'pagina': pagina, 'por_pagina': por_pagina,
            }, 'required': ['fecha_desde', 'fecha_hasta']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_nc_por_corporativo',
            'description': (
                'Notas de crédito (TDoc=07) agrupadas por corporativo: COUNT(*) lineas_nc, SUM(Valor), SUM(Peso) '
                'y % del total por NombreCoorporativo. LLAMAR SIEMPRE junto a ventasgeneral_resumen o ventasgeneral_pareto_nc_zonaprecio '
                'cuando el usuario pregunta por notas de crédito (cantidad, total, detalle), para mostrar automáticamente el desglose por corporativo.'
            ),
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt, 'top_n': dn,
                'pagina': pagina, 'por_pagina': por_pagina,
            }, 'required': ['fecha_desde', 'fecha_hasta']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_top_clientes_zona_precio',
            'description': f'Top clientes por SUM(Valor) dentro de una zona de precio (prefijo obligatorio). top_n acota el universo; pagina/por_pagina lo navegan. reporte_url={REPORTS_PREFIX}{REPORT_SLUG_PARETO_CLIENTES_ZONA}?…',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt,
                'prefijo_descri_zona_precio': pref, 'top_n': dn,
                'pagina': pagina, 'por_pagina': por_pagina,
            }, 'required': ['fecha_desde', 'fecha_hasta', 'prefijo_descri_zona_precio']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_barras_ventas_dimension',
            'description': f'Ranking de zonas por SUM(Valor) en una dimensión. NO usar dos veces para comparar períodos — usar ventasgeneral_comparativo_periodos. top_n acota el universo; pagina/por_pagina lo navegan. reporte_url={REPORTS_PREFIX}{REPORT_SLUG_VENTAS_BARRAS_DIMENSION}?…',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt, 'dimension': dim, 'top_n': dn,
                'pagina': pagina, 'por_pagina': por_pagina,
            }, 'required': ['fecha_desde', 'fecha_hasta']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_comparativo_periodos',
            'description': f'Compara SUM(Valor) entre dos períodos en la misma dimensión. Llamar UNA sola vez con los cuatro rangos. top_n acota el universo; pagina/por_pagina lo navegan. reporte_url={REPORTS_PREFIX}{REPORT_SLUG_VENTAS_COMPARATIVO}?…',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde_a': d_opt, 'fecha_hasta_a': d_opt,
                'fecha_desde_b': d_opt, 'fecha_hasta_b': d_opt,
                'dimension': dim, 'top_n': dn,
                'pagina': pagina, 'por_pagina': por_pagina,
            }, 'required': ['fecha_desde_a', 'fecha_hasta_a', 'fecha_desde_b', 'fecha_hasta_b']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_top_productos',
            'description': f'Top productos por SUM(Valor). top_n acota el universo; pagina/por_pagina lo navegan. reporte_url={REPORTS_PREFIX}{REPORT_SLUG_VENTAS_TOP_PRODUCTOS}?…',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt, 'top_n': dn,
                'pagina': pagina, 'por_pagina': por_pagina,
            }, 'required': ['fecha_desde', 'fecha_hasta']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_top_clientes_globales',
            'description': f'Top clientes global. Por defecto ordena por SUM(Valor); usar orden="peso" para ordenar por SUM(Peso) en kg. Soporta filtros opcionales: provincia (ej. AREQUIPA, TACNA) y linea_comercial. Usar cuando el usuario pide top clientes por provincia o sin especificar zona de precio. top_n acota el universo; pagina/por_pagina lo navegan. reporte_url={REPORTS_PREFIX}{REPORT_SLUG_VENTAS_TOP_CLIENTES_GLOBAL}?…',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt, 'top_n': dn,
                'provincia': prov,
                'linea_comercial': {'type': 'string', 'description': "Filtra por línea comercial, ej. 'Pollo Vivo'"},
                'orden': {'type': 'string', 'enum': ['valor', 'peso'], 'description': '"peso" para ordenar por kg (mayor volumen en kg); "valor" para ordenar por importe S/ (default).'},
                'pagina': pagina, 'por_pagina': por_pagina,
            }, 'required': ['fecha_desde', 'fecha_hasta']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_top_clientes_nota_credito',
            'description': f'Top clientes por cantidad de líneas TDoc=07 (NC/devoluciones). Solo usar cuando el usuario pide explícitamente notas de crédito. top_n acota el universo; pagina/por_pagina lo navegan. reporte_url={REPORTS_PREFIX}{REPORT_SLUG_VENTAS_TOP_CLIENTES_NC}?…',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt, 'top_n': dn,
                'pagina': pagina, 'por_pagina': por_pagina,
            }, 'required': ['fecha_desde', 'fecha_hasta']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_mix_tdoc',
            'description': f'Mix de SUM(Valor) por tipo de documento (TDoc). reporte_url={REPORTS_PREFIX}{REPORT_SLUG_VENTAS_MIX_TDOC}?…',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt,
            }, 'required': ['fecha_desde', 'fecha_hasta']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_barras_ruta_comercial',
            'description': f'Ranking de rutas comerciales por SUM(Valor). top_n acota el universo; pagina/por_pagina lo navegan. reporte_url={REPORTS_PREFIX}{REPORT_SLUG_VENTAS_BARRAS_RUTA}?…',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt, 'top_n': dn,
                'pagina': pagina, 'por_pagina': por_pagina,
            }, 'required': ['fecha_desde', 'fecha_hasta']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_barras_corporativo',
            'description': f'Ranking de corporativos (NombreCoorporativo) por SUM(Valor). Filtros opcionales: nombre_cliente (NombreCliente LIKE) para ver corporativos de un cliente específico; nombre_corporativo (NombreCoorporativo LIKE) para filtrar por nombre de corporativo. top_n acota el universo; pagina/por_pagina lo navegan. reporte_url={REPORTS_PREFIX}{REPORT_SLUG_VENTAS_BARRAS_CORPORATIVO}?…',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt, 'top_n': dn,
                'nombre_cliente': {'type': 'string', 'description': 'Filtro parcial por NombreCliente (LIKE). Ej: "Machicado"'},
                'nombre_corporativo': {'type': 'string', 'description': 'Filtro parcial por NombreCoorporativo (LIKE). Ej: "ABC"'},
                'pagina': pagina, 'por_pagina': por_pagina,
            }, 'required': ['fecha_desde', 'fecha_hasta']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_serie_mensual_valor',
            'description': f'Serie de SUM(Valor) agrupada por mes. reporte_url={REPORTS_PREFIX}{REPORT_SLUG_VENTAS_SERIE_MENSUAL}?…',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt,
            }, 'required': ['fecha_desde', 'fecha_hasta']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_resumen_diario',
            'description': (
                'Totales de ventas agrupados por día: registros, suma_cantidad, suma_peso, suma_valor. '
                'Ordenados de mayor a menor por valor por defecto. '
                'Usar para "qué día se vendió más/menos", "día con más ventas", "desglose diario", '
                '"ventas día a día", "cuánto se vendió cada día". '
                'Filtros opcionales: linea_comercial, provincia. '
                'orden: "valor" (defecto), "cantidad" o "peso".'
            ),
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt,
                'linea_comercial': {'type': 'string', 'description': "Filtra por línea comercial, ej. 'Pollo Vivo'"},
                'provincia': prov,
                'orden': {'type': 'string', 'description': '"valor" (defecto), "cantidad" o "peso"'},
            }, 'required': ['fecha_desde', 'fecha_hasta']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_resumen_semanal',
            'description': (
                'Totales de ventas agrupados por semana (lunes–domingo): registros, suma_cantidad, suma_peso, suma_valor. '
                'Usar para "por semana", "semana a semana", "cada semana", "desglose semanal". '
                'Filtros opcionales: linea_comercial, provincia.'
            ),
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt,
                'linea_comercial': {'type': 'string', 'description': "Filtra por línea comercial, ej. 'Pollo Vivo'"},
                'provincia': prov,
            }, 'required': ['fecha_desde', 'fecha_hasta']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_proyeccion_ventas',
            'description': (
                'Proyección de ventas futuras con regresión lineal sobre la serie mensual histórica. '
                'Proyecta simultáneamente: valor (S/), cantidad (unidades) y peso promedio (kg/unidad). '
                'Requiere ≥2 meses de historial. Filtros opcionales: linea_comercial, provincia, zona_comercial, prefijo_descri_zona_precio.'
            ),
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt,
                'meses_a_proyectar': {'type': 'integer', 'default': 3, 'description': 'Meses futuros a proyectar (1-12)'},
                'linea_comercial': {'type': 'string', 'description': "Filtrar por línea comercial, ej. 'Pollo Vivo'"},
                'provincia': prov,
                'zona_comercial': {'type': 'string', 'description': 'Filtrar por zona comercial'},
                'prefijo_descri_zona_precio': pref,
            }, 'required': ['fecha_desde', 'fecha_hasta']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_linea_resumen_provincia',
            'description': f'Resumen de ventas de una línea comercial agrupado por provincia y cliente: SUM(Cantidad), SUM(Peso), SUM(Valor), ordenado por peso DESC. Paginado con pagina/por_pagina. Filtros opcionales: cod_item (producto, ej. 100=carne, 103=brasa) y mercado (prefijo DescripcionZonaPrecio, ej. TACNA, AQPMERCADO). reporte_url={REPORTS_PREFIX}{REPORT_SLUG_VENTAS_LINEA_RESUMEN_PROVINCIA}?…',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt,
                'linea_comercial': {'type': 'string', 'description': "Texto de LineaComercial, ej. 'Pollo Vivo'"},
                'cod_item': {'type': 'string', 'description': 'Código de producto, ej. 100 (carne), 103 (brasa)'},
                'mercado': pref,
                'pagina': pagina, 'por_pagina': por_pagina,
            }, 'required': ['fecha_desde', 'fecha_hasta', 'linea_comercial']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_linea_diario_provincia',
            'description': f'Ventas diarias de una línea comercial por fecha, provincia y cliente. Paginado con pagina/por_pagina. Filtros opcionales: cod_item (ej. 100=carne, 103=brasa) y mercado (prefijo zona precio). reporte_url={REPORTS_PREFIX}{REPORT_SLUG_VENTAS_LINEA_DIARIO_PROVINCIA}?…',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt,
                'linea_comercial': {'type': 'string', 'description': "Texto de LineaComercial, ej. 'Pollo Vivo'"},
                'cod_item': {'type': 'string', 'description': 'Código de producto, ej. 100 (carne), 103 (brasa)'},
                'mercado': pref,
                'pagina': pagina, 'por_pagina': por_pagina,
            }, 'required': ['fecha_desde', 'fecha_hasta', 'linea_comercial']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_linea_precio_diario',
            'description': f'Precio/kg diario (Valor/Peso) de una línea por fecha, provincia y cliente. reporte_url={REPORTS_PREFIX}{REPORT_SLUG_VENTAS_LINEA_PRECIO_DIARIO}?…',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt,
                'linea_comercial': {'type': 'string', 'description': "Texto de LineaComercial, ej. 'Pollo Vivo'"},
                'cod_item': {'type': 'string', 'description': 'Código de producto, ej. 100 (carne), 103 (brasa)'},
                'mercado': pref,
                'pagina': pagina, 'por_pagina': por_pagina,
            }, 'required': ['fecha_desde', 'fecha_hasta', 'linea_comercial']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_linea_precio_resumen_provincia',
            'description': f'Precio promedio (Valor/Peso) por provincia de una línea comercial, sin desglose por cliente ni día. reporte_url={REPORTS_PREFIX}{REPORT_SLUG_VENTAS_LINEA_PRECIO_RESUMEN_PROV}?…',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt,
                'linea_comercial': {'type': 'string', 'description': "Texto de LineaComercial, ej. 'Pollo Vivo'"},
                'cod_item': {'type': 'string', 'description': 'Código de producto, ej. 100 (carne), 103 (brasa)'},
                'mercado': pref,
            }, 'required': ['fecha_desde', 'fecha_hasta', 'linea_comercial']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_linea_mix_productos',
            'description': f'Mix de productos dentro de una línea comercial: SUM(Cantidad), SUM(Peso), SUM(Valor), precio_kg y % del peso total por CodigoItem. Responde "¿cuánto carne vs brasa se vendió?". Filtro opcional: mercado. reporte_url={REPORTS_PREFIX}{REPORT_SLUG_VENTAS_LINEA_MIX_PRODUCTOS}?…',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt,
                'linea_comercial': {'type': 'string', 'description': "Texto de LineaComercial, ej. 'Pollo Vivo'"},
                'mercado': pref,
            }, 'required': ['fecha_desde', 'fecha_hasta', 'linea_comercial']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_resumen_por_linea',
            'description': (
                f'Totales por LineaComercial: SUM(Cantidad), SUM(Peso), SUM(Valor) y % del total. '
                f'Usar para "ventas de todas las líneas", "resumen por línea", "cuánto vendió cada línea", '
                f'"línea de pollo" (pasar lineas_comerciales con las líneas del grupo). '
                f'Filtros opcionales: provincia, prefijo_descri_zona_precio, lineas_comerciales. '
                f'reporte_url={REPORTS_PREFIX}{REPORT_SLUG_VENTAS_RESUMEN_POR_LINEA}?…'
            ),
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt,
                'provincia': prov,
                'prefijo_descri_zona_precio': pref,
                'lineas_comerciales': {
                    'type': 'string',
                    'description': (
                        'Líneas a incluir separadas por coma. Dejar vacío para todas. '
                        'Ej: "Pollo Vivo,Pollo Beneficiado,Pollo Trozado Seco,Menudencia"'
                    ),
                },
                'pagina': pagina, 'por_pagina': por_pagina,
            }, 'required': ['fecha_desde', 'fecha_hasta']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_resumen_por_provincia',
            'description': (
                'Totales por Provincia: SUM(Cantidad), SUM(Peso), SUM(Valor) y % del total. '
                'Usar para "resumen de ventas por provincia", "ventas por provincia", '
                '"desglose por provincia", "cuánto vendió cada provincia". '
                'UNA sola llamada — NUNCA llames ventasgeneral_resumen varias veces con provincia distinta. '
                'Filtros opcionales: linea_comercial, zona_comercial, cod_cliente, prefijo_descri_zona_precio, '
                'tipo_documento, codigo_documento (07 para NC). '
                f'reporte_url={REPORT_VENTASGENERAL_RESUMEN_TABLA}?…'
            ),
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt,
                'linea_comercial': {'type': 'string', 'description': "Texto de LineaComercial, ej. 'Pollo Vivo'"},
                'zona_comercial': {'type': 'string'},
                'cod_cliente': {'type': 'string'},
                'prefijo_descri_zona_precio': pref,
                'tipo_documento': tdoc,
                'codigo_documento': {'type': 'string', 'description': 'Código TDoc, ej. 07 para notas de crédito'},
                'pagina': pagina, 'por_pagina': por_pagina,
            }, 'required': ['fecha_desde', 'fecha_hasta']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_clientes_corporativo',
            'description': (
                'Lista los clientes (NombreCliente) que pertenecen a un corporativo (NombreCoorporativo). '
                'Usar para "¿qué clientes pertenecen al corporativo X?", "clientes del corporativo X", '
                '"¿cuántos clientes tiene el corporativo X?". '
                'Devuelve por cliente: codigo, nombre, lineas, suma_peso, suma_valor, primera y última venta. '
                'nombre_corporativo es obligatorio. Las fechas son opcionales (sin fechas devuelve todos los registros históricos).'
            ),
            'parameters': {'type': 'object', 'properties': {
                'nombre_corporativo': {'type': 'string', 'description': 'Nombre parcial del corporativo (LIKE). Ej: "HUAYPUNA MAMANI".'},
                'fecha_desde': d_opt,
                'fecha_hasta': d_opt,
            }, 'required': ['nombre_corporativo']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_catalogo',
            'description': (
                'Devuelve los valores distintos (catálogo/maestro) de un campo de ventasgeneral2. '
                'Usar para: "¿qué provincias hay?", "¿qué líneas comerciales existen?", '
                '"¿qué corporativos están registrados?", "¿qué zonas de precio hay?", '
                '"¿qué rutas comerciales existen?", "¿qué tipos de documento hay?", '
                '"descripciones de descuento/ítems/glosas para línea X" → campo="glosa" con linea_comercial, '
                '"motivos de devolución para línea X" → campo="glosa" con linea_comercial y codigo_documento="07". '
                'Las fechas y filtros son opcionales.'
            ),
            'parameters': {'type': 'object', 'properties': {
                'campo': {
                    'type': 'string',
                    'enum': ['provincia', 'linea_comercial', 'corporativo', 'zona_precio', 'zona_comercial', 'ruta', 'tipo_documento', 'glosa'],
                    'description': 'Campo del que se quieren los valores distintos. "glosa" devuelve GlosaDetalle (descripciones de ítems, descuentos, motivos de devolución).',
                },
                'fecha_desde': d_opt,
                'fecha_hasta': d_opt,
                'linea_comercial': {'type': 'string', 'description': 'Filtrar por línea comercial exacta. Ej: "Pollo Vivo".'},
                'codigo_documento': {'type': 'string', 'description': 'Filtrar por tipo de documento. Ej: "07" para notas de crédito/devoluciones.'},
            }, 'required': ['campo']},
        }},
    ]


def chat_history_tool_definitions():
    """Meta-consultas sobre el propio historial de chats (app_chat_messages / app_chat_threads / app_users).

    Permiten a la IA responder preguntas como:
      - "¿cuántas preguntas hizo admin esta semana?"
      - "¿qué usuario consultó más en mayo?"
      - "mostrame las últimas preguntas de gerente"
      - "¿alguien preguntó por Pollo Vivo?"
    """
    d_opt = {'type': 'string', 'description': 'YYYY-MM-DD'}
    user_opt = {
        'type': 'string',
        'description': (
            'Username exacto del usuario del chatbot (ej. admin, fabiola.tapara). '
            'Omitir para agregar todos los usuarios.'
        ),
    }
    role_opt = {
        'type': 'string',
        'description': (
            'Rol del usuario a filtrar. Valores posibles: admin, gerencia, administrador, '
            'estrategico, tactico, operativo, analista, lector. '
            'Usar cuando el usuario mencione el cargo/rol en vez del nombre de login '
            '(ej. "gerente" → role="gerencia", "operativo", "analista").'
        ),
    }
    texto = {
        'type': 'string',
        'description': 'Texto/fragmento a buscar dentro del contenido de las preguntas (case-insensitive).',
    }
    top_n = {
        'anyOf': [{'type': 'integer'}, {'type': 'string'}],
        'description': 'Entero positivo (1-100). Default 10.',
    }
    pagina = {
        'anyOf': [{'type': 'integer'}, {'type': 'string'}],
        'description': 'Página solicitada (entero ≥1). Default 1.',
    }
    por_pagina = {
        'anyOf': [{'type': 'integer'}, {'type': 'string'}],
        'description': 'Tamaño de página (entero 10-100). Default 50.',
    }

    return [
        {'type': 'function', 'function': {
            'name': 'chat_usuario_estadisticas',
            'description': 'Estadísticas de uso del chatbot por usuario o todos: total preguntas, chats, primera/última pregunta del período.',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt, 'username': user_opt,
            }, 'required': ['fecha_desde', 'fecha_hasta']},
        }},
        {'type': 'function', 'function': {
            'name': 'chat_top_usuarios',
            'description': 'Ranking de usuarios del chatbot por total de preguntas en el período.',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt, 'top_n': top_n,
                'pagina': pagina, 'por_pagina': por_pagina,
            }, 'required': ['fecha_desde', 'fecha_hasta']},
        }},
        {'type': 'function', 'function': {
            'name': 'chat_actividad_por_dia',
            'description': (
                'Serie diaria de uso del chatbot: preguntas y usuarios activos por día. '
                'Para "día con más actividad" usar orden="desc" y top_n=1. '
                'Para "día con menos actividad" usar orden="desc" y top_n=0 (tomar el último). '
                'Filtra por username si se da.'
            ),
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt, 'username': user_opt,
                'orden': {'type': 'string', 'enum': ['asc', 'desc'], 'description': '"desc" ordena por más preguntas primero; "asc" por fecha. Default: "asc".'},
                'top_n': {'type': 'integer', 'description': 'Limitar a los N días con más actividad. Ej: 1 para el día más activo, 5 para el top 5.'},
            }, 'required': ['fecha_desde', 'fecha_hasta']},
        }},
        {'type': 'function', 'function': {
            'name': 'chat_listar_preguntas',
            'description': (
                'Lista las preguntas del chatbot paginadas (message_id, username, content, created_at). '
                'Si el usuario menciona "últimas N preguntas" sin dar fechas, omitir fecha_desde/fecha_hasta '
                'y usar por_pagina=N. Filtrar por username (login) o role (cargo/rol).'
            ),
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt,
                'username': user_opt, 'role': role_opt,
                'pagina': pagina, 'por_pagina': por_pagina,
            }, 'required': []},
        }},
        {'type': 'function', 'function': {
            'name': 'chat_buscar_pregunta',
            'description': 'Busca preguntas del chatbot que contengan un texto. Filtros opcionales: fecha, username.',
            'parameters': {'type': 'object', 'properties': {
                'texto': texto, 'fecha_desde': d_opt, 'fecha_hasta': d_opt, 'username': user_opt,
                'pagina': pagina, 'por_pagina': por_pagina,
            }, 'required': ['texto']},
        }},
        {'type': 'function', 'function': {
            'name': 'chat_resumen_threads',
            'description': 'Resumen de chats (threads) abiertos por usuario en el período: total chats, mensajes, último mensaje.',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt, 'username': user_opt,
            }, 'required': ['fecha_desde', 'fecha_hasta']},
        }},
        {'type': 'function', 'function': {
            'name': 'filtrar_previo',
            'description': 'Filtra/ordena/extrae subgrupo del resultado PREVIO sin ir a la BD. Usar cuando el usuario diga "de esa lista", "de ese resultado", "el top N de esos".',
            'parameters': {'type': 'object', 'properties': {
                'campo': {'type': 'string', 'description': 'Nombre exacto del campo a filtrar u ordenar (ej. Valor, Cliente, Producto, Cantidad, Peso)'},
                'valor_filtro': {'type': 'string', 'description': 'Valor a comparar (solo si se filtra por igualdad/contenido)'},
                'comparador': {'type': 'string', 'enum': ['igual', 'contiene', 'mayor', 'menor'], 'description': 'Operador de comparación (default: igual)'},
                'ordenar_por': {'type': 'string', 'description': 'Campo por el cual ordenar el resultado'},
                'orden': {'type': 'string', 'enum': ['desc', 'asc'], 'description': 'Dirección del orden (default: desc = mayor primero)'},
                'top_n': {'anyOf': [{'type': 'integer'}, {'type': 'string'}], 'description': 'Limitar a los N primeros resultados'},
            }, 'required': []},
        }},
    ]
