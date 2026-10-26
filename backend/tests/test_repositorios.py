"""Pruebas del patrón Repository: las implementaciones en memoria cumplen el contrato."""
from datetime import date, datetime

from app.core.contexto import UsuarioContexto, establecer_usuario
from app.domain.modelos import Cita, Consulta, EstadoCita, Paciente, Rol
from app.repositories.memoria import (
    MemoryAuditoriaRepository,
    MemoryCitaRepository,
    MemoryConsultaRepository,
    MemoryPacienteRepository,
)


def paciente(documento="1001", nombres="Ana María", apellidos="Pérez Gómez") -> Paciente:
    return Paciente(
        tipo_documento="CC", numero_documento=documento, nombres=nombres, apellidos=apellidos,
        fecha_nacimiento=date(1990, 1, 1),
    )


def test_devuelve_copias_y_solo_cambia_con_actualizar():
    repo = MemoryPacienteRepository(MemoryAuditoriaRepository())
    guardado = repo.agregar(paciente())
    guardado.nombres = "Cambiado sin guardar"
    assert repo.obtener_por_id(guardado.id).nombres == "Ana María"

    repo.actualizar(guardado)
    assert repo.obtener_por_id(guardado.id).nombres == "Cambiado sin guardar"


def test_borrado_logico_conserva_el_registro():
    repo = MemoryPacienteRepository(MemoryAuditoriaRepository())
    guardado = repo.agregar(paciente())
    repo.desactivar(guardado.id)

    assert repo.obtener_por_id(guardado.id) is None
    assert repo.listar() == []
    assert len(repo.listar(incluir_inactivos=True)) == 1  # RNF-11: no se elimina físicamente


def test_busqueda_sin_tildes_ni_mayusculas_y_por_documento():
    repo = MemoryPacienteRepository(MemoryAuditoriaRepository())
    repo.agregar(paciente("1001", "Ana María", "Pérez Gómez"))
    repo.agregar(paciente("2002", "Luis", "Vargas"))

    assert [p.numero_documento for p in repo.buscar("MARIA perez")] == ["1001"]
    assert [p.numero_documento for p in repo.buscar("2002")] == ["2002"]
    assert repo.buscar("zzz") == []


def test_audita_con_el_usuario_del_contexto_y_no_audita_sin_usuario():
    auditoria = MemoryAuditoriaRepository()
    repo = MemoryPacienteRepository(auditoria)

    repo.agregar(paciente("1001"))  # sin usuario: carga interna
    assert auditoria.consultar() == []

    establecer_usuario(UsuarioContexto(7, "recepcion1", Rol.RECEPCION))
    guardado = repo.agregar(paciente("2002"))
    repo.obtener_por_id(guardado.id)

    registros = auditoria.consultar()
    assert [(r.usuario, r.accion, r.entidad) for r in registros] == [
        ("recepcion1", "LECTURA", "Paciente"),
        ("recepcion1", "CREACION", "Paciente"),
    ]


def test_cita_cancelada_libera_el_horario():
    repo = MemoryCitaRepository()
    inicio = datetime(2030, 1, 7, 9, 0)
    cita = repo.agregar(Cita(paciente_id=1, medico_id=5, fecha_hora=inicio))

    assert repo.existe_cruce(5, inicio) is True
    assert repo.existe_cruce(5, inicio, excluir_cita_id=cita.id) is False  # al reprogramar
    assert repo.existe_cruce(6, inicio) is False  # otro médico

    repo.actualizar_estado(cita.id, EstadoCita.CANCELADA, "Paciente no puede asistir")
    assert repo.existe_cruce(5, inicio) is False


def test_historial_del_paciente_de_la_consulta_mas_reciente_a_la_mas_antigua():
    repo = MemoryConsultaRepository(MemoryAuditoriaRepository())
    for dia in (3, 20, 11):
        repo.agregar(Consulta(paciente_id=1, cita_id=dia, medico_id=1, fecha_hora=datetime(2030, 1, dia, 9, 0)))
    repo.agregar(Consulta(paciente_id=2, cita_id=99, medico_id=1, fecha_hora=datetime(2030, 1, 1, 9, 0)))

    historial = repo.obtener_por_paciente(1)
    assert [c.fecha_hora.day for c in historial] == [20, 11, 3]
