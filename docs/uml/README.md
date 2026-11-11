# Diagramas UML – Sistema de Gestión "Salud Integral"

Los diagramas están escritos en [PlantUML](https://plantuml.com) y se derivan del *Documento de Levantamiento de Requerimientos* (casos de uso CU-01 a CU-12, requisitos RF/RNF y patrón Repository).

| Archivo | Diagrama | Imagen |
| --- | --- | --- |
| `01_casos_de_uso.puml` | Casos de uso | `img/01_casos_de_uso.png` |
| `02a_clases_dominio.puml` | Clases (1 de 2): modelo de dominio | `img/02a_clases_dominio.png` |
| `02b_clases_repository.puml` | Clases (2 de 2): servicios y patrón Repository | `img/02b_clases_repository.png` |
| `03_secuencia_agendar_cita.puml` | Secuencia: CU-04 Agendar cita | `img/03_secuencia_agendar_cita.png` |
| `04_despliegue.puml` | Despliegue en la nube | `img/04_despliegue.png` |
| `05_componentes_distribuido.dot` | Componentes: facturación electrónica distribuida (Unidad 2) | `img/05_componentes_distribuido.png` |
| `render_distribuido.py` | Secuencia: emitir con failover entre nodos (Unidad 2) | `img/06_secuencia_distribuida.png` |
| `07_despliegue_distribuido.dot` | Despliegue: API, nodos proveedor y red (Unidad 2) | `img/07_despliegue_distribuido.png` |

## Cómo generar las imágenes

Opción rápida: pegar el contenido de cada `.puml` en <https://www.plantuml.com/plantuml> y descargar el PNG o SVG.

Opción local (requiere Java y Graphviz):

```bash
java -jar plantuml.jar -tpng -o img *.puml
java -jar plantuml.jar -tsvg -o img *.puml
```

---

## 1. Diagrama de casos de uso

**Descripción.** Muestra los cuatro actores (recepcionista, médico, administrador y el servicio de notificaciones, externo) y los 19 casos de uso que cubren los requisitos funcionales (RF-04 se modela como variante de CU-02 y RF-14 queda como extensión futura). CU-13 a CU-16 son el módulo de ingresos y facturación: ingresar al paciente, registrar procedimientos, facturar y cobrar, y gestionar el catálogo de tarifas. CU-17 a CU-19 llevan el sistema al terreno de una IPS: pagadores y convenios (EPS, ARL, SOAT), cartera con radicación, abonos y glosas, y el borrador de RIPS. CU-20 y CU-21 son las órdenes y resultados de apoyo diagnóstico (con un cuarto actor: laboratorio), y CU-22 y CU-23 la facturación electrónica con notas crédito y la caja con sus recibos. Las relaciones `<<include>>` indican pasos reutilizados: Agendar cita incluye Buscar paciente y Enviar recordatorio; Registrar consulta incluye Consultar historia clínica. `<<extend>>` indica que Adjuntar documento es opcional dentro de Registrar consulta. Iniciar sesión (CU-01) lo incluyen todos los casos de uso excepto CU-10; esas flechas se omiten y se aclaran en una nota.

**Justificación.** Es el puente entre el análisis y el diseño: fija qué hace el sistema y quién lo usa antes de decidir cómo se construye. Evidencia la separación de responsabilidades por rol (RNF-01): la recepción no accede a los casos de uso clínicos (CU-07 a CU-09) y el administrador no atiende pacientes. Cada caso de uso se traza a un dolor del documento de requerimientos (sección 12).

**Requisitos que cubre:** RF-01 a RF-13 y RF-15 a RF-22 (ingreso, procedimientos, catálogo, facturación, convenios, cartera y RIPS).

## 2. Diagramas de clases

Se presentan dos vistas del mismo modelo para mantener la legibilidad.

### 2a. Modelo de dominio

**Descripción.** Entidades del negocio y sus relaciones: `Paciente` posee una `HistoriaClinica` que contiene `Consulta`s y los `ProcedimientoRealizado`s; el paciente es admitido en un `Ingreso`, cuya cuenta acumula procedimientos que se cobran en una `Factura` con sus `LineaFactura`. El ingreso se atiende bajo un `Convenio` de un `Pagador` (EPS, ARL, SOAT…): la factura copia sus condiciones, reparte el valor entre paciente y pagador, recibe `PagoFactura` y puede recibir `Glosa`s; cada `Consulta` surge de una `Cita`, la registra un `Medico` (especialización de `Usuario`) y puede tener `NotaAclaratoria` y `DocumentoAdjunto`. `OrdenClinica` (con sus `ResultadoValor`) cuelga del ingreso; `DocumentoElectronico` (factura electrónica o nota crédito, con su `EventoDocumento`) cuelga de la factura y `Caja` agrupa los recibos que recibe un cajero. `RegistroAuditoria` guarda quién hizo cada acción. `Rol` y `EstadoCita` son enumeraciones.

**Justificación.** Traduce las reglas de negocio a estructura: la identidad única del paciente por tipo y número de documento (RN-01), la imposibilidad de modificar una consulta cerrada (RN-04, resuelta con `NotaAclaratoria`), que el valor de un procedimiento se congele al registrarlo (RN-10) y que se facture una sola vez (RN-12), la tarifa pactada y el reparto de la cuenta entre paciente y pagador (RN-14, RN-15), que solo se glose lo radicado (RN-18, RN-19) y el control de acceso por rol (RNF-01). Separar `HistoriaClinica` de `Paciente` permite conservar el historial completo sin duplicar datos personales (D-02).

**Requisitos que cubre:** RF-01, RF-02, RF-05, RF-07 a RF-09, RF-11, RF-13; RN-01, RN-04.

### 2b. Servicios y patrón Repository

**Descripción.** Tres niveles: los servicios de aplicación (`PacienteService`, `CitaService`, `ConsultaService`, `IngresoService`, `FacturacionService`, `ConvenioService`, `CarteraService`, `RipsService`, `CatalogoService`, `NotificacionService`, `AutenticacionService`) contienen la lógica de negocio; las interfaces `I...Repository` definen cómo se obtienen y guardan los objetos de dominio; las clases `Memory...Repository` implementan esas interfaces y son las únicas que tocan el almacén (en el prototipo, listas de objetos en memoria; en producción se reemplazan por clases `Sql...Repository` sin cambiar los servicios). Todas las interfaces, salvo la de auditoría, extienden `IRepository<T>` con las operaciones comunes. Los repositorios de paciente, consulta, ingreso, procedimientos y factura registran cada acceso mediante `IAuditoriaRepository`.

**Justificación.** Es la aplicación directa del patrón Repository (Evans, 2003; Fowler, 2002): los servicios dependen de abstracciones, no de la base de datos, lo que permite:

- aplicar en un solo lugar la validación de documento único (RF-02) y el borrado lógico (RNF-11);
- disparar la auditoría desde el repositorio, de modo que ninguna pantalla pueda saltársela (RF-13);
- cambiar de motor de base de datos o de proveedor de nube sin tocar la lógica de negocio (RNF-10);
- probar las reglas con repositorios en memoria (RNF-09).

**Requisitos que cubre:** RF-02, RF-13, RNF-09, RNF-10, RNF-11.

## 3. Diagrama de secuencia: CU-04 Agendar cita

**Descripción.** Muestra la interacción, en orden temporal, entre la recepcionista, la interfaz web, la API, los servicios, los repositorios, la base de datos y el servicio de notificaciones. Tiene tres etapas: buscar al paciente (CU-03), consultar horarios libres y confirmar la cita. Un bloque `alt` modela la decisión central: si `existeCruce` indica que el horario ya está ocupado, el sistema responde con un conflicto (409) y propone otros horarios; si está libre, guarda la cita como "Programada" y programa el recordatorio.

**Justificación.** Se eligió este caso de uso porque resuelve el dolor D-03 (citas cruzadas) y recorre todas las capas de la arquitectura, de modo que evidencia el patrón Repository en acción: el servicio nunca consulta la base directamente, siempre pasa por `ICitaRepository` y `IPacienteRepository`. También muestra la validación de sesión y rol en la API (RNF-01).

**Requisitos que cubre:** RF-03, RF-05, RF-10, RNF-01; RN-02.

## 4. Diagrama de despliegue

**Descripción.** Muestra dónde se ejecuta cada parte del sistema: el navegador del usuario se conecta por HTTPS a un servidor de aplicación en la nube que aloja la interfaz web, la API con seguridad, los servicios y los repositorios. Los repositorios acceden a una base de datos relacional administrada y a un servicio de almacenamiento de archivos (documentos adjuntos). La base de datos se respalda cada día en un servicio de copias de seguridad. Los recordatorios salen hacia un servicio externo de correo o SMS.

**Justificación.** Demuestra que la arquitectura cumple los atributos de calidad que motivaron el proyecto: respaldos automáticos (D-04, RNF-05), disponibilidad (RNF-04), comunicación cifrada (RNF-02) y acceso desde un navegador sin instalación (RNF-10). Está dibujado sin atarse a un proveedor concreto; el proveedor y el servicio de cada nodo se definen al construir el prototipo.

**Requisitos que cubre:** RF-09, RF-10, RNF-02, RNF-04, RNF-05, RNF-10.

---

## Diagramas de la arquitectura distribuida (Unidad 2)

Se dibujan con Graphviz y Matplotlib, a color, ejecutando `python docs/uml/render_distribuido.py` (genera PNG y SVG en `img/`). Los diagramas 05 y 07 se guardan también como fuentes DOT.

### 5. Componentes

**Descripción.** El servidor de aplicación contiene el servicio de facturación electrónica, el `ProveedorProxy` (que implementa `IProveedorTecnologico`), el `MediadorNodos` con su circuit breaker, el `ClienteNodo` con pool de conexiones, el `BusEventos` con sus observadores y un hilo vigilante. Cada nodo proveedor es un proceso independiente con servidor TCP, pool de hilos, caché de idempotencia y el proveedor simulado.

**Justificación.** Separa lo que cambia (cuántos nodos y dónde están) de lo que no (el servicio de facturación). El proxy oculta la distribución; el mediador concentra el conocimiento de los nodos; el bus desacopla la observación.

### 6. Secuencia: emitir una factura electrónica con failover

**Descripción.** Recorre el camino completo: reserva del consecutivo con candado, envío fuera del candado, despacho al nodo A, y, si falla o está saturado, registro del fallo, espera con backoff y reintento en el nodo B con la misma clave de idempotencia. Los eventos se publican de forma asíncrona.

**Justificación.** Muestra la interacción entre nodos e hilos (hilo de conexión y pool de hilos en cada nodo) y cómo el sistema tolera la caída de un nodo sin perder ni duplicar documentos.

### 7. Despliegue

**Descripción.** El navegador usa HTTPS contra el servidor de aplicación (contenedor); este abre conexiones TCP con JSON por línea hacia los nodos, que pueden estar en la misma máquina o en hosts distintos. El proveedor tecnológico real (DIAN) queda como sistema externo futuro.

**Justificación.** Evidencia la distribución física y lógica y que agregar capacidad es agregar nodos y sus direcciones en `NODOS_PROVEEDOR`, sin tocar el código.

---

## Referencias

Evans, E. (2003). *Domain-driven design: Tackling complexity in the heart of software*. Addison-Wesley.

Fowler, M. (2002). *Patterns of enterprise application architecture*. Addison-Wesley.
