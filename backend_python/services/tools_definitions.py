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
            'description': f'Totales ventasgeneral (filas, suma Valor/Cantidad/Peso) con filtros opcionales. reporte_url={REPORT_VENTASGENERAL_RESUMEN_TABLA}?…',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt,
                'zona_comercial': d, 'cod_cliente': d,
                'prefijo_descri_zona_precio': pref, 'provincia': prov, 'tipo_documento': tdoc,
            }, 'required': ['fecha_desde', 'fecha_hasta']},
        }},
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_buscar',
            'description': f'Filas individuales ventasgeneral (paginado). Usar para buscar líneas concretas, no para totales. Usa pagina/por_pagina para navegar el resultado. reporte_url={REPORT_VENTASGENERAL_BUSCAR_TABLA}?…',
            'parameters': {'type': 'object', 'properties': {
                'nombre_cliente': d, 'numero_doc': d, 'cod_item': d, 'tdoc': d,
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
            'description': f'Top clientes global por SUM(Valor), sin filtro de zona. top_n acota el universo; pagina/por_pagina lo navegan. reporte_url={REPORTS_PREFIX}{REPORT_SLUG_VENTAS_TOP_CLIENTES_GLOBAL}?…',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt, 'top_n': dn,
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
            'description': f'Ranking de corporativos (NombreCoorporativo) por SUM(Valor). top_n acota el universo; pagina/por_pagina lo navegan. reporte_url={REPORTS_PREFIX}{REPORT_SLUG_VENTAS_BARRAS_CORPORATIVO}?…',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt, 'top_n': dn,
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
            'name': 'ventasgeneral_proyeccion_ventas',
            'description': 'Proyección de ventas futuras con regresión lineal sobre la serie mensual histórica. Requiere ≥2 meses de historial.',
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt,
                'meses_a_proyectar': {'type': 'integer', 'default': 3, 'description': 'Meses futuros a proyectar (1-12)'},
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
            'description': (
                f'Precio por día (precio/kg = Valor/Peso) de una línea por fecha, provincia, cliente y '
                f'cantidades: incluye líneas, cantidad, peso, valor. Orden en el reporte web: días en orden cronológico y '
                f'dentro de cada día por peso de mayor a menor. Paginado con pagina/por_pagina. '
                f'Filtros opcionales: cod_item, mercado. '
                f'reporte_url={REPORTS_PREFIX}{REPORT_SLUG_VENTAS_LINEA_PRECIO_DIARIO}?…'
            ),
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
        {'type': 'function', 'function': {
            'name': 'ventasgeneral_catalogo',
            'description': (
                'Devuelve los valores distintos (catálogo/maestro) de un campo de ventasgeneral2. '
                'Usar para preguntas como "¿qué provincias hay?", "¿qué líneas comerciales existen?", '
                '"¿qué corporativos están registrados?", "¿qué zonas de precio hay?", '
                '"¿qué rutas comerciales existen?", "¿qué tipos de documento hay?". '
                'Las fechas son opcionales; si se dan, solo muestra valores presentes en ese período.'
            ),
            'parameters': {'type': 'object', 'properties': {
                'campo': {
                    'type': 'string',
                    'enum': ['provincia', 'linea_comercial', 'corporativo', 'zona_precio', 'zona_comercial', 'ruta', 'tipo_documento'],
                    'description': 'Campo del que se quieren los valores distintos',
                },
                'fecha_desde': d_opt,
                'fecha_hasta': d_opt,
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
            'Username exacto del usuario del chatbot (ej. admin, gerente, usuario2). '
            'Omitir para agregar todos los usuarios.'
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
            'description': (
                'Estadísticas de uso del CHATBOT (no de ventas) por un usuario o por todos. '
                'Devuelve total de preguntas hechas, total de chats (threads) distintos, '
                'primera y última pregunta del período. Si se omite username agrega TODOS los usuarios. '
                'Úsala cuando el usuario pregunte por su propio uso del bot o por el de otros, ej. '
                '"¿cuántas preguntas hizo admin esta semana?", "¿cuántas consultas hubo en mayo?", '
                '"¿cuánto se usó el chatbot del 1 al 10 de mayo?".'
            ),
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt, 'username': user_opt,
            }, 'required': ['fecha_desde', 'fecha_hasta']},
        }},
        {'type': 'function', 'function': {
            'name': 'chat_top_usuarios',
            'description': (
                'Ranking de usuarios del CHATBOT por cantidad de preguntas hechas en el período. '
                'Devuelve username, display_name, rol del usuario, total_preguntas y total_chats. '
                'top_n acota el ranking (default 10); pagina/por_pagina lo navegan. '
                'Úsala para "¿qué usuarios consultaron más esta semana?", "top usuarios del chatbot", '
                '"¿quién pregunta más al bot?".'
            ),
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt, 'top_n': top_n,
                'pagina': pagina, 'por_pagina': por_pagina,
            }, 'required': ['fecha_desde', 'fecha_hasta']},
        }},
        {'type': 'function', 'function': {
            'name': 'chat_actividad_por_dia',
            'description': (
                'Serie diaria de uso del CHATBOT: una fila por día con total de preguntas y usuarios activos. '
                'Si se da username filtra solo a ese usuario. '
                'Úsala para "¿cómo evolucionó el uso del chatbot esta semana?", '
                '"actividad diaria del chatbot", "¿qué días se usó más el bot?".'
            ),
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt, 'username': user_opt,
            }, 'required': ['fecha_desde', 'fecha_hasta']},
        }},
        {'type': 'function', 'function': {
            'name': 'chat_listar_preguntas',
            'description': (
                'Lista las preguntas del CHATBOT (mensajes con role=user) del período, paginadas. '
                'Devuelve message_id, username, thread_title, content, created_at. '
                'Útil para auditar o revisar qué se preguntó. '
                'Úsala para "mostrame las últimas preguntas de gerente", "qué preguntó admin ayer", '
                '"lista las consultas del 1 al 10 de mayo".'
            ),
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt, 'username': user_opt,
                'pagina': pagina, 'por_pagina': por_pagina,
            }, 'required': ['fecha_desde', 'fecha_hasta']},
        }},
        {'type': 'function', 'function': {
            'name': 'chat_buscar_pregunta',
            'description': (
                'Busca preguntas del CHATBOT (role=user) cuyo content contenga un texto/fragmento. '
                'Filtros opcionales por fecha y/o username. Paginado. '
                'Úsala para "¿alguien preguntó por Pollo Vivo?", "buscá consultas sobre TACNA", '
                '"qué preguntas hicieron sobre notas de crédito".'
            ),
            'parameters': {'type': 'object', 'properties': {
                'texto': texto, 'fecha_desde': d_opt, 'fecha_hasta': d_opt, 'username': user_opt,
                'pagina': pagina, 'por_pagina': por_pagina,
            }, 'required': ['texto']},
        }},
        {'type': 'function', 'function': {
            'name': 'chat_resumen_threads',
            'description': (
                'Resumen de CHATS (threads) por usuario en el período: total de chats abiertos, '
                'total de mensajes (user + assistant), último mensaje. '
                'Úsala para "¿cuántos chats abrió cada usuario este mes?", '
                '"resumen de conversaciones por usuario".'
            ),
            'parameters': {'type': 'object', 'properties': {
                'fecha_desde': d_opt, 'fecha_hasta': d_opt, 'username': user_opt,
            }, 'required': ['fecha_desde', 'fecha_hasta']},
        }},
    ]
