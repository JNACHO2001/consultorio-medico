# Consultorio Médico "Salud Integral"

**Creado por José Ignacio Gómez Guzmán**

Prototipo de un sistema web para centralizar y proteger la información de pacientes, citas e historias clínicas de un consultorio médico pequeño. Proyecto de la actividad de arquitectura de software: análisis de requisitos, diagramas UML, patrones de diseño y prototipo listo para la nube.

- **Backend:** Python 3.12+ con FastAPI.
- **Frontend:** JavaScript puro (módulos ES), sin paso de compilación. FastAPI lo sirve en la raíz (`/`).
- **Módulo de ingresos y facturación (estilo "mini salud facil"):** lista de todos los pacientes, ingreso del paciente, procedimientos realizados que quedan en su historia clínica y facturación por procedimiento.
- **Módulo de IPS:** pagadores y convenios (EPS, ARL, SOAT) con tarifa pactada, copago, cuota moderadora y autorización; cartera con radicación, abonos, glosas y antigüedad; borrador de RIPS con validación de datos.
- **Órdenes y resultados:** el médico solicita exámenes (laboratorio, imagenología, ECG) con diagnóstico CIE-10; apoyo diagnóstico registra los resultados con valores de referencia y el servicio se carga a la cuenta.
- **Facturación electrónica y caja:** factura electrónica y notas crédito con CUFE/CUDE, XML UBL 2.1 simplificado y estado por documento (proveedor tecnológico **simulado**); recibos de caja con consecutivo, apertura y cierre de caja con diferencia y facturación a terceros (la EPS como adquirente).
- **Patrón principal:** Repository. Los datos viven en **listas de objetos en memoria**, accedidas solo a través de interfaces de repositorio.

> Prototipo académico. Los pacientes y usuarios de demostración son ficticios. Los datos se pierden al reiniciar el servidor.

**Aplicación en línea:** <https://consultorio-medico-pty2.onrender.com>. En el plan gratuito el servicio se suspende si no se usa; la primera visita puede tardar unos segundos.

## Qué hace el sistema

| Área | Funciones |
|---|---|
| **Pacientes** | Registro, búsqueda y actualización, con documento único; historia clínica por paciente. |
| **Agenda** | Citas con horarios libres, control de cruces, reprogramación y cancelación; recordatorios simulados 24 horas antes. |
| **Consulta médica** | Registro de la consulta, cierre y notas aclaratorias (una consulta cerrada no se modifica); diagnóstico con catálogo CIE-10. |
| **Ingreso y cuenta** | Admisión y egreso con convenio y autorización; procedimientos realizados con catálogo y tarifas, que quedan en la historia clínica. |
| **Órdenes y resultados** | El médico solicita exámenes de laboratorio, imagenología o ECG; apoyo diagnóstico registra los resultados con valores de referencia y el servicio se carga a la cuenta. |
| **Facturación y caja** | Facturación por procedimiento, pago y anulación; apertura y cierre de caja con diferencia y recibos consecutivos. |
| **Pagadores y cartera** | Convenios con EPS, ARL y SOAT (tarifa, copago, cuota moderadora); radicación, abonos, glosas y antigüedad de cartera. |
| **Factura electrónica** | Factura y notas crédito con CUFE/CUDE y XML descargable, con proveedor tecnológico simulado. |
| **RIPS** | Borrador en JSON con validación de datos. |
| **Seguridad y control** | Usuarios con roles, bitácora de auditoría, contraseñas cifradas y sesiones que vencen. |

## A quién va dirigido

| Quién | Cómo lo usa |
|---|---|
| **Consultorio médico pequeño** (médico independiente o grupo de pocos médicos) | Agenda, historia clínica, consultas y cobro. Puede ignorar los módulos de IPS. |
| **Centro médico o IPS pequeña** | Además: ingresos, órdenes de laboratorio, convenios con EPS, cartera con glosas, caja y facturación electrónica. |
| **Recepción y caja** | Pacientes, citas, facturación, cobros, caja y cartera. Sin acceso a información clínica. |
| **Médicos** | Su agenda, las consultas, la historia clínica, los procedimientos, el diagnóstico y las órdenes de sus pacientes. |
| **Laboratorio o apoyo diagnóstico** | Cola de órdenes y registro de resultados. |
| **Administración** | Usuarios, catálogo, convenios, cartera, RIPS, auditoría y consulta de documentos electrónicos y turnos de caja. |
| **Estudiantes y docentes** | Ejemplo de arquitectura por capas con patrón Repository, UML, pruebas automáticas y despliegue en la nube. |

