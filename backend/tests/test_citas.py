"""RF-05, RF-06 y RF-10: agenda de citas, cruces de horario y recordatorios."""
from datetime import datetime, timedelta

from tests.conftest import hora


def agendar(cliente, headers, paciente_id, medico_id, dia, hhmm):
    return cliente.post(
        "/api/citas",
        json={"paciente_id": paciente_id, "medico_id": medico_id, "fecha_hora": hora(dia, hhmm)},
        headers=headers,
    )


def test_agendar_cita(cliente, recepcion, usuarios, pacientes, fecha):
    medico_id = usuarios["dr.perez"]["id"]
    r = agendar(cliente, recepcion, pacientes["1000000001"]["id"], medico_id, fecha, "09:00")

    assert r.status_code == 201
    assert r.json()["estado"] == "PROGRAMADA"


def test_no_permite_dos_citas_del_mismo_medico_en_el_mismo_horario(cliente, recepcion, usuarios, pacientes, fecha):
    medico_id = usuarios["dr.perez"]["id"]
    agendar(cliente, recepcion, pacientes["1000000001"]["id"], medico_id, fecha, "09:00")

    r = agendar(cliente, recepcion, pacientes["1000000002"]["id"], medico_id, fecha, "09:00")

    assert r.status_code == 409  # RN-02
    libres = r.json()["horarios_libres"]
    assert hora(fecha, "09:00") not in libres
    assert hora(fecha, "09:30") in libres  # propone otros horarios


def test_otro_medico_si_puede_atender_a_la_misma_hora(cliente, recepcion, usuarios, pacientes, fecha):
    agendar(cliente, recepcion, pacientes["1000000001"]["id"], usuarios["dr.perez"]["id"], fecha, "09:00")
    r = agendar(cliente, recepcion, pacientes["1000000002"]["id"], usuarios["dra.gomez"]["id"], fecha, "09:00")
    assert r.status_code == 201


def test_horarios_libres_excluyen_los_ocupados(cliente, recepcion, usuarios, pacientes, fecha):
    medico_id = usuarios["dr.perez"]["id"]
    antes = cliente.get(
        "/api/citas/horarios-libres", params={"medico_id": medico_id, "fecha": fecha.isoformat()}, headers=recepcion
    ).json()["horarios"]
    agendar(cliente, recepcion, pacientes["1000000001"]["id"], medico_id, fecha, "10:00")
    despues = cliente.get(
        "/api/citas/horarios-libres", params={"medico_id": medico_id, "fecha": fecha.isoformat()}, headers=recepcion
    ).json()["horarios"]

    assert len(antes) == 18  # 08:00 a 17:00 en franjas de 30 minutos
    assert hora(fecha, "10:00") in antes
    assert hora(fecha, "10:00") not in despues
    assert len(despues) == 17


def test_cancelar_libera_el_horario(cliente, recepcion, usuarios, pacientes, fecha):
    medico_id = usuarios["dr.perez"]["id"]
    cita = agendar(cliente, recepcion, pacientes["1000000001"]["id"], medico_id, fecha, "11:00").json()

    r = cliente.post(f"/api/citas/{cita['id']}/cancelar", json={"motivo": "El paciente no puede asistir"}, headers=recepcion)
    assert r.status_code == 200
    assert r.json()["estado"] == "CANCELADA"
    assert r.json()["motivo_cancelacion"] == "El paciente no puede asistir"

    # RN-06: el horario queda disponible de inmediato
    nueva = agendar(cliente, recepcion, pacientes["1000000002"]["id"], medico_id, fecha, "11:00")
    assert nueva.status_code == 201
    # y no se puede cancelar dos veces
    assert cliente.post(f"/api/citas/{cita['id']}/cancelar", json={"motivo": "x"}, headers=recepcion).status_code == 422


def test_cancelar_exige_motivo(cliente, recepcion, usuarios, pacientes, fecha):
    cita = agendar(cliente, recepcion, pacientes["1000000001"]["id"], usuarios["dr.perez"]["id"], fecha, "11:00").json()
    r = cliente.post(f"/api/citas/{cita['id']}/cancelar", json={"motivo": "  "}, headers=recepcion)
    assert r.status_code == 422


def test_reprogramar_cita(cliente, recepcion, usuarios, pacientes, fecha):
    medico_id = usuarios["dr.perez"]["id"]
    cita = agendar(cliente, recepcion, pacientes["1000000001"]["id"], medico_id, fecha, "09:00").json()
    agendar(cliente, recepcion, pacientes["1000000002"]["id"], medico_id, fecha, "10:00")

    ocupado = cliente.put(f"/api/citas/{cita['id']}/reprogramar", json={"fecha_hora": hora(fecha, "10:00")}, headers=recepcion)
    assert ocupado.status_code == 409

    ok = cliente.put(f"/api/citas/{cita['id']}/reprogramar", json={"fecha_hora": hora(fecha, "09:30")}, headers=recepcion)
    assert ok.status_code == 200
    assert ok.json()["fecha_hora"] == hora(fecha, "09:30")
    # el horario anterior quedó libre
    assert agendar(cliente, recepcion, pacientes["1000000003"]["id"], medico_id, fecha, "09:00").status_code == 201


