# Consultorio Médico "Salud Integral"

**Creado por José Ignacio Gómez Guzmán**

Prototipo de un sistema web para centralizar y proteger la información de pacientes, citas e historias clínicas de un consultorio médico pequeño. Proyecto de la actividad de arquitectura de software: análisis de requisitos, diagramas UML, patrones de diseño y prototipo listo para la nube.

- **Backend:** Python 3.12+ con FastAPI.
- **Frontend:** JavaScript puro (módulos ES), sin paso de compilación. FastAPI lo sirve en la raíz (`/`).
- **Módulo de ingresos y facturación (estilo "mini salud facil"):** lista de todos los pacientes, ingreso del paciente, procedimientos realizados que quedan en su historia clínica y facturación por procedimiento.
- **Patrón principal:** Repository. Los datos viven en **listas de objetos en memoria**, accedidas solo a través de interfaces de repositorio.

> Prototipo académico. Los pacientes y usuarios de demostración son ficticios. Los datos se pierden al reiniciar el servidor.

**Aplicación en línea:** <https://consultorio-medico-pty2.onrender.com>. En el plan gratuito el servicio se suspende si no se usa; la primera visita puede tardar unos segundos.

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
| `recepcion1`, `recepcion2` | Recepción | Listar y registrar pacientes, agendar citas, **ingresar pacientes, facturar y cobrar procedimientos**. No ve información clínica. |
| `dr.perez`, `dra.gomez`, `dr.rojas`, `dra.torres` | Médico | Ver su agenda, atender citas, registrar y cerrar consultas, agregar notas aclaratorias, ver historias clínicas, **registrar procedimientos a sus pacientes ingresados y dar el egreso**. |
| `admin` | Administrador | Crear y desactivar usuarios, consultar la bitácora de auditoría, ver y procesar recordatorios, gestionar el catálogo de procedimientos y tarifas, consultar facturas. |

Una prueba rápida de citas: entre como `recepcion1`, vaya al día siguiente y agende una cita; luego entre como `dr.perez`, abra su agenda del día siguiente y atienda esa cita.

Prueba rápida de ingresos y facturación: como `recepcion1` abra *Pacientes*, elija uno y pulse *Ingresar paciente* (médico `Dr. Andrés Pérez`); salga y entre como `dr.perez`, abra *Ingresos* → *Abrir cuenta* y use *Registrar procedimiento* varias veces; vuelva como `recepcion1`, abra la cuenta del ingreso, pulse *Facturar pendientes*, genere la factura y *Registre el pago*.

### Pruebas automáticas

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

Son 82 pruebas: contrato de los repositorios, reglas de negocio (documento único, cruce de citas, consulta cerrada, un ingreso abierto por paciente, valor congelado, factura única por procedimiento), permisos por rol, sesiones y bitácora.

### Configuración

Variables de entorno opcionales (ver `.env.example`): `SECRET_KEY`, `TZ_CONSULTORIO`, `JORNADA_INICIO`, `JORNADA_FIN`, `DURACION_CITA_MIN`, `TOKEN_MINUTOS`, `RECORDATORIO_HORAS`, `SEMBRAR_DATOS_DEMO`, `RECORDATORIOS_AUTOMATICOS`. Defina `SECRET_KEY` en cualquier despliegue real; si no, se genera una al arrancar y las sesiones se pierden al reiniciar.

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

Implementado: registro, listado completo, búsqueda y actualización de pacientes; ingreso (admisión) y egreso; procedimientos realizados con catálogo y tarifas, que quedan en la historia clínica; facturación por procedimiento con pago y anulación; agenda con horarios libres, cruce de citas, reprogramación y cancelación; consultas médicas con cierre y notas aclaratorias; historia clínica; usuarios y roles; bitácora de auditoría; recordatorios simulados.

No implementado (queda como trabajo futuro):

- **RF-09, adjuntar documentos** a la historia clínica.
- **RF-14, reportes** de gestión.
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
