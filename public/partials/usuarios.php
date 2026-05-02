<?php
declare(strict_types=1);

app_require_role('admin');
app_check_csrf();

$pdo = ventas_pdo();

$flashOk = '';
$flashErr = '';

$rolesDisponibles = [
    'admin' => 'Admin',
    'gerencia' => 'Gerencia',
    'analista' => 'Analista',
    'lector' => 'Lector',
];

$accion = (string) ($_POST['accion'] ?? '');
if ($_SERVER['REQUEST_METHOD'] === 'POST' && $accion !== '') {
    try {
        if ($accion === 'crear') {
            $username = trim((string) ($_POST['username'] ?? ''));
            $displayName = trim((string) ($_POST['display_name'] ?? ''));
            $role = strtolower(trim((string) ($_POST['role'] ?? '')));
            $password = (string) ($_POST['password'] ?? '');
            $isActive = (int) (($_POST['is_active'] ?? '1') === '1' ? 1 : 0);

            if ($username === '' || $password === '') {
                throw new RuntimeException('Usuario y contraseña son obligatorios.');
            }
            if (!preg_match('/^[a-zA-Z0-9._@-]{3,120}$/', $username)) {
                throw new RuntimeException('El usuario debe tener 3–120 caracteres (letras, números, punto, guion, @ o _).');
            }
            if (!isset($rolesDisponibles[$role])) {
                $role = 'lector';
            }
            if (strlen($password) < 6) {
                throw new RuntimeException('La contraseña debe tener al menos 6 caracteres.');
            }

            $hash = password_hash($password, PASSWORD_DEFAULT);
            $st = $pdo->prepare('INSERT INTO app_users (username, password_hash, display_name, role, is_active) VALUES (:u, :h, :d, :r, :a)');
            $st->execute([
                ':u' => $username,
                ':h' => $hash,
                ':d' => ($displayName !== '' ? $displayName : null),
                ':r' => $role,
                ':a' => $isActive,
            ]);
            $flashOk = 'Usuario creado correctamente.';
        } elseif ($accion === 'toggle_active') {
            $id = (int) ($_POST['id'] ?? 0);
            $newActive = (int) (($_POST['new_active'] ?? '0') === '1' ? 1 : 0);
            if ($id <= 0) {
                throw new RuntimeException('Usuario inválido.');
            }
            $pdo->prepare('UPDATE app_users SET is_active = :a WHERE id = :id')->execute([':a' => $newActive, ':id' => $id]);
            $flashOk = 'Estado actualizado.';
        } elseif ($accion === 'cambiar_rol') {
            $id = (int) ($_POST['id'] ?? 0);
            $role = strtolower(trim((string) ($_POST['role'] ?? '')));
            if ($id <= 0) {
                throw new RuntimeException('Usuario inválido.');
            }
            if (!isset($rolesDisponibles[$role])) {
                throw new RuntimeException('Rol inválido.');
            }
            $pdo->prepare('UPDATE app_users SET role = :r WHERE id = :id')->execute([':r' => $role, ':id' => $id]);
            $flashOk = 'Rol actualizado.';
        } elseif ($accion === 'reset_password') {
            $id = (int) ($_POST['id'] ?? 0);
            $password = (string) ($_POST['new_password'] ?? '');
            if ($id <= 0) {
                throw new RuntimeException('Usuario inválido.');
            }
            if (strlen($password) < 6) {
                throw new RuntimeException('La contraseña debe tener al menos 6 caracteres.');
            }
            $hash = password_hash($password, PASSWORD_DEFAULT);
            $pdo->prepare('UPDATE app_users SET password_hash = :h WHERE id = :id')->execute([':h' => $hash, ':id' => $id]);
            $flashOk = 'Contraseña actualizada.';
        } else {
            throw new RuntimeException('Acción no reconocida.');
        }
    } catch (Throwable $e) {
        $flashErr = $e->getMessage();
    }
}

