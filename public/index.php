<?php
declare(strict_types=1);
$pageTitle = 'Ventas · cia2026';
$script = str_replace('\\', '/', (string) ($_SERVER['SCRIPT_NAME'] ?? '/index.php'));
$scriptDir = str_replace('\\', '/', dirname($script));
$docRoot = @realpath((string) ($_SERVER['DOCUMENT_ROOT'] ?? '')) ?: '';
$publicFs = @realpath(__DIR__) ?: '';
if ($docRoot !== '' && $publicFs !== '' && strcasecmp($docRoot, $publicFs) === 0) {
    $ventasPublicWebBase = ($scriptDir === '/' || $scriptDir === '.') ? '/' : (rtrim($scriptDir, '/') . '/');
} elseif (str_ends_with($script, '/public/index.php')) {
    $ventasPublicWebBase = rtrim($scriptDir, '/') . '/';
} else {
    $ventasPublicWebBase = rtrim($scriptDir, '/') . '/public/';
}
?>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <base href="<?= htmlspecialchars($ventasPublicWebBase, ENT_QUOTES, 'UTF-8') ?>">
    <title><?= htmlspecialchars($pageTitle, ENT_QUOTES, 'UTF-8') ?></title>
    <style>
        :root {
            --bg: #0f1419;
            --border: #2d3a4d;
            --text: #e7edf4;
            --muted: #8b9cb3;
            --accent: #3b82f6;
        }
        * { box-sizing: border-box; }
        body {
            font-family: "Segoe UI", system-ui, sans-serif;
            background: var(--bg);
            color: var(--text);
            margin: 0;
            min-height: 100vh;
            line-height: 1.5;
        }
        .wrap { max-width: 720px; margin: 0 auto; padding: 1.25rem; }
        header {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            justify-content: space-between;
            gap: 0.75rem;
            margin-bottom: 1rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--border);
        }
        h1 { font-size: 1.25rem; font-weight: 600; margin: 0; }
        nav a {
            color: var(--accent);
            text-decoration: none;
            font-size: 0.9rem;
        }
        nav a:hover { text-decoration: underline; }
        .landing {
            color: var(--muted);
            font-size: 0.95rem;
            margin: 0;
        }
    </style>
</head>
<body>
    <div class="wrap">
        <header>
            <h1>Ventas · cia2026</h1>
            <nav>
                <a href="modules/ventasgeneral_table.php">Ventas general</a>
            </nav>
        </header>
        <p class="landing">El asistente de consultas está en la vista <strong>Ventas general</strong> (botón flotante abajo a la derecha). La página <strong>Resumen</strong> sigue disponible en <a href="modules/resumen.php">modules/resumen.php</a> (si la usas, siempre filtra por fechas en el formulario).</p>
    </div>
</body>
</html>
