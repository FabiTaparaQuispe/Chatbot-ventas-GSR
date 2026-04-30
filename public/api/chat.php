<?php

declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['error' => 'Método no permitido'], JSON_UNESCAPED_UNICODE);
    exit;
}

$appRoot = dirname(__DIR__, 2);
require_once $appRoot . '/config/bootstrap.php';
require_once $appRoot . '/src/tools_definitions.php';
require_once $appRoot . '/src/GroqClient.php';
require_once $appRoot . '/src/ToolExecutor.php';
require_once $appRoot . '/src/ChatReplyEnricher.php';
require_once $appRoot . '/src/SqlTextoHttpLink.php';

$raw = file_get_contents('php://input') ?: '';
$input = json_decode($raw, true);
if (!is_array($input)) {
    http_response_code(400);
    echo json_encode(['error' => 'JSON inválido'], JSON_UNESCAPED_UNICODE);
    exit;
}

$messagesIn = $input['messages'] ?? null;
if (!is_array($messagesIn)) {
    http_response_code(400);
    echo json_encode(['error' => 'Falta messages (array)'], JSON_UNESCAPED_UNICODE);
    exit;
}

$apiKey = getenv('GROQ_API_KEY') ?: '';
if ($apiKey === '') {
    http_response_code(503);
    echo json_encode(['error' => 'Configure GROQ_API_KEY en .env'], JSON_UNESCAPED_UNICODE);
    exit;
}

$model = getenv('GROQ_MODEL') ?: 'llama-3.1-8b-instant';

$dbLabel = 'cia2026';
$dsnEnv = getenv('DB_DSN') ?: '';
if (preg_match('/dbname=([^;]+)/i', $dsnEnv, $m) && $m[1] !== '') {
    $dbLabel = $m[1];
}