> **Antes de usarlo con pacientes reales** hacen falta una base de datos con copias de seguridad (hoy los datos viven en memoria), un proveedor tecnológico autorizado para la facturación electrónica, un servidor siempre activo con HTTPS y la revisión legal de la protección de datos de salud y de la historia clínica. Ver *Alcance del prototipo*.

## Cómo ejecutarlo

Requisitos: Python 3.12 o superior.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:crear_app --factory --reload
```

Abra <http://localhost:8000>. La documentación interactiva de la API está en <http://localhost:8000/docs> y el estado del sistema en <http://localhost:8000/health>.

### Con Docker

```bash
docker build -t consultorio-medico .
docker run --rm -p 8000:8000 consultorio-medico
```

### Usuarios de demostración

La contraseña de todos es `Salud2026*`.

| Usuario | Rol | Qué puede hacer |
|---|---|---|
| `recepcion1`, `recepcion2` | Recepción | Listar y registrar pacientes, agendar citas, **ingresar pacientes con su convenio, abrir caja, facturar, cobrar el copago, emitir la factura electrónica y notas crédito, radicar facturas y gestionar abonos y glosas**. No ve información clínica. |
| `dr.perez`, `dra.gomez`, `dr.rojas`, `dra.torres` | Médico | Ver su agenda, atender citas, registrar y cerrar consultas, agregar notas aclaratorias, ver historias clínicas, **registrar procedimientos y el diagnóstico CIE-10 de sus pacientes ingresados y dar el egreso**. |
| `lab1` | Apoyo diagnóstico | Ver la cola de órdenes de laboratorio, imagenología y diagnóstico, y registrar sus resultados. No ve la historia clínica completa. |
| `admin` | Administrador | Crear y desactivar usuarios, consultar la bitácora de auditoría, ver y procesar recordatorios, gestionar el catálogo (con CUPS), **pagadores y convenios**, **cartera y glosas**, generar el **borrador de RIPS**, consultar facturas, **documentos electrónicos y turnos de caja**. |

Una prueba rápida de citas: entre como `recepcion1`, vaya al día siguiente y agende una cita; luego entre como `dr.perez`, abra su agenda del día siguiente y atienda esa cita.

Prueba rápida de ingresos y facturación: como `recepcion1` abra *Pacientes*, elija uno y pulse *Ingresar paciente* (médico `Dr. Andrés Pérez`); salga y entre como `dr.perez`, abra *Ingresos* → *Abrir cuenta* y use *Registrar procedimiento* varias veces; vuelva como `recepcion1`, abra la cuenta del ingreso, pulse *Facturar pendientes*, genere la factura y *Registre el pago*.

Prueba rápida de convenios y cartera: como `recepcion1` ingrese un paciente con el convenio *EPS Demo B · Subsidiado* (pide número de autorización); como `dr.perez` registre procedimientos y un diagnóstico (por ejemplo `R074`); como `recepcion1` facture, cobre el copago al paciente, *Radique al pagador*, registre un abono y una glosa y respóndala; en *Cartera y glosas* vea la antigüedad. Como `admin`, abra *RIPS*, genere el borrador del mes y descárguelo en JSON.

Prueba rápida de órdenes y facturación electrónica: como `dr.perez` abra la cuenta de un ingreso, registre el diagnóstico buscando en el catálogo CIE-10 y use *Nueva orden*; entre como `lab1` y *Registre el resultado*; como `recepcion1` abra *Caja*, facture, *Emita la factura electrónica*, cobre el copago (sale un recibo `RC-…`), radique, registre y acepte una glosa y emita su nota crédito; cierre la caja contando el efectivo.

### Reglas del módulo de IPS

| Regla | Descripción |
|---|---|
| RN-14 | El valor de un procedimiento es la tarifa base por el porcentaje del convenio; se copia al registrarlo. |
| RN-15 | La cuenta se reparte entre paciente (copago % + cuota moderadora, una vez por ingreso) y pagador. |
| RN-16 | Un convenio que exige autorización pide el número al ingresar al paciente. |
| RN-17 | Una factura con pagos recibidos o ya radicada no se puede anular. |
| RN-18 | El pagador solo abona sobre facturas radicadas y hasta su saldo libre de glosas en disputa. |
| RN-19 | Solo se glosan facturas radicadas; la glosa pasa de abierta a respondida y termina aceptada o levantada. |
| RN-20 | No se da el egreso mientras haya órdenes solicitadas sin resultado. |
| RN-21 | Al registrar un resultado, el servicio se carga a la cuenta con el precio del convenio. |
| RN-22 | Sin factura electrónica aceptada no se radica una factura al pagador. |
| RN-23 | Una factura con factura electrónica aceptada se anula con una nota crédito; una glosa aceptada tiene una sola nota crédito. |
| RN-24 | Cada cajero tiene como máximo una caja abierta. |
| RN-25 | Cobrar al paciente exige una caja abierta; cada pago recibido genera un recibo con consecutivo. |
| RN-26 | Al cerrar la caja, el efectivo contado se compara con base + cobros en efectivo; una diferencia exige observaciones. |

Endpoints nuevos: `/api/pagadores`, `/api/convenios`, `/api/cartera`, `/api/rips`, `/api/facturas/{id}/radicar`, `/pagos-pagador`, `/glosas`, `/api/ingresos/{id}/diagnostico`, `/api/ordenes`, `/api/cie10`, `/api/electronica/...` (emitir, reintentar, notas crédito, descarga del XML) y `/api/caja/...` (apertura, cierre, turnos). Los valores son pesos colombianos enteros.

### Pruebas automáticas

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

Son 155 pruebas: contrato de los repositorios, reglas de negocio (documento único, cruce de citas, consulta cerrada, un ingreso abierto por paciente, valor congelado, factura única por procedimiento, tarifas y copagos por convenio, radicación, abonos, glosas, RIPS, órdenes y resultados, CUFE y XML, rechazos y reintentos, notas crédito, recibos y caja), permisos por rol, sesiones y bitácora.

### Configuración

Variables de entorno opcionales (ver `.env.example`): `SECRET_KEY`, `TZ_CONSULTORIO`, `JORNADA_INICIO`, `JORNADA_FIN`, `DURACION_CITA_MIN`, `TOKEN_MINUTOS`, `RECORDATORIO_HORAS`, `SEMBRAR_DATOS_DEMO`, `RECORDATORIOS_AUTOMATICOS`, `IPS_NOMBRE`, `IPS_NIT`, `IPS_CODIGO_HABILITACION` (datos del prestador que salen en el RIPS y la factura electrónica), `DIAN_AMBIENTE`, `DIAN_PREFIJO`, `DIAN_RESOLUCION`, `DIAN_RANGO_DESDE`, `DIAN_RANGO_HASTA`, `DIAN_CLAVE_TECNICA`, `DIAN_PIN_SOFTWARE`, `DIAN_OBLIGATORIA` y `CAJA_OBLIGATORIA`. Defina `SECRET_KEY` en cualquier despliegue real; si no, se genera una al arrancar y las sesiones se pierden al reiniciar.

## Arquitectura

```
Navegador (frontend/)  ──HTTP/JSON──►  API REST (app/api)  ──►  Servicios (app/services)
                                                                       │
                                                                       ▼
                                                    Interfaces de repositorio (app/repositories/interfaces.py)
                                                                       │
                                                                       ▼
                                                Implementaciones en memoria (app/repositories/memoria.py)
