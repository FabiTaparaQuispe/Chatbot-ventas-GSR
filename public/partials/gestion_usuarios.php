<?php
declare(strict_types=1);

app_require_role('administrador');
app_check_csrf();

$pdo = ventas_pdo();
$flashOk = '';
$flashErr = '';
$myUsername = app_user_username();

/** Roles gestionados en esta pantalla (listado y edición). */
$rolesGestionTabla = [
    'administrador' => 'Administrador',
    'estrategico'   => 'Estratégico',
    'tactico'       => 'Táctico',
    'operativo'     => 'Operativo',
];

/** Solo estratégico, táctico y operativo al crear usuario (administrador no por formulario). */
$rolesCrearUsuario = [
    'estrategico' => 'Estratégico',
    'tactico'     => 'Táctico',
    'operativo'   => 'Operativo',
];

$rolesSqlIn = "'administrador','estrategico','tactico','operativo'";

$accion = (string) ($_POST['accion'] ?? '');
if ($_SERVER['REQUEST_METHOD'] === 'POST' && $accion !== '') {
    try {
        if ($accion === 'crear') {
            $username    = trim((string) ($_POST['username'] ?? ''));
            $displayName = trim((string) ($_POST['display_name'] ?? ''));
            $role        = strtolower(trim((string) ($_POST['role'] ?? '')));
            $password    = (string) ($_POST['password'] ?? '');

            if ($username === '' || $password === '') {
                throw new RuntimeException('Usuario y contraseña son obligatorios.');
            }
            if (!preg_match('/^[a-zA-Z0-9._@-]{3,120}$/', $username)) {
                throw new RuntimeException('El usuario debe tener 3–120 caracteres (letras, números, punto, guion, @ o _).');
            }
            if (!isset($rolesCrearUsuario[$role])) {
                throw new RuntimeException('Rol inválido.');
            }
            if (strlen($password) < 6) {
                throw new RuntimeException('La contraseña debe tener al menos 6 caracteres.');
            }

            $hash = password_hash($password, PASSWORD_DEFAULT);
            $st = $pdo->prepare('INSERT INTO app_users (username, password_hash, display_name, role, is_active) VALUES (:u, :h, :d, :r, 1)');
            $st->execute([
                ':u' => $username,
                ':h' => $hash,
                ':d' => ($displayName !== '' ? $displayName : null),
                ':r' => $role,
            ]);
            $flashOk = 'Usuario creado correctamente.';

        } elseif ($accion === 'toggle_active') {
            $id        = (int) ($_POST['id'] ?? 0);
            $newActive = (int) (($_POST['new_active'] ?? '0') === '1' ? 1 : 0);
            if ($id <= 0) {
                throw new RuntimeException('Usuario inválido.');
            }
            $st = $pdo->prepare("UPDATE app_users SET is_active = :a WHERE id = :id AND role IN ($rolesSqlIn)");
            $st->execute([':a' => $newActive, ':id' => $id]);
            $flashOk = 'Estado actualizado.';

        } elseif ($accion === 'cambiar_rol') {
            $id   = (int) ($_POST['id'] ?? 0);
            $role = strtolower(trim((string) ($_POST['role'] ?? '')));
            if ($id <= 0) {
                throw new RuntimeException('Usuario inválido.');
            }
            if (!isset($rolesGestionTabla[$role])) {
                throw new RuntimeException('Rol inválido.');
            }
            $stWho = $pdo->prepare('SELECT username FROM app_users WHERE id = :id LIMIT 1');
            $stWho->execute([':id' => $id]);
            $targetUser = (string) ($stWho->fetchColumn() ?: '');
            if ($targetUser !== '' && $targetUser === $myUsername) {
                throw new RuntimeException('No puede cambiar su propio rol desde esta pantalla.');
            }
            $st = $pdo->prepare("UPDATE app_users SET role = :r WHERE id = :id AND role IN ($rolesSqlIn)");
            $st->execute([':r' => $role, ':id' => $id]);
            $flashOk = 'Rol actualizado.';

        } elseif ($accion === 'reset_password') {
            $id       = (int) ($_POST['id'] ?? 0);
            $password = (string) ($_POST['new_password'] ?? '');
            if ($id <= 0) {
                throw new RuntimeException('Usuario inválido.');
            }
            if (strlen($password) < 6) {
                throw new RuntimeException('La contraseña debe tener al menos 6 caracteres.');
            }
            $hash = password_hash($password, PASSWORD_DEFAULT);
            $st = $pdo->prepare("UPDATE app_users SET password_hash = :h WHERE id = :id AND role IN ($rolesSqlIn)");
            $st->execute([':h' => $hash, ':id' => $id]);
            $flashOk = 'Contraseña actualizada.';

        } elseif ($accion === 'eliminar') {
            $id = (int) ($_POST['id'] ?? 0);
            if ($id <= 0) {
                throw new RuntimeException('Usuario inválido.');
            }
            $stCheck = $pdo->prepare('SELECT username FROM app_users WHERE id = :id LIMIT 1');
            $stCheck->execute([':id' => $id]);
            $targetUsername = (string) ($stCheck->fetchColumn() ?: '');
            if ($targetUsername === $myUsername) {
                throw new RuntimeException('No puede eliminarse a sí mismo.');
            }
            $st = $pdo->prepare("DELETE FROM app_users WHERE id = :id AND role IN ($rolesSqlIn)");
            $st->execute([':id' => $id]);
            $flashOk = 'Usuario eliminado.';

        } else {
            throw new RuntimeException('Acción no reconocida.');
        }
    } catch (Throwable $e) {
        $flashErr = $e->getMessage();
    }
}

