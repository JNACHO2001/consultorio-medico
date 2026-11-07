"""Conversión de entidades de dominio a esquemas de salida que necesitan datos extra."""
from typing import Optional

from app.api.schemas import (
    AgendaItemOut,
    CajaDetalleOut,
    CajaOut,
    ConsultaOut,
    DocumentoElectronicoOut,
    DocumentoResumenOut,
    FacturaOut,
    IngresoDetalleOut,
    IngresoOut,
    OrdenOut,
    RealizadoOut,
    ReciboOut,
    ResultadoValorOut,
)
from app.container import Contenedor
from app.domain.excepciones import NoEncontrado
from app.domain.modelos import (
    Caja,
    Cita,
    Consulta,
    DocumentoElectronico,
    EstadoCaja,
    Factura,
    Ingreso,
    OrdenClinica,
    OrigenPago,
    Paciente,
    ProcedimientoRealizado,
)


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
    convenios: dict[int, tuple[str, str, int]] = {}
    for convenio_id in {i.convenio_id for i in ingresos if i.convenio_id}:
        try:
            convenio = c.convenios.obtener_convenio(convenio_id)
            pagador = c.convenios.obtener_pagador(convenio.pagador_id, incluir_inactivo=True)
            convenios[convenio_id] = (convenio.nombre, pagador.nombre, convenio.porcentaje_tarifa)
        except NoEncontrado:
            convenios[convenio_id] = ("", "", 100)
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
        salida.diagnostico_principal = ingreso.diagnostico_principal if clinico else None
        if clinico and ingreso.diagnostico_principal:
            salida.diagnostico_descripcion = c.cie10.descripcion(ingreso.diagnostico_principal)
        salida.convenio_nombre, salida.pagador_nombre, salida.porcentaje_tarifa = convenios.get(ingreso.convenio_id, ("", "", 100))
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
        salida.pagado_paciente = factura.pagado(OrigenPago.PACIENTE)
        salida.pagado_pagador = factura.pagado(OrigenPago.PAGADOR)
        salida.dias_radicada = c.cartera.edad_dias(factura)
        electronica = c.electronica.factura_electronica(factura.id)
        salida.factura_electronica = DocumentoResumenOut.model_validate(electronica) if electronica else None
        salida.notas_credito = [
            DocumentoResumenOut.model_validate(n) for n in c.electronica.notas_credito(factura.id)
        ]
        salida.dian_obligatoria = c.config.dian_obligatoria
        resultado.append(salida)
    return resultado


def documentos_out(c: Contenedor, documentos: list[DocumentoElectronico]) -> list[DocumentoElectronicoOut]:
    facturas = {d.factura_id: c.facturacion.obtener(d.factura_id) for d in documentos}
    pacientes = _pacientes_por_id(c, {f.paciente_id for f in facturas.values()})
    resultado = []
    for d in documentos:
        salida = DocumentoElectronicoOut.model_validate(d)
        factura = facturas[d.factura_id]
        salida.factura_numero = factura.numero
        paciente = pacientes.get(factura.paciente_id)
        salida.paciente_nombre = paciente.nombre_completo if paciente else ""
        resultado.append(salida)
    return resultado


def cajas_out(c: Contenedor, cajas: list[Caja], con_recibos: bool = False) -> list:
    cajeros = _nombres_de_usuarios(c, {x.cajero_id for x in cajas})
    resultado = []
    for caja in cajas:
        resumen = c.cajas.resumen(caja)
        salida = (CajaDetalleOut if con_recibos else CajaOut).model_validate(caja)
        salida.cajero_nombre = cajeros.get(caja.cajero_id, "")
        salida.n_recibos = resumen.n_recibos
        salida.total_recibido = resumen.total
        salida.efectivo_esperado_actual = resumen.efectivo_esperado
        if caja.estado == EstadoCaja.ABIERTA:
            salida.por_metodo = resumen.por_metodo
        if con_recibos:
            recibos = c.cajas.recibos(caja.id)
            pacientes = _pacientes_por_id(c, {f.paciente_id for f, _ in recibos})
            salida.recibos = [
                ReciboOut(
                    recibo_numero=p.recibo_numero, factura_id=f.id, factura_numero=f.numero, origen=p.origen,
                    metodo=p.metodo, valor=p.valor, fecha=p.fecha, referencia=p.referencia,
                    paciente_nombre=pacientes[f.paciente_id].nombre_completo if f.paciente_id in pacientes else "",
                )
                for f, p in recibos
            ]
        resultado.append(salida)
    return resultado


def ordenes_out(c: Contenedor, ordenes: list[OrdenClinica]) -> list[OrdenOut]:
    """Las órdenes y resultados son datos clínicos: solo se piden desde rutas de médico o laboratorio."""
    pacientes = _pacientes_por_id(c, {o.paciente_id for o in ordenes})
    usuarios = _nombres_de_usuarios(c, {o.medico_id for o in ordenes} | {o.registrado_por_id for o in ordenes if o.registrado_por_id})
    resultado = []
    for o in ordenes:
        salida = OrdenOut.model_validate(o)
        salida.valores = [
            ResultadoValorOut(
                parametro=v.parametro, valor=v.valor, unidad=v.unidad, ref_min=v.ref_min, ref_max=v.ref_max, alterado=v.alterado
            )
            for v in o.valores
        ]
        salida.alterada = any(v.alterado for v in o.valores)
        paciente = pacientes.get(o.paciente_id)
        if paciente is not None:
            salida.paciente_nombre = paciente.nombre_completo
            salida.paciente_documento = f"{paciente.tipo_documento} {paciente.numero_documento}"
        salida.medico_nombre = usuarios.get(o.medico_id, "")
        salida.registrado_por = usuarios.get(o.registrado_por_id, "") if o.registrado_por_id else ""
        resultado.append(salida)
    return resultado
