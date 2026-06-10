# Propuesta: Caché de resultados con Redis para el chatbot de ventas

**Autora:** Fabiola Tapara
**Fecha:** Junio 2026
**Estado:** Propuesta para evaluación

---

## 1. Resumen ejecutivo

Se propone incorporar una **caché de resultados en memoria (Redis)** al chatbot de
ventas. La idea es guardar en RAM el resultado de una consulta o cálculo la primera vez
que se realiza, de modo que cuando un usuario vuelva a hacer la misma pregunta, la
respuesta se entregue **al instante**, sin volver a procesarla ni a consultar la base de
datos ni a llamar a la IA.

Beneficio principal: **respuestas más rápidas, menor costo de la API de Gemini y menos
errores de saturación (503)**.

---

## 2. Problema / motivación

Hoy, cada vez que un usuario hace una pregunta:

1. Se llama a la **API de Gemini** (tiene costo, demora, y a veces devuelve error 503 por
   saturación de los servidores de Google).
2. Se ejecuta una **consulta a la base de datos** (recorre los registros para calcular).

Si dos usuarios hacen **la misma pregunta** —o el mismo usuario la repite— todo ese
trabajo se vuelve a hacer **desde cero**, aunque el resultado sea idéntico. Eso es tiempo,
costo y carga innecesarios.

Esto es especialmente notorio en las **proyecciones**, que son cálculos repetitivos y que
varios usuarios de la empresa consultan con los mismos parámetros.

---

## 3. Solución propuesta

Agregar una capa de **caché con Redis** (almacén de datos en memoria RAM, muy rápido).
Aplica en dos niveles:

### Nivel 1 — Caché de respuestas del chatbot (mayor impacto)
Cuando un usuario hace una pregunta, se guarda la respuesta asociada a esa pregunta. Si
cualquier usuario vuelve a hacer **la misma pregunta**, se devuelve la respuesta guardada
**sin llamar a Gemini**.

- Ahorra **costo** de la API de Gemini.
- Ahorra **tiempo** (respuesta inmediata).
- **Reduce los errores 503**, porque se hacen menos llamadas a Google.

### Nivel 2 — Caché de cálculos (proyecciones, resúmenes)
Cuando se calcula una proyección, el resultado se guarda con una **clave** que identifica
los parámetros (línea, cliente, producto, provincia, rango de fechas). Si otro usuario pide
la **misma proyección**, se entrega la guardada sin recalcular.

- Ahorra **carga a la base de datos**.
- Respuesta inmediata para consultas repetidas.

---

## 4. Cómo funciona (flujo)

```
Usuario hace una pregunta
        |
        v
¿Está en la caché (Redis)?  --- SÍ --->  Devolver resultado guardado (instantáneo)
        |
        NO
        |
        v
Procesar normal (Gemini + base de datos)
        |
        v
Guardar el resultado en la caché (con tiempo de expiración)
        |
        v
Devolver al usuario
```

Como los datos del chatbot son de **una sola empresa** (no por usuario), la caché es
**compartida**: lo que calcula un usuario sirve para todos. Esto la hace más simple y más
eficiente que en aplicaciones multiempresa.

---

## 5. Beneficios

| Beneficio | Detalle |
|---|---|
| **Velocidad** | Consultas repetidas se responden al instante (desde RAM). |
| **Menor costo** | Menos llamadas a la API de Gemini (que se paga por uso). |
| **Menos saturación (503)** | Al hacer menos llamadas a Google, baja la probabilidad de error. |
| **Menos carga a la base de datos** | No se recalcula lo ya calculado. |
| **Escalabilidad** | Soporta más usuarios sin multiplicar el procesamiento. |

---

## 6. Caso de uso: proyecciones

Ejemplo concreto en nuestro contexto:

- Un usuario pide *"proyección de Pollo Vivo a los próximos 6 meses"*.
- El sistema calcula la proyección y **guarda el resultado** en Redis con la clave de esos
  parámetros.
- Otro usuario de la empresa pide **la misma proyección** → la recibe **al instante**, ya
  calculada.
- Si un usuario pide una proyección **distinta** (otro producto, otro rango) → se calcula y
  se guarda esa nueva, quedando disponible para los demás.

---

## 7. Reto principal: invalidación de la caché

El punto más delicado es decidir **cuándo se borra/actualiza** el valor guardado. Si entran
ventas nuevas a la base de datos, una proyección guardada queda **desactualizada**.

Reglas posibles (a definir):

- **Por tiempo (TTL):** el valor expira automáticamente, por ejemplo cada noche o cada
  cierto número de horas.
- **Por evento:** la caché se limpia cuando se carga data nueva a la base.

Se recomienda empezar con expiración por tiempo, que es lo más simple y seguro.

---

## 8. Alcance y esfuerzo estimado

- **Infraestructura:** instalar y configurar un servidor Redis en el servidor actual.
- **Desarrollo:** agregar la capa de caché en el flujo del chatbot (consultar antes de
  procesar, guardar después).
- **Implementación sugerida por etapas:**
  1. Empezar con el **Nivel 1** (cachear respuestas idénticas del chatbot) — mayor impacto,
     menor complejidad.
  2. Luego el **Nivel 2** (cachear cálculos de proyecciones).
  3. Definir y afinar las reglas de **invalidación**.

---

## 9. Cuándo implementarlo (recomendación de timing)

- **Hoy no es urgente:** con el volumen actual (~3 millones de registros, consultas rápidas
  gracias a los índices) y el bajo costo actual de Gemini, el sistema responde bien.
- **Cobra sentido cuando:**
  - Crezca el número de usuarios o de consultas.
  - Los errores de saturación (503) se vuelvan frecuentes.
  - El costo de la API de Gemini empiece a subir.

Es una mejora pensada para **escalar y dar estabilidad** a futuro, no un parche urgente.

---

## 10. Conclusión

La caché con Redis es un patrón estándar y probado que permite **responder más rápido,
gastar menos en la API de IA y reducir la saturación**, reutilizando cálculos ya hechos en
lugar de repetirlos. Es especialmente útil para las **proyecciones**, que son consultas
repetitivas y compartidas por varios usuarios. Se propone implementarla **por etapas** y en
el momento en que el crecimiento del uso lo justifique.