def test_una_cita_puede_moverse_a_su_propio_horario(cliente, recepcion, usuarios, pacientes, fecha):
    cita = agendar(cliente, recepcion, pacientes["1000000001"]["id"], usuarios["dr.perez"]["id"], fecha, "09:00").json()
    r = cliente.put(f"/api/citas/{cita['id']}/reprogramar", json={"fecha_hora": hora(fecha, "09:00")}, headers=recepcion)
    assert r.status_code == 200


def test_hora_fuera_de_franja_o_en_el_pasado(cliente, recepcion, usuarios, pacientes, fecha):
    medico_id = usuarios["dr.perez"]["id"]
    paciente_id = pacientes["1000000001"]["id"]
    ayer = fecha - timedelta(days=31)

    assert agendar(cliente, recepcion, paciente_id, medico_id, fecha, "09:15").status_code == 422
    assert agendar(cliente, recepcion, paciente_id, medico_id, fecha, "07:00").status_code == 422
    assert agendar(cliente, recepcion, paciente_id, medico_id, fecha, "17:00").status_code == 422
    assert agendar(cliente, recepcion, paciente_id, medico_id, ayer, "09:00").status_code == 422


def test_paciente_o_medico_inexistente(cliente, recepcion, usuarios, pacientes, fecha):
    assert agendar(cliente, recepcion, 9999, usuarios["dr.perez"]["id"], fecha, "09:00").status_code == 404
    assert agendar(cliente, recepcion, pacientes["1000000001"]["id"], 9999, fecha, "09:00").status_code == 404
    # una recepcionista no es un médico
    assert agendar(cliente, recepcion, pacientes["1000000001"]["id"], usuarios["recepcion2"]["id"], fecha, "09:00").status_code == 404


def test_agenda_diaria_y_semanal(cliente, recepcion, usuarios, pacientes, fecha):
    medico_id = usuarios["dr.perez"]["id"]
    agendar(cliente, recepcion, pacientes["1000000001"]["id"], medico_id, fecha, "14:00")
    agendar(cliente, recepcion, pacientes["1000000002"]["id"], medico_id, fecha, "08:30")
    agendar(cliente, recepcion, pacientes["1000000003"]["id"], medico_id, fecha + timedelta(days=2), "09:00")

    diaria = cliente.get("/api/citas/agenda", params={"medico_id": medico_id, "fecha": fecha.isoformat()}, headers=recepcion).json()
    semanal = cliente.get(
        "/api/citas/agenda", params={"medico_id": medico_id, "fecha": fecha.isoformat(), "dias": 7}, headers=recepcion
    ).json()

    assert [c["paciente_nombre"] for c in diaria] == ["Juan David Herrera Castro", "Camila Andrea Rodríguez Silva"]  # por hora
    assert len(semanal) == 3


def test_un_medico_solo_ve_su_propia_agenda(cliente, medico, usuarios, fecha):
    propia = cliente.get("/api/citas/agenda", params={"medico_id": usuarios["dr.perez"]["id"], "fecha": fecha.isoformat()}, headers=medico)
    ajena = cliente.get("/api/citas/agenda", params={"medico_id": usuarios["dra.gomez"]["id"], "fecha": fecha.isoformat()}, headers=medico)
    assert propia.status_code == 200
    assert ajena.status_code == 403


def test_agendar_programa_un_recordatorio_y_se_envia_cuando_llega_su_hora(cliente, app, recepcion, admin, usuarios, pacientes, fecha):
    medico_id = usuarios["dr.perez"]["id"]
    cita = agendar(cliente, recepcion, pacientes["1000000001"]["id"], medico_id, fecha, "09:00").json()

    recordatorios = cliente.get("/api/recordatorios", headers=admin).json()
    suyo = [r for r in recordatorios if r["cita_id"] == cita["id"]]
    assert len(suyo) == 1
    assert suyo[0]["estado"] == "PROGRAMADO"
    assert suyo[0]["canal"] == "CORREO"
    assert suyo[0]["fecha_envio"] == hora(fecha - timedelta(days=1), "09:00")  # 24 horas antes

    # Todavía no es la hora: no se envía.
    enviados_ahora = cliente.post("/api/recordatorios/procesar", headers=admin).json()
    assert all(r["cita_id"] != cita["id"] for r in enviados_ahora)

    # Llega la hora: se envía una sola vez.
    notificaciones = app.state.contenedor.notificaciones
    enviados = notificaciones.procesar_pendientes(datetime.combine(fecha, datetime.min.time()))
    assert any(r.cita_id == cita["id"] for r in enviados)
    assert notificaciones.procesar_pendientes(datetime.combine(fecha, datetime.min.time())) == []


def test_cancelar_cancela_el_recordatorio(cliente, recepcion, admin, usuarios, pacientes, fecha):
    cita = agendar(cliente, recepcion, pacientes["1000000001"]["id"], usuarios["dr.perez"]["id"], fecha, "09:00").json()
    cliente.post(f"/api/citas/{cita['id']}/cancelar", json={"motivo": "Reagenda"}, headers=recepcion)

    estados = [r["estado"] for r in cliente.get("/api/recordatorios", headers=admin).json() if r["cita_id"] == cita["id"]]
    assert estados == ["CANCELADO"]


def test_solo_recepcion_agenda(cliente, medico, admin, usuarios, pacientes, fecha):
    for headers in (medico, admin):
        r = cliente.post(
            "/api/citas",
            json={"paciente_id": 1, "medico_id": usuarios["dr.perez"]["id"], "fecha_hora": hora(fecha, "09:00")},
            headers=headers,
        )
        assert r.status_code == 403
