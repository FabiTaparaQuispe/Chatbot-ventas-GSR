<?php
declare(strict_types=1);

$usuario = $_SESSION['usuario'] ?? '';
$currentPage = $currentPage ?? 'ventas';

?>
<aside class="app-sidebar-col" id="appSidebarCol">
    <div class="app-sidebar-card app-sidebar-card--ix2" id="appSidebarCard">
        <div class="app-sidebar-scroll" id="appSidebarScroll">
            <div class="app-sidebar-upper">
                <div class="app-sidebar-top">
                    <div class="app-sidebar-top-row">
                        <span class="app-sidebar-brand">
                            <span class="app-brand-icon" aria-hidden="true">🤖</span>
                            <span class="app-brand-text">Chatbot</span>
                        </span>
                        <div class="app-sidebar-actions">
                            <div class="app-sidebar-theme-pin">
                                <button type="button" id="appBtnTheme" class="app-theme-switch" onclick="appToggleTheme()" aria-label="Cambiar tema claro u oscuro" title="Tema">
                                    <span class="app-theme-thumb">
                                        <i class="fas fa-sun app-theme-sun" aria-hidden="true"></i>
                                        <i class="fas fa-moon app-theme-moon hidden" aria-hidden="true"></i>
                                    </span>
                                </button>
                                <button type="button" id="appBtnSidebarPin" class="app-icon-btn app-sidebar-pin-btn app-sidebar-action-hit" onclick="appToggleSidebarPin()" aria-pressed="false" aria-label="Fijar menú expandido" title="Fijar menú lateral">
                                    <i class="fas fa-lock-open app-sidebar-pin-icon" aria-hidden="true"></i>
                                </button>
                            </div>
                            <details class="app-user-wrap">
                                <summary class="app-icon-btn app-sidebar-action-hit" aria-label="Usuario">
                                    <i class="fas fa-user" aria-hidden="true"></i>
                                </summary>
                                <div class="app-user-menu">
                                    <div class="app-user-menu-header"><?= htmlspecialchars((string) $usuario, ENT_QUOTES, 'UTF-8') ?></div>
                                    <a href="logout.php" class="app-user-out">Salir</a>
                                </div>
                            </details>
                        </div>
                    </div>
                </div>
                <nav class="app-sidebar-nav" aria-label="Principal">
                    <a href="index.php?page=ventas" class="app-nav-link<?= $currentPage === 'ventas' ? ' app-nav-link-active' : '' ?>">
                        <i class="fas fa-table" aria-hidden="true"></i>
                        <span>Ventas general</span>
                    </a>
                    <a href="index.php?page=chatbot" class="app-nav-link<?= $currentPage === 'chatbot' ? ' app-nav-link-active' : '' ?>">
                        <i class="fas fa-comments" aria-hidden="true"></i>
                        <span>Chatbot</span>
                    </a>
                </nav>
            </div>
        </div>
    </div>
</aside>