$users = $pdo->query(
    "SELECT id, username, display_name, role, is_active, last_login_at, created_at
     FROM app_users
     WHERE role IN ($rolesSqlIn)
     ORDER BY created_at DESC, id DESC"
)->fetchAll(PDO::FETCH_ASSOC) ?: [];

$csrf = app_csrf_token();

$roleBadgeClass = [
    'administrador' => 'gu-badge--administrador',
    'estrategico'   => 'gu-badge--estrategico',
    'tactico'       => 'gu-badge--tactico',
    'operativo'     => 'gu-badge--operativo',
];
?>

<style>
/* ── Badges de rol ─────────────────────────────────────────── */
.gu-role-wrap { display:flex; align-items:center; gap:.5rem; }
.gu-badge {
    display:inline-flex; align-items:center; gap:.35rem;
    padding:.25rem .65rem; border-radius:999px; font-size:.75rem;
    font-weight:600; letter-spacing:.02em; white-space:nowrap;
    border:1px solid transparent;
}
.gu-badge--administrador { background:rgba(234,88,12,.12); color:#c2410c; border-color:rgba(234,88,12,.35); }
.gu-badge--estrategico { background:rgba(59,130,246,.15); color:#2563eb; border-color:rgba(59,130,246,.3); }
.gu-badge--tactico     { background:rgba(168,85,247,.15);  color:#7c3aed; border-color:rgba(168,85,247,.3); }
.gu-badge--operativo   { background:rgba(16,185,129,.15);  color:#059669; border-color:rgba(16,185,129,.3); }
[data-theme="dark"] .gu-badge--administrador { background:rgba(234,88,12,.2); color:#fdba74; border-color:rgba(234,88,12,.45); }
[data-theme="dark"] .gu-badge--estrategico { background:rgba(59,130,246,.2); color:#93c5fd; border-color:rgba(59,130,246,.4); }
[data-theme="dark"] .gu-badge--tactico     { background:rgba(168,85,247,.2);  color:#c4b5fd; border-color:rgba(168,85,247,.4); }
[data-theme="dark"] .gu-badge--operativo   { background:rgba(16,185,129,.2);  color:#6ee7b7; border-color:rgba(16,185,129,.4); }

/* ── Select de rol compacto ────────────────────────────────── */
.gu-role-select {
    appearance:none; -webkit-appearance:none;
    padding:.28rem 1.8rem .28rem .6rem;
    border-radius:999px; font-size:.75rem; font-weight:600;
    border:1px solid transparent; cursor:pointer;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%236b7280'/%3E%3C/svg%3E");
    background-repeat:no-repeat; background-position:right .5rem center;
    transition:box-shadow .15s;
}
.gu-role-select:focus { outline:none; box-shadow:0 0 0 2px rgba(59,130,246,.4); }
.gu-role-select.gu-badge--administrador { background-color:rgba(234,88,12,.12); color:#c2410c; border-color:rgba(234,88,12,.35); }
.gu-role-select.gu-badge--estrategico { background-color:rgba(59,130,246,.15); color:#2563eb; border-color:rgba(59,130,246,.3); }
.gu-role-select.gu-badge--tactico     { background-color:rgba(168,85,247,.15);  color:#7c3aed; border-color:rgba(168,85,247,.3); }
.gu-role-select.gu-badge--operativo   { background-color:rgba(16,185,129,.15);  color:#059669; border-color:rgba(16,185,129,.3); }
[data-theme="dark"] .gu-role-select.gu-badge--administrador { background-color:rgba(234,88,12,.2); color:#fdba74; border-color:rgba(234,88,12,.45); }
[data-theme="dark"] .gu-role-select.gu-badge--estrategico { background-color:rgba(59,130,246,.2); color:#93c5fd; border-color:rgba(59,130,246,.4); }
[data-theme="dark"] .gu-role-select.gu-badge--tactico     { background-color:rgba(168,85,247,.2);  color:#c4b5fd; border-color:rgba(168,85,247,.4); }
[data-theme="dark"] .gu-role-select.gu-badge--operativo   { background-color:rgba(16,185,129,.2);  color:#6ee7b7; border-color:rgba(16,185,129,.4); }

/* ── Campo contraseña con toggle ───────────────────────────── */
.gu-pwd-wrap { position:relative; display:flex; align-items:center; }
.gu-pwd-wrap input[type="password"],
.gu-pwd-wrap input[type="text"] {
    padding-right:2.4rem !important; width:100%;
}
.gu-pwd-toggle {
    position:absolute; right:.6rem; background:none; border:none;
    cursor:pointer; color:var(--muted,#9ca3af); padding:0; line-height:1;
    display:flex; align-items:center; font-size:.95rem;
}
.gu-pwd-toggle:hover { color:var(--fg,#374151); }

/* ── Modal ─────────────────────────────────────────────────── */
.gu-modal-overlay {
    display:none; position:fixed; inset:0; z-index:1000;
    background:rgba(0,0,0,.45); align-items:center; justify-content:center;
}
.gu-modal-overlay.open { display:flex; }
.gu-modal {
    background:var(--card-bg,#fff); border-radius:.875rem;
    box-shadow:0 20px 60px rgba(0,0,0,.2); padding:2rem;
    width:100%; max-width:420px; position:relative;
}
[data-theme="dark"] .gu-modal { background:var(--card-bg,#1e293b); }
.gu-modal-title { font-size:1.1rem; font-weight:700; margin:0 0 .35rem; }
.gu-modal-sub   { font-size:.85rem; color:var(--muted,#6b7280); margin:0 0 1.25rem; }
.gu-modal-close {
    position:absolute; top:.85rem; right:.85rem; background:none; border:none;
    cursor:pointer; color:var(--muted,#6b7280); font-size:1.1rem; padding:.25rem;
    border-radius:.375rem; line-height:1;
}
.gu-modal-close:hover { color:var(--fg,#374151); background:var(--hover-bg,rgba(0,0,0,.06)); }
.gu-modal-field { margin-bottom:1rem; }
.gu-modal-field label { display:block; font-size:.8rem; font-weight:600; margin-bottom:.35rem; }
.gu-modal-actions { display:flex; gap:.6rem; justify-content:flex-end; margin-top:1.4rem; }
</style>

<!-- Modal cambiar contraseña -->
<div class="gu-modal-overlay" id="guModalPwd" role="dialog" aria-modal="true" aria-labelledby="guModalPwdTitle">
    <div class="gu-modal">
        <button type="button" class="gu-modal-close" id="guModalPwdClose" aria-label="Cerrar">
            <i class="fas fa-times" aria-hidden="true"></i>
        </button>
        <p class="gu-modal-title" id="guModalPwdTitle">Cambiar contraseña</p>
        <p class="gu-modal-sub" id="guModalPwdSub">Usuario: —</p>
        <form method="post" id="guModalPwdForm" autocomplete="off">
            <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($csrf, ENT_QUOTES, 'UTF-8') ?>">
            <input type="hidden" name="accion" value="reset_password">
            <input type="hidden" name="id" id="guModalPwdId" value="">
            <div class="gu-modal-field">
                <label for="guModalPwdInput">Nueva contraseña</label>
                <div class="gu-pwd-wrap">
                    <input type="password" id="guModalPwdInput" name="new_password"
                           minlength="6" required placeholder="Mínimo 6 caracteres">
                    <button type="button" class="gu-pwd-toggle" data-target="guModalPwdInput" aria-label="Ver/ocultar contraseña">
                        <i class="fas fa-eye"></i>
                    </button>
                </div>
            </div>
            <div class="gu-modal-actions">
                <button type="button" class="btn btn-ghost" id="guModalPwdCancel">Cancelar</button>
                <button type="submit" class="btn btn-primary">
                    <i class="fas fa-key" aria-hidden="true"></i> Guardar
                </button>
            </div>
        </form>
    </div>
</div>

<div class="page-head">
    <h1>Creación de usuarios</h1>
    <p style="margin:0; color: var(--muted);">Solo el rol administrador accede aquí. Usuarios de la app: administrador, estratégico, táctico y operativo.</p>
</div>

<?php if ($flashOk !== ''): ?>
    <div class="card-filtros-demo" style="padding:.9rem 1rem; border-left:4px solid rgba(34,197,94,.75);">
        <strong><?= htmlspecialchars($flashOk, ENT_QUOTES, 'UTF-8') ?></strong>
    </div>
<?php endif; ?>
<?php if ($flashErr !== ''): ?>
    <div class="card-filtros-demo" style="padding:.9rem 1rem; border-left:4px solid rgba(239,68,68,.75);">
        <strong><?= htmlspecialchars($flashErr, ENT_QUOTES, 'UTF-8') ?></strong>
    </div>
<?php endif; ?>

<div class="card-filtros-demo">
    <button type="button" class="card-filtros-demo__head" id="btnToggleGestionCrear" aria-expanded="false" aria-controls="contenidoGestionCrear">
        <div class="card-filtros-demo__head-left">
            <span class="card-filtros-demo__emoji" aria-hidden="true">➕</span>
            <span class="card-filtros-demo__title">Crear usuario</span>
        </div>
        <svg id="iconoGestionCrear" class="card-filtros-demo__chev" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
    </button>
    <div id="contenidoGestionCrear" class="card-filtros-demo__body hidden">
        <form method="post" class="filters-block filters-block--inner" autocomplete="off">
            <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($csrf, ENT_QUOTES, 'UTF-8') ?>">
            <input type="hidden" name="accion" value="crear">

            <div class="filter-row">
                <div class="filter-field">
                    <label for="gu_username">Usuario</label>
                    <input type="text" id="gu_username" name="username" placeholder="Ej. j.perez" required>
                </div>
                <div class="filter-field">
                    <label for="gu_display">Nombre para mostrar</label>
                    <input type="text" id="gu_display" name="display_name" placeholder="Ej. Juan Pérez">
                </div>
            </div>

            <div class="filter-row">
                <div class="filter-field">
                    <label for="gu_role">Rol</label>
                    <select id="gu_role" name="role">
                        <?php foreach ($rolesCrearUsuario as $k => $label): ?>
                            <option value="<?= htmlspecialchars($k, ENT_QUOTES, 'UTF-8') ?>"><?= htmlspecialchars($label, ENT_QUOTES, 'UTF-8') ?></option>
                        <?php endforeach; ?>
                    </select>
                </div>
                <div class="filter-field">
                    <label for="gu_password">Contraseña</label>
                    <div class="gu-pwd-wrap">
                        <input type="password" id="gu_password" name="password"
                               required minlength="6" placeholder="Mínimo 6 caracteres">
                        <button type="button" class="gu-pwd-toggle" data-target="gu_password" aria-label="Ver/ocultar contraseña">
                            <i class="fas fa-eye"></i>
                        </button>
                    </div>
                </div>
            </div>

            <div class="filter-actions">
                <button type="submit" class="btn btn-primary">
                    <i class="fas fa-user-plus" aria-hidden="true"></i> Crear
                </button>
            </div>
        </form>
    </div>
</div>

<div class="tabla-listado-wrapper" id="tablaUsuariosWrapper" data-vista-tabla-iconos data-vista="lista" data-sync-app-theme>
    <div class="reportes-toolbar-row" id="usuariosToolbarRow">
        <div class="view-toggle-group" id="viewToggleGroupUsuarios">
            <button type="button" class="view-toggle-btn active" id="btnViewListaUsuarios" title="Lista">
                <i class="fas fa-list" aria-hidden="true"></i> Lista
            </button>
            <button type="button" class="view-toggle-btn" id="btnViewIconosUsuarios" title="Iconos">
                <i class="fas fa-th" aria-hidden="true"></i> Iconos
            </button>
        </div>
        <div class="productos-dt-toolbar-slot" id="usuariosDtControls"></div>
        <div class="productos-dt-toolbar-slot" id="usuariosIconosControls" style="display:none;"></div>
    </div>

    <div class="view-tarjetas-wrap" id="viewTarjetasUsuarios" style="display:none;">
        <div id="cardsControlsTopUsuarios" class="productos-cards-controls-top" aria-hidden="true"></div>
        <div id="cardsContainerUsuarios" class="cards-grid cards-grid-iconos" data-vista-cards="iconos"></div>
        <div id="cardsPaginationUsuarios" data-table="#tablaGestionUsuarios" data-vista="iconos"></div>
    </div>

    <div class="view-lista-wrap productos-dt-skin" id="viewListaUsuarios">
        <div class="table-wrapper overflow-x-auto">
            <table id="tablaGestionUsuarios" class="data-table config-table display stripe nowrap" style="width:100%">
                <thead>
                <tr>
                    <th>N°</th>
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
                <?php $nro = 0; foreach ($users as $u): $nro++; ?>
                    <?php
                        $id          = (int) ($u['id'] ?? 0);
                        $username    = (string) ($u['username'] ?? '');
                        $displayName = (string) ($u['display_name'] ?? '');
                        $role        = app_normalize_user_role((string) ($u['role'] ?? ''));
                        $active      = (int) ($u['is_active'] ?? 0) === 1;
                        $last        = (string) ($u['last_login_at'] ?? '');
                        $created     = (string) ($u['created_at'] ?? '');
                        $isSelf      = ($username === $myUsername);
                        $badgeClass  = $roleBadgeClass[$role] ?? '';
                        $roleLabel   = $rolesGestionTabla[$role] ?? ucfirst($role);
                    ?>
                    <tr>
                        <td><?= $nro ?></td>
                        <td><?= htmlspecialchars($username, ENT_QUOTES, 'UTF-8') ?></td>
                        <td><?= htmlspecialchars($displayName, ENT_QUOTES, 'UTF-8') ?></td>
                        <td>
                            <form method="post" class="gu-role-wrap">
                                <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($csrf, ENT_QUOTES, 'UTF-8') ?>">
                                <input type="hidden" name="accion" value="cambiar_rol">
                                <input type="hidden" name="id" value="<?= $id ?>">
                                <select name="role"
                                        class="gu-role-select <?= htmlspecialchars($badgeClass, ENT_QUOTES, 'UTF-8') ?>"
                                        <?= $isSelf ? 'disabled title="No puede cambiar su propio rol desde aquí"' : 'onchange="guUpdateSelectStyle(this); this.form.submit();"' ?>
                                        aria-label="Cambiar rol">
                                    <?php foreach ($rolesGestionTabla as $k => $lbl): ?>
                                        <option value="<?= htmlspecialchars($k, ENT_QUOTES, 'UTF-8') ?>" <?= $k === $role ? 'selected' : '' ?>>
                                            <?= htmlspecialchars($lbl, ENT_QUOTES, 'UTF-8') ?>
                                        </option>
                                    <?php endforeach; ?>
                                </select>
                            </form>
                        </td>
                        <td><?= $active ? 'Sí' : 'No' ?></td>
                        <td><?= htmlspecialchars($last, ENT_QUOTES, 'UTF-8') ?></td>
                        <td><?= htmlspecialchars($created, ENT_QUOTES, 'UTF-8') ?></td>
                        <td>
                            <div style="display:flex; gap:.5rem; flex-wrap:wrap; align-items:center;">

                                <form method="post">
                                    <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($csrf, ENT_QUOTES, 'UTF-8') ?>">
                                    <input type="hidden" name="accion" value="toggle_active">
                                    <input type="hidden" name="id" value="<?= $id ?>">
                                    <input type="hidden" name="new_active" value="<?= $active ? '0' : '1' ?>">
                                    <button type="submit" class="btn btn-ghost" <?= $isSelf ? 'disabled title="No puede desactivarse a sí mismo"' : '' ?>>
                                        <i class="fas <?= $active ? 'fa-user-slash' : 'fa-user-check' ?>" aria-hidden="true"></i>
                                        <?= $active ? 'Desactivar' : 'Activar' ?>
                                    </button>
                                </form>

                                <button type="button" class="btn btn-primary"
                                        onclick="guOpenModal(<?= $id ?>, <?= htmlspecialchars(json_encode($username), ENT_QUOTES, 'UTF-8') ?>)">
                                    <i class="fas fa-key" aria-hidden="true"></i> Contraseña
                                </button>

                                <?php if (!$isSelf): ?>
                                <form method="post" onsubmit="return confirm(<?= htmlspecialchars(json_encode('¿Eliminar al usuario ' . $username . '? Esta acción no se puede deshacer.'), ENT_QUOTES, 'UTF-8') ?>);">
                                    <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($csrf, ENT_QUOTES, 'UTF-8') ?>">
                                    <input type="hidden" name="accion" value="eliminar">
                                    <input type="hidden" name="id" value="<?= $id ?>">
                                    <button type="submit" class="btn btn-ghost" style="color:var(--danger,#ef4444);">
                                        <i class="fas fa-trash" aria-hidden="true"></i> Eliminar
                                    </button>
                                </form>
                                <?php endif; ?>

                            </div>
                        </td>
                    </tr>
                <?php endforeach; ?>
                <?php if ($users === []): ?>
                    <tr><td colspan="8" style="text-align:center; color:var(--muted); padding:1.5rem;">No hay usuarios con estos roles.</td></tr>
                <?php endif; ?>
                </tbody>
            </table>
        </div>
    </div>
</div>

<!-- Vanilla JS: accordion + modal + toggle contraseña (no necesita jQuery) -->
<script>
(function () {

    /* ── Accordion crear usuario ── */
    var btn  = document.getElementById('btnToggleGestionCrear');
    var body = document.getElementById('contenidoGestionCrear');
    var chev = document.getElementById('iconoGestionCrear');
    if (btn && body && chev) {
        btn.addEventListener('click', function () {
            var open = !body.classList.contains('hidden');
            body.classList.toggle('hidden', open);
            btn.setAttribute('aria-expanded', open ? 'false' : 'true');
            chev.classList.toggle('card-filtros-demo__chev--open', !open);
        });
    }

    /* ── Toggle ver/ocultar contraseña ── */
    document.addEventListener('click', function (e) {
        var toggleBtn = e.target.closest('.gu-pwd-toggle');
        if (!toggleBtn) return;
        var targetId = toggleBtn.getAttribute('data-target');
        var input = targetId ? document.getElementById(targetId) : toggleBtn.previousElementSibling;
        if (!input) return;
        var show = input.type === 'password';
        input.type = show ? 'text' : 'password';
        var icon = toggleBtn.querySelector('i');
        if (icon) {
            icon.className = show ? 'fas fa-eye-slash' : 'fas fa-eye';
        }
    });

    /* ── Modal contraseña ── */
    var overlay  = document.getElementById('guModalPwd');
    var modalSub = document.getElementById('guModalPwdSub');
    var modalId  = document.getElementById('guModalPwdId');
    var modalInp = document.getElementById('guModalPwdInput');

    function guOpenModal(id, username) {
        if (!overlay) return;
        modalId.value = id;
        modalSub.textContent = 'Usuario: ' + username;
        if (modalInp) { modalInp.value = ''; modalInp.type = 'password'; }
        var icon = overlay.querySelector('[data-target="guModalPwdInput"] i');
        if (icon) icon.className = 'fas fa-eye';
        overlay.classList.add('open');
        if (modalInp) setTimeout(function () { modalInp.focus(); }, 80);
    }

    function guCloseModal() {
        if (overlay) overlay.classList.remove('open');
    }

    window.guOpenModal = guOpenModal;
    window.guUpdateSelectStyle = function (sel) {
        var badges = ['gu-badge--administrador', 'gu-badge--estrategico', 'gu-badge--tactico', 'gu-badge--operativo'];
        var map = { administrador: 'gu-badge--administrador', estrategico: 'gu-badge--estrategico', tactico: 'gu-badge--tactico', operativo: 'gu-badge--operativo' };
        badges.forEach(function (c) { sel.classList.remove(c); });
        var cls = map[sel.value];
        if (cls) sel.classList.add(cls);
    };

    document.getElementById('guModalPwdClose') && document.getElementById('guModalPwdClose').addEventListener('click', guCloseModal);
    document.getElementById('guModalPwdCancel') && document.getElementById('guModalPwdCancel').addEventListener('click', guCloseModal);
    overlay && overlay.addEventListener('click', function (e) {
        if (e.target === overlay) guCloseModal();
    });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') guCloseModal();
    });

})();
</script>

<?php
$extraScripts .= <<<'GUJS'
<script>
(function ($) {
    'use strict';

    var GU_LANG = {
        processing:'Procesando…', search:'Buscar:',
        lengthMenu:'Mostrar _MENU_ registros',
        info:'Mostrando _START_ a _END_ de _TOTAL_ registros',
        infoEmpty:'Mostrando 0 a 0 de 0 registros',
        infoFiltered:'(filtrado de _MAX_ registros totales)',
        loadingRecords:'Cargando…', zeroRecords:'No se encontraron registros',
        emptyTable:'Sin datos en la tabla',
        paginate:{ first:'Primero', previous:'Anterior', next:'Siguiente', last:'Último' },
    };

    var guTable;
    var guIconosBound = false;

    function escHtml(s) {
        return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }

    var roleBadgeLabel = { administrador:'Administrador', estrategico:'Estratégico', tactico:'Táctico', operativo:'Operativo' };

    function rebuildUsuariosCards() {
        if (!guTable) return;
        var $c = $('#cardsContainerUsuarios');
        $c.empty();
        var nodes = guTable.rows({ page:'current' }).nodes().toArray();
        nodes.forEach(function (tr) {
            var tds    = tr.querySelectorAll('td');
            var nro    = tds[0] ? tds[0].textContent.trim() : '';
            var user   = tds[1] ? tds[1].textContent.trim() : '';
            var nombre = tds[2] ? tds[2].textContent.trim() : '';
            var sel    = tds[3] ? tds[3].querySelector('select') : null;
            var rolVal = sel ? sel.value : '';
            var rol    = roleBadgeLabel[rolVal] || rolVal;
            var activo = tds[4] ? tds[4].textContent.trim() : '';
            var ultimo = tds[5] ? tds[5].textContent.trim() : '';
            var creado = tds[6] ? tds[6].textContent.trim() : '';
            $c.append(
                '<article class="card-item prod-card">' +
                '<div class="card-numero-row">#' + escHtml(nro) + '</div>' +
                '<div class="card-campos">' +
                '<div class="card-row"><span class="label">Usuario</span><span>' + escHtml(user) + '</span></div>' +
                '<div class="card-row"><span class="label">Nombre</span><span>' + escHtml(nombre) + '</span></div>' +
                '<div class="card-row"><span class="label">Rol</span><span>' + escHtml(rol) + '</span></div>' +
                '<div class="card-row"><span class="label">Activo</span><span>' + escHtml(activo) + '</span></div>' +
                '<div class="card-row"><span class="label">Último acceso</span><span>' + escHtml(ultimo) + '</span></div>' +
                '<div class="card-row"><span class="label">Creado</span><span>' + escHtml(creado) + '</span></div>' +
                '</div></article>'
            );
        });
    }

    function renderIconosControlsGU() {
        if (!guTable || !$('#usuariosIconosControls').is(':visible')) return;
        var $c = $('#usuariosIconosControls');
        if (!$c.find('.productos-iconos-toolbar-row').length) {
            $c.html(
                '<div class="productos-iconos-toolbar-row iconos-toolbar-row">' +
                '<div class="dataTables_length"><label>Mostrar ' +
                '<select class="js-gu-len dt-toolbar-length-select cards-length-select">' +
                '<option value="20">20</option><option value="25">25</option><option value="50">50</option><option value="100">100</option>' +
                '</select> registros</label></div>' +
                '<div class="dataTables_filter"><label>Buscar <input type="search" class="js-gu-search" placeholder=""></label></div>' +
                '</div>'
            );
        }
        if (!guIconosBound) {
            $c.on('change', '.js-gu-len', function () {
                var v = parseInt($(this).val(), 10);
                if (guTable && !isNaN(v)) guTable.page.len(v).draw(false);
            });
            $c.on('input', '.js-gu-search', function () {
                var v = ($(this).val() || '').toString();
                setTimeout(function () { if (guTable) guTable.search(v).draw(); }, 220);
            });
            guIconosBound = true;
        }
        var $len = $c.find('.js-gu-len');
        var $srch = $c.find('.js-gu-search');
        if ($len.length) $len.val(String(guTable.page.len()));
        if ($srch.length && !$srch.is(':focus')) $srch.val(guTable.search() || '');
    }

    function updateUsuariosPagination() {
        if (!guTable || typeof window.buildPaginationIconos !== 'function') return;
        if ($('#tablaUsuariosWrapper').attr('data-vista') !== 'iconos') return;
        var info = guTable.page.info();
        $('#cardsControlsTopUsuarios').empty();
        $('#cardsPaginationUsuarios').html(window.buildPaginationIconos(info));
    }

    function syncVistaUsuarios() {
        var esLista = $('#tablaUsuariosWrapper').attr('data-vista') === 'lista';
        $('#btnViewListaUsuarios').toggleClass('active', esLista);
        $('#btnViewIconosUsuarios').toggleClass('active', !esLista);
        $('#viewListaUsuarios').toggle(esLista);
        $('#viewTarjetasUsuarios').toggle(!esLista);
        if (esLista) {
            $('#usuariosDtControls').show();
            $('#usuariosIconosControls').hide();
        } else {
            $('#usuariosDtControls').hide();
            $('#usuariosIconosControls').show();
            renderIconosControlsGU();
        }
        if (guTable) {
            try { guTable.columns.adjust(); } catch (e) {}
            rebuildUsuariosCards();
            updateUsuariosPagination();
        }
    }

    $(function () {
        if (!$.fn.DataTable || !$('#tablaGestionUsuarios').length) return;

        guTable = $('#tablaGestionUsuarios').DataTable({
            language: GU_LANG,
            serverSide: false,
            searching: true,
            ordering: true,
            /* Sin scrollX: evita thead/tbody duplicados que desalinean columnas; el scroll va en .table-wrapper */
            pageLength: 20,
            lengthMenu: [[20,25,50,100],[20,25,50,100]],
            dom: '<"dt-top-row"lf>rt<"dt-bottom-row"ip>',
            columnDefs: [
                { targets: 0, orderable: false, searchable: false },
                { targets: 3, orderable: false },
                { targets: 7, orderable: false, searchable: false },
            ],
            rowCallback: function (row, data, index) {
                var info = guTable.page.info();
                $('td:first', row).text(info.start + index + 1);
            },
            drawCallback: function () {
                rebuildUsuariosCards();
                renderIconosControlsGU();
                updateUsuariosPagination();
            },
            initComplete: function () {
                var $w = $('#tablaGestionUsuarios').closest('.dataTables_wrapper');
                $('#usuariosDtControls').empty()
                    .append($w.find('.dataTables_length').first())
                    .append($w.find('.dataTables_filter').first());
                var vista = $('#tablaUsuariosWrapper').attr('data-vista') || 'lista';
                $('#usuariosDtControls').toggle(vista === 'lista');
                $('#usuariosIconosControls').toggle(vista === 'iconos');
                try { guTable.columns.adjust(); } catch (e) {}
            },
        });

        $('#btnViewListaUsuarios').on('click', function () {
            $('#tablaUsuariosWrapper').attr('data-vista', 'lista');
            syncVistaUsuarios();
        });
        $('#btnViewIconosUsuarios').on('click', function () {
            $('#tablaUsuariosWrapper').attr('data-vista', 'iconos');
            syncVistaUsuarios();
        });

        if ($(window).width() < 768) {
            $('#tablaUsuariosWrapper').attr('data-vista', 'iconos');
        }

        $(window).on('resize orientationchange', function () {
            if (!guTable) return;
            try { guTable.columns.adjust(); } catch (e) {}
        });

        syncVistaUsuarios();
    });

})(jQuery);
</script>
GUJS;
?>
