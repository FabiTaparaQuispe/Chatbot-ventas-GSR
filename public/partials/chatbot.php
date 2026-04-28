<?php
declare(strict_types=1);

$usuario = (string) ($_SESSION['usuario'] ?? '');
$nomCorto = '';
if ($usuario !== '') {
    $p = explode('@', $usuario, 2)[0];
    $p = str_replace(['.', '_', '-'], ' ', $p);
    $nomCorto = trim($p) !== '' ? (', ' . ucfirst(trim($p))) : '';
}
?>
<div class="chatbot-page" id="ventasChatPanel">
    <header class="chatbot-topbar">
        <a href="index.php?page=ventas" class="chatbot-back" aria-label="Volver a Ventas general" title="Volver">
            <i class="fas fa-arrow-left" aria-hidden="true"></i>
        </a>
        <span class="chatbot-topbar-title">Asistente de ventas</span>
        <div class="chatbot-topbar-actions">
            <button type="button" id="ventasChatClear" class="chatbot-icon-btn" title="Limpiar conversación" aria-label="Limpiar conversación">⌫</button>
        </div>
    </header>
    <div class="chatbot-body">
        <div class="chatbot-center">
            <div id="chatbotHero" class="chatbot-hero">
                <p class="chatbot-greet">Hola<?= htmlspecialchars($nomCorto, ENT_QUOTES, 'UTF-8') ?></p>
                <h1 class="chatbot-hero-title">¿Por dónde empezamos?</h1>
            </div>
            <div id="ventasChatLog" class="chatbot-log" aria-live="polite"></div>
        </div>
    </div>
    <div class="chatbot-surface">
        <details class="ventas-chat-shortcuts chatbot-shortcuts">
            <summary>Atajos y palabras clave</summary>
            <ul>
                <li><strong>Fechas</strong>: dos fechas en formato YYYY-MM-DD o un mes claro; si faltan, el asistente debe pedirlas antes de consultar.</li>
                <li><strong>Zona / mercado</strong>: prefijos (AQP, TACNA, MOQUEGUA…) sobre DescriZonaPrecio; no hay campo ciudad.</li>
                <li><strong>Nota de crédito</strong> (comprobante tipo 07): rankings de NC solo si lo pides en la consulta.</li>
            </ul>
        </details>
        <div class="ventas-chat-chips-wrap chatbot-faq-wrap">
            <label for="ventasChatFaqSelect" class="ventas-chat-faq-label">Preguntas frecuentes</label>
            <select id="ventasChatFaqSelect" class="ventas-chat-faq-select" aria-label="Seleccionar pregunta frecuente"></select>
        </div>
        <div class="chatbot-composer">
            <textarea id="ventasChatInput" rows="1" placeholder="Escribe tu pregunta sobre ventas, fechas, clientes, productos…"></textarea>
            <div class="chatbot-composer-row">
                <button type="button" id="ventasChatSend" class="btn btn-primary chatbot-send">Enviar</button>
            </div>
        </div>
        <p id="ventasChatError" class="ventas-chat-err" hidden></p>
    </div>
</div>
<script>window.VENTAS_CHAT_FULL = true;</script>
<?php
require_once __DIR__ . '/../modules/ventas_chat_config.inc.php';
require_once __DIR__ . '/../modules/chat_assistant_script.inc.php';
