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
            <summary>Consejos para tu consulta</summary>
            <ul>
                <li><strong>Fechas</strong>: indica desde qué día y hasta qué día te interesa (por ejemplo <em>1 de marzo al 31 de marzo de 2026</em>, o también <em>2026-03-01</em> y <em>2026-03-31</em>). Si falta eso, el asistente te lo preguntará antes de sacar números.</li>
                <li><strong>Zona o mercado</strong>: si quieres acotar por región, usa el mismo nombre corto que suele aparecer en tus listas o facturas (como AQP, TACNA o MOQUEGUA). No filtramos por “ciudad” aparte; va por esa zona comercial.</li>
                <li><strong>Notas de crédito o devoluciones</strong>: solo las ponemos en primer plano en rankings especiales si lo pides explícitamente en tu mensaje.</li>
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
