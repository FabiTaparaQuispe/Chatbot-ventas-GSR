<?php
declare(strict_types=1);

require_once __DIR__ . '/includes/bootstrap.php';

if (!empty($_SESSION['active'])) {
    header('Location: ' . app_public_base() . 'index.php');
    exit;
}

$error = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $u = trim((string) ($_POST['usuario'] ?? ''));
    $c = (string) ($_POST['clave'] ?? '');
    if ($u === '' || $c === '') {
        $error = 'Usuario y contraseña requeridos.';
    } else {
        try {
            $pdo = ventas_pdo();
            $st = $pdo->prepare('SELECT password_hash, is_active, role, display_name FROM app_users WHERE username = :u LIMIT 1');
            $st->execute([':u' => $u]);
            $row = $st->fetch(PDO::FETCH_ASSOC) ?: null;
            $ok = false;
            $role = '';
            $displayName = '';
            if ($row && (int) ($row['is_active'] ?? 0) === 1) {
                $hash = (string) ($row['password_hash'] ?? '');
                $ok = $hash !== '' && password_verify($c, $hash);
                if ($ok) {
                    $pdo->prepare('UPDATE app_users SET last_login_at = NOW() WHERE username = :u')->execute([':u' => $u]);
                    $role = strtolower(trim((string) ($row['role'] ?? '')));
                    $displayName = trim((string) ($row['display_name'] ?? ''));
                }
            }
            if ($ok) {
                $_SESSION['active'] = true;
                $_SESSION['usuario'] = $u;
                $_SESSION['role'] = $role;
                $_SESSION['display_name'] = $displayName;
                header('Location: ' . app_public_base() . 'index.php');
                exit;
            }
            $error = 'Usuario o contraseña incorrectos.';
        } catch (Throwable $e) {
            // Ya no permitimos login ficticio.
            $error = 'No se pudo validar el acceso (tablas de usuarios no configuradas). Ejecuta `docs/schema_auth_chat.sql` en la BD.';
        }
    }
}

?>
<!DOCTYPE html>
<html lang="es" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Acceso — <?= htmlspecialchars(APP_NAME, ENT_QUOTES, 'UTF-8') ?></title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link rel="stylesheet" href="assets/css/app.css">
    <script>
    (function () {
        function readCookieTheme() {
            try {
                var m = document.cookie.match(/(?:^|; )ix2-theme=([^;]*)/);
                return m ? decodeURIComponent(m[1]).toLowerCase().trim() : '';
            } catch (e) { return ''; }
        }
        var mode = readCookieTheme() || (function(){ try { return localStorage.getItem('ix2-theme'); } catch(e){ return null; } })();
        if (mode !== 'dark' && mode !== 'light') {
            mode = (window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches) ? 'dark' : 'light';
        }
        var d = document.documentElement;
        d.setAttribute('data-theme', mode);
        d.style.colorScheme = mode === 'dark' ? 'dark' : 'light';
    })();
    </script>
</head>
<body class="login-page font-sans antialiased">

<div class="login-split min-h-screen flex w-full">
    <div class="login-hero" aria-hidden="false">
        <div class="login-hero-shapes" aria-hidden="true"></div>
        <div class="login-hero-content">
            <div class="login-hero-card" aria-hidden="true">
                <span style="font-size:86px; line-height:1;" role="img" aria-label="Chatbot">🤖</span>
            </div>
            <h2 class="login-hero-title">Chatbot</h2>
            <p class="login-hero-co"><?= htmlspecialchars(APP_COMPANY, ENT_QUOTES, 'UTF-8') ?></p>
        </div>
    </div>

    <div class="login-panel login-sip-panel w-full flex items-center justify-center p-6 sm:p-12 relative min-h-0">
        <div class="absolute right-4 top-4 z-20">
            <button type="button" class="app-theme-switch login-theme-btn" id="loginBtnTheme" onclick="appToggleTheme()" aria-label="Tema">
                <span class="app-theme-thumb">
                    <i class="fas fa-sun app-theme-sun" aria-hidden="true"></i>
                    <i class="fas fa-moon app-theme-moon hidden" aria-hidden="true"></i>
                </span>
            </button>
        </div>

        <div class="w-full max-w-md space-y-8 pt-6 lg:pt-0">
            <div class="text-center lg:text-left">
                <h1 class="text-3xl font-bold text-gray-900 mb-2 login-sip-h1">¡Bienvenido de nuevo!</h1>
                <p class="text-gray-500">Por favor, ingresa tus credenciales para continuar.</p>
            </div>

            <form method="post" id="loginForm" class="space-y-6 mt-8" autocomplete="on">
                <div>
                    <label class="block text-sm font-semibold text-gray-700 mb-2" for="usuario">Usuario</label>
                    <div class="relative group">
                        <div class="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                            <i class="fas fa-user text-gray-400 group-focus-within:text-blue-600 transition-colors"></i>
                        </div>
                        <input type="text" id="usuario" name="usuario" required autocomplete="username"
                               class="block w-full pl-11 pr-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-gray-900 placeholder-gray-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all duration-200"
                               placeholder="Ingresa tu código de usuario">
                    </div>
                </div>

                <div>
                    <label class="block text-sm font-semibold text-gray-700 mb-2" for="clave">Contraseña</label>
                    <div class="relative group">
                        <div class="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                            <i class="fas fa-lock text-gray-400 group-focus-within:text-blue-600 transition-colors"></i>
                        </div>
                        <input type="password" id="clave" name="clave" required autocomplete="current-password"
                               class="block w-full pl-11 pr-12 py-3 bg-gray-50 border border-gray-200 rounded-xl text-gray-900 placeholder-gray-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all duration-200"
                               placeholder="••••••••">
                        <button type="button" id="togglePassword" tabindex="-1"
                                class="absolute inset-y-0 right-0 pr-4 flex items-center text-gray-400 hover:text-blue-600 focus:outline-none transition-colors"
                                aria-label="Mostrar u ocultar contraseña">
                            <i class="fas fa-eye" id="togglePasswordIcon"></i>
                        </button>
                    </div>
                </div>

                <div id="loginAlert" class="<?= $error !== '' ? 'flex' : 'hidden' ?> items-start gap-2 p-3 text-sm text-red-600 bg-red-50 rounded-lg border border-red-100" role="alert">
                    <i class="fas fa-exclamation-circle mt-0.5 flex-shrink-0" aria-hidden="true"></i>
                    <span id="loginAlertMsg"><?= $error !== '' ? htmlspecialchars($error, ENT_QUOTES, 'UTF-8') : '' ?></span>
                </div>

                <button type="submit" id="btnSubmit"
                        class="w-full flex justify-center items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white py-3.5 px-4 rounded-xl font-semibold shadow-lg shadow-blue-600/30 hover:shadow-blue-600/40 transform hover:-translate-y-0.5 transition-all duration-200 focus:outline-none focus:ring-4 focus:ring-blue-500/50">
                    <span>Ingresar al Sistema</span>
                    <i class="fas fa-arrow-right text-sm" aria-hidden="true"></i>
                </button>
            </form>
        </div>
    </div>
</div>

<script src="assets/js/theme.js"></script>
<script>
(function () {
    var btn = document.getElementById('togglePassword');
    var input = document.getElementById('clave');
    var icon = document.getElementById('togglePasswordIcon');
    if (btn && input && icon) {
        btn.addEventListener('click', function () {
            var show = input.type === 'password';
            input.type = show ? 'text' : 'password';
            icon.className = show ? 'fas fa-eye-slash' : 'fas fa-eye';
        });
    }
})();
</script>
</body>
</html>

