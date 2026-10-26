"""RF-01 a RF-04: registro, duplicados, búsqueda y actualización de pacientes."""
from datetime import date, timedelta

NUEVO = {
    "tipo_documento": "CC",
    "numero_documento": "5550001",
    "nombres": "Pedro José",
    "apellidos": "Suárez León",
    "fecha_nacimiento": "1980-05-20",
    "sexo": "M",
    "telefono": "3001112233",
    "correo": "pedro@example.com",
    "eps": "EPS Demo",
    "alergias": "Ninguna",
}


def test_registrar_paciente(cliente, recepcion):
    r = cliente.post("/api/pacientes", json=NUEVO, headers=recepcion)
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["id"] > 0
    assert cuerpo["nombre_completo"] == "Pedro José Suárez León"


def test_no_permite_pacientes_duplicados_por_documento(cliente, recepcion):
    cliente.post("/api/pacientes", json=NUEVO, headers=recepcion)
    r = cliente.post("/api/pacientes", json={**NUEVO, "nombres": "Otro"}, headers=recepcion)

    assert r.status_code == 409
    assert r.json()["paciente_existente"]["nombre_completo"] == "Pedro José Suárez León"
    buscados = cliente.get("/api/pacientes", params={"q": "5550001"}, headers=recepcion).json()
    assert len(buscados) == 1


def test_el_mismo_numero_con_otro_tipo_de_documento_es_otro_paciente(cliente, recepcion):
    cliente.post("/api/pacientes", json=NUEVO, headers=recepcion)
    r = cliente.post("/api/pacientes", json={**NUEVO, "tipo_documento": "CE"}, headers=recepcion)
    assert r.status_code == 201


def test_buscar_por_documento_o_por_nombre_parcial(cliente, recepcion):
    por_documento = cliente.get("/api/pacientes", params={"q": "1000000002"}, headers=recepcion).json()
    por_nombre = cliente.get("/api/pacientes", params={"q": "herrera juan"}, headers=recepcion).json()

    assert [p["nombre_completo"] for p in por_documento] == ["Juan David Herrera Castro"]
    assert [p["id"] for p in por_nombre] == [p["id"] for p in por_documento]
    assert cliente.get("/api/pacientes", params={"q": "no-existe"}, headers=recepcion).json() == []


def test_actualizar_conserva_el_historial_de_cambios_y_no_cambia_el_documento(cliente, recepcion, usuarios):
    paciente = cliente.post("/api/pacientes", json=NUEVO, headers=recepcion).json()

    r = cliente.put(
        f"/api/pacientes/{paciente['id']}",
        json={"telefono": "3109998877", "eps": "EPS Demo B", "numero_documento": "9999999"},
        headers=recepcion,
    )
    assert r.status_code == 200
    actualizado = r.json()
    assert actualizado["telefono"] == "3109998877"
    assert actualizado["numero_documento"] == "5550001"  # la identidad no cambia (RN-01)

    cambios = {c["campo"]: c for c in actualizado["historial_cambios"]}
    assert set(cambios) == {"telefono", "eps"}
    assert cambios["telefono"]["valor_anterior"] == "3001112233"
    assert cambios["telefono"]["valor_nuevo"] == "3109998877"
    assert cambios["telefono"]["usuario_id"] == usuarios["recepcion1"]["id"]


def test_actualizar_sin_cambios_reales_no_agrega_historial(cliente, recepcion):
    paciente = cliente.post("/api/pacientes", json=NUEVO, headers=recepcion).json()
    r = cliente.put(f"/api/pacientes/{paciente['id']}", json={"telefono": "3001112233"}, headers=recepcion)
    assert r.json()["historial_cambios"] == []


def test_datos_invalidos_se_rechazan(cliente, recepcion):
    manana = (date.today() + timedelta(days=1)).isoformat()
    casos = [
        ({**NUEVO, "fecha_nacimiento": manana}, "fecha de nacimiento"),
        ({**NUEVO, "numero_documento": "12"}, "número de documento"),
        ({**NUEVO, "correo": "sin-arroba"}, "correo"),
        ({**NUEVO, "nombres": "   "}, "nombres"),
        ({**NUEVO, "tipo_documento": "XX"}, "tipo_documento"),
    ]
    for cuerpo, texto in casos:
        r = cliente.post("/api/pacientes", json=cuerpo, headers=recepcion)
        assert r.status_code == 422, cuerpo
        assert texto in r.json()["detail"]


def test_paciente_inexistente(cliente, recepcion):
    assert cliente.get("/api/pacientes/9999", headers=recepcion).status_code == 404


def test_permisos_por_rol(cliente, medico, admin):
    assert cliente.post("/api/pacientes", json=NUEVO, headers=medico).status_code == 403
    assert cliente.get("/api/pacientes", params={"q": "camila"}, headers=admin).status_code == 403
    assert cliente.get("/api/pacientes", params={"q": "camila"}, headers=medico).status_code == 200
