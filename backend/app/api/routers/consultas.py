from fastapi import APIRouter, Depends

from app.api.deps import contenedor, requiere_roles
from app.api.mapeos import consulta_out
from app.api.schemas import ConsultaIn, ConsultaOut, ConsultaUpdate, NotaIn
from app.container import Contenedor
from app.domain.modelos import Rol, Usuario

router = APIRouter(prefix="/api/consultas", tags=["Consultas médicas"])

# Todo el contenido clínico es exclusivo del médico (RNF-01, RN-03).
_medico = requiere_roles(Rol.MEDICO)


@router.post("", response_model=ConsultaOut, status_code=201, summary="Registrar consulta (CU-07)")
def registrar_consulta(
    datos: ConsultaIn, c: Contenedor = Depends(contenedor), medico: Usuario = Depends(_medico)
) -> ConsultaOut:
    consulta = c.consultas.registrar_consulta(
        datos.cita_id, medico, **datos.model_dump(exclude={"cita_id"})
    )
    return consulta_out(c, consulta)


@router.get(
    "/por-cita/{cita_id}",
    response_model=ConsultaOut,
    summary="Consulta asociada a una cita (404 si aún no se registra)",
)
def consulta_de_cita(
    cita_id: int, c: Contenedor = Depends(contenedor), medico: Usuario = Depends(_medico)
) -> ConsultaOut:
    return consulta_out(c, c.consultas.obtener_por_cita(cita_id, medico))


@router.get("/{consulta_id}", response_model=ConsultaOut, summary="Ver una consulta")
def obtener_consulta(
    consulta_id: int, c: Contenedor = Depends(contenedor), _: Usuario = Depends(_medico)
) -> ConsultaOut:
    return consulta_out(c, c.consultas.obtener_consulta(consulta_id))


@router.put("/{consulta_id}", response_model=ConsultaOut, summary="Editar una consulta abierta")
def actualizar_consulta(
    consulta_id: int,
    datos: ConsultaUpdate,
    c: Contenedor = Depends(contenedor),
    medico: Usuario = Depends(_medico),
) -> ConsultaOut:
    consulta = c.consultas.actualizar_consulta(
        consulta_id, medico, **datos.model_dump(exclude_unset=True)
    )
    return consulta_out(c, consulta)


@router.post("/{consulta_id}/cerrar", response_model=ConsultaOut, summary="Cerrar la consulta")
def cerrar_consulta(
    consulta_id: int, c: Contenedor = Depends(contenedor), medico: Usuario = Depends(_medico)
) -> ConsultaOut:
    return consulta_out(c, c.consultas.cerrar_consulta(consulta_id, medico))


@router.post(
    "/{consulta_id}/notas",
    response_model=ConsultaOut,
    summary="Agregar nota aclaratoria a una consulta cerrada",
)
def agregar_nota(
    consulta_id: int,
    datos: NotaIn,
    c: Contenedor = Depends(contenedor),
    medico: Usuario = Depends(_medico),
) -> ConsultaOut:
    return consulta_out(c, c.consultas.agregar_nota(consulta_id, medico, datos.texto))
