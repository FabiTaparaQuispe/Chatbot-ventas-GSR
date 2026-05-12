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
    dn_top_linea_resumen = {
        'anyOf': [{'type': 'integer'}, {'type': 'string'}],
        'description': 'Opcional. Omitir para devolver todas las filas (sin LIMIT). Si se indica un entero >0, máximo ese número de filas (tope 100000).',
    }
    dim = {'type': 'string', 'enum': ['precio', 'comercial'], 'description': 'precio=DescripcionZonaPrecio, comercial=ZonaComercial'}
    pref = {'type': 'string', 'description': 'Prefijo de DescripcionZonaPrecio, ej. AQP, TACNA, MOQUEGUA, LAJOYA'}
    prov = {'type': 'string', 'description': 'Valor de Provincia, ej. AREQUIPA, TACNA'}
    tdoc = {'type': 'string', 'description': 'Valor de TipoDocumento, ej. "Boleta de Venta", "Factura"'}

    return [
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_resumen',
            'description': f'Totales ventasgeneral (filas, suma Valor/Cantidad/Peso) con filtros opcionales. reporte_url={REPORT_VENTASGENERAL_RESUMEN_TABLA}?…',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt,
                'zona_comercial': d, 'cod_cliente': d,
                'prefijo_descri_zona_precio': pref, 'provincia': prov, 'tipo_documento': tdoc,
            }, 'required': ['fecha_desde', 'fecha_hasta']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_buscar',
            'description': f'Filas individuales ventasgeneral (máx 100). Usar para buscar líneas concretas, no para totales. reporte_url={REPORT_VENTASGENERAL_BUSCAR_TABLA}?…',
            'parameters': {'type': 'object', 'properties': {
                'nombre_cliente': d, 'numero_doc': d, 'cod_item': d, 'tdoc': d,
                'prefijo_descri_zona_precio': pref, 'fecha_desde': d_opt, 'fecha_hasta': d_opt,
                'provincia': prov, 'tipo_documento': tdoc, 'limit': dn, 'offset': dn,
            }, 'required': []},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_pareto_nc_zonaprecio',
            'description': f'Pareto de notas de crédito (TDoc=07) agrupado por DescripcionZonaPrecio. reporte_url={REPORTS_PREFIX}{REPORT_SLUG_PARETO_NC_ZONA}?…',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt, 'max_zonas': dn,
            }, 'required': ['fecha_desde', 'fecha_hasta']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_top_clientes_zona_precio',
            'description': f'Top clientes por SUM(Valor) dentro de una zona de precio (prefijo obligatorio). reporte_url={REPORTS_PREFIX}{REPORT_SLUG_PARETO_CLIENTES_ZONA}?…',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt,
                'prefijo_descri_zona_precio': pref, 'top_n': dn,
            }, 'required': ['fecha_desde', 'fecha_hasta', 'prefijo_descri_zona_precio']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_barras_ventas_dimension',
            'description': f'Ranking de zonas por SUM(Valor) en una dimensión. NO usar dos veces para comparar períodos — usar ventasgeneral_comparativo_periodos. reporte_url={REPORTS_PREFIX}{REPORT_SLUG_VENTAS_BARRAS_DIMENSION}?…',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt, 'dimension': dim, 'top_n': dn,
            }, 'required': ['fecha_desde', 'fecha_hasta']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_comparativo_periodos',
            'description': f'Compara SUM(Valor) entre dos períodos en la misma dimensión. Llamar UNA sola vez con los cuatro rangos. reporte_url={REPORTS_PREFIX}{REPORT_SLUG_VENTAS_COMPARATIVO}?…',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde_a': d_opt, 'fecha_hasta_a': d_opt,
                'fecha_desde_b': d_opt, 'fecha_hasta_b': d_opt,
                'dimension': dim, 'top_n': dn,
            }, 'required': ['fecha_desde_a', 'fecha_hasta_a', 'fecha_desde_b', 'fecha_hasta_b']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_top_productos',
            'description': f'Top productos por SUM(Valor). reporte_url={REPORTS_PREFIX}{REPORT_SLUG_VENTAS_TOP_PRODUCTOS}?…',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt, 'top_n': dn,
            }, 'required': ['fecha_desde', 'fecha_hasta']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_top_clientes_globales',
            'description': f'Top clientes global por SUM(Valor), sin filtro de zona. reporte_url={REPORTS_PREFIX}{REPORT_SLUG_VENTAS_TOP_CLIENTES_GLOBAL}?…',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt, 'top_n': dn,
            }, 'required': ['fecha_desde', 'fecha_hasta']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_top_clientes_nota_credito',
            'description': f'Top clientes por cantidad de líneas TDoc=07 (NC/devoluciones). Solo usar cuando el usuario pide explícitamente notas de crédito. reporte_url={REPORTS_PREFIX}{REPORT_SLUG_VENTAS_TOP_CLIENTES_NC}?…',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt, 'top_n': dn,
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
            'description': f'Ranking de rutas comerciales por SUM(Valor). reporte_url={REPORTS_PREFIX}{REPORT_SLUG_VENTAS_BARRAS_RUTA}?…',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt, 'top_n': dn,
            }, 'required': ['fecha_desde', 'fecha_hasta']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_barras_corporativo',
            'description': f'Ranking de corporativos (NombreCoorporativo) por SUM(Valor). reporte_url={REPORTS_PREFIX}{REPORT_SLUG_VENTAS_BARRAS_CORPORATIVO}?…',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt, 'top_n': dn,
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
            'name': 'ventasgeneral_proyeccion_ventas',
            'description': 'Proyección de ventas futuras con regresión lineal sobre la serie mensual histórica. Requiere ≥2 meses de historial.',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt,
                'meses_a_proyectar': {'type': 'integer', 'default': 3, 'description': 'Meses futuros a proyectar (1-12)'},
            }, 'required': ['fecha_desde', 'fecha_hasta']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_linea_resumen_provincia',
            'description': f'Resumen de ventas de una línea comercial agrupado por provincia y cliente: SUM(Cantidad), SUM(Peso), SUM(Valor), ordenado por peso DESC. Por defecto sin límite de filas (todas). Filtros opcionales: cod_item (producto, ej. 100=carne, 103=brasa) y mercado (prefijo DescripcionZonaPrecio, ej. TACNA, AQPMERCADO). reporte_url={REPORTS_PREFIX}{REPORT_SLUG_VENTAS_LINEA_RESUMEN_PROVINCIA}?…',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt,
                'linea_comercial': {'type': 'string', 'description': "Texto de LineaComercial, ej. 'Pollo Vivo'"},
                'cod_item': {'type': 'string', 'description': 'Código de producto, ej. 100 (carne), 103 (brasa)'},
                'mercado': pref,
                'top_n': dn_top_linea_resumen,
            }, 'required': ['fecha_desde', 'fecha_hasta', 'linea_comercial']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_linea_diario_provincia',
            'description': f'Ventas diarias de una línea comercial por fecha, provincia y cliente. Filtros opcionales: cod_item (ej. 100=carne, 103=brasa) y mercado (prefijo zona precio). reporte_url={REPORTS_PREFIX}{REPORT_SLUG_VENTAS_LINEA_DIARIO_PROVINCIA}?…',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt,
                'linea_comercial': {'type': 'string', 'description': "Texto de LineaComercial, ej. 'Pollo Vivo'"},
                'cod_item': {'type': 'string', 'description': 'Código de producto, ej. 100 (carne), 103 (brasa)'},
                'mercado': pref,
                'top_n': dn,
            }, 'required': ['fecha_desde', 'fecha_hasta', 'linea_comercial']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_linea_precio_diario',
            'description': (
                f'Precio por día (precio/kg = Valor/Peso) de una línea por fecha, provincia, cliente y '
                f'cantidades: incluye líneas, cantidad, peso, valor. Orden en el reporte web: días en orden cronológico y '
                f'dentro de cada día por peso de mayor a menor. Usar cuando pidan precio por día '
                f'como resumen con provincia/cliente/cantidad/peso/valor. Filtros opcionales: cod_item, mercado. '
                f'reporte_url={REPORTS_PREFIX}{REPORT_SLUG_VENTAS_LINEA_PRECIO_DIARIO}?…'
            ),
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt,
                'linea_comercial': {'type': 'string', 'description': "Texto de LineaComercial, ej. 'Pollo Vivo'"},
                'cod_item': {'type': 'string', 'description': 'Código de producto, ej. 100 (carne), 103 (brasa)'},
                'mercado': pref,
                'top_n': dn,
            }, 'required': ['fecha_desde', 'fecha_hasta', 'linea_comercial']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_linea_precio_resumen_provincia',
            'description': (
                f'Precio resumen por PROVINCIA (sin desglose por cliente ni por día) de una línea comercial. '
                f'Devuelve una fila por provincia con líneas, cantidad, peso, valor y precio/kg ponderado (SUM(Valor)/SUM(Peso)), '
                f'ordenado por peso descendente. Úsala cuando pidan "precio resumen por provincia", '
                f'"precio por provincia" o "precio promedio por provincia". '
                f'No agrupa por cliente — para eso usar ventasgeneral_linea_precio_diario. '
                f'Requiere fecha_desde/fecha_hasta y linea_comercial; si faltan, pregúntalos antes de llamar. '
                f'Filtros opcionales: cod_item (ej. 100=carne, 103=brasa) y mercado (prefijo zona precio). '
                f'reporte_url={REPORTS_PREFIX}{REPORT_SLUG_VENTAS_LINEA_PRECIO_RESUMEN_PROV}?…'
            ),
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
    ]
