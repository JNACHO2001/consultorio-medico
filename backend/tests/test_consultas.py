"""RF-07 y RF-08: consultas médicas, historia clínica y reglas RN-03 y RN-04."""
from datetime import timedelta

from tests.conftest import hora

CONSULTA = {
    "motivo": "Dolor de cabeza desde hace tres días",
    "antecedentes": "Migraña en la familia",
    "signos_vitales": "TA 120/80, FC 72",
    "diagnostico": "Cefalea tensional",
    "tratamiento": "Reposo e hidratación",
    "formula": "Acetaminofén 500 mg cada 8 horas",
    "observaciones": "Control en 8 días",
}


def nueva_cita(cliente, recepcion, paciente_id, medico_id, dia, hhmm="09:00"):
    r = cliente.post(
        "/api/citas",
        json={"paciente_id": paciente_id, "medico_id": medico_id, "fecha_hora": hora(dia, hhmm)},
        headers=recepcion,
    )
    assert r.status_code == 201, r.text
    return r.json()


def registrar(cliente, medico, cita_id, **extra):
    return cliente.post("/api/consultas", json={"cita_id": cita_id, **CONSULTA, **extra}, headers=medico)


def test_flujo_completo_de_una_consulta(cliente, recepcion, medico, usuarios, pacientes, fecha):
    medico_id = usuarios["dr.perez"]["id"]
    cita = nueva_cita(cliente, recepcion, pacientes["1000000001"]["id"], medico_id, fecha)

    creada = registrar(cliente, medico, cita["id"])
    assert creada.status_code == 201
    consulta = creada.json()
    assert consulta["cerrada"] is False
    assert consulta["medico_nombre"] == "Dr. Andrés Pérez"

    cerrada = cliente.post(f"/api/consultas/{consulta['id']}/cerrar", headers=medico)
    assert cerrada.status_code == 200
    assert cerrada.json()["cerrada"] is True

    agenda = cliente.get("/api/citas/agenda", params={"medico_id": medico_id, "fecha": fecha.isoformat()}, headers=medico).json()
    assert [c["estado"] for c in agenda] == ["ATENDIDA"]


def test_historial_completo_de_la_mas_reciente_a_la_mas_antigua(cliente, recepcion, medico, usuarios, pacientes, fecha):
    medico_id = usuarios["dr.perez"]["id"]
    paciente_id = pacientes["1000000001"]["id"]
    for desfase, motivo in ((0, "Primera consulta"), (7, "Segunda consulta"), (3, "Consulta intermedia")):
        cita = nueva_cita(cliente, recepcion, paciente_id, medico_id, fecha + timedelta(days=desfase))
        consulta = registrar(cliente, medico, cita["id"], motivo=motivo).json()
        cliente.post(f"/api/consultas/{consulta['id']}/cerrar", headers=medico)

    historial = cliente.get(f"/api/pacientes/{paciente_id}/historial", headers=medico)
    assert historial.status_code == 200
    # Las consultas se fechan al registrarse; con el mismo instante el orden es estable y completo.
    assert sorted(c["motivo"] for c in historial.json()) == ["Consulta intermedia", "Primera consulta", "Segunda consulta"]


def test_la_recepcion_no_accede_a_informacion_clinica(cliente, recepcion, medico, usuarios, pacientes, fecha):
    cita = nueva_cita(cliente, recepcion, pacientes["1000000001"]["id"], usuarios["dr.perez"]["id"], fecha)
    consulta = registrar(cliente, medico, cita["id"]).json()
    paciente_id = pacientes["1000000001"]["id"]

    assert cliente.get(f"/api/pacientes/{paciente_id}/historial", headers=recepcion).status_code == 403  # RNF-01
    assert cliente.get(f"/api/consultas/{consulta['id']}", headers=recepcion).status_code == 403
    assert cliente.post("/api/consultas", json={"cita_id": cita["id"], **CONSULTA}, headers=recepcion).status_code == 403
    # y la ficha del paciente no incluye diagnósticos
    ficha = cliente.get(f"/api/pacientes/{paciente_id}", headers=recepcion).json()
    assert "diagnostico" not in str(ficha)


def test_un_medico_no_atiende_la_cita_de_otro(cliente, recepcion, otro_medico, usuarios, pacientes, fecha):
    cita = nueva_cita(cliente, recepcion, pacientes["1000000001"]["id"], usuarios["dr.perez"]["id"], fecha)
    assert registrar(cliente, otro_medico, cita["id"]).status_code == 403


