"""Conversión de entidades de dominio a esquemas de salida que necesitan datos extra."""
from typing import Optional

from app.api.schemas import (
    AgendaItemOut,
    ConsultaOut,
    FacturaOut,
    IngresoDetalleOut,
    IngresoOut,
    RealizadoOut,
)
from app.container import Contenedor
from app.domain.modelos import Cita, Consulta, Factura, Ingreso, Paciente, ProcedimientoRealizado


def consulta_out(c: Contenedor, consulta: Consulta) -> ConsultaOut:
    salida = ConsultaOut.model_validate(consulta)
    medico = c.repo_usuarios.obtener_por_id(consulta.medico_id)
    salida.medico_nombre = medico.nombre_completo if medico else ""
    return salida


def agenda_item_out(cita: Cita, paciente: Optional[Paciente]) -> AgendaItemOut:
    salida = AgendaItemOut.model_validate(cita)
    if paciente is not None:
        salida.paciente_nombre = paciente.nombre_completo
        salida.paciente_documento = f"{paciente.tipo_documento} {paciente.numero_documento}"
    return salida


def _nombres_de_usuarios(c: Contenedor, ids: set[int]) -> dict[int, str]:
    nombres = {}
    for id_ in ids:
        usuario = c.repo_usuarios.obtener_por_id(id_)
        nombres[id_] = usuario.nombre_completo if usuario else ""
    return nombres


def _pacientes_por_id(c: Contenedor, ids: set[int]) -> dict[int, Paciente]:
    return {p.id: p for p in c.repo_pacientes.obtener_por_ids(list(ids))} if ids else {}


def realizados_out(
    c: Contenedor, realizados: list[ProcedimientoRealizado], clinico: bool
) -> list[RealizadoOut]:
    """`clinico=False` oculta las observaciones: la recepción factura pero no lee la historia."""
    medicos = _nombres_de_usuarios(c, {r.medico_id for r in realizados})
    resultado = []
    for r in realizados:
        salida = RealizadoOut.model_validate(r)
        salida.medico_nombre = medicos[r.medico_id]
        salida.observaciones = r.observaciones if clinico else None
        if r.factura_id is not None:
            salida.factura_numero = f"FAC-{r.factura_id:06d}"
        resultado.append(salida)
    return resultado


def ingresos_out(
    c: Contenedor, ingresos: list[Ingreso], clinico: bool, detalle: bool = False
) -> list[IngresoOut]:
    pacientes = _pacientes_por_id(c, {i.paciente_id for i in ingresos})
    medicos = _nombres_de_usuarios(c, {i.medico_id for i in ingresos})
    todos = c.ingresos.procedimientos_de_ingresos([i.id for i in ingresos])
    resultado = []
    for ingreso in ingresos:
        propios = [r for r in todos if r.ingreso_id == ingreso.id]
        vigentes = [r for r in propios if not r.anulado]
        datos = dict(
            total=sum(r.subtotal for r in vigentes),
            pendiente_facturar=sum(r.subtotal for r in vigentes if r.factura_id is None),
            n_procedimientos=len(vigentes),
        )
        if detalle:
            salida = IngresoDetalleOut.model_validate(ingreso)
            salida.procedimientos = realizados_out(c, propios, clinico)
        else:
            salida = IngresoOut.model_validate(ingreso)
        for campo, valor in datos.items():
            setattr(salida, campo, valor)
        paciente = pacientes.get(ingreso.paciente_id)
        if paciente is not None:
            salida.paciente_nombre = paciente.nombre_completo
            salida.paciente_documento = f"{paciente.tipo_documento} {paciente.numero_documento}"
        salida.medico_nombre = medicos[ingreso.medico_id]
        salida.resumen_egreso = ingreso.resumen_egreso if clinico else None
        resultado.append(salida)
    return resultado


def facturas_out(c: Contenedor, facturas: list[Factura]) -> list[FacturaOut]:
    pacientes = _pacientes_por_id(c, {f.paciente_id for f in facturas})
    emisores = _nombres_de_usuarios(c, {f.emitida_por_id for f in facturas})
    resultado = []
    for factura in facturas:
        salida = FacturaOut.model_validate(factura)
        paciente = pacientes.get(factura.paciente_id)
        if paciente is not None:
            salida.paciente_nombre = paciente.nombre_completo
            salida.paciente_documento = f"{paciente.tipo_documento} {paciente.numero_documento}"
        salida.emitida_por = emisores[factura.emitida_por_id]
        resultado.append(salida)
    return resultado