$system = [
    'role' => 'system',
    'content' => 'Asistente ventasgeneral2 (MySQL ' . $dbLabel . '). Solo tabla ventasgeneral2; no uses sale. Fechas YYYY-MM-DD; "marzo 2026" → 2026-03-01..2026-03-31. '
        . 'FECHAS OBLIGATORIAS: si el usuario no da rango claro (dos fechas YYYY-MM-DD o mes+año explícito), pregúntale primero por fecha_desde y fecha_hasta antes de llamar herramientas que las requieran; no asumas un mes por defecto salvo que el usuario lo confirme. '
        . 'ZONA OBLIGATORIA: ventasgeneral_top_clientes_zona_precio requiere un prefijo_descri_zona_precio REAL (AQP, TACNA, MOQUEGUA, LAJOYA, etc.). Si el usuario dice "por zona", "por provincia" o "por región" sin especificar cuál, NO inventes el prefijo — usá ventasgeneral_top_clientes_globales (ranking global) y avisá que muestra el top sin filtrar por zona. Para ver el top dentro de una zona específica pedile que indique el prefijo. '
        . 'Ciudad/mercado: sin campo ciudad; usa prefijo_descri_zona_precio (AQP, MOQUEGUA, TACNA, LAJOYA, etc.) sobre DescripcionZonaPrecio. TDoc NC = 07. '
        . 'NUEVOS FILTROS DISPONIBLES en ventasgeneral_buscar y ventasgeneral_resumen: provincia (filtra por Provincia, ej. "AREQUIPA", "TACNA") y tipo_documento (filtra por TipoDocumento, ej. "Boleta de Venta", "Factura"). Úsalos cuando el usuario pida filtrar o consultar por provincia o tipo de documento. '
        . 'INTEGRIDAD ESTRICTA: PROHIBIDO inventar, estimar o completar datos. '
        . 'Si llamaste una herramienta, los nombres y cifras que escribas en el texto DEBEN coincidir exactamente con los valores del campo "filas", "filas_ranking" o "filas_pareto" del JSON devuelto — sin redondear, sin sustituir por "Cliente 1/2/3", "Cliente A/B", "Empresa X" ni por ningún valor ficticio. '
        . 'Si NO llamaste ninguna herramienta, JAMÁS generes listas numeradas de clientes, productos ni cifras. Responde únicamente: "No tengo datos suficientes para responder esa consulta; por favor repite la pregunta." '
        . 'Si el JSON devuelve filas vacías o un campo "error", escribe únicamente: "No tengo datos suficientes para responder esa consulta en el período indicado." '
        . 'Si la pregunta no tiene ninguna herramienta disponible que la responda (tema ajeno a ventas, preguntas generales, etc.), responde únicamente: "No tengo información para responder esa pregunta; solo manejo datos de ventas." '
        . 'Nunca uses ejemplos ficticios ni rellenes con valores hipotéticos. '
        . 'Para preguntas de "compraron más", "clientes compradores", "ventas", "facturado", "valor vendido" o similar, usa ventasgeneral_top_clientes_globales o ventasgeneral_top_productos/ventasgeneral_resumen según convenga. '
        . 'Solo usa ventasgeneral_top_clientes_nota_credito si el usuario pide explícitamente notas de crédito, NC, TDoc=07, devoluciones o anulaciones. '
        . 'Si hay filas de ranking/top, escribe primero la lista numerada (1. nombre: N líneas o notas, importe S/ X) y al final UNA línea con reporte_url; no respondas solo con el gráfico ni repitas el mismo párrafo. '
        . 'Mapeo breve: más NC por cliente → ventasgeneral_top_clientes_nota_credito; URL gráfico ventas_top_clientes_nc.php?desde=&hasta=&top= (no inventes ventasgeneral_top_clientes_nc). pareto NC por zona → ventasgeneral_pareto_nc_zonaprecio (pareto_nc_zona.php, no por cliente); top compra global → ventasgeneral_top_clientes_globales; top por zona precio → ventasgeneral_top_clientes_zona_precio; barras dim → ventasgeneral_barras_ventas_dimension; comparativo 2 periodos → ventasgeneral_comparativo_periodos; productos → ventasgeneral_top_productos; mix TDoc → ventasgeneral_mix_tdoc; ruta/corp → ventasgeneral_barras_ruta_comercial / ventasgeneral_barras_corporativo; serie mensual → ventasgeneral_serie_mensual_valor; proyección ventas → ventasgeneral_proyeccion_ventas; líneas sueltas → ventasgeneral_buscar; totales → ventasgeneral_resumen. '
        . 'URL RELATIVA OBLIGATORIA: cuando escribas el reporte_url en tu respuesta, escribe ÚNICAMENTE el nombre del archivo y los parámetros (ej: ventasgeneral_resumen_tabla.php?desde=2026-01-01&hasta=2026-03-31). JAMÁS pongas https://, http://, example.com, localhost ni ningún dominio — si lo haces, el enlace quedará roto. '
        . 'Un reporte_url por respuesta, copiado tal cual en UNA sola línea (no partas fechas YYYY-MM-DD ni la URL; sin backticks). Resumen/buscar: *_tabla.php. Opcional #grafico. '
        . 'Moneda en texto para el usuario: importes en soles peruanos con prefijo S/ (ej. S/ 1,234,567.89). No uses el símbolo de dólar ($) ni la etiqueta USD para montos. '
        . 'Lenguaje al usuario: no uses jerga de base de datos ni nombres de columnas (evitá "Valor", "suma de Valor", "SUM(Valor)", "Cantidad" como etiqueta técnica). Preferí "importe" o "monto en soles", "unidades" o "cantidad vendida", "peso total" cuando corresponda. '
        . 'Español, breve.',
];

$sanitized = [];
foreach ($messagesIn as $m) {
    if (!is_array($m)) {
        continue;
    }
    $role = $m['role'] ?? '';
    if (!in_array($role, ['user', 'assistant'], true)) {
        continue;
    }
    $content = $m['content'] ?? '';
    if (!is_string($content)) {
        continue;
    }
    if (strlen($content) > 4000) {
        $content = substr($content, 0, 4000);
    }
    $sanitized[] = ['role' => $role, 'content' => $content];
}