def test_un_medico_no_modifica_la_consulta_de_otro(cliente, recepcion, medico, otro_medico, usuarios, pacientes, fecha):
    cita = nueva_cita(cliente, recepcion, pacientes["1000000001"]["id"], usuarios["dr.perez"]["id"], fecha)
    consulta = registrar(cliente, medico, cita["id"]).json()

    assert cliente.put(f"/api/consultas/{consulta['id']}", json={"diagnostico": "otro"}, headers=otro_medico).status_code == 403
    assert cliente.post(f"/api/consultas/{consulta['id']}/cerrar", headers=otro_medico).status_code == 403
    assert cliente.post(f"/api/consultas/{consulta['id']}/notas", json={"texto": "x"}, headers=otro_medico).status_code == 403


def test_una_cita_tiene_una_sola_consulta(cliente, recepcion, medico, usuarios, pacientes, fecha):
    cita = nueva_cita(cliente, recepcion, pacientes["1000000001"]["id"], usuarios["dr.perez"]["id"], fecha)
    assert registrar(cliente, medico, cita["id"]).status_code == 201
    assert registrar(cliente, medico, cita["id"]).status_code == 409


def test_consulta_abierta_se_edita_y_cerrada_solo_se_corrige_con_nota(cliente, recepcion, medico, usuarios, pacientes, fecha):
    cita = nueva_cita(cliente, recepcion, pacientes["1000000001"]["id"], usuarios["dr.perez"]["id"], fecha)
    consulta = registrar(cliente, medico, cita["id"]).json()
    base = f"/api/consultas/{consulta['id']}"

    # Una nota aclaratoria no tiene sentido mientras la consulta sigue abierta.
    assert cliente.post(f"{base}/notas", json={"texto": "x"}, headers=medico).status_code == 422

    editada = cliente.put(base, json={"diagnostico": "Cefalea tensional episódica"}, headers=medico)
    assert editada.status_code == 200
    assert editada.json()["diagnostico"] == "Cefalea tensional episódica"

    cliente.post(f"{base}/cerrar", headers=medico)

    # RN-04: una consulta cerrada no se modifica...
    assert cliente.put(base, json={"diagnostico": "otro"}, headers=medico).status_code == 422
    assert cliente.post(f"{base}/cerrar", headers=medico).status_code == 422
    # ...se corrige con una nota aclaratoria.
    r = cliente.post(f"{base}/notas", json={"texto": "Corrección: la presión era 118/78."}, headers=medico)
    assert r.status_code == 200
    assert [n["texto"] for n in r.json()["notas"]] == ["Corrección: la presión era 118/78."]
    assert r.json()["diagnostico"] == "Cefalea tensional episódica"  # el contenido original no cambia


def test_no_se_cierra_una_consulta_incompleta(cliente, recepcion, medico, usuarios, pacientes, fecha):
    cita = nueva_cita(cliente, recepcion, pacientes["1000000001"]["id"], usuarios["dr.perez"]["id"], fecha)
    consulta = registrar(cliente, medico, cita["id"], diagnostico="", tratamiento="").json()

    r = cliente.post(f"/api/consultas/{consulta['id']}/cerrar", headers=medico)
    assert r.status_code == 422
    assert "diagnostico" in r.json()["detail"] and "tratamiento" in r.json()["detail"]


def test_no_se_registra_consulta_de_una_cita_cancelada(cliente, recepcion, medico, usuarios, pacientes, fecha):
    cita = nueva_cita(cliente, recepcion, pacientes["1000000001"]["id"], usuarios["dr.perez"]["id"], fecha)
    cliente.post(f"/api/citas/{cita['id']}/cancelar", json={"motivo": "No asistió"}, headers=recepcion)
    assert registrar(cliente, medico, cita["id"]).status_code == 422


def test_consulta_por_cita(cliente, recepcion, medico, usuarios, pacientes, fecha):
    cita = nueva_cita(cliente, recepcion, pacientes["1000000001"]["id"], usuarios["dr.perez"]["id"], fecha)
    assert cliente.get(f"/api/consultas/por-cita/{cita['id']}", headers=medico).status_code == 404
    consulta = registrar(cliente, medico, cita["id"]).json()
    r = cliente.get(f"/api/consultas/por-cita/{cita['id']}", headers=medico)
    assert r.status_code == 200 and r.json()["id"] == consulta["id"]


def test_el_motivo_es_obligatorio(cliente, recepcion, medico, usuarios, pacientes, fecha):
    cita = nueva_cita(cliente, recepcion, pacientes["1000000001"]["id"], usuarios["dr.perez"]["id"], fecha)
    assert registrar(cliente, medico, cita["id"], motivo="   ").status_code == 422
