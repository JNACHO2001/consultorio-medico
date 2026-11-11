"""Raíz de composición: aquí se decide qué implementación de cada Repository se usa.

Para pasar de listas en memoria a una base de datos SQL solo se cambian las
clases `Memory...Repository` de este archivo por sus equivalentes SQL; los
servicios y la API no se modifican.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.config import Configuracion
from app.repositories.interfaces import (
    IAuditoriaRepository,
    ICajaRepository,
    ICitaRepository,
    IConsultaRepository,
    IConvenioRepository,
    IDocumentoElectronicoRepository,
    IFacturaRepository,
    IIngresoRepository,
    IOrdenRepository,
    IPacienteRepository,
    IPagadorRepository,
    IProcedimientoRealizadoRepository,
    IProcedimientoRepository,
    IRecordatorioRepository,
    IUsuarioRepository,
)
from app.repositories.memoria import (
    MemoryAuditoriaRepository,
    MemoryCajaRepository,
    MemoryCitaRepository,
    MemoryConsultaRepository,
    MemoryConvenioRepository,
    MemoryDocumentoElectronicoRepository,
    MemoryFacturaRepository,
    MemoryIngresoRepository,
    MemoryOrdenRepository,
    MemoryPacienteRepository,
    MemoryPagadorRepository,
    MemoryProcedimientoRealizadoRepository,
    MemoryProcedimientoRepository,
    MemoryRecordatorioRepository,
    MemoryUsuarioRepository,
)
from app.distribuido.cluster import ClusterProveedor, crear_cluster
from app.services.auditoria import AuditoriaService
from app.services.autenticacion import AutenticacionService
from app.services.caja import CajaService
from app.services.catalogo import CatalogoService
from app.services.cartera import CarteraService
from app.services.cita import CitaService
from app.services.cie10 import Cie10Service
from app.services.consulta import ConsultaService
from app.services.convenios import ConvenioService
from app.services.dian import ProveedorSimulado
from app.services.facturacion import FacturacionService
from app.services.facturacion_electronica import FacturacionElectronicaService
from app.services.ingreso import IngresoService
from app.services.notificaciones import NotificacionService, NotificadorSimulado
from app.services.ordenes import OrdenService
from app.services.paciente import PacienteService
from app.services.rips import RipsService
from app.services.usuario import UsuarioService


@dataclass
class Contenedor:
    config: Configuracion
    # Repositorios (se manejan por su interfaz)
    repo_auditoria: IAuditoriaRepository
    repo_pacientes: IPacienteRepository
    repo_citas: ICitaRepository
    repo_consultas: IConsultaRepository
    repo_usuarios: IUsuarioRepository
    repo_recordatorios: IRecordatorioRepository
    repo_procedimientos: IProcedimientoRepository
    repo_ingresos: IIngresoRepository
    repo_realizados: IProcedimientoRealizadoRepository
    repo_facturas: IFacturaRepository
    repo_pagadores: IPagadorRepository
    repo_convenios: IConvenioRepository
    repo_ordenes: IOrdenRepository
    repo_documentos: IDocumentoElectronicoRepository
    repo_cajas: ICajaRepository
    # Servicios
    notificador: NotificadorSimulado
    notificaciones: NotificacionService
    autenticacion: AutenticacionService
    usuarios: UsuarioService
    pacientes: PacienteService
    citas: CitaService
    consultas: ConsultaService
    auditoria: AuditoriaService
    catalogo: CatalogoService
    ingresos: IngresoService
    facturacion: FacturacionService
    convenios: ConvenioService
    cartera: CarteraService
    rips: RipsService
    ordenes: OrdenService
    cie10: Cie10Service
    cajas: CajaService
    electronica: FacturacionElectronicaService
    # Clúster de nodos proveedor (None = proveedor simulado dentro del mismo proceso)
    cluster: Optional[ClusterProveedor] = None


def crear_contenedor(config: Configuracion) -> Contenedor:
    repo_auditoria = MemoryAuditoriaRepository()
    repo_pacientes = MemoryPacienteRepository(repo_auditoria)
    repo_citas = MemoryCitaRepository()
    repo_consultas = MemoryConsultaRepository(repo_auditoria)
    repo_usuarios = MemoryUsuarioRepository()
    repo_recordatorios = MemoryRecordatorioRepository()
    repo_procedimientos = MemoryProcedimientoRepository()
    repo_ingresos = MemoryIngresoRepository(repo_auditoria)
    repo_realizados = MemoryProcedimientoRealizadoRepository(repo_auditoria)
    repo_facturas = MemoryFacturaRepository(repo_auditoria)
    repo_pagadores = MemoryPagadorRepository()
    repo_convenios = MemoryConvenioRepository()
    repo_ordenes = MemoryOrdenRepository(repo_auditoria)
    repo_documentos = MemoryDocumentoElectronicoRepository()
    repo_cajas = MemoryCajaRepository()

    notificador = NotificadorSimulado()
    notificaciones = NotificacionService(repo_recordatorios, notificador, config)
    catalogo = CatalogoService(repo_procedimientos)
    convenios = ConvenioService(repo_pagadores, repo_convenios)
    convenios.asegurar_particular()  # siempre existe el pagador particular
    ingresos = IngresoService(
        repo_ingresos, repo_realizados, catalogo, repo_pacientes, repo_usuarios, config, convenios, repo_ordenes
    )
    cajas = CajaService(repo_cajas, repo_facturas, repo_auditoria, config)
    facturacion = FacturacionService(
        repo_facturas, repo_realizados, repo_ingresos, config, convenios, cajas, repo_documentos
    )
    # Con NODOS_PROVEEDOR el proveedor es un proxy hacia nodos remotos; el servicio no nota la diferencia.
    cluster = crear_cluster(config)
    proveedor = cluster.proxy if cluster is not None else ProveedorSimulado(config)
    electronica = FacturacionElectronicaService(
        repo_documentos, facturacion, repo_pacientes, repo_realizados, convenios,
        proveedor, repo_auditoria, config,
    )

    return Contenedor(
        config=config,
        repo_auditoria=repo_auditoria,
        repo_pacientes=repo_pacientes,
        repo_citas=repo_citas,
        repo_consultas=repo_consultas,
        repo_usuarios=repo_usuarios,
        repo_recordatorios=repo_recordatorios,
        repo_procedimientos=repo_procedimientos,
        repo_ingresos=repo_ingresos,
        repo_realizados=repo_realizados,
        repo_facturas=repo_facturas,
        repo_pagadores=repo_pagadores,
        repo_convenios=repo_convenios,
        repo_ordenes=repo_ordenes,
        repo_documentos=repo_documentos,
        repo_cajas=repo_cajas,
        notificador=notificador,
        notificaciones=notificaciones,
        autenticacion=AutenticacionService(repo_usuarios, repo_auditoria, config),
        usuarios=UsuarioService(repo_usuarios, repo_auditoria, config),
        pacientes=PacienteService(repo_pacientes),
        citas=CitaService(repo_citas, repo_pacientes, repo_usuarios, notificaciones, config),
        consultas=ConsultaService(repo_consultas, repo_citas, repo_pacientes, config),
        auditoria=AuditoriaService(repo_auditoria),
        catalogo=catalogo,
        ingresos=ingresos,
        facturacion=facturacion,
        convenios=convenios,
        cartera=CarteraService(facturacion, repo_facturas, config, cajas, repo_documentos),
        rips=RipsService(
            repo_facturas, repo_ingresos, repo_realizados, repo_pacientes, repo_auditoria, config, repo_documentos
        ),
        ordenes=OrdenService(repo_ordenes, ingresos, catalogo, repo_auditoria, config),
        cie10=Cie10Service(),
        cajas=cajas,
        electronica=electronica,
        cluster=cluster,
    )
