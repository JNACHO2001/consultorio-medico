# Guion del video – Unidad 2: «Tejiendo redes: arquitectura de software entre hilos y nodos»

**Duración objetivo:** 12 a 15 minutos · **Publicación:** YouTube, modo *no listado* · **Enlace:** pegar en la portada y en el Anexo B del informe.
Cada integrante habla en al menos una parte (el rol sugerido está entre paréntesis; ajústenlo al equipo).

| Tiempo | Parte | Qué se muestra | Qué se dice |
|---|---|---|---|
| 0:00–1:00 | **1. Presentación** (Líder) | Portada del informe | Nombres, curso, proyecto «Salud Integral» y el reto: distribuir una parte del sistema de la Unidad 1. |
| 1:00–2:30 | **2. Problema y alcance** (Líder) | Sección 1–2 del informe | Por qué solo la facturación electrónica: es la única dependencia remota (proveedor tecnológico) y la que más sufre latencia, fallos y concurrencia. Supuestos: nodos simulados, 40 ms de latencia. |
| 2:30–5:00 | **3. Arquitectura y UML** (Diseñador) | Figuras 1, 2 y 3 (componentes, secuencia, despliegue) | Recorrer el flujo: API → `ProveedorProxy` → `MediadorNodos` → `ClienteNodo` → nodos. Mostrar el *alt* de la secuencia (nodo caído → reintento en otro nodo). Despliegue: procesos independientes por TCP. |
| 5:00–7:00 | **4. Patrones** (Diseñador) | Tabla 7 y sección 5 | Proxy, Mediator, Observer, Circuit Breaker + Retry con *backoff* y *jitter*, Idempotent Receiver, pool de hilos con contrapresión; y por qué cada uno resuelve un problema concreto. |
| 7:00–9:30 | **5. Demostración del prototipo** (Desarrollador) | Terminal y navegador | 1) `python -m app.distribuido.cluster --nodos 3`. 2) Arrancar la API con `NODOS_PROVEEDOR=...`. 3) Emitir facturas; mostrar `GET /api/electronica/nodos` (carga por nodo). 4) **Matar un nodo** (SIGKILL) y mostrar que las facturas siguen aceptándose, el circuito pasa a ABIERTO y luego se recupera. 5) Sin nodos: el documento queda RECHAZADO `NODOS-01` y se reenvía con «Reintentar». |
| 9:30–10:30 | **6. Pruebas automáticas** (Evaluador) | `pytest` en terminal | 181 pruebas pasan (155 previas + 26 nuevas); mencionar idempotencia, contrapresión y fuga de hilos. |
| 10:30–13:00 | **7. Evaluación de desempeño** (Evaluador) | Figuras 4–8 y Tabla 12–17 | Escalabilidad horizontal (98,8 → 392,6 docs/s con 4 nodos, 99,2 % de eficiencia); vertical (hilos por nodo, ley de Little, tope por CPU/GIL); saturación y contrapresión (cola 1: 43,5 % de éxito; cola 32: 100 %); robustez (caída de 1 de 3 nodos: 100 % de éxito, detección 0,01 s, recuperación 0,96 s). |
| 13:00–14:00 | **8. Hallazgo y ajuste** (Desarrollador) | Figura 8 y Tabla 16 | El candado del servicio anulaba la escalabilidad (22,4 → 22,9 facturas/s); se separó *reservar* (con candado) de *transmitir* (sin candado) y subió a 271,7 facturas/s (11,9×). Siguiente cuello de botella: CPU/GIL de la API. |
| 14:00–15:00 | **9. Conclusiones** (todos) | Sección 8 | Lecciones: medir antes de afirmar, idempotencia para poder reintentar, degradar con elegancia. Trabajo futuro y cierre. |

## Lista de verificación antes de grabar
- [ ] Ejecutar `pytest` una vez antes para tener la salida fresca (23 s aprox.).
- [ ] Tener tres terminales listas: clúster, API y comandos de prueba (`curl`/Swagger en `/docs`).
- [ ] Probar el *kill* del nodo ensayando el comando con el PID real (`kill -9 <pid>`).
- [ ] Grabar a 1080p con micrófono claro; cada integrante debe aparecer o hablar.
- [ ] Subir a YouTube como **no listado** y copiar el enlace en la portada y en el Anexo B (regenerar con `docs/informe/generador/generar.sh`).
