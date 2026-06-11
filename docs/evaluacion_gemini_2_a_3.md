# Evaluación interna: migración de Gemini 2.x a Gemini 3.x

**Autora:** Fabiola Tapara
**Fecha:** Junio 2026
**Estado:** Evaluación para decisión

---

## 1. Contexto

Actualmente el chatbot usa el modelo **Gemini 2.5 Flash**. Google ya liberó la generación
**3.x** (por ejemplo Gemini 3.1 Flash-Lite, Gemini 3.5 Flash, Gemini 3.1 Pro), que está
disponible en nuestra consola de Google AI Studio. Esta evaluación analiza si conviene
migrar.

Aclaración importante: esto es un cambio de **generación de modelo** (la "inteligencia"),
distinto del **nivel de facturación** (Nivel 1/2/3), que solo afecta los límites de uso.

---

## 2. Qué mejora al cambiar de generación

Las generaciones nuevas suelen traer mejoras en tres frentes, aunque con matices:

- **Mejor entendimiento:** razonan mejor las preguntas complejas o ambiguas. Este es el
  punto más relevante para nosotros, porque las pocas fallas actuales se dan justamente en
  preguntas poco específicas.
- **A veces más velocidad:** las generaciones nuevas suelen optimizar el tiempo de respuesta.
- **A veces mejor costo-rendimiento:** mejor relación entre lo que cuesta y lo que entrega.

---

## 3. Consideraciones y riesgos

- Las mejoras **no están garantizadas** para nuestro caso puntual: hay que **medirlas con
  nuestros propios datos**, no asumirlas.
- Cada modelo nuevo puede **comportarse distinto** (formato de las respuestas, manejo de las
  herramientas/consultas). Hay que verificar que las consultas de ventas sigan funcionando
  igual o mejor.
- Conviene revisar los **límites de frecuencia y el costo** del modelo específico, porque
  varían entre modelos.
- Los modelos marcados como **"vista previa / preview"** pueden tener límites más estrictos o
  cambiar sin aviso; para producción es preferible una versión estable.

---

## 4. Cómo probarlo (riesgo bajo y reversible)

La migración es sencilla y **100% reversible**:

1. Cambiar **una sola línea** en el archivo de configuración (`.env`):
   `GEMINI_MODEL=gemini-3.x-flash` (el identificador exacto según la consola).
2. Reiniciar el servicio.
3. Correr la **batería automatizada de 58 preguntas** y comparar resultados.
4. Si no mejora, se vuelve a `gemini-2.5-flash` cambiando esa misma línea.

---

## 5. Qué comparar en la prueba

Con la misma batería de preguntas, medir Gemini 2.5 Flash vs el modelo 3.x en:

| Criterio | Cómo se mide |
|---|---|
| **Efectividad** | % de respuestas correctas (sobre todo en preguntas ambiguas) |
| **Velocidad** | Tiempo promedio de respuesta |
| **Costo** | Gasto por la misma cantidad de consultas |
| **Estabilidad** | Que el formato de respuestas y las consultas no se rompan |

---

## 6. Criterios de decisión

**Migrar si:** sube la efectividad (especialmente en preguntas ambiguas), mantiene o mejora
la velocidad, y el costo es similar o menor.

**No migrar (por ahora) si:** no mejora la efectividad, empeora la velocidad o el costo, o
altera el formato de las respuestas.

---

## 7. Recomendación

Hacer una **prueba controlada** con un modelo **Flash de la generación 3** (el equilibrio
velocidad/costo, equivalente al que usamos hoy), compararlo contra Gemini 2.5 Flash con la
misma batería de preguntas, y **decidir con datos reales**, no por la descripción del
proveedor. La prueba es de bajo riesgo, rápida y reversible, así que se puede hacer sin
comprometer el servicio actual.
