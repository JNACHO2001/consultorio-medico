// Cuerpo del informe de la Unidad 3. Las cifras se leen de los resultados de la medición.
const fs = require("fs");
const path = require("path");
const lib = require("../../informe/generador/lib");
const { P, H1, H2, H3, viñetas, codigo, tabla, figura, AlignmentType } = lib;

const IMG = path.resolve(__dirname, "../../uml/img");
const FIG = path.resolve(__dirname, "../img");
const D = AlignmentType.RIGHT;
const C = AlignmentType.CENTER;

const n = (x, d = 2) =>
  Number(x).toLocaleString("es-CO", { minimumFractionDigits: d, maximumFractionDigits: d });
const miles = (x) => Number(x).toLocaleString("es-CO");

module.exports = function contenido(R) {
  const lat = R.n1_latencia;
  const porEscala = (e) => lat.filter((f) => f.estrategia === e);
  const sec = porEscala("secuencial");
  const idx = porEscala("indice");
  const grande = (filas) => filas[filas.length - 1];
  const factor = (i) => (sec[i].p50_ms / idx[i].p50_ms);
  const ultimo = sec.length - 1;
  const prof = R.n4_profundidad;
  const puls = R.n2_pulsaciones;
  const pulsSec = puls.find((f) => f.estrategia === "secuencial");
  const pulsIdx = puls.find((f) => f.estrategia === "indice");
  const constr = grande(R.n3_construccion);

  return [
    // ------------------------------------------------------------------ 1
    H1("Introducción"),
    P("«Salud Integral» es un sistema de gestión para consultorios y centros médicos pequeños de Colombia, desarrollado a lo largo del curso de Arquitectura de Software. Cubre la agenda de citas, la historia clínica, el ingreso y la cuenta del paciente, el catálogo de procedimientos, la facturación —incluida la electrónica— y los módulos propios de una IPS: pagadores y convenios, cartera con glosas, órdenes de apoyo diagnóstico y el borrador de RIPS. Está construido con FastAPI en el servidor y una aplicación de una sola página en JavaScript sin dependencias en el cliente, sobre el patrón Repository, y se despliega en la nube."),
    P("Un sistema con esa cobertura funcional crece en pantallas antes de crecer en usuarios. El prototipo declara **17 rutas** de navegación y cuatro roles con permisos distintos, y una de sus pantallas —el registro del diagnóstico— consulta un catálogo que en su versión oficial supera los doce mil códigos. La pregunta que motiva este trabajo no es si el sistema hace lo que debe, sino si el usuario *llega* a lo que necesita en el tiempo que la tarea clínica tolera."),
    P("Este informe documenta el problema de navegación del sistema, el análisis de las estrategias disponibles, el diseño arquitectónico que lo resuelve —modelado en UML—, los patrones de diseño que lo sostienen y las mediciones que permiten afirmar, con datos y no con intuición, que la estrategia elegida escala. El prototipo no es una maqueta: es el mismo sistema del curso, con su código fuente en un repositorio público y su suite de pruebas automáticas."),

    // ------------------------------------------------------------------ 2
    H1("Planteamiento del problema de navegación"),
    H2("Delimitación del problema"),
    P("De las cuatro opciones sugeridas por la actividad, este proyecto aborda la **navegación eficiente en catálogos extensos**, con dos caras que el sistema presenta de forma simultánea:"),
    ...viñetas([
      "**Navegación estructural.** Moverse entre las 17 pantallas del sistema. Cada rol ve un subconjunto distinto, algunas pantallas son hijas de otras (la cuenta de un ingreso cuelga de la lista de ingresos; la atención, de la agenda del médico) y el usuario llega a ellas desde un menú, desde un enlace directo o pegando una dirección en el navegador.",
      "**Navegación por contenido.** Encontrar un código dentro del catálogo CIE-10 mientras se escribe. El médico no recuerda que la diabetes tipo 2 sin complicaciones es «E119»: escribe «diab» y espera que el sistema le proponga la lista correcta antes de terminar la palabra.",
    ]),
    P("Ambas comparten la misma exigencia: *responder más rápido de lo que el usuario alcanza a notar*. Card et al. (1991) fijaron en 100 ms el umbral de la reacción inmediata y en un segundo el de la continuidad del pensamiento; Nielsen (1993) usa los mismos límites para la respuesta de una interfaz. Una búsqueda que tarde medio segundo no rompe el sistema, pero rompe el ritmo de escritura del médico, que ya está escribiendo la letra siguiente."),

    H2("Relevancia e impacto"),
    P("El problema no es cosmético. En un consultorio la consulta dura entre quince y veinte minutos, y el registro del diagnóstico ocurre al final, con el paciente todavía en el consultorio. Cada segundo que el sistema se interpone es un segundo que no es clínico. El impacto se puede ordenar en tres dimensiones:"),
    ...tabla(
      "Impacto del problema de navegación en las tres dimensiones evaluadas",
      ["Dimensión", "Manifestación en «Salud Integral»", "Consecuencia si no se atiende"],
      [
        ["Experiencia de usuario", "El médico escribe un diagnóstico por consulta y la lista debe aparecer mientras escribe; el recepcionista cambia de pantalla decenas de veces al día.", "Se abandona el buscador y se teclea el código de memoria, con el riesgo de registrar un diagnóstico equivocado."],
        ["Rendimiento del sistema", "Cada pulsación podía disparar una petición que recorría el catálogo completo en el servidor.", "El costo crece con el tamaño del catálogo y se multiplica por el número de usuarios concurrentes."],
        ["Eficiencia operativa", "El código CIE-10 es obligatorio en el RIPS y en la factura electrónica; un diagnóstico mal registrado se devuelve como glosa.", "Reproceso administrativo y demora en el pago de la cuenta por parte del pagador."],
      ],
      [1900, 4100, 3360],
      { nota: "Elaboración propia a partir del documento de requerimientos del proyecto y de la normativa de RIPS citada en el informe." }
    ),

    H2("Criterios de diseño"),
    P("Del análisis anterior se derivaron cinco criterios que guiaron el diseño y que se usan después como rúbrica de evaluación. Los dos primeros son los que la actividad exige medir; los tres restantes acotan las soluciones admisibles."),
    ...tabla(
      "Criterios de diseño y forma de verificarlos",
      ["Criterio", "Qué exige", "Cómo se verifica en este informe"],
      [
        ["Eficiencia", "Respuesta por debajo del umbral de 100 ms, incluso con el catálogo oficial.", "Experimento n1: latencia por consulta a cinco escalas."],
        ["Escalabilidad", "Que el costo no crezca de forma lineal con el tamaño del catálogo.", "Comparación de la pendiente de ambas estrategias en la Figura 5."],
        ["Accesibilidad", "Navegación utilizable con teclado y con lector de pantalla.", "Revisión del marcado: foco programático, `aria-current` y enlace de salto."],
        ["Seguridad", "Que ocultar una ruta no sea el mecanismo de control de acceso.", "El servidor revalida el rol en cada petición (`requiere_roles`)."],
        ["Mantenibilidad", "Agregar una pantalla no debe obligar a tocar el despachador.", "La tabla de rutas es declarativa; la vista se inyecta como función."],
      ],
      [1700, 3900, 3760],
      { nota: "Elaboración propia." }
    ),

    // ------------------------------------------------------------------ 3
    H1("Investigación y análisis"),
    H2("Estrategias de navegación en la literatura"),
    P("La literatura de arquitectura separa dos decisiones que suelen confundirse: *cómo se despacha* una solicitud de navegación y *cómo se resuelve* la búsqueda que esa pantalla necesita."),
    P("Para lo primero, Fowler (2002) describe el **Front Controller**: un único punto de entrada que recibe todas las solicitudes, decide qué controlador las atiende y concentra las tareas comunes —autorización, registro, manejo de errores— en vez de repetirlas en cada pantalla. La alternativa, un controlador por página, dispersa esas decisiones y hace que cada vista deba recordar validar el rol. Martin (2017) llega al mismo lugar desde la regla de dependencia: la política de navegación pertenece a una capa que no depende de los detalles de cada pantalla."),
    P("Para lo segundo, Manning et al. (2008) formalizan el **índice invertido**: en lugar de recorrer todos los documentos buscando un término, se guarda, para cada término, la lista de documentos que lo contienen; la consulta se resuelve intersecando listas, y el costo pasa a depender de la frecuencia del término y no del tamaño de la colección. Es la estructura que sostiene cualquier buscador, y la que convierte un recorrido lineal en una operación casi constante."),
    P("A esas dos decisiones se suma una tercera, propia de las interfaces que buscan mientras el usuario escribe: el **control del flujo de peticiones**. Tidwell et al. (2020) y Krug (2014) coinciden en que la búsqueda incremental solo funciona si el sistema no castiga al usuario por escribir rápido; de ahí las técnicas de retardo (*debounce*) y de descarte de respuestas que llegan fuera de orden."),

    H2("Enfoques en sistemas reales"),
    P("Los tres dominios que la actividad propone como referencia resuelven el mismo problema con énfasis distintos, y de cada uno se tomó una decisión concreta:"),
    ...tabla(
      "Estrategias de navegación en sistemas reales y decisión adoptada",
      ["Sistema de referencia", "Estrategia característica", "Qué se adoptó en «Salud Integral»"],
      [
        ["Aplicaciones de mapas", "Jerarquía y preprocesamiento: el grafo se indexa una vez para que la consulta sea barata.", "El índice del catálogo se construye al arrancar, no en cada consulta."],
        ["Comercio electrónico", "Catálogo por categorías más buscador, con migas de pan y resultados paginados.", "Rutas padre/hijo para el contexto y recorte perezoso de los resultados."],
        ["Buscadores y sistemas de recomendación", "Índice invertido con intersección de listas y ordenamiento por relevancia.", "Índice de prefijos; los resultados cuyo código coincide se muestran primero."],
      ],
      [2500, 3600, 3260],
      { nota: "Elaboración propia a partir de Manning et al. (2008), Fowler (2002) y Tidwell et al. (2020)." }
    ),
    P("La conclusión del análisis es que el problema no exige una arquitectura nueva, sino hacer explícitas dos piezas que el sistema ya insinuaba: un despachador único de rutas y una estrategia de búsqueda intercambiable. Ambas se modelan a continuación."),

    // ------------------------------------------------------------------ 4
    H1("Diseño y modelado arquitectónico"),
    P("Se presentan cuatro vistas UML. La de componentes muestra la estructura; la de clases, la lógica interna; la de secuencia, el flujo de navegación en el tiempo; y la de actividad, las decisiones que el despachador toma en cada cambio de ruta. Los diagramas se generan con el guion `docs/uml/render_navegacion.py` y sus fuentes están versionadas en el repositorio."),

    H2("Vista de componentes"),
    P("La Figura 1 separa el navegador del servidor y, dentro de cada uno, aísla la pieza que concentra las decisiones. En el cliente, la dirección (`#/ruta/parámetro`) es la única fuente de verdad sobre dónde está el usuario: el menú no guarda estado, solo escribe direcciones, y el despachador reacciona al cambio. En el servidor, el servicio de catálogo no sabe cómo se resuelve la búsqueda: depende de una interfaz y recibe la implementación concreta en el arranque."),
    ...figura(
      "Diagrama de componentes de la navegación del sistema",
      path.join(IMG, "08_componentes_navegacion.png"),
      345,
      "El menú solo escribe direcciones; el despachador decide. La validación del rol ocurre dos veces: en el cliente para no mostrar lo que no corresponde, y en el servidor como control real de acceso. Elaboración propia."
    ),

    H2("Vista de clases"),
    P("La Figura 2 modela las dos piezas. `TablaDeRutas` es una colección de objetos `Ruta`; cada uno declara su título, los roles que pueden verla, si está oculta del menú y cuál es su ruta padre —esa autorreferencia es la que permite las migas de pan sin una estructura aparte—. El `Despachador` consulta la tabla, autoriza y delega el dibujado en la función `montar` que la ruta declara."),
    P("Del lado del servidor, `Cie10Service` mantiene una referencia a `EstrategiaBusqueda` y nunca a una implementación concreta. `BusquedaSecuencial` y `BusquedaIndiceInvertido` son intercambiables porque cumplen el mismo contrato; esa es la condición que hace posible medir una contra otra sin modificar la API ni el frontend."),
    ...figura(
      "Diagrama de clases: tabla de rutas y estrategias de búsqueda",
      path.join(IMG, "09_clases_navegacion.png"),
      400,
      "La autorreferencia `padre` de la clase `Ruta` modela la jerarquía de pantallas. Las dos estrategias cumplen la misma interfaz. Elaboración propia."
    ),

    H2("Flujo de navegación en el tiempo"),
    P("La Figura 3 recorre el caso más exigente: el médico escribe «diab» en el buscador de diagnósticos. El marco `loop` muestra que cada pulsación reinicia el retardo de 250 ms, de modo que cuatro pulsaciones producen una sola petición. El marco `alt` del final recoge la decisión que evita el error más difícil de depurar en una búsqueda incremental: si mientras llega la respuesta el usuario ya escribió otra cosa, la respuesta se descarta en vez de pintarse."),
    ...figura(
      "Diagrama de secuencia: búsqueda incremental de un diagnóstico",
      path.join(IMG, "10_secuencia_navegacion.png"),
      445,
      "El retardo reduce las peticiones; el descarte evita que una respuesta tardía sobrescriba una más reciente. Elaboración propia."
    ),

    H2("Decisiones del despachador"),
    P("La Figura 4 formaliza lo que ocurre en cada cambio de ruta. Dos decisiones merecen atención. La primera: si la ruta no existe o el rol no la tiene permitida, no se muestra un error sino que se redirige a la pantalla de inicio de ese rol, de modo que una dirección pegada o un marcador viejo nunca dejan al usuario en una pantalla rota. La segunda: antes de montar, el despachador toma un turno (`version = ++version`); al terminar la carga, solo pinta si su turno sigue siendo el vigente. Es el mismo mecanismo de la búsqueda, aplicado a la pantalla completa."),
    ...figura(
      "Diagrama de actividad: resolución de una ruta",
      path.join(IMG, "11_actividad_navegacion.png"),
      330,
      "Las dos rutas punteadas son los caminos de excepción: respuesta obsoleta y error de carga. Ninguno deja al usuario sin navegación. Elaboración propia."
    ),

    // ------------------------------------------------------------------ 5
    H1("Patrones de diseño aplicados"),
    P("Los patrones no se eligieron por catálogo sino por la fuerza que debían resistir. La Tabla 4 los resume; los párrafos siguientes justifican los tres que sostienen la estrategia de navegación."),
    ...tabla(
      "Patrones de diseño aplicados a la navegación",
      ["Patrón", "Dónde está", "Qué problema resuelve"],
      [
        ["Front Controller\n(Fowler, 2002)", "`mostrar()` en `frontend/js/app.js`", "Un único punto decide ruta, permiso y turno; ninguna vista repite esas comprobaciones."],
        ["Strategy", "`EstrategiaBusqueda` y sus dos implementaciones", "Permite cambiar y medir el algoritmo de búsqueda sin tocar servicio, API ni cliente."],
        ["Iterator", "`buscar()` devuelve un iterador perezoso", "Evita construir resultados que la página no va a mostrar."],
        ["Composite", "Campo `padre` de la tabla de rutas", "Trata pantallas sueltas y anidadas de forma uniforme y da origen a las migas de pan."],
        ["Observer", "Escucha de `hashchange` y aviso de sesión vencida", "Desacopla quién cambia la dirección de quién reacciona al cambio."],
        ["Proxy", "`api.js` ante la API; `ProveedorProxy` ante la DIAN", "Centraliza token, errores y reintentos; el llamador no los conoce."],
        ["Repository", "`app/repositories/`", "Aísla el almacenamiento: cambiar memoria por SQL no afecta a la navegación."],
      ],
      [2000, 3200, 4160],
      { nota: "Las referencias de archivo corresponden al repositorio del proyecto. Elaboración propia." }
    ),

    H3("Front Controller"),
    P("La alternativa descartada era que cada vista comprobara el rol al montarse. Se descartó por una razón de seguridad y otra de mantenimiento: la comprobación repetida se olvida en la pantalla número once, y el día que cambie la regla hay que editar diecisiete archivos. Con un despachador único, agregar una pantalla es agregar una fila a la tabla de rutas."),
    H3("Strategy"),
    P("Es el patrón que hace posible este informe. Sin una interfaz común no habría forma de medir la implementación vieja contra la nueva sobre el mismo catálogo y las mismas consultas; se compararían dos sistemas distintos. La estrategia activa se decide en la raíz de composición (`container.py`), que es el único lugar del código que conoce ambas clases."),
    ...codigo([
      "class Cie10Service:",
      "    def __init__(self, catalogo=CIE10, estrategia=None):",
      "        self._estrategia = estrategia or BusquedaIndiceInvertido(catalogo)",
      "",
      "    def buscar(self, consulta, limite=20):",
      "        encontrados = sorted(self._estrategia.buscar(consulta), key=lambda t: (t[0], t[1]))",
      "        return [(codigo, desc) for _, codigo, desc in encontrados[:limite]]",
    ]),
    H3("Iterator"),
    P("`buscar()` de la estrategia devuelve un iterador, no una lista. El servicio ordena y recorta a veinte; los resultados restantes —que con una consulta corta pueden ser cientos— nunca se construyen como tuplas en memoria. El efecto es pequeño con el catálogo de muestra y deja de serlo con el oficial."),

    // ------------------------------------------------------------------ 6
    H1("Prototipo funcional"),
    P("El prototipo es el sistema completo, no un ejercicio aparte. Lo que esta unidad agregó fue la estrategia de búsqueda intercambiable y su medición; el resto de la navegación —tabla de rutas, menú por rol, rutas anidadas, retardo y descarte de respuestas— ya operaba y aquí se documentó, se modeló y se midió."),
    ...viñetas([
      "**Servidor.** Python 3 con FastAPI. Catálogo CIE-10 con una muestra de 149 códigos frecuentes en consulta externa; la medición usa catálogos sintéticos de hasta 30.000 entradas construidos con el mismo vocabulario clínico.",
      "**Cliente.** JavaScript de módulos nativos, sin framework ni dependencias de construcción. 17 rutas declaradas, 4 roles.",
      "**Repositorio.** `github.com/JNACHO2001/consultorio-medico`. La estrategia está en `backend/app/services/busqueda.py` y la medición en `backend/benchmarks/benchmark_navegacion.py`.",
      "**Despliegue.** La aplicación se publica en la nube como un único servicio que sirve la API y los archivos del cliente.",
    ]),
    P("Conviene declarar los límites del prototipo. El catálogo CIE-10 incluido es una **muestra**, no el catálogo oficial completo; los datos de pacientes son ficticios y viven en memoria, de modo que se pierden al reiniciar el servidor; y la facturación electrónica usa un proveedor tecnológico simulado. Ninguna de esas limitaciones afecta a lo que aquí se mide, porque la medición se hace sobre catálogos a escala real."),

    // ------------------------------------------------------------------ 7
    H1("Pruebas y resultados"),
    H2("Método"),
    P(`Se ejecutaron cuatro experimentos sobre la misma máquina y el mismo proceso. Las consultas son ${R.consultas.length} términos reales de consulta externa («diabetes», «hipertension», «a09», «infeccion urinaria», «lumbago», entre otros), que mezclan búsquedas por código y por descripción, cortas y largas. Cada medición se repite y se reporta la **mediana (p50)** y el **percentil 95 (p95)**, no el promedio, porque lo que degrada la experiencia es la cola lenta y no el caso típico. Los catálogos de más de 149 entradas son sintéticos: conservan el vocabulario de las descripciones reales para que el comportamiento del índice sea representativo.`),

    H2("Latencia de búsqueda"),
    P(`La Tabla 5 recoge el tiempo de una consulta completa —resolver, ordenar y recortar a veinte resultados— para cada estrategia y cada escala. Con el catálogo de muestra la diferencia es irrelevante: ${n(sec[0].p50_ms, 3)} ms contra ${n(idx[0].p50_ms, 3)} ms. Con el catálogo oficial (12.000 códigos) la búsqueda secuencial sube a ${n(sec[3].p50_ms, 2)} ms y el índice se mantiene en ${n(idx[3].p50_ms, 3)} ms: un factor de ${n(factor(3), 0)} veces.`),
    ...tabla(
      "Latencia por consulta según estrategia y tamaño del catálogo (milisegundos)",
      ["Códigos", "Secuencial p50", "Secuencial p95", "Índice p50", "Índice p95", "Mejora"],
      sec.map((f, i) => [
        miles(f.n), n(f.p50_ms, 3), n(f.p95_ms, 3), n(idx[i].p50_ms, 3), n(idx[i].p95_ms, 3), `${n(factor(i), 1)} ×`,
      ]),
      [1360, 1700, 1700, 1600, 1600, 1400],
      {
        alinear: [C, D, D, D, D, D],
        nota: `Mediana y percentil 95 de ${R.consultas.length} consultas distintas, 30 repeticiones. Medición propia con benchmark_navegacion.py.`,
      }
    ),
    P(`La Figura 5 muestra por qué la diferencia importa: la curva de la estrategia secuencial es una recta que crece con el catálogo, mientras que la del índice es prácticamente plana. No se trata de que una sea «más rápida», sino de que una depende del tamaño del catálogo y la otra no. A ${miles(grande(sec).n)} códigos —escala que un catálogo oficial ampliado alcanzaría sin dificultad— la separación llega a ${n(factor(ultimo), 0)} veces.`),
    ...figura(
      "Latencia por consulta frente al tamaño del catálogo",
      path.join(FIG, "fig5_latencia.png"),
      420,
      "Escala logarítmica en el eje vertical. La línea punteada marca el umbral de 100 ms de respuesta inmediata (Card et al., 1991). Medición propia."
    ),

    H2("Costo por pulsación y efecto del retardo"),
    P(`El experimento n2 mide lo que cuesta escribir «diabetes» letra a letra sobre el catálogo de 12.000 códigos. Sin el retardo del frontend, cada una de las ${pulsSec.pulsaciones} pulsaciones dispara una consulta; con el retardo, solo la última llega al servidor. Las dos técnicas se suman: el retardo recorta el número de peticiones y el índice recorta el costo de cada una.`),
    ...tabla(
      "Costo de escribir una palabra de ocho letras (catálogo de 12.000 códigos)",
      ["Estrategia", "Sin retardo (8 consultas)", "Con retardo (1 consulta)", "Reducción"],
      [
        ["Secuencial", `${n(pulsSec.sin_debounce_p50_ms, 1)} ms`, `${n(pulsSec.con_debounce_p50_ms, 1)} ms`,
          `${n(pulsSec.sin_debounce_p50_ms / pulsSec.con_debounce_p50_ms, 1)} ×`],
        ["Índice invertido", `${n(pulsIdx.sin_debounce_p50_ms, 2)} ms`, `${n(pulsIdx.con_debounce_p50_ms, 2)} ms`,
          `${n(pulsIdx.sin_debounce_p50_ms / pulsIdx.con_debounce_p50_ms, 1)} ×`],
        ["Reducción entre estrategias",
          `${n(pulsSec.sin_debounce_p50_ms / pulsIdx.sin_debounce_p50_ms, 0)} ×`,
          `${n(pulsSec.con_debounce_p50_ms / pulsIdx.con_debounce_p50_ms, 0)} ×`, "—"],
      ],
      [2560, 2400, 2400, 2000],
      { alinear: [AlignmentType.LEFT, D, D, D], nota: "Mediana de 30 repeticiones. El retardo del cliente es de 250 ms. Medición propia." }
    ),

    H2("Costo de construir el índice"),
    P(`El índice no es gratis: se construye al arrancar y ocupa memoria. La Tabla 7 muestra que ese costo es asumible —${n(constr.construccion_p50_ms, 0)} ms y ${miles(constr.claves)} claves para ${miles(constr.n)} códigos— y, sobre todo, que se paga **una sola vez** por proceso, mientras que el costo de la búsqueda secuencial se paga en cada pulsación de cada usuario. Es el intercambio clásico entre preprocesamiento y consulta que describen Manning et al. (2008).`),
    ...tabla(
      "Costo de construcción y tamaño del índice invertido",
      ["Códigos del catálogo", "Construcción (p50, ms)", "Claves del índice", "Claves por código"],
      R.n3_construccion.map((f) => [
        miles(f.n), n(f.construccion_p50_ms, 1), miles(f.claves), n(f.claves / f.n, 1),
      ]),
      [2560, 2500, 2300, 2000],
      { alinear: [C, D, D, D], nota: "El índice guarda todos los prefijos de cada palabra hasta doce caracteres. Medición propia." }
    ),

    H2("Profundidad de navegación"),
    P(`El experimento n4 no mide tiempo sino estructura: lee la tabla de rutas del frontend y calcula, para cada rol, cuántas pantallas ve y cuántos pasos necesita para llegar a cada una. El resultado confirma la decisión de filtrar el menú por rol: de las ${prof._rutas_declaradas} rutas declaradas, ningún rol ve más de ${Math.max(...["RECEPCION", "MEDICO", "ADMINISTRADOR", "LABORATORIO"].map((r) => prof[r].en_menu))} opciones en su menú, y **ninguna pantalla está a más de dos pasos**: las pantallas anidadas se alcanzan desde su pantalla padre, que sí está en el menú.`),
    ...tabla(
      "Pantallas y pasos de navegación por rol",
      ["Rol", "Pantallas habilitadas", "En el menú", "Anidadas", "Pasos máximos", "Ocultas al rol"],
      ["RECEPCION", "MEDICO", "ADMINISTRADOR", "LABORATORIO"].map((r) => [
        r.charAt(0) + r.slice(1).toLowerCase(),
        String(prof[r].pantallas_totales), String(prof[r].en_menu), String(prof[r].anidadas),
        String(prof[r].pasos_maximo), String(prof[r].ocultas_por_rol),
      ]),
      [2160, 1900, 1400, 1300, 1400, 1200],
      { alinear: [AlignmentType.LEFT, C, C, C, C, C], nota: "Calculado automáticamente a partir de la tabla de rutas de `frontend/js/app.js`. Medición propia." }
    ),
    P("La última columna es la que sostiene el criterio de seguridad: el laboratorio no ve dieciséis de las diecisiete pantallas. Pero ocultarlas es una decisión de interfaz, no de control de acceso; si ese usuario escribe la dirección de otra pantalla, el despachador lo devuelve a la suya y, aunque no lo hiciera, el servidor rechazaría la petición."),

    H2("Pruebas automáticas"),
    P(`La suite del proyecto ejecuta **${R.pruebas.total} pruebas** y pasa completa tras el cambio de estrategia. Esa es la verificación de que el intercambio fue transparente: ninguna prueba de la API, de los servicios ni de los repositorios tuvo que modificarse, porque la interfaz pública de \`Cie10Service\` no cambió. Las pruebas cubren, entre otras cosas, la búsqueda por código y por descripción sin tildes, el recorte al límite de resultados y el rechazo de la consulta vacía.`),

    // ------------------------------------------------------------------ 8
    H1("Discusión y oportunidades de mejora"),
    P("Los resultados respaldan la estrategia elegida, pero conviene leerlos con sus límites. La medición se hizo **en proceso**, sin red: aísla el costo del algoritmo, que es lo que se quería comparar, pero el usuario percibe además la latencia de la red y la del navegador. Con el índice, el algoritmo deja de ser el factor dominante; con la estrategia secuencial a 12.000 códigos, sí lo era."),
    P("De ahí se desprenden las mejoras pendientes, en orden de rendimiento esperado:"),
    ...viñetas([
      "**Cargar el catálogo oficial.** Es la limitación más visible del prototipo. La medición ya demuestra que la arquitectura lo soporta; falta la fuente de datos y su proceso de actualización.",
      "**Caché de consultas frecuentes.** Un *Proxy* con memoria sobre la estrategia evitaría recalcular los prefijos cortos, que son los más repetidos entre todos los usuarios.",
      "**Memoria del índice.** Guardar todos los prefijos es rápido pero generoso en memoria; un árbol de prefijos (trie) daría el mismo resultado con menos claves, a cambio de un recorrido más complejo.",
      "**Historial de navegación con deshacer.** El patrón Command permitiría registrar los saltos entre pantallas y ofrecer «volver» dentro de la aplicación, no solo con el botón del navegador.",
      "**Medición con usuarios reales.** Todo lo medido aquí es técnico. Falta observar a un médico usando el buscador en consulta: cuántas veces abandona, cuántas teclea el código de memoria.",
    ]),

    // ------------------------------------------------------------------ 9
    H1("Conclusiones"),
    P(`**Sobre el problema.** La navegación de «Salud Integral» tiene dos caras —estructural y por contenido— y ambas se resolvieron con el mismo principio: concentrar la decisión en un punto y preparar de antemano lo que la consulta necesita. La estructural ya estaba resuelta y se documentó; la de contenido se midió y se corrigió.`),
    P(`**Sobre el diseño.** Los cuatro modelos UML no describen un sistema distinto del que está en el repositorio: describen el que corre. El valor del ejercicio no fue dibujar, sino que dibujar obligó a hacer explícitas dos piezas que estaban implícitas en el código —el despachador y la estrategia— y solo al hacerlas explícitas fue posible medirlas.`),
    P(`**Sobre los patrones.** Strategy fue el patrón decisivo, y no por elegancia: sin una interfaz común no habría existido una comparación honesta entre la implementación anterior y la nueva. Front Controller e Iterator resolvieron, respectivamente, la dispersión de las comprobaciones de permiso y el costo de construir resultados que nadie iba a ver.`),
    P(`**Sobre los resultados.** Con el catálogo de muestra las dos estrategias son indistinguibles; con el catálogo oficial el índice es ${n(factor(3), 0)} veces más rápido, y a ${miles(grande(sec).n)} códigos, ${n(factor(ultimo), 0)} veces. La estrategia secuencial cruza el umbral de los 100 ms de respuesta inmediata, y el índice no lo cruza en ninguna de las escalas probadas. Sumado al retardo del cliente, escribir una palabra completa pasó de ${n(pulsSec.sin_debounce_p50_ms, 0)} ms a ${n(pulsIdx.con_debounce_p50_ms, 2)} ms de cómputo.`),
    P(`**Sobre la validez.** Las ${R.pruebas.total} pruebas automáticas pasan sin modificación, lo que confirma que el cambio fue interno. Pero la evaluación es técnica: queda pendiente la validación con usuarios reales, que es la única capaz de decir si el tiempo ganado se traduce en una mejor consulta médica.`),
  ];
};