$users = $pdo->query('SELECT id, username, display_name, role, is_active, last_login_at, created_at FROM app_users ORDER BY created_at DESC, id DESC')->fetchAll(PDO::FETCH_ASSOC) ?: [];

$csrf = app_csrf_token();
?>

<div class="page-head">
    <h1>Usuarios</h1>
    <p style="margin:0; color: var(--muted);">Administración de accesos y alcances (roles).</p>
</div>

<?php if ($flashOk !== ''): ?>
    <div class="card-filtros-demo" style="padding: 0.9rem 1rem; border-left: 4px solid rgba(34, 197, 94, 0.75);">
        <strong><?= htmlspecialchars($flashOk, ENT_QUOTES, 'UTF-8') ?></strong>
    </div>
<?php endif; ?>
<?php if ($flashErr !== ''): ?>
    <div class="card-filtros-demo" style="padding: 0.9rem 1rem; border-left: 4px solid rgba(239, 68, 68, 0.75);">
        <strong><?= htmlspecialchars($flashErr, ENT_QUOTES, 'UTF-8') ?></strong>
    </div>
<?php endif; ?>

<div class="card-filtros-demo">
    <button type="button" class="card-filtros-demo__head" id="btnToggleUsuariosCrear" aria-expanded="false" aria-controls="contenidoUsuariosCrear">
        <div class="card-filtros-demo__head-left">
            <span class="card-filtros-demo__emoji" aria-hidden="true">➕</span>
            <span class="card-filtros-demo__title">Crear usuario</span>
        </div>
        <svg id="iconoUsuariosCrear" class="card-filtros-demo__chev" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
    </button>
    <div id="contenidoUsuariosCrear" class="card-filtros-demo__body hidden">
        <form method="post" class="filters-block filters-block--inner" autocomplete="off">
            <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($csrf, ENT_QUOTES, 'UTF-8') ?>">
            <input type="hidden" name="accion" value="crear">

            <div class="filter-row">
                <div class="filter-field">
                    <label for="u_username">Usuario</label>
                    <input type="text" id="u_username" name="username" placeholder="Ej. j.perez" required>
                </div>
                <div class="filter-field">
                    <label for="u_display">Nombre para mostrar</label>
                    <input type="text" id="u_display" name="display_name" placeholder="Ej. Juan Pérez">
                </div>
            </div>

            <div class="filter-row">
                <div class="filter-field">
                    <label for="u_role">Rol</label>
                    <select id="u_role" name="role">
                        <?php foreach ($rolesDisponibles as $k => $label): ?>
                            <option value="<?= htmlspecialchars($k, ENT_QUOTES, 'UTF-8') ?>"><?= htmlspecialchars($label, ENT_QUOTES, 'UTF-8') ?></option>
                        <?php endforeach; ?>
                    </select>
                </div>
                <div class="filter-field">
                    <label for="u_password">Contraseña</label>
                    <input type="password" id="u_password" name="password" required minlength="6" placeholder="Mínimo 6 caracteres">
                </div>
                <div class="filter-field">
                    <label for="u_active">Activo</label>
                    <select id="u_active" name="is_active">
                        <option value="1" selected>Sí</option>
                        <option value="0">No</option>
                    </select>
                </div>
            </div>

            <div class="filter-actions">
                <button type="submit" class="btn btn-primary"><i class="fas fa-user-plus"></i> Crear</button>
            </div>
        </form>
    </div>
</div>