```

| Capa | Responsabilidad |
|---|---|
| `api/` | Rutas FastAPI, validación de entrada, permisos por rol y traducción de errores a HTTP. |
| `services/` | Lógica de negocio: reglas de las citas, consultas, autenticación, recordatorios. No sabe dónde se guardan los datos. |
| `repositories/` | `IRepository[T]` y una interfaz por entidad. `MemoryXRepository` guarda copias de los objetos en listas y hace borrado lógico. |
| `domain/` | Entidades (`Paciente`, `Cita`, `Consulta`…) y excepciones de negocio. |
| `core/` | Seguridad (hash de contraseñas, JWT), auditoría, zona horaria y contexto del usuario. |
| `container.py` | Único lugar donde se eligen las implementaciones concretas y se conectan los servicios. |

### Por qué el patrón Repository

Los servicios dependen de interfaces (`IPacienteRepository`, `ICitaRepository`…), no de cómo se almacenan los datos. Por eso:

- Para pasar a una base de datos real basta con escribir clases `Sql…Repository` que cumplan las mismas interfaces y cambiarlas en `container.py`; los servicios, la API y el frontend no se modifican.
- Las pruebas usan los repositorios en memoria sin preparar ninguna base de datos.
- La **auditoría** (quién consultó o modificó datos de pacientes) se dispara desde los repositorios de pacientes y consultas, así no depende de que cada servicio se acuerde de registrarla.
- `desactivar()` hace borrado lógico: no existe eliminación física de pacientes ni consultas.

### Otros patrones y decisiones

- **Health Endpoint Monitoring:** `/health` informa el estado de los componentes sin autenticación, para que la plataforma en la nube detecte fallas.
- **Control de acceso por rol (RBAC):** cada ruta declara los roles permitidos; recepción no puede leer datos clínicos.
- **Notificador simulado:** los recordatorios se programan 24 horas antes de cada cita y un proceso en segundo plano los "envía" (no sale ningún correo real).
- **Seguridad:** contraseñas con PBKDF2-SHA256, sesiones con JWT que vencen y se pueden revocar al cerrar sesión, respuestas de la API con `Cache-Control: no-store`, todo el texto del frontend se inserta sin `innerHTML`.

## Alcance del prototipo

Implementado: registro, listado completo, búsqueda y actualización de pacientes; ingreso (admisión) y egreso; procedimientos realizados con catálogo y tarifas, que quedan en la historia clínica; facturación por procedimiento con pago y anulación; pagadores y convenios; cartera con radicación, abonos, glosas y antigüedad; borrador de RIPS; órdenes y resultados de apoyo diagnóstico con catálogo CIE-10; factura electrónica y notas crédito simuladas; recibos y cierre de caja; agenda con horarios libres, cruce de citas, reprogramación y cancelación; consultas médicas con cierre y notas aclaratorias; historia clínica; usuarios y roles; bitácora de auditoría; recordatorios simulados.

No implementado (queda como trabajo futuro):

- **RF-09, adjuntar documentos** a la historia clínica.
- **RF-14, reportes** de gestión.
- **Transmisión real a la DIAN:** la facturación electrónica usa un proveedor tecnológico **simulado**. Calcula el CUFE/CUDE (SHA-384) y genera un XML UBL 2.1 simplificado, pero no lo firma (XAdES), no usa certificado digital ni resolución de numeración reales, y su respuesta no tiene validez tributaria. Para producción se escribe un adaptador de `IProveedorTecnologico` con un proveedor autorizado.
- Validación oficial del RIPS ante el Ministerio de Salud; el RIPS es un borrador.
- Catálogos completos: el CIE-10 es una muestra de 149 códigos y los CUPS de la demostración son ejemplos.
- Hospitalización con camas, inventario y nómina.
- Persistencia real: al reiniciar, los datos vuelven a los de demostración.
- Un solo proceso: con varios procesos cada uno tendría sus propios datos en memoria.
- Envío real de correos o mensajes.

## Estructura del repositorio

```
.
├── backend/
│   ├── app/
│   │   ├── api/            rutas, esquemas, permisos y errores HTTP
│   │   ├── core/           seguridad, auditoría, tiempo, contexto
│   │   ├── domain/         entidades y excepciones
│   │   ├── repositories/   interfaces y implementaciones en memoria
│   │   ├── services/       lógica de negocio
│   │   ├── config.py       configuración por variables de entorno
│   │   ├── container.py    composición de dependencias
│   │   ├── main.py         aplicación FastAPI
│   │   └── seed.py         datos de demostración
│   ├── tests/              pruebas con pytest
│   └── requirements*.txt
├── frontend/               HTML, CSS y JavaScript (módulos ES)
├── docs/uml/               diagramas PlantUML (fuente, PNG y SVG) y su explicación
├── Dockerfile
├── render.yaml             despliegue en Render
└── .env.example
```

## Documentación

El informe técnico está en [`docs/informe/Informe_Salud_Integral.pdf`](docs/informe/Informe_Salud_Integral.pdf).

Los diagramas UML (casos de uso, clases de dominio, clases con el patrón Repository, secuencia de agendar una cita y despliegue) están en [`docs/uml/`](docs/uml/README.md) con su descripción y justificación.

## Despliegue en la nube

El repositorio incluye `Dockerfile` y `render.yaml`. En Render: *New → Blueprint*, elegir este repositorio y aplicar. La plataforma construye la imagen, genera `SECRET_KEY` y usa `/health` para verificar el servicio. Cualquier plataforma que ejecute contenedores (Railway, Fly.io, Google Cloud Run) sirve con el mismo `Dockerfile`; el puerto se toma de la variable `PORT`.
