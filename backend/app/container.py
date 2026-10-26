"""Raíz de composición: aquí se decide qué implementación de cada Repository se usa.

Para pasar de listas en memoria a una base de datos SQL solo se cambian las
clases `Memory...Repository` de este archivo por sus equivalentes SQL; los
servicios y la API no se modifican.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.config import Configuracion
from app.repositories.interfaces import (
    IAuditoriaRepository,
    ICitaRepository,
    IConsultaRepository,
    IFacturaRepository,
    IIngresoRepository,
    IPacienteRepository,
    IProcedimientoRealizadoRepository,
    IProcedimientoRepository,
    IRecordatorioRepository,
    IUsuarioRepository,
)
from app.repositories.memoria import (
    MemoryAuditoriaRepository,
    MemoryCitaRepository,
    MemoryConsultaRepository,
    MemoryFacturaRepository,
    MemoryIngresoRepository,
    MemoryPacienteRepository,
    MemoryProcedimientoRealizadoRepository,
    MemoryProcedimientoRepository,
    MemoryRecordatorioRepository,
    MemoryUsuarioRepository,
)
from app.services.auditoria import AuditoriaService
from app.services.autenticacion import AutenticacionService
from app.services.catalogo import CatalogoService
from app.services.cita import CitaService
from app.services.consulta import ConsultaService
from app.services.facturacion import FacturacionService
from app.services.ingreso import IngresoService
from app.services.notificaciones import NotificacionService, NotificadorSimulado
from app.services.paciente import PacienteService
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

    notificador = NotificadorSimulado()
    notificaciones = NotificacionService(repo_recordatorios, notificador, config)
    catalogo = CatalogoService(repo_procedimientos)

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
        notificador=notificador,
        notificaciones=notificaciones,
        autenticacion=AutenticacionService(repo_usuarios, repo_auditoria, config),
        usuarios=UsuarioService(repo_usuarios, repo_auditoria, config),
        pacientes=PacienteService(repo_pacientes),
        citas=CitaService(repo_citas, repo_pacientes, repo_usuarios, notificaciones, config),
        consultas=ConsultaService(repo_consultas, repo_citas, repo_pacientes, config),
        auditoria=AuditoriaService(repo_auditoria),
        catalogo=catalogo,
        ingresos=IngresoService(
            repo_ingresos, repo_realizados, catalogo, repo_pacientes, repo_usuarios, config
        ),
        facturacion=FacturacionService(repo_facturas, repo_realizados, repo_ingresos, config),
    )
