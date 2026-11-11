// Secciones 7 a 9 (evaluación, conclusiones, referencias) y anexos. Todas las cifras salen del JSON de resultados.
const fs = require("fs");
const path = require("path");
const { P, H1, H2, viñetas, tabla, figura, AlignmentType, runs, FUENTE, NEGRO } = require("./lib");
const { Paragraph } = require("docx");

const IMG = path.resolve(__dirname, "../img");
const R = JSON.parse(fs.readFileSync(path.resolve(__dirname, "../../../backend/benchmarks/resultados/resultados_distribuido.json"), "utf-8"));
const C = AlignmentType.CENTER;
const D = AlignmentType.RIGHT;

const n0 = (x) => String(Math.round(x));
const n1 = (x) => (Math.round(x * 10) / 10).toFixed(1).replace(".", ",");
const n2 = (x) => (Math.round(x * 100) / 100).toFixed(2).replace(".", ",");

module.exports = function seccionB({ nPruebas, nPruebasNuevas, duracionPruebas }) {
  const out = [];
  const add = (...bloques) => bloques.flat().forEach((b) => out.push(b));

  const e1 = R.e1_horizontal.filas;
  const e2 = R.e2_vertical.filas;
  const e3c = R.e3_saturacion.cola_corta;
  const e3a = R.e3_saturacion.cola_ajustada;
  const e4 = R.e4_robustez;
  const a5 = R.e5_servicio_antes.filas;
  const d5 = R.e5_servicio_despues.filas;
  const s5 = R.e5_servicio_sin_latencia.filas;
  const util3c = (e3c.docs_por_s_media * e3c.tasa_exito_pct) / 100;

  // =====================================================================================  7
  add(H1("7. Evaluación del desempeño y ajustes"));
  add(H2("7.1 Metodología"));
  add(
    P(`Las mediciones se hicieron el ${R.entorno.fecha.slice(0, 10)} en una máquina Linux de ${R.entorno.nucleos} núcleos y 8 GB de memoria con Python ${R.entorno.python}. Cada nodo es un proceso independiente; el generador de carga son hilos dentro del proceso de la API, que llaman al proxy como lo haría el servicio. Cada documento espera ${R.entorno.latencia_simulada_ms} ms (±25 %) en el nodo para representar la firma y la transmisión. Antes de medir se hace un calentamiento que abre las conexiones del pool, y los experimentos e1 a e3 se repiten 3 veces. Las latencias se miden en el cliente e incluyen los reintentos.`),
    tabla(
      "Experimentos realizados",
      ["Id", "Pregunta", "Configuración", "Carga"],
      [
        ["e1", "¿Escala al agregar nodos?", "1, 2 y 4 nodos con 4 hilos y cola de 64", "600 documentos, 64 clientes"],
        ["e2", "¿Escala al agregar hilos?", "1 nodo con 1, 2, 4, 8 y 16 hilos", "400 documentos, 64 clientes"],
        ["e3", "¿Qué pasa al saturar y cómo influye la cola?", "2 nodos de 2 hilos; cola de 1 frente a cola de 32", "500 documentos, 64 clientes"],
        ["e4", "¿Tolera la caída de un nodo?", "3 nodos; SIGKILL a nodo-2 a los 5 s y regreso a los 11 s", "18 s continuos, 12 clientes"],
        ["e5", "¿El servicio completo aprovecha los nodos?", "Servicio real, 1 y 4 nodos, código antes y después del ajuste", "95 facturas, 16 clientes"],
      ],
      [600, 2760, 3600, 2400]
    )
  );

  // ---- e1
  add(H2("7.2 Escalabilidad horizontal (e1)"));
  add(
    tabla(
      "Escalabilidad horizontal: nodos de 4 hilos cada uno",
      ["Nodos", "Documentos/s (media ± desv.)", "Aceleración", "Eficiencia", "p50 (ms)", "p95 (ms)", "p99 (ms)", "Éxito"],
      e1.map((f) => [n0(f.nodos), `${n1(f.docs_por_s_media)} ± ${n1(f.docs_por_s_desv)}`, `${n2(f.aceleracion)}×`, `${n1(f.eficiencia_pct)} %`, n0(f.p50_ms), n0(f.p95_ms), n0(f.p99_ms), `${n0(f.tasa_exito_pct)} %`]),
      [800, 1900, 1300, 1100, 900, 900, 900, 1560],
      { alinear: [C, C, C, C, D, D, D, C], nota: "Tres repeticiones por configuración. Eficiencia = aceleración dividida por el número de nodos." }
    ),
    figura("Documentos por segundo según el número de nodos", path.join(IMG, "g1_horizontal.png"), 430, "Barras: medición; línea punteada: escalado lineal ideal. Entre paréntesis, la eficiencia."),
    P(`El sistema escala de forma casi lineal: con 4 nodos se alcanzan ${n1(e1[2].docs_por_s_media)} documentos por segundo, ${n2(e1[2].aceleracion)} veces lo de un nodo (${n1(e1[2].eficiencia_pct)} % de eficiencia), por encima de la meta del 90 %. La predicción de la ley de Little era de unos 100 documentos por segundo por nodo (4 hilos entre 40 ms) y se midieron ${n1(e1[0].docs_por_s_media)}. La latencia p95 baja de ${n0(e1[0].p95_ms)} a ${n0(e1[2].p95_ms)} ms porque los 64 clientes esperan menos en la cola: en un sistema cerrado, la latencia es aproximadamente el número de clientes entre el rendimiento (64 / ${n1(e1[0].docs_por_s_media)} ≈ ${n0((64 / e1[0].docs_por_s_media) * 1000)} ms).`),
    P("**Alcance de la conclusión.** La parte secuencial del trabajo (elegir nodo y serializar) es mínima frente a los 40 ms de espera, así que la ley de Amdahl (Amdahl, 1967) apenas limita el escalado. Con un trabajo que consumiera CPU en la API, esa fracción serial pesaría mucho más, como muestra la sección 7.6."),
  );

  // ---- e2
  add(H2("7.3 Escalabilidad vertical: hilos por nodo (e2)"));
  add(
    tabla(
      "Escalabilidad vertical: un nodo con distinto número de hilos",
      ["Hilos", "Documentos/s medido", "Teórico (hilos / 40 ms)", "Cumplimiento", "p50 (ms)", "p95 (ms)"],
      e2.map((f) => [n0(f.hilos_por_nodo), n1(f.docs_por_s_media), n1(f.capacidad_teorica), `${n1((100 * f.docs_por_s_media) / f.capacidad_teorica)} %`, n0(f.p50_ms), n0(f.p95_ms)]),
      [900, 1900, 2260, 1500, 1400, 1400],
      { alinear: [C, D, D, C, D, D] }
    ),
    figura("Documentos por segundo según los hilos de un nodo", path.join(IMG, "g2_vertical.png"), 430, "Línea punteada: capacidad teórica h / W con W = 40 ms."),
    P(`El rendimiento de un solo nodo sigue la ley de Little casi exactamente (entre ${n0((100 * e2[0].docs_por_s_media) / e2[0].capacidad_teorica)} % y ${n0((100 * e2[4].docs_por_s_media) / e2[4].capacidad_teorica)} % de lo teórico) hasta 16 hilos. Es lo esperado para un trabajo que casi no usa CPU: los hilos pasan su tiempo esperando y el GIL no estorba. Para un trabajo que sí calculara (por ejemplo, firmar con XAdES), más hilos dejarían de ayudar al saturar un núcleo y habría que agregar nodos, que son procesos y no comparten el GIL. Esa es la razón de combinar ambos niveles de concurrencia.`),
  );

  // ---- e3
  add(H2("7.4 Saturación y contrapresión (e3)"));
  add(
    tabla(
      "Efecto del tamaño de la cola de admisión (2 nodos de 2 hilos, 64 clientes)",
      ["Configuración", "Éxito", "Docs/s totales", "Docs/s aceptados", "p95 (ms)", "Reintentos", "Intentos fallidos"],
      [
        ["Cola corta (cola = 1)", `${n1(e3c.tasa_exito_pct)} %`, n1(e3c.docs_por_s_media), n1(util3c), n0(e3c.p95_ms), n0(e3c.reintentos), `${n0(e3c.intentos_fallidos.saturado || 0)} OCUPADO, ${n0(e3c.intentos_fallidos.sin_nodos || 0)} sin nodos`],
        ["Cola ajustada (cola = 32)", `${n1(e3a.tasa_exito_pct)} %`, n1(e3a.docs_por_s_media), n1(e3a.docs_por_s_media), n0(e3a.p95_ms), n0(e3a.reintentos), "ninguno"],
      ],
      [2000, 900, 1100, 1300, 1000, 1260, 1800],
      { alinear: [AlignmentType.LEFT, C, D, D, D, D, AlignmentType.LEFT], nota: "Los reintentos y los intentos fallidos suman las tres repeticiones. «Docs/s aceptados» = documentos por segundo × tasa de éxito." }
    ),
    figura("Éxito, latencia p95 y reintentos según la cola de admisión", path.join(IMG, "g3_saturacion.png"), 560),
    P(`La capacidad de los dos nodos es de unos 100 documentos por segundo y la carga de 64 clientes la supera de lejos. Con la cola corta, los nodos se protegen respondiendo OCUPADO: el proxy reintenta en el otro nodo, pero tras 4 intentos fallidos entrega un rechazo NODOS-01 y solo el ${n1(e3c.tasa_exito_pct)} % de los documentos se acepta a la primera. Los documentos aceptados por segundo (${n1(util3c)}) son, sin embargo, casi los mismos que con la cola ajustada (${n1(e3a.docs_por_s_media)}): **la capacidad real no cambia; cambia qué se hace con el exceso**. La latencia p95 de la cola corta (${n0(e3c.p95_ms)} ms) parece mejor, pero es engañosa porque incluye los envíos que fallan rápido.`),
    P(`Con la cola de 32, el exceso espera en la cola del nodo: el éxito sube al ${n0(e3a.tasa_exito_pct)} % sin un solo reintento y la latencia sube a unos ${n0(e3a.p95_ms)} ms (≈ 64 clientes / ${n0(e3a.docs_por_s_media)} documentos por segundo). Es un compromiso de diseño legítimo: la cola corta protege la latencia y delega el exceso al «Reintentar» de la aplicación (los documentos quedan RECHAZADOS, no se pierden); la cola larga absorbe ráfagas a costa de latencia. El valor por defecto (cola de 16) y la recomendación de dimensionarla según la ráfaga esperada salen de este experimento.`),
  );

  // ---- e4
  add(H2("7.5 Robustez ante la caída de un nodo (e4)"));
  add(
    tabla(
      "Caída y recuperación de un nodo (3 nodos de 4 hilos, 12 clientes)",
      ["Indicador", "Valor"],
      [
        ["Documentos enviados en 18 s", `${n0(e4.global.documentos)}`],
        ["Documentos aceptados (tasa de éxito)", `${n0(e4.global.aceptados)} (${n1(e4.global.tasa_exito_pct)} %)`],
        ["Reintentos totales (todos por conexión rechazada)", n0(e4.reintentos)],
        ["Detección: caída del nodo → circuito ABIERTO", `${n2(e4.deteccion_s)} s`],
        ["Recuperación: nodo de regreso → circuito CERRADO", `${n2(e4.recuperacion_s)} s`],
        ["Rendimiento antes de la caída", `${n1(e4.docs_por_s_antes)} docs/s`],
        ["Rendimiento con el nodo caído", `${n1(e4.docs_por_s_con_caida)} docs/s (${n0((100 * e4.docs_por_s_con_caida) / e4.docs_por_s_antes)} % del normal)`],
        ["Rendimiento tras la recuperación", `${n1(e4.docs_por_s_despues)} docs/s`],
        ["Latencia p95 por segundo, antes → con la caída", `${n0(e4.serie[1].p95_ms)} → ${n0(e4.serie[7].p95_ms)} ms`],
        ["Latencia máxima de cualquier documento", `${n0(e4.global.max_ms)} ms`],
      ],
      [5760, 3600]
    ),
    figura("Rendimiento y latencia p95 por segundo durante la caída de nodo-2", path.join(IMG, "g4_robustez.png"), 540, "La franja roja marca el intervalo en que nodo-2 estuvo caído (SIGKILL a los 5 s; reinicio a los 11 s)."),
    P(`Ningún documento se perdió ni quedó sin respuesta (${n1(e4.global.tasa_exito_pct)} % de éxito). El circuito del nodo caído se abrió ${n2(e4.deteccion_s)} s después de la caída y solo hicieron falta ${n0(e4.reintentos)} reintentos, porque tras abrirse el circuito el mediador deja de enviarle tráfico. Con un nodo de tres fuera, el rendimiento cae al ${n0((100 * e4.docs_por_s_con_caida) / e4.docs_por_s_antes)} % del normal, proporcional a la capacidad perdida (2/3), y la latencia p95 sube de unos ${n0(e4.serie[1].p95_ms)} a unos ${n0(e4.serie[7].p95_ms)} ms: **degradación proporcional y no un colapso**. Mientras el nodo está caído, su circuito pasa a SEMIABIERTO una vez por segundo y vuelve a abrirse; cuesta una sola solicitud de prueba por segundo. Cuando el nodo regresa, el circuito se cierra ${n2(e4.recuperacion_s)} s después (aproximadamente el enfriamiento de 1 s configurado para esta prueba) y el rendimiento vuelve al nivel anterior sin reiniciar la API.`),
    P("Este resultado cumple la meta del 100 % de éxito con la caída de 1 de 3 nodos y la recuperación automática. Conviene recordar el límite del experimento: se probó la caída por parada (SIGKILL), no la partición de red ni un nodo que responde mal pero no cae."),
  );

  // ---- e5
  add(H2("7.6 Servicio completo y el ajuste del candado (e5)"));
  add(
    P("Los experimentos anteriores miden el proxy y los nodos. El experimento e5 mide el sistema completo: 16 clientes llaman a `FacturacionElectronicaService.emitir` sobre facturas distintas, como lo harían varios cajeros a la vez. La primera medición, con el código tal como estaba, reveló un problema que las anteriores no mostraban."),
    tabla(
      "Emisiones simultáneas por el servicio completo: antes y después del ajuste",
      ["Nodos", "Antes (facturas/s)", "Antes p50 (ms)", "Después (facturas/s)", "Después p50 (ms)", "Mejora"],
      a5.map((f, i) => [n0(f.nodos), n1(f.docs_por_s), n0(f.p50_ms), n1(d5[i].docs_por_s), n0(d5[i].p50_ms), `${n1(d5[i].docs_por_s / f.docs_por_s)}×`]),
      [900, 1800, 1600, 1900, 1760, 1400],
      { alinear: [C, D, D, D, D, C], nota: "En todas las mediciones el éxito fue del 100 % y los consecutivos quedaron sin repetir." }
    ),
    figura("Facturas por segundo antes y después de separar la reserva del envío", path.join(IMG, "g5_servicio.png"), 430),
    P(`**Cuello de botella.** Con 1 y con 4 nodos el servicio entregaba lo mismo (${n1(a5[0].docs_por_s)} y ${n1(a5[1].docs_por_s)} facturas por segundo): agregar nodos no servía de nada. La causa estaba en el servicio: `+"`emitir`"+` tomaba un candado para numerar el documento y lo mantenía mientras esperaba la respuesta del proveedor, así que todas las emisiones se hacían una tras otra (cada una tardaba cerca de 44 ms, y el p50 de ${n0(a5[0].p50_ms)} ms es la espera en fila de 16 clientes). Era un cuello de botella de **diseño** que ninguna cantidad de nodos podía arreglar.`),
    P(`**Ajuste.** Se separó la emisión en dos pasos. *Reservar* (con candado): validar, numerar, calcular el CUFE y el XML y guardar el documento en estado GENERADO. *Transmitir* (sin candado): enviar al proveedor y guardar su respuesta. El documento reservado impide que otra emisión de la misma factura se cuele y el consecutivo ya no puede repetirse. Si el proveedor lanza una excepción, el documento pasa a RECHAZADO (ERR-PROVEEDOR) para no quedar «en curso» eternamente. Las ${nPruebas - nPruebasNuevas} pruebas previas y las nuevas siguen pasando.`),
    P(`**Resultado.** Con 1 nodo se pasa de ${n1(a5[0].docs_por_s)} a ${n1(d5[0].docs_por_s)} facturas por segundo (${n1(d5[0].docs_por_s / a5[0].docs_por_s)}×, casi la capacidad de 100 que predice la ley de Little para 4 hilos) y con 4 nodos de ${n1(a5[1].docs_por_s)} a ${n1(d5[1].docs_por_s)} (${n1(d5[1].docs_por_s / a5[1].docs_por_s)}×); la latencia mediana cae de ${n0(a5[1].p50_ms)} a ${n0(d5[1].p50_ms)} ms.`),
    P(`**Nuevo límite.** Con 4 nodos se llegan a ${n1(d5[1].docs_por_s)} facturas por segundo, por debajo de los ${n0(e1[2].docs_por_s_media)} que admiten los nodos. Para ubicar el siguiente cuello se repitió la medición con latencia simulada cero, es decir, sin esperar a ningún nodo: la API sola procesó entre ${n0(s5[1].docs_por_s)} y ${n0(s5[0].docs_por_s)} facturas por segundo. El techo es ahora el **trabajo de CPU del propio proceso de la API** (generar el XML, calcular el CUFE SHA-384 y copiar objetos en los repositorios en memoria), que además comparte el GIL con los hilos de las peticiones. Es una medición de orden de magnitud (95 facturas por corrida), no un valor preciso.`),
  );

  // ---- cuellos de botella
  add(H2("7.7 Cuellos de botella y ajustes"));
  add(
    tabla(
      "Resumen de cuellos de botella, evidencia y ajustes",
      ["Cuello de botella", "Evidencia", "Ajuste", "Efecto"],
      [
        ["Candado del servicio retenido durante el envío", `e5: ${n1(a5[0].docs_por_s)} y ${n1(a5[1].docs_por_s)} facturas/s con 1 y 4 nodos`, "Separar reservar (con candado) de transmitir (sin candado)", `${n1(d5[1].docs_por_s / a5[1].docs_por_s)}× con 4 nodos; consecutivos sin repetir`],
        ["Cola de admisión demasiado corta frente a ráfagas", `e3: éxito ${n1(e3c.tasa_exito_pct)} % con cola de 1`, "Cola dimensionada según la ráfaga (32 en la prueba; 16 por defecto)", `Éxito ${n0(e3a.tasa_exito_pct)} %, a cambio de latencia p95 de ${n0(e3a.p95_ms)} ms`],
        ["Reintentos sobre un nodo caído", `e4: ${n0(e4.reintentos)} reintentos en ${n0(e4.global.documentos)} documentos`, "Circuit breaker: el nodo caído deja de recibir tráfico", `Detección en ${n2(e4.deteccion_s)} s; éxito ${n0(e4.global.tasa_exito_pct)} %`],
        ["CPU y GIL del proceso de la API (nuevo techo)", `e5 sin latencia: ${n0(s5[1].docs_por_s)} a ${n0(s5[0].docs_por_s)} facturas/s`, "Pendiente: más procesos de API con base de datos real, o mover la generación del XML a workers", "No aplicado (trabajo futuro)"],
      ],
      [2300, 2400, 2660, 2000]
    )
  );

  // ---- pruebas automáticas
  add(H2("7.8 Resultado de las pruebas automáticas"));
  add(
    P(`Al cierre del trabajo, la suite completa pasa: **${nPruebas} pruebas** (155 de la Unidad 1 y ${nPruebasNuevas} del módulo distribuido) en ${duracionPruebas}. Las pruebas del módulo se ejecutan por TCP real, incluyen la caída y recuperación de nodos, y verifican propiedades que las mediciones solo muestran de forma indirecta (idempotencia, contrapresión, ausencia de fuga de hilos).`),
  );

  // ---- límites
  add(H2("7.9 Límites y amenazas a la validez"));
  add(
    ...viñetas([
      "**Proveedor simulado.** La latencia es una espera fija con variación; el proveedor real tendría colas, errores y latencias de cola larga. Por eso se reportan p95 y p99, que dominan la experiencia en sistemas distribuidos (Dean y Barroso, 2013).",
      "**Red local.** Los nodos hablan por el bucle local: no hay pérdida de paquetes, retardo real ni particiones. Se probó la caída de un proceso, no de la red.",
      `**Máquina pequeña y compartida.** Los ${R.entorno.nucleos} núcleos los comparten generador de carga, API y nodos. Como los nodos casi no usan CPU (esperan), el efecto es pequeño, pero no nulo.`,
      "**Carga de lazo cerrado.** Cada cliente envía el siguiente documento al recibir la respuesta; una carga de llegadas independientes (lazo abierto) podría mostrar colas distintas.",
      "**Trabajo limitado por espera.** Las conclusiones de escalado de hilos valen para ese tipo de trabajo; para uno limitado por CPU habría que repetir e2.",
      "**Repeticiones.** e1 a e3 se repitieron 3 veces; e4 y e5 se midieron una vez por configuración, por lo que sus cifras son indicativas.",
      "**Datos en memoria.** El servicio y los repositorios no se reparten: hay una sola API. La escalabilidad medida es la de la facturación electrónica, no la de todo el sistema.",
    ])
  );

  // =====================================================================================  8
  add(H1("8. Conclusiones"));
  add(
    P("El mini proyecto cumplió su objetivo: se diseñó, modeló, implementó y evaluó una arquitectura distribuida real para una parte del consultorio «Salud Integral», sin romper el sistema existente. Las conclusiones principales son:"),
    ...viñetas([
      `**La arquitectura escala.** Con nodos de 4 hilos, el rendimiento crece de ${n1(e1[0].docs_por_s_media)} a ${n1(e1[2].docs_por_s_media)} documentos por segundo de 1 a 4 nodos (${n1(e1[2].eficiencia_pct)} % de eficiencia) y, dentro de un nodo, hasta 16 hilos siguen la ley de Little.`,
      `**Tolera fallos.** Con la caída de un nodo en plena carga no se perdió ningún documento (${n1(e4.global.tasa_exito_pct)} % de éxito), la detección tardó ${n2(e4.deteccion_s)} s y el sistema se recuperó solo cuando el nodo volvió.`,
      "**Los patrones resolvieron problemas concretos.** Proxy y Adapter permitieron distribuir sin tocar el servicio; Mediator concentró el balanceo y la salud de los nodos; Observer midió sin frenar; Circuit Breaker e Idempotent Receiver hicieron seguros los reintentos.",
      `**Medir encontró lo que el diseño no mostraba.** El mayor hallazgo no estaba en los nodos sino en el candado del servicio, que anulaba todo el escalado. Corregirlo multiplicó el rendimiento por ${n1(d5[1].docs_por_s / a5[1].docs_por_s)} con 4 nodos.`,
      "**La contrapresión es una decisión de producto.** Acotar la cola protege la latencia pero convierte el exceso en rechazos reintentables; ampliarla acepta todo a costa de espera. La elección depende de qué es peor para el consultorio.",
    ]),
  );
  add(H2("8.1 Reflexión sobre las decisiones y los desafíos"));
  add(
    ...viñetas([
      "**Elegir la facturación electrónica** fue acertado: es la única dependencia remota del sistema, y por eso la distribución tiene sentido real y no es un ejercicio artificial.",
      "**Pensar en fallos parciales.** La mayor dificultad conceptual es que una llamada remota puede haberse ejecutado aunque no haya respuesta. Resolverlo exigió idempotencia y claves, no solo reintentos.",
      "**Probar la concurrencia.** Las pruebas con nodos en hilos por TCP real fueron la forma de hacerlas rápidas y repetibles; las mediciones con procesos reales aportaron lo que las pruebas no pueden (SIGKILL y tiempos de recuperación).",
      "**Honestidad en la evaluación.** Un resultado como «el escalado es del 99 %» solo es creíble junto a sus límites: proveedor simulado, red local, trabajo limitado por espera.",
    ])
  );
  add(H2("8.2 Trabajo futuro"));
  add(
    ...viñetas([
      "Reemplazar el proveedor simulado por un adaptador de un proveedor tecnológico autorizado por la DIAN, que ya tiene su puerto (`IProveedorTecnologico`).",
      "Cifrar y autenticar la comunicación entre la API y los nodos (TLS mutuo) y registrar los nodos de forma dinámica.",
      "Persistir los datos en una base de datos real y escalar la API en varias réplicas, que es el siguiente techo medido; con ella, usar un *outbox* transaccional para no perder envíos si la API se cae entre reservar y transmitir.",
      "Reducir la latencia de cola larga con solicitudes redundantes al segundo nodo (Dean y Barroso, 2013) y medir con carga de lazo abierto.",
      "Empaquetar cada nodo en un contenedor y desplegar varios en la nube.",
    ])
  );

  // =====================================================================================  Referencias
  add(H1("Referencias", { salto: true }));
  const refs = [
    "Amdahl, G. M. (1967). Validity of the single processor approach to achieving large scale computing capabilities. *AFIPS Conference Proceedings, 30*, 483–485. https://doi.org/10.1145/1465482.1465560",
    "Bass, L., Clements, P., & Kazman, R. (2021). *Software architecture in practice* (4.ª ed.). Addison-Wesley.",
    "Dean, J., & Barroso, L. A. (2013). The tail at scale. *Communications of the ACM, 56*(2), 74–80. https://doi.org/10.1145/2408776.2408794",
    "Evans, E. (2003). *Domain-driven design: Tackling complexity in the heart of software*. Addison-Wesley.",
    "Fowler, M. (2002). *Patterns of enterprise application architecture*. Addison-Wesley.",
    "Gamma, E., Helm, R., Johnson, R., & Vlissides, J. (1994). *Design patterns: Elements of reusable object-oriented software*. Addison-Wesley.",
    "Hohpe, G., & Woolf, B. (2003). *Enterprise integration patterns: Designing, building, and deploying messaging solutions*. Addison-Wesley.",
    "Little, J. D. C. (1961). A proof for the queuing formula: L = λW. *Operations Research, 9*(3), 383–387. https://doi.org/10.1287/opre.9.3.383",
    "Microsoft. (s. f.). *Cloud design patterns*. Azure Architecture Center. https://learn.microsoft.com/en-us/azure/architecture/patterns/",
    "Nygard, M. T. (2018). *Release it! Design and deploy production-ready software* (2.ª ed.). Pragmatic Bookshelf.",
    "Python Software Foundation. (s. f.-a). *concurrent.futures — Launching parallel tasks*. Python 3 documentation. https://docs.python.org/3/library/concurrent.futures.html",
    "Python Software Foundation. (s. f.-b). *socketserver — A framework for network servers*. Python 3 documentation. https://docs.python.org/3/library/socketserver.html",
    "Tanenbaum, A. S., & van Steen, M. (2017). *Distributed systems* (3.ª ed.). Maarten van Steen.",
  ];
  refs.forEach((r) =>
    out.push(
      new Paragraph({
        children: runs(r, { size: 21 }),
        indent: { left: 720, hanging: 720 },
        spacing: { after: 100, line: 280 },
        alignment: AlignmentType.LEFT,
      })
    )
  );

  // =====================================================================================  Anexos
  add(H1("Anexo A. Trazabilidad con los criterios de evaluación", { salto: true }));
  add(
    tabla(
      "Criterios de evaluación y evidencia",
      ["Criterio", "Evidencia", "Sección"],
      [
        ["Diseño de la arquitectura distribuida", "Diagramas de componentes, secuencia y despliegue; requisitos RFD y RNFD", "3 y 4"],
        ["Implementación del prototipo", "Paquete `app/distribuido`, integración con la API, pruebas automáticas", "6"],
        ["Uso de patrones de diseño", "Proxy, Mediator, Observer, Circuit Breaker, Retry, Idempotent Receiver y pool de hilos", "5"],
        ["Evaluación de escalabilidad y robustez", "Experimentos e1 a e5, cuellos de botella y ajustes", "7"],
        ["Presentación en video", "Video no listado en YouTube de 12 a 15 minutos; guion en `docs/video/guion_video.md`", "Anexo B"],
        ["Trabajo en equipo", "Roles, estrategia y cronograma", "3.4 y 3.5"],
      ],
      [3300, 4960, 1100]
    )
  );
  add(H1("Anexo B. Enlaces de la entrega"));
  add(
    tabla(
      "Enlaces",
      ["Producto", "Enlace"],
      [
        ["Repositorio del código fuente", "https://github.com/JNACHO2001/consultorio-medico"],
        ["Aplicación en línea (modo local)", "https://consultorio-medico-pty2.onrender.com"],
        ["Video en YouTube (no listado)", "[Pegar aquí el enlace del video una vez subido]"],
      ],
      [3300, 6060]
    )
  );
  return out;
};