<div class="tabla-listado-wrapper" style="padding: 1rem;">
    <div class="table-wrapper overflow-x-auto">
        <table class="data-table config-table display stripe nowrap" style="width:100%">
            <thead>
            <tr>
                <th>ID</th>
                <th>Usuario</th>
                <th>Nombre</th>
                <th>Rol</th>
                <th>Activo</th>
                <th>Último acceso</th>
                <th>Creado</th>
                <th>Acciones</th>
            </tr>
            </thead>
            <tbody>
            <?php foreach ($users as $u): ?>
                <?php
                    $id = (int) ($u['id'] ?? 0);
                    $username = (string) ($u['username'] ?? '');
                    $displayName = (string) ($u['display_name'] ?? '');
                    $role = app_normalize_user_role((string) ($u['role'] ?? ''));
                    $active = (int) ($u['is_active'] ?? 0) === 1;
                    $last = (string) ($u['last_login_at'] ?? '');
                    $created = (string) ($u['created_at'] ?? '');
                ?>
                <tr>
                    <td><?= $id ?></td>
                    <td><?= htmlspecialchars($username, ENT_QUOTES, 'UTF-8') ?></td>
                    <td><?= htmlspecialchars($displayName, ENT_QUOTES, 'UTF-8') ?></td>
                    <td>
                        <form method="post" style="display:flex; gap:0.5rem; align-items:center;">
                            <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($csrf, ENT_QUOTES, 'UTF-8') ?>">
                            <input type="hidden" name="accion" value="cambiar_rol">
                            <input type="hidden" name="id" value="<?= $id ?>">
                            <select name="role" onchange="this.form.submit()">
                                <?php foreach ($rolesDisponibles as $k => $label): ?>
                                    <option value="<?= htmlspecialchars($k, ENT_QUOTES, 'UTF-8') ?>" <?= $k === $role ? 'selected' : '' ?>>
                                        <?= htmlspecialchars($label, ENT_QUOTES, 'UTF-8') ?>
                                    </option>
                                <?php endforeach; ?>
                            </select>
                        </form>
                    </td>
                    <td><?= $active ? 'Sí' : 'No' ?></td>
                    <td><?= htmlspecialchars($last, ENT_QUOTES, 'UTF-8') ?></td>
                    <td><?= htmlspecialchars($created, ENT_QUOTES, 'UTF-8') ?></td>
                    <td>
                        <div style="display:flex; gap:0.5rem; flex-wrap:wrap;">
                            <form method="post">
                                <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($csrf, ENT_QUOTES, 'UTF-8') ?>">
                                <input type="hidden" name="accion" value="toggle_active">
                                <input type="hidden" name="id" value="<?= $id ?>">
                                <input type="hidden" name="new_active" value="<?= $active ? '0' : '1' ?>">
                                <button type="submit" class="btn btn-ghost">
                                    <i class="fas <?= $active ? 'fa-user-slash' : 'fa-user-check' ?>" aria-hidden="true"></i>
                                    <?= $active ? 'Desactivar' : 'Activar' ?>
                                </button>
                            </form>

                            <form method="post" onsubmit="return confirm('¿Resetear contraseña para <?= htmlspecialchars($username, ENT_QUOTES, 'UTF-8') ?>?');">
                                <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($csrf, ENT_QUOTES, 'UTF-8') ?>">
                                <input type="hidden" name="accion" value="reset_password">
                                <input type="hidden" name="id" value="<?= $id ?>">
                                <input type="password" name="new_password" minlength="6" required placeholder="Nueva clave" style="min-width: 10rem;">
                                <button type="submit" class="btn btn-primary">
                                    <i class="fas fa-key" aria-hidden="true"></i> Reset
                                </button>
                            </form>
                        </div>
                    </td>
                </tr>
            <?php endforeach; ?>
            </tbody>
        </table>
    </div>
</div>

<script>
(function () {
    var btn = document.getElementById('btnToggleUsuariosCrear');
    var body = document.getElementById('contenidoUsuariosCrear');
    var chev = document.getElementById('iconoUsuariosCrear');
    if (!btn || !body || !chev) return;
    btn.addEventListener('click', function () {
        var open = !body.classList.contains('hidden');
        if (open) {
            body.classList.add('hidden');
            btn.setAttribute('aria-expanded', 'false');
            chev.classList.remove('card-filtros-demo__chev--open');
        } else {
            body.classList.remove('hidden');
            btn.setAttribute('aria-expanded', 'true');
            chev.classList.add('card-filtros-demo__chev--open');
        }
    });
})();
</script>

