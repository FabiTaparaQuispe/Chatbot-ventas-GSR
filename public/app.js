const logEl = document.getElementById("log");
const form = document.getElementById("form");
const msgEl = document.getElementById("msg");
const sendBtn = document.getElementById("send");
const chipsMount = document.getElementById("chips");

const API_URL = new URL("api/chat", window.location.href).href;

const history = [];

function pad2(n) {
  return String(n).padStart(2, "0");
}

function toYmd(d) {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

/** Mes calendario anterior completo (ej. reportes cerrados). */
function defaultReportRange() {
  const now = new Date();
  const first = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  const last = new Date(now.getFullYear(), now.getMonth(), 0);
  return { desde: toYmd(first), hasta: toYmd(last) };
}

function faqChipsTemplates(desde, hasta) {
  const a1 = desde;
  const a2 = hasta;
  const y = new Date().getFullYear();
  const b1 = toYmd(new Date(y, 0, 1));
  const b2 = toYmd(new Date(y, 1, 0));
  const c1 = toYmd(new Date(y, 1, 1));
  const c2 = toYmd(new Date(y, 2, 0));
  return [
    {
      label: "Totales del período",
      text: `Del ${a1} al ${a2}: totales en tabla ventasgeneral (líneas de detalle, importe total en soles, unidades y peso). Usá la herramienta ventasgeneral_resumen con esas fechas y al final una sola línea reporte_url hacia ventasgeneral_resumen_tabla.php con los mismos parámetros.`,
    },
    {
      label: "Top clientes por importe",
      text: `Del ${a1} al ${a2}: top 10 clientes globales por importe total facturado (soles) en ventasgeneral. Usá ventasgeneral_top_clientes_globales y reporte_url ventas_top_clientes_global.php.`,
    },
    {
      label: "Top productos",
      text: `Del ${a1} al ${a2}: top 15 productos por importe total (soles). Usá ventasgeneral_top_productos y reporte_url ventas_top_productos.php.`,
    },
    {
      label: "Serie mensual",
      text: `Del ${a1} al ${a2}: serie mensual del importe total (soles). Usá ventasgeneral_serie_mensual_valor y reporte_url ventas_serie_mensual.php.`,
    },
    {
      label: "Mix por tipo de documento",
      text: `Del ${a1} al ${a2}: mix del importe total (soles) por tipo de documento (TDoc). Usá ventasgeneral_mix_tdoc y reporte_url ventas_mix_tdoc.php.`,
    },
    {
      label: "NC por zona de precio",
      text: `Del ${a1} al ${a2}: pareto de notas de crédito (TDoc 07) por DescripcionZonaPrecio. Usá ventasgeneral_pareto_nc_zonaprecio y reporte_url pareto_nc_zona.php.`,
    },
    {
      label: "Top clientes en zona TACNA",
      text: `Del ${a1} al ${a2}: top 10 clientes por importe total (soles) donde el prefijo de DescripcionZonaPrecio sea TACNA. Usá ventasgeneral_top_clientes_zona_precio con prefijo_descri_zona_precio TACNA y reporte_url pareto_clientes_zona.php.`,
    },
    {
      label: "Barras por precio",
      text: `Del ${a1} al ${a2}: barras del importe total (soles) con dimensión precio (no comercial). Usá ventasgeneral_barras_ventas_dimension y reporte_url ventas_barras_dimension.php.`,
    },
    {
      label: "Comparar 2 meses",
      text: `Comparativo: período A del ${b1} al ${b2} vs período B del ${c1} al ${c2}, dimensión precio, top 10. Usá ventasgeneral_comparativo_periodos y reporte_url ventas_comparativo.php con a_desde, a_hasta, b_desde, b_hasta.`,
    },
  ];
}

function appendBubble(role, text, isError = false) {
  const div = document.createElement("div");
  div.className = `bubble ${isError ? "error" : role}`;
  div.textContent = text;
  logEl.appendChild(div);
  logEl.scrollTop = logEl.scrollHeight;
}

if (chipsMount) {
  const { desde, hasta } = defaultReportRange();
  for (const { label, text } of faqChipsTemplates(desde, hasta)) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip";
    b.textContent = label;
    b.addEventListener("click", () => {
      msgEl.value = text;
      msgEl.focus();
    });
    chipsMount.appendChild(b);
  }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = msgEl.value.trim();
  if (!text) return;

  msgEl.value = "";
  history.push({ role: "user", content: text });
  appendBubble("user", text);

  sendBtn.disabled = true;
  try {
    const res = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: history }),
    });
    const data = await res.json().catch(() => ({}));

    if (!res.ok || data.ok === false) {
      const serverMsg = String(data.error || data.detail?.error?.message || '');
      const err = serverMsg.toLowerCase();
      const isRateLimit = res.status === 429 || err.includes('rate limit') || err.includes('rate_limit') || err.includes('too many requests') || err.includes('tokens per day') || err.includes('tpd') || err.includes('límite') || err.includes('limite');
      const friendly = isRateLimit
        ? (serverMsg && serverMsg.toLowerCase().startsWith('límite') ? serverMsg : 'Se alcanzó el límite de consultas. Intentá nuevamente en unos minutos.')
        : (serverMsg && serverMsg.length > 0 && serverMsg.length < 900 ? serverMsg : 'Hubo un inconveniente. Por favor intentá de nuevo.');
      appendBubble("assistant", friendly, true);
      history.pop();
      return;
    }

    const answer = data.reply || data.message || "(sin texto)";
    history.push({ role: "assistant", content: answer });
    appendBubble("assistant", answer);
  } catch (err) {
    appendBubble("assistant", "Un momento, estoy procesando... No pude conectarme. Verificá tu conexión e intentá de nuevo.", true);
    history.pop();
  } finally {
    sendBtn.disabled = false;
    msgEl.focus();
  }
});