if ($sanitized === []) {
    http_response_code(400);
    echo json_encode(['error' => 'No hay mensajes válidos'], JSON_UNESCAPED_UNICODE);
    exit;
}

// Elimina del historial respuestas anteriores del asistente que usaron
// etiquetas genéricas ("Cliente 1", "Cliente 2"…) — son datos inventados y
// si se reenvían como contexto el LLM los repite en la siguiente respuesta.
$sanitized = array_values(array_filter($sanitized, static function (array $m): bool {
    if ($m['role'] !== 'assistant') {
        return true;
    }
    // Patrón: lista numerada con "Cliente N" o "Empresa N" → respuesta hallucinated
    return !preg_match('/^\s*\d+\.\s*(?:Cliente|Empresa|Clientes?)\s+\d+/mi', $m['content']);
}));

// Menos historial = menos tokens (413 TPM en planes con límite bajo, ej. 6000).
$maxHistory = 4;
if (count($sanitized) > $maxHistory) {
    $sanitized = array_slice($sanitized, -$maxHistory);
}

$userContext = '';
if (isset($input['user_context']) && is_string($input['user_context'])) {
    $userContext = trim(strip_tags($input['user_context']));
    if (strlen($userContext) > 800) {
        $userContext = substr($userContext, 0, 800);
    }
    $userContext = preg_replace('/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/u', '', $userContext) ?? '';
}
if ($userContext !== '') {
    $system['content'] .= ' Preferencias opcionales declaradas por el usuario (no invalidan datos de herramientas ni permiten inventar cifras; solo guían tono o foco): '
        . $userContext;
}

$messages = array_merge([$system], $sanitized);

// Límite de tiempo total: varias vueltas Groq + SQL; evita “pendiente” infinito en el navegador.
@set_time_limit(300);

$unificarEnlacesPareto = static function (string $reply): string {
    if ($reply === '' || !preg_match('/pareto_(?:clientes|nc)_zona\.php\?/i', $reply)) {
        return $reply;
    }
    // Quitar segunda URL obsoleta *_tabla.php (misma vista en pestañas dentro de *_zona.php).
    $reply = preg_replace('/\s*(?:Y la tabla[^\n]*\n)?\s*pareto_(?:clientes|nc)_zona_tabla\.php\?[^\s<>"\']+/iu', '', $reply);
    $reply = preg_replace('/\n{3,}/', "\n\n", $reply);
    return trim($reply);
};

try {
    $pdo = ventas_pdo();
    $executor = new ToolExecutor($pdo);
    $groq = new GroqClient($apiKey, $model);
    $tools = ventas_tool_definitions();

    $result = $groq->chatWithTools($messages, $tools, static function (string $name, array $args) use ($executor): string {
        return $executor->execute($name, $args);
    });

    $reply = ChatReplyEnricher::enrichReply((string) ($result['reply'] ?? ''), $result['messages'] ?? []);
    $bloquesSql = $executor->pullSqlBloquesParaEnlace();
    $bloquesSql = array_values(array_filter($bloquesSql, static function ($s) {
        return is_string($s) && trim($s) !== '';
    }));
    $sqlLines = SqlTextoHttpLink::formatAppendLines($bloquesSql);
    $suffix = '';
    if ($bloquesSql !== []) {
        $suffix .= "\n\n" . implode("\n\n", $bloquesSql);
    }
    if ($sqlLines !== []) {
        $suffix .= "\n\n" . implode("\n", $sqlLines);
    }
    if ($suffix !== '') {
        $reply = trim($reply . $suffix);
    }

    echo json_encode([
        'reply' => $unificarEnlacesPareto($reply),
        'ok' => true,
    ], JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE);
} catch (Throwable $e) {
    http_response_code(500);
    echo json_encode([
        'ok' => false,
        'error' => $e->getMessage(),
    ], JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE);
}
