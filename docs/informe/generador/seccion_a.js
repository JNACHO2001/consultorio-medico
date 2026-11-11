// Secciones 1 a 6 del informe (introducción, sistema, análisis, UML, patrones, implementación).
const path = require("path");
const { P, H1, H2, H3, viñetas, codigo, tabla, figura, AlignmentType } = require("./lib");

const IMG_UML = path.resolve(__dirname, "../../uml/img");
const C = AlignmentType.CENTER;

module.exports = function seccionA({ nPruebas, nPruebasNuevas }) {
  const out = [];
  const add = (...bloques) => bloques.flat().forEach((b) => out.push(b));

  // =====================================================================================  1
  add(H1("1. Introducción", { salto: true }));
  add(H2("1.1 Contexto del proyecto"));
  add(
    P("El consultorio médico **«Salud Integral»** es el proyecto que el equipo desarrolló en la Unidad 1: un sistema web que centraliza pacientes, citas, historias clínicas, ingresos, facturación, convenios con EPS, cartera, órdenes de apoyo diagnóstico, caja y facturación electrónica. Está construido en Python con FastAPI, organizado por capas y con el patrón Repository como eje, y su prototipo está publicado en un repositorio de GitHub y desplegado en la nube."),
    P("En esa primera versión todo se ejecuta en **un solo proceso**. Para la Unidad 2 («Tejiendo redes: arquitectura de software entre hilos y nodos») el reto es llevar una parte real del sistema a una **arquitectura distribuida**, en la que varios componentes repartidos en una red cooperan para cumplir un objetivo común, y evaluarla con rigor."),
    P("La parte elegida es la **facturación electrónica**. Es el único servicio del consultorio que depende de un tercero remoto: un proveedor tecnológico que valida, firma y transmite cada factura o nota crédito a la DIAN. Ese proveedor es lento (decenas o cientos de milisegundos por documento), puede fallar de forma independiente y es crítico, porque por la regla de negocio RN-22 no se puede radicar una factura al pagador sin factura electrónica aceptada. Reúne, por eso, los problemas clásicos de la computación distribuida: latencia de red, fallos parciales, concurrencia, balanceo de carga y necesidad de reintentos seguros."),
  );
  add(H2("1.2 Propósito del diseño de la arquitectura"));
  add(
    P("El propósito es diseñar, modelar, implementar y evaluar una arquitectura en la que el envío de documentos electrónicos se reparta entre **nodos proveedor independientes**, cada uno con su propio pool de hilos, sin que el resto del sistema note la diferencia, y demostrar con mediciones que esa arquitectura escala, tolera la caída de un nodo y degrada con elegancia cuando falla."),
  );
  add(H2("1.3 Objetivos"));
  add(
    P("**Objetivo general.** Diseñar y evaluar una arquitectura de software distribuida para la facturación electrónica del consultorio «Salud Integral», aplicando modelado UML y patrones de diseño, e implementar un prototipo que simule la interacción de nodos e hilos en una red."),
    P("**Objetivos específicos.**", { keepNext: true }),
    ...viñetas([
      "Modelar la arquitectura con UML: diagrama de componentes, de secuencia (nodos e hilos) y de despliegue.",
      "Seleccionar y justificar patrones de diseño pertinentes (Proxy, Mediator, Observer, Circuit Breaker, Retry e Idempotent Receiver) con base en la bibliografía.",
      "Implementar un prototipo con nodos como procesos independientes, pool de hilos por nodo y comunicación por TCP, integrado al sistema existente sin romper sus pruebas.",
      "Evaluar escalabilidad horizontal y vertical, saturación y robustez ante la caída de un nodo, documentando métricas y cuellos de botella.",
      "Aplicar los ajustes que la evaluación justifique y medir su efecto.",
    ]),
  );
  add(H2("1.4 Alcance y límites"));
  add(
    P("El proveedor tecnológico de los nodos es **simulado**: valida localmente las reglas básicas del documento, espera un tiempo configurable (por defecto 40 ms) para representar la firma y la transmisión, y no habla con la DIAN real. Los nodos de las mediciones corren como procesos del sistema operativo en una misma máquina de 2 núcleos; la red es el bucle local (*loopback*). El informe señala en la sección 7 qué conclusiones sobreviven a esa simplificación y cuáles no."),
  );

  // =====================================================================================  2
  add(H1("2. Descripción del sistema distribuido"));
  add(H2("2.1 Tipo de sistema"));
  add(
    P("Es un **servicio distribuido de procesamiento** con un grupo de trabajadores remotos: la API recibe la solicitud de emisión, y un proxy reparte el trabajo entre N nodos que lo ejecutan en paralelo. La comunicación es síncrona (petición y respuesta) sobre TCP con un mensaje JSON por línea. Cada nodo atiende varias solicitudes a la vez con un pool de hilos, de modo que el sistema combina dos niveles de concurrencia: **entre nodos** (procesos distintos, escalado horizontal) y **dentro de cada nodo** (hilos, escalado vertical)."),
  );
  add(H2("2.2 Componentes funcionales"));
  add(
    tabla(
      "Componentes del sistema distribuido",
      ["Componente", "Responsabilidad", "Dónde corre"],
      [
        ["`FacturacionElectronicaService`", "Numera el documento, calcula CUFE y XML, lo guarda como GENERADO y llama al proveedor; guarda la respuesta.", "API (proceso uvicorn)"],
        ["`ProveedorProxy`", "Representa al proveedor remoto: serializa, envía, reintenta con espera exponencial y jitter, y degrada si no hay nodos.", "API"],
        ["`MediadorNodos`", "Registro de nodos, elección del menos cargado, circuit breaker por nodo y latidos.", "API"],
        ["`ClienteNodo`", "Pool de conexiones TCP persistentes hacia un nodo.", "API"],
        ["`BusEventos` y `Metricas`", "Publicación asíncrona de eventos y cálculo de totales, reparto por nodo y percentiles.", "API (hilo propio)"],
        ["`NodoProveedor`", "Servidor TCP con pool de hilos, cola acotada, caché de idempotencia y proveedor simulado.", "N procesos independientes"],
        ["`ClusterLocal`", "Lanza N nodos como procesos del sistema operativo (demostración, pruebas y mediciones).", "Máquina del desarrollador"],
      ],
      [3000, 4260, 2100]
    )
  );
  add(H2("2.3 Supuestos"));
  add(
    ...viñetas([
      "**Modelo de fallos.** Los nodos fallan por parada (el proceso muere o deja de responder); no se consideran nodos que mientan o corrompan datos.",
      "**Red.** Puede rechazar conexiones, cortarlas o tardar; no se supone sincronía de relojes entre la API y los nodos.",
      "**Idempotencia.** Enviar dos veces el mismo documento al proveedor no debe producir dos documentos; el nodo lo garantiza con una clave de idempotencia.",
      "**Una sola API.** Los datos del consultorio siguen en memoria dentro de un proceso (Unidad 1). Los nodos no guardan datos clínicos ni contables: solo reciben el documento a validar.",
      "**Latencia representativa.** 40 ms por documento representa la firma y la transmisión al proveedor; el valor es configurable.",
      "**Confianza en la red interna.** En el prototipo no hay cifrado ni autenticación entre la API y los nodos; en producción se exigirían TLS mutuo o una red privada.",
    ])
  );
  add(H2("2.4 Herramientas seleccionadas"));
  add(
    tabla(
      "Herramientas y justificación",
      ["Herramienta", "Uso", "Motivo"],
      [
        ["Python 3.13 (biblioteca estándar)", "`socketserver`, `concurrent.futures`, `threading`, `socket`", "Hilos, pool y TCP reales sin dependencias nuevas; el proyecto ya es Python."],
        ["FastAPI y uvicorn", "API REST existente", "Se conserva; solo se añade configuración, un endpoint de estado y el arranque del clúster."],
        ["pytest", `${nPruebas} pruebas automáticas`, "Verifican el contrato y las reglas, y ahora el comportamiento distribuido."],
        ["Procesos del sistema operativo", "Nodos reales (`subprocess`)", "Permiten matar un nodo con SIGKILL y medir la recuperación."],
        ["Matplotlib y Graphviz", "Diagramas UML a color y gráficas", "Reproducibles desde un script del repositorio."],
        ["GitHub, Docker y Render", "Repositorio y despliegue", "Ya usados en la Unidad 1; el modo local sigue desplegándose igual."],
      ],
      [2500, 2860, 4000]
    )
  );

  // =====================================================================================  3
  add(H1("3. Análisis y planificación del proyecto"));
  add(H2("3.1 Definición de requisitos"));
  add(
    P("Los requisitos de la Unidad 2 se agregan a los de la Unidad 1 (RF-01 a RF-27 y RN-01 a RN-26). Se identifican con el sufijo D de «distribuido»."),
    tabla(
      "Requisitos del sistema distribuido",
      ["Código", "Requisito", "Verificación"],
      [
        ["RFD-01", "La factura electrónica se emite por medio de nodos remotos sin cambiar el servicio de facturación.", "Prueba de integración por la API"],
        ["RFD-02", "El número de nodos es configurable (`NODOS_PROVEEDOR`) y la carga se reparte entre ellos.", "Prueba de balanceo con 3 nodos"],
        ["RFD-03", "Si un nodo falla, se agota el tiempo o está saturado, el envío se reintenta en otro nodo.", "Pruebas de caída, lentitud y saturación"],
        ["RFD-04", "Reintentar no duplica el trabajo (idempotencia).", "Pruebas de clave repetida y simultánea"],
        ["RFD-05", "Sin nodos disponibles, el documento queda RECHAZADO (NODOS-01) y se reenvía con «Reintentar».", "Prueba de API sin nodos y recuperación"],
        ["RFD-06", "El administrador puede ver el estado de los nodos y las métricas; `/health` informa los nodos disponibles.", "Prueba del endpoint de nodos"],
        ["RNFD-01", "Escalabilidad horizontal casi lineal hasta 4 nodos.", "Experimento e1"],
        ["RNFD-02", "Tolerancia a la caída de un nodo sin perder documentos.", "Experimento e4"],
        ["RNFD-03", "Contrapresión: una cola de admisión acotada, no una cola infinita.", "Experimento e3 y pruebas del nodo"],
        ["RNFD-04", "La numeración de facturas es única aunque se emita en paralelo.", "Prueba concurrente y experimento e5"],
        ["RNFD-05", "Sin `NODOS_PROVEEDOR` el sistema funciona como en la Unidad 1 (Render).", `Las ${nPruebas - nPruebasNuevas} pruebas previas siguen pasando`],
      ],
      [1100, 5460, 2800]
    )
  );
  add(H2("3.2 Relevancia de la comunicación entre nodos e hilos"));
  add(
    P("La emisión de un documento es un trabajo **limitado por espera** (red y proveedor), no por cálculo. Por eso los hilos son la herramienta correcta: mientras un hilo espera la respuesta del proveedor, otros avanzan. En Python el bloqueo global del intérprete (GIL) impide que varios hilos ejecuten bytecode a la vez, pero se libera durante las esperas de entrada y salida, de modo que un pool de hilos sí multiplica el rendimiento de un trabajo que mayormente espera."),
    P("La capacidad de un nodo se puede predecir con la ley de Little (Little, 1961): si cada documento ocupa un hilo durante *W* segundos y hay *h* hilos, el nodo procesa como máximo *h / W* documentos por segundo. Con *W* = 40 ms, un nodo de 4 hilos admite unos 100 documentos por segundo, y N nodos, unos 100·N. La sección 7 contrasta esta predicción con las mediciones."),
    P("Los **nodos** (procesos separados) añaden lo que los hilos no dan: aislamiento de fallos (si un nodo muere, los demás siguen), escalado más allá de una máquina y despliegue independiente. A cambio aparecen los problemas de la distribución: la comunicación puede fallar a medias, las respuestas pueden perderse y los reintentos pueden duplicar trabajo; de ahí que el diseño incluya idempotencia, circuit breaker y degradación controlada (Tanenbaum y van Steen, 2017)."),
  )
  add(H2("3.3 Metas del sistema"));
  add(
    ...viñetas([
      "Eficiencia de escalado horizontal de al menos 90 % al pasar de 1 a 4 nodos.",
      "Tasa de éxito del 100 % cuando cae 1 de 3 nodos en plena carga, con recuperación automática del nodo sin reiniciar la API.",
      "Capacidad de agregar nodos solo cambiando una variable de entorno.",
      "Ningún consecutivo repetido ni documento perdido bajo concurrencia.",
      "Cero cambios en el comportamiento observable del sistema cuando no hay nodos configurados.",
    ])
  );
  add(H2("3.4 Estrategia del equipo y roles"));
  add(
    P("El equipo (4 a 5 integrantes) trabajó con roles definidos y entregables por rol. Los nombres de quienes ocupan cada rol figuran en la portada."),
    tabla(
      "Roles del equipo",
      ["Rol", "Responsabilidades", "Entregables principales"],
      [
        ["Líder de proyecto", "Plan, seguimiento del cronograma, integración de entregables y entrega en el LMS.", "Plan de proyecto, entrega final"],
        ["Diseñador de arquitectura", "Diagramas UML, selección y justificación de patrones.", "Secciones 4 y 5, diagramas"],
        ["Desarrollador", "Implementación de nodos, proxy, mediador y observadores; integración con la API.", "Paquete `app/distribuido`, repositorio"],
        ["Evaluador de calidad", "Pruebas automáticas, experimentos de carga y análisis de cuellos de botella.", "Pruebas, `benchmarks/`, sección 7"],
        ["Documentación y video", "Informe, referencias APA 7 y presentación en video.", "Este informe, video no listado"],
      ],
      [2200, 4560, 2600]
    ),
    P("La estrategia fue **iterativa y guiada por mediciones**: se construyó primero el camino completo más simple (un nodo, un envío), se cubrió con pruebas, se añadió tolerancia a fallos y, solo después, se midió. Los ajustes se decidieron con los números y no por intuición."),
  );
  add(H2("3.5 Cronograma"));
  add(
    tabla(
      "Cronograma tentativo",
      ["Fase", "Actividades", "Duración", "Resultado"],
      [
        ["1. Análisis y plan", "Elegir el sistema, definir requisitos RFD y RNFD, roles y herramientas.", "Semana 1", "Plan y requisitos"],
        ["2. Diseño", "Diagramas de componentes, secuencia y despliegue; selección de patrones.", "Semana 1", "Sección 4 y 5"],
        ["3. Implementación", "Nodo, protocolo, proxy, mediador, observadores, integración.", "Semana 2", "Prototipo funcional"],
        ["4. Evaluación y ajustes", "Pruebas automáticas, experimentos e1 a e5, ajuste del candado y de la cola.", "Semana 2", "Sección 7"],
        ["5. Informe y video", "Informe técnico, guion y grabación del video de 12 a 15 minutos.", "Semana 3", "PDF/Word y video"],
        ["6. Revisión y entrega", "Coherencia de artefactos y carga en el LMS.", "Semana 3", "Entrega"],
      ],
      [1900, 4260, 1200, 2000]
    )
  );
  add(H2("3.6 Riesgos"));
  add(
    tabla(
      "Riesgos identificados",
      ["Riesgo", "Efecto", "Mitigación"],
      [
        ["Reintentos que duplican trabajo", "Documentos repetidos o consecutivos duplicados", "Clave de idempotencia en el nodo y reserva del consecutivo con candado"],
        ["Un nodo lento o caído", "Latencia alta o pérdida de documentos", "Tiempo de espera, circuit breaker y reintento en otro nodo"],
        ["Sobrecarga de un nodo", "Colas ilimitadas y memoria creciente", "Cola de admisión acotada con respuesta OCUPADO"],
        ["Mediciones poco representativas", "Conclusiones engañosas", "Repeticiones, calentamiento y límites declarados en la sección 7"],
      ],
      [2700, 2900, 3760]
    )
  );

  // =====================================================================================  4
  add(H1("4. Modelado UML"));
  add(
    P("Los diagramas se generan con el script `docs/uml/render_distribuido.py` (Graphviz y Matplotlib) y se presentan a color. Complementan los diagramas de la Unidad 1 (casos de uso, clases, secuencia de agendar una cita y despliegue), que siguen vigentes."),
  );
  add(H2("4.1 Diagrama de componentes"));
  add(
    P("El diagrama de componentes separa dos grandes bloques: el servidor de aplicación y los nodos proveedor. Dentro del servidor, `FacturacionElectronicaService` solo conoce la interfaz `IProveedorTecnologico`; el `ProveedorProxy` la implementa y delega en el `MediadorNodos`, que usa un `ClienteNodo` por nodo. Proxy y mediador publican hechos en el `BusEventos`, que los entrega a `Metricas`, y un `Vigilante` envía latidos. Cada nodo es un proceso con servidor TCP, pool de hilos, caché de idempotencia y proveedor simulado."),
    figura("Diagrama de componentes de la facturación electrónica distribuida", path.join(IMG_UML, "05_componentes_distribuido.png"), 600, "Elaboración propia. Verde: patrones Proxy y Mediator; morado: Observer; naranja: nodos; azul: servicio y API."),
    P("**Explicación técnica.** La dependencia clave es la inversión: el servicio depende de una abstracción (`IProveedorTecnologico`) y no de dónde corre el proveedor. Cambiar de proveedor local a distribuido es una decisión de composición en `container.py`, igual que en la Unidad 1 se cambiaba de repositorio en memoria a SQL. Las flechas hacia los nodos son el único punto donde hay red; todo lo demás es llamada local."),
  );
  add(H2("4.2 Diagrama de secuencia"));
  add(
    P("El diagrama de secuencia sigue una emisión completa, incluyendo el caso en que el primer nodo falla. Muestra también qué ocurre dentro de cada nodo: un hilo de conexión recibe la solicitud y la entrega al pool de hilos, que hace el trabajo."),
    figura("Diagrama de secuencia: emisión de una factura electrónica con failover entre nodos", path.join(IMG_UML, "06_secuencia_distribuida.png"), 620, "Elaboración propia. El marco *alt* distingue el nodo A que atiende del que falla; las flechas de publicación al bus son asíncronas."),
    P("**Explicación técnica.**", { keepNext: true }),
    ...viñetas([
      "**Reserva con candado.** El servicio numera el documento (consecutivo, CUFE, XML) y lo guarda como GENERADO dentro de un candado corto. Así el consecutivo queda reservado y cualquier otra emisión de la misma factura recibe un conflicto.",
      "**Envío fuera del candado.** La transmisión es lenta; si el candado la cubriera, se serializarían todas las emisiones (cuello de botella medido en la sección 7).",
      "**Despacho.** El mediador elige el nodo con menos solicitudes en curso. El mensaje lleva una clave de idempotencia.",
      "**Fallo y reintento.** Ante conexión rechazada, tiempo agotado u OCUPADO, el mediador registra el fallo (y abre el circuito tras varios seguidos) y el proxy espera con backoff y jitter antes de probar otro nodo con la misma clave.",
      "**Observación.** Los eventos se publican sin esperar a los observadores, de modo que medir no frena la emisión.",
    ]),
  );
  add(H2("4.3 Diagrama de despliegue"));
  add(
    P("El despliegue muestra la distribución física: el navegador del usuario, el servidor de aplicación en un contenedor y los nodos proveedor, que pueden compartir host o repartirse en varios. La API abre conexiones TCP hacia cada nodo; los nodos, en el futuro, hablarían con el proveedor tecnológico real."),
    figura("Diagrama de despliegue de la facturación electrónica distribuida", path.join(IMG_UML, "07_despliegue_distribuido.png"), 620, "Elaboración propia. Línea punteada: sistema externo fuera del alcance del prototipo."),
    P("**Explicación técnica.** La lista de nodos es la única información de topología y vive en la variable `NODOS_PROVEEDOR` (por ejemplo, `host1:9101,host1:9102,host2:9101`). Agregar capacidad es levantar otro nodo y añadir su dirección. El despliegue en Render de la Unidad 1 no cambia porque, sin esa variable, el sistema usa el proveedor simulado dentro del mismo proceso."),
  );

  // =====================================================================================  5
  add(H1("5. Selección y justificación de patrones de diseño"));
  add(
    P("Los patrones se eligieron por el problema concreto que resuelven en este sistema, no por catálogo. La tabla resume la selección y las subsecciones la justifican con la bibliografía."),
    tabla(
      "Patrones aplicados",
      ["Patrón", "Dónde", "Problema que resuelve", "Fuente"],
      [
        ["Proxy (remoto)", "`ProveedorProxy`", "Ocultar que el proveedor está en otra máquina", "Gamma et al., 1994"],
        ["Mediator", "`MediadorNodos`", "Que los clientes no conozcan a cada nodo ni su estado", "Gamma et al., 1994"],
        ["Observer", "`BusEventos`, `Metricas`", "Observar sin acoplar ni frenar la emisión", "Gamma et al., 1994"],
        ["Circuit Breaker", "`MediadorNodos`", "No insistir contra un nodo caído", "Nygard, 2018; Microsoft, s. f."],
        ["Retry con backoff y jitter", "`ProveedorProxy`", "Superar fallos transitorios sin avalancha de reintentos", "Microsoft, s. f."],
        ["Idempotent Receiver", "`NodoProveedor`", "Reintentar sin duplicar trabajo", "Hohpe y Woolf, 2003"],
        ["Competing Consumers y contrapresión", "Pool de hilos y cola acotada", "Procesar en paralelo sin colas infinitas", "Hohpe y Woolf, 2003; Tanenbaum y van Steen, 2017"],
        ["Adapter (heredado)", "`IProveedorTecnologico`", "Cambiar de proveedor sin tocar el servicio", "Gamma et al., 1994"],
        ["Repository (heredado)", "Repositorios en memoria", "Independencia del almacenamiento", "Fowler, 2002; Evans, 2003"],
        ["Health Endpoint Monitoring (extendido)", "`/health`, `/api/electronica/nodos`", "Que la plataforma detecte fallas", "Microsoft, s. f."],
      ],
      [1900, 2500, 2960, 2000]
    )
  );
  add(H2("5.1 Proxy"));
  add(
    P("Un proxy remoto es un representante local de un objeto que está en otro espacio de direcciones (Gamma et al., 1994). `ProveedorProxy` cumple `IProveedorTecnologico`, de modo que el servicio lo usa como si fuera el proveedor simulado local. Es además la pieza donde viven las políticas de comunicación: serialización, tiempo de espera, reintentos y la degradación. **Consecuencia:** una llamada que parece local puede tardar o fallar; por eso el proxy nunca lanza una excepción de red hacia arriba, sino que devuelve un rechazo NODOS-01 que el sistema ya sabe tratar con «Reintentar»."),
  );
  add(H2("5.2 Mediator"));
  add(
    P("El mediador encapsula cómo interactúa un conjunto de objetos y evita que se refieran entre sí de forma explícita (Gamma et al., 1994). Aquí el proxy solo dice «despacha este mensaje»; el `MediadorNodos` conoce los nodos, elige el que tiene menos solicitudes en curso (con reparto por turnos en los empates) y mantiene su estado de salud. **Consecuencia:** la política de balanceo y los circuitos se cambian en un único lugar; el riesgo, un mediador demasiado grande, se contiene porque no hace red por sí mismo (delega en `ClienteNodo`)."),
  );
  add(H2("5.3 Observer"));
  add(
    P("Observer define una dependencia uno a muchos para que, al cambiar un objeto, sus dependientes se enteren sin acoplarse (Gamma et al., 1994). `BusEventos` publica hechos del sistema distribuido (envío exitoso, intento fallido, cambio de circuito) y entrega cada evento a sus suscriptores, entre ellos `Metricas`, desde un hilo propio con cola acotada. Si la cola se llena, el evento se descarta y se cuenta: la observabilidad nunca debe tumbar la operación. **Limitación declarada:** el bus vive dentro del proceso de la API; es un Observer *sobre eventos originados en un sistema distribuido*. Para observar entre procesos habría que reemplazarlo por un intermediario de mensajes, algo que la interfaz de suscripción permite sin cambiar a los observadores."),
  );
  add(H2("5.4 Circuit Breaker y Retry"));
  add(
    P("El circuit breaker evita que un cliente siga llamando a un servicio que probablemente falle, y le da tiempo de recuperarse (Nygard, 2018). Cada nodo tiene tres estados: CERRADO (recibe tráfico), ABIERTO (se descarta durante un enfriamiento) y SEMIABIERTO (deja pasar una sola solicitud de prueba). Se abre tras `CIRCUITO_FALLOS` fallos seguidos (3 por defecto) y un nodo saturado no cuenta como caído: responde, solo que sin cupo. El reintento usa espera exponencial con jitter para que muchos clientes no reintenten a la vez (Microsoft, s. f.): base de 50 ms, tope de 1 s y factor aleatorio entre 0,5 y 1,5."),
  );
  add(H2("5.5 Idempotent Receiver"));
  add(
    P("Si un cliente no recibe respuesta, no sabe si el servidor ejecutó o no la operación; reintentar sin más puede duplicarla. Un receptor idempotente reconoce los mensajes repetidos y no repite el efecto (Hohpe y Woolf, 2003). El nodo guarda por clave (`tipo:número:CUFE`) el resultado ya calculado y, si una clave llega mientras otra igual está en proceso, comparte el resultado en lugar de procesarla dos veces. Las pruebas cubren ambos casos."),
  );
  add(H2("5.6 Competing Consumers, pool de hilos y contrapresión"));
  add(
    P("Un pool de hilos fijo es la forma estándar de que varios consumidores compitan por el trabajo sin crear un hilo por solicitud (Hohpe y Woolf, 2003; Python Software Foundation, s. f.-a). La decisión de diseño importante es que la **cola de admisión está acotada**: caben `hilos + cola` solicitudes; la siguiente recibe OCUPADO de inmediato. Es contrapresión explícita: es preferible que el nodo diga «no puedo» y el proxy derive el trabajo a otro nodo, a que acepte sin límite y degrade para todos. La sección 7 muestra el costo de acotar demasiado la cola y el efecto de ajustarla."),
  );
  add(H2("5.7 Patrones heredados de la Unidad 1"));
  add(
    P("El **Adapter** (`IProveedorTecnologico`) fue lo que permitió insertar el proxy sin tocar el servicio. El **Repository** no cambia: los documentos siguen en el repositorio en memoria y la reserva del consecutivo se apoya en sus operaciones atómicas. El **Health Endpoint Monitoring** se extiende: `/health` informa cuántos nodos están disponibles sin alterar su código de estado (la API sigue viva aunque los nodos estén caídos) y un endpoint de administración detalla el circuito y las métricas de cada nodo."),
  );

  // =====================================================================================  6
  add(H1("6. Implementación y simulación del prototipo distribuido"));
  add(H2("6.1 Estructura del código"));
  add(
    tabla(
      "Archivos del módulo distribuido",
      ["Archivo", "Contenido"],
      [
        ["`backend/app/distribuido/protocolo.py`", "Formato de mensajes, serialización del documento y clave de idempotencia."],
        ["`backend/app/distribuido/nodo.py`", "`NodoProveedor`: servidor TCP, pool de hilos, cola acotada, caché; ejecutable como proceso."],
        ["`backend/app/distribuido/mediador.py`", "`MediadorNodos`, `ClienteNodo` y circuit breaker."],
        ["`backend/app/distribuido/proxy.py`", "`ProveedorProxy`: reintentos, backoff y degradación."],
        ["`backend/app/distribuido/eventos.py`", "`BusEventos` y `Metricas` (Observer)."],
        ["`backend/app/distribuido/cluster.py`", "`ClusterProveedor`, `ClusterLocal` y `NodoProceso` (lanzador de procesos)."],
        ["`backend/tests/test_distribuido.py`", `${nPruebasNuevas} pruebas del módulo.`],
        ["`backend/benchmarks/`", "Experimentos, resultados en JSON y gráficas."],
        ["`docs/uml/render_distribuido.py`", "Generador de los diagramas UML a color."],
      ],
      [4200, 5160]
    )
  );
  add(H2("6.2 Protocolo de comunicación"));
  add(
    P("Cada mensaje es un objeto JSON en una línea terminada en salto de línea, sobre una conexión TCP persistente. Se eligió un protocolo propio y simple, solo con la biblioteca estándar, porque deja ver cada paso en las pruebas y en el informe; en producción se usaría HTTP o gRPC con TLS."),
    ...codigo([
      '-> {"id":1,"tipo":"ENVIAR","clave":"FACTURA:SETP990000000:<cufe>","documento":{...}}',
      '<- {"id":1,"ok":true,"aceptado":true,"codigo":"SIM-00","mensaje":"...","nodo":"nodo-1","ms":41.2}',
      '<- {"id":1,"ok":false,"error":"OCUPADO","nodo":"nodo-1"}      (cola de admisión llena)',
      '-> {"id":2,"tipo":"ESTADO"}      (latido: hilos, cola, procesadas, saturadas, duplicadas)',
    ]),
    P(" ", { spacing: { after: 60 } }),
  );
  add(H2("6.3 Hilos y procesos"));
  add(
    tabla(
      "Hilos y procesos del sistema",
      ["Proceso", "Hilo", "Función"],
      [
        ["API (uvicorn)", "Bucle de eventos y pool de hilos de FastAPI", "Atiende las peticiones HTTP; cada emisión concurrente ocupa un hilo mientras espera al nodo."],
        ["API", "`bus-eventos`", "Entrega los eventos a los observadores."],
        ["API", "`vigilante-nodos`", "Latidos cada 2 s: actualiza el circuito y la carga de cada nodo."],
        ["Nodo", "`nodo-N-servidor`", "Acepta conexiones nuevas."],
        ["Nodo", "Un hilo por conexión", "Lee solicitudes y las entrega al pool; espera el resultado."],
        ["Nodo", "Pool `nodo-N-hilo` (4 por defecto)", "Ejecuta el trabajo: valida y «transmite»."],
      ],
      [1700, 3100, 4560]
    )
  );
  add(H2("6.4 Cómo se simula el entorno distribuido"));
  add(
    ...viñetas([
      "**Nodos como procesos reales.** `ClusterLocal` lanza cada nodo con `python -m app.distribuido.nodo`; cada uno elige su puerto y lo informa por su salida estándar.",
      "**Red real.** La comunicación usa sockets TCP sobre el bucle local; cada nodo ve conexiones, desconexiones y lectura parcial como en una red real.",
      "**Latencia del proveedor.** Cada documento espera `latencia_ms` (40 ms, con 25 % de variación) para representar la firma y la transmisión.",
      "**Fallos inyectados.** Un nodo puede fallar con probabilidad configurable (`prob_error`), apagarse en caliente (`detener()`) o morir de forma abrupta con SIGKILL, que es lo que usan las mediciones de robustez.",
      "**Nodos en hilos para las pruebas.** Las pruebas arrancan nodos dentro de hilos del proceso de prueba, pero igualmente por TCP, para que sean rápidas y deterministas.",
    ])
  );
  add(H2("6.5 Integración con el sistema existente"));
  add(
    P("La integración se hizo con cambios mínimos y verificables:"),
    ...viñetas([
      "**Configuración.** Variables `NODOS_PROVEEDOR`, `PROXY_TIMEOUT_SEG`, `PROXY_MAX_INTENTOS`, `CIRCUITO_FALLOS` y `CIRCUITO_ENFRIAMIENTO_SEG`. Vacía la primera, el comportamiento es el de la Unidad 1.",
      "**Composición.** `container.py` crea el clúster si hay nodos y le pasa su proxy al servicio como proveedor; el resto del sistema no cambia.",
      "**Ciclo de vida.** El arranque de la API inicia el bus y los latidos y el apagado los detiene.",
      "**Observabilidad.** `GET /api/electronica/nodos` (solo administrador) y el campo `nodos_facturacion` de `/health`.",
      "**Ajuste del servicio.** `FacturacionElectronicaService` separó la emisión en *reservar* (con candado) y *transmitir* (sin candado); ver sección 7.6.",
    ])
  );
  add(H2("6.6 Cómo ejecutarlo"));
  add(
    ...codigo([
      "cd backend",
      "python -m app.distribuido.cluster --nodos 3     # imprime NODOS_PROVEEDOR=127.0.0.1:P1,127.0.0.1:P2,127.0.0.1:P3",
      "NODOS_PROVEEDOR=127.0.0.1:P1,127.0.0.1:P2,127.0.0.1:P3 uvicorn app.main:crear_app --factory",
      "",
      "pytest                                         # todas las pruebas",
      "python benchmarks/benchmark_distribuido.py     # experimentos e1 a e4",
      "python benchmarks/graficas.py                  # gráficas",
    ]),
    P(" ", { spacing: { after: 60 } }),
  );
  add(H2("6.7 Pruebas automáticas"));
  add(
    P(`El repositorio pasa de 155 a ${nPruebas} pruebas. Las ${nPruebasNuevas} nuevas ejercitan el camino de red real; se agrupan así:`),
    tabla(
      "Pruebas del módulo distribuido",
      ["Grupo", "Qué verifican", "Pruebas"],
      [
        ["Protocolo", "El documento viaja completo y la clave de idempotencia se conserva.", "1"],
        ["Nodo", "Ping y estado, solicitudes inválidas, uso exacto del pool de hilos, contrapresión (OCUPADO) e idempotencia (secuencial y simultánea).", "6"],
        ["Proxy y mediador", "Cumple la interfaz, rechazo del proveedor sin reintento, reparto entre 3 nodos, caída de un nodo, cierre del circuito al volver, ningún nodo, nodo lento, nodo saturado y error del nodo.", "9"],
        ["Observadores", "Entrega, aislamiento de observadores rotos, descarte con cola llena y percentiles.", "3"],
        ["Integración con la API", "Emisión por nodos, estado del clúster y permisos, API sin nodos y reintento al volver, emisión simultánea de una misma factura, ausencia de fuga de hilos.", "5"],
        ["Ajuste del servicio", "Tres facturas distintas se emiten en paralelo sin repetir consecutivos; una excepción del proveedor deja el documento en RECHAZADO y se puede reintentar.", "2"],
      ],
      [1900, 6560, 900],
      { alinear: [AlignmentType.LEFT, AlignmentType.LEFT, C] }
    )
  );
  return out;
};
