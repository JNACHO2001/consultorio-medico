"""RF-23 y RF-24: catálogo CIE-10, órdenes de apoyo diagnóstico y resultados (RN-20, RN-21)."""
import pytest

from tests.conftest import iniciar_sesion


@pytest.fixture
def lab(cliente):
    return iniciar_sesion(cliente, "lab1")


@pytest.fixture
def catalogo(cliente, recepcion) -> dict:
    return {p["codigo"]: p for p in cliente.get("/api/procedimientos", headers=recepcion).json()}


@pytest.fixture
def ingreso(cliente, recepcion, usuarios, pacientes) -> dict:
    r = cliente.post(
        "/api/ingresos",
        json={"paciente_id": pacientes["1000000001"]["id"], "medico_id": usuarios["dr.perez"]["id"], "motivo": "Control"},
        headers=recepcion,
    )
    assert r.status_code == 201, r.text
    return r.json()


def ordenar(cliente, medico, ingreso, procedimiento, **extra):
    return cliente.post(
        "/api/ordenes",
        json={"ingreso_id": ingreso["id"], "procedimiento_id": procedimiento["id"], **extra},
        headers=medico,
    )


def resultado(cliente, headers, orden, **cuerpo):
    return cliente.post(f"/api/ordenes/{orden['id']}/resultado", json=cuerpo, headers=headers)


HEMOGRAMA = {
    "valores": [
        {"parametro": "Hemoglobina", "valor": "10,5", "unidad": "g/dL", "ref_min": 12, "ref_max": 17.5},
        {"parametro": "Leucocitos", "valor": "7200", "unidad": "/µL", "ref_min": 4500, "ref_max": 11000},
    ],
    "interpretacion": "Anemia leve.",
}


# ------------------------------------------------------------------ CIE-10


def test_busqueda_cie10_por_codigo_y_por_texto(cliente, medico):
    por_codigo = cliente.get("/api/cie10", params={"q": "j0"}, headers=medico).json()
    assert por_codigo and all(d["codigo"].startswith("J0") for d in por_codigo[:3])
    por_texto = cliente.get("/api/cie10", params={"q": "infeccion urinaria"}, headers=medico).json()
    assert [d["codigo"] for d in por_texto] == ["N390"]
    assert cliente.get("/api/cie10", params={"q": ""}, headers=medico).json() == []


def test_recepcion_y_laboratorio_no_consultan_cie10(cliente, recepcion, lab):
    assert cliente.get("/api/cie10", params={"q": "j00"}, headers=recepcion).status_code == 403
    assert cliente.get("/api/cie10", params={"q": "j00"}, headers=lab).status_code == 403


def test_el_diagnostico_muestra_su_descripcion_solo_al_medico(cliente, medico, recepcion, ingreso):
    r = cliente.put(f"/api/ingresos/{ingreso['id']}/diagnostico", json={"codigo_cie10": "i10"}, headers=medico)
    assert r.status_code == 200
    visto = cliente.get(f"/api/ingresos/{ingreso['id']}", headers=medico).json()
    assert visto["diagnostico_principal"] == "I10"
    assert visto["diagnostico_descripcion"] == "Hipertensión esencial (primaria)"
    oculto = cliente.get(f"/api/ingresos/{ingreso['id']}", headers=recepcion).json()
    assert oculto["diagnostico_principal"] is None and oculto["diagnostico_descripcion"] is None


# ------------------------------------------------------------------ órdenes


def test_el_catalogo_marca_los_servicios_de_apoyo(catalogo):
    assert catalogo["LAB-HEM"]["area_apoyo"] == "LABORATORIO"
    assert catalogo["RX-TOR"]["area_apoyo"] == "IMAGENOLOGIA"
    assert catalogo["ECG-001"]["area_apoyo"] == "DIAGNOSTICO"
    assert catalogo["CON-GEN"]["area_apoyo"] == "NINGUNA"


def test_el_medico_ordena_y_queda_solicitada(cliente, medico, ingreso, catalogo):
    r = ordenar(cliente, medico, ingreso, catalogo["LAB-HEM"], prioridad="URGENTE", indicacion="Palidez")
    assert r.status_code == 201, r.text
    orden = r.json()
    assert orden["estado"] == "SOLICITADA" and orden["prioridad"] == "URGENTE"
    assert orden["area"] == "LABORATORIO" and orden["paciente_nombre"]
    # Pedir una orden no genera cargo: solo el resultado lo hace.
    assert cliente.get(f"/api/ingresos/{ingreso['id']}", headers=medico).json()["total"] == 0


def test_no_se_ordena_un_servicio_que_no_es_de_apoyo(cliente, medico, ingreso, catalogo):
    r = ordenar(cliente, medico, ingreso, catalogo["CUR-SIM"])
    assert r.status_code == 422 and "apoyo diagnóstico" in r.json()["detail"]


def test_solo_el_medico_tratante_ordena(cliente, otro_medico, recepcion, lab, ingreso, catalogo):
    assert ordenar(cliente, otro_medico, ingreso, catalogo["LAB-HEM"]).status_code == 403
    assert ordenar(cliente, recepcion, ingreso, catalogo["LAB-HEM"]).status_code == 403
    assert ordenar(cliente, lab, ingreso, catalogo["LAB-HEM"]).status_code == 403


def test_no_se_ordena_en_un_ingreso_con_egreso(cliente, medico, ingreso, catalogo):
    cliente.post(f"/api/ingresos/{ingreso['id']}/egreso", json={"resumen": ""}, headers=medico)
    assert ordenar(cliente, medico, ingreso, catalogo["LAB-HEM"]).status_code == 422


def test_cantidad_invalida(cliente, medico, ingreso, catalogo):
    assert ordenar(cliente, medico, ingreso, catalogo["LAB-HEM"], cantidad=0).status_code == 422


def test_el_medico_anula_una_orden_sin_resultado(cliente, medico, otro_medico, ingreso, catalogo):
    orden = ordenar(cliente, medico, ingreso, catalogo["LAB-HEM"]).json()
    assert cliente.post(f"/api/ordenes/{orden['id']}/anular", json={"motivo": "x"}, headers=otro_medico).status_code == 403
    assert cliente.post(f"/api/ordenes/{orden['id']}/anular", json={"motivo": " "}, headers=medico).status_code == 422
    r = cliente.post(f"/api/ordenes/{orden['id']}/anular", json={"motivo": "Duplicada"}, headers=medico)
    assert r.status_code == 200 and r.json()["estado"] == "ANULADA"
    assert resultado(cliente, medico, orden, **HEMOGRAMA).status_code == 422


# ------------------------------------------------------------------ resultados


def test_el_resultado_se_carga_a_la_cuenta_con_el_precio_del_convenio(
    cliente, recepcion, medico, lab, usuarios, pacientes, catalogo
):
    convenios = {c["nombre"]: c for p in cliente.get("/api/pagadores", headers=recepcion).json() for c in p["convenios"]}
    r = cliente.post(
        "/api/ingresos",
        json={
            "paciente_id": pacientes["1000000002"]["id"], "medico_id": usuarios["dr.perez"]["id"], "motivo": "Control",
            "convenio_id": convenios["Contributivo"]["id"],
        },
        headers=recepcion,
    )
    ingreso = r.json()
    orden = ordenar(cliente, medico, ingreso, catalogo["LAB-HEM"], cantidad=2).json()
    r = resultado(cliente, lab, orden, **HEMOGRAMA)
    assert r.status_code == 200, r.text
    hecha = r.json()
    assert hecha["estado"] == "REALIZADA" and hecha["registrado_por"] == "Sandra Quintero"
    assert hecha["alterada"] is True
    por_parametro = {v["parametro"]: v for v in hecha["valores"]}
    assert por_parametro["Hemoglobina"]["alterado"] is True
    assert por_parametro["Leucocitos"]["alterado"] is False
    cuenta = cliente.get(f"/api/ingresos/{ingreso['id']}", headers=medico).json()
    assert len(cuenta["procedimientos"]) == 1
    cargo = cuenta["procedimientos"][0]
    assert cargo["codigo"] == "LAB-HEM" and cargo["cantidad"] == 2
    assert cargo["valor_unitario"] == 25200  # 28.000 al 90 %
    assert cuenta["total"] == 50400


def test_el_resultado_exige_valores_o_interpretacion(cliente, medico, lab, ingreso, catalogo):
    orden = ordenar(cliente, medico, ingreso, catalogo["LAB-GLU"]).json()
    assert resultado(cliente, lab, orden).status_code == 422
    assert resultado(cliente, lab, orden, valores=[{"parametro": "Glucosa", "valor": ""}]).status_code == 422
    invertido = {"parametro": "Glucosa", "valor": "90", "ref_min": 100, "ref_max": 70}
    assert resultado(cliente, lab, orden, valores=[invertido]).status_code == 422
    ok = resultado(cliente, lab, orden, interpretacion="Normal")
    assert ok.status_code == 200 and ok.json()["alterada"] is False


def test_un_resultado_no_se_registra_dos_veces(cliente, medico, lab, ingreso, catalogo):
    orden = ordenar(cliente, medico, ingreso, catalogo["LAB-HEM"]).json()
    assert resultado(cliente, lab, orden, **HEMOGRAMA).status_code == 200
    assert resultado(cliente, lab, orden, **HEMOGRAMA).status_code == 422
    assert cliente.get(f"/api/ingresos/{ingreso['id']}", headers=medico).json()["total"] == 28000


def test_valores_no_numericos_no_se_marcan_como_alterados(cliente, medico, lab, ingreso, catalogo):
    orden = ordenar(cliente, medico, ingreso, catalogo["LAB-ORI"]).json()
    r = resultado(cliente, lab, orden, valores=[{"parametro": "Aspecto", "valor": "Turbio"}])
    assert r.json()["valores"][0]["alterado"] is None and r.json()["alterada"] is False


def test_el_egreso_espera_las_ordenes_pendientes(cliente, medico, lab, ingreso, catalogo):
    orden = ordenar(cliente, medico, ingreso, catalogo["LAB-HEM"]).json()
    r = cliente.post(f"/api/ingresos/{ingreso['id']}/egreso", json={"resumen": ""}, headers=medico)
    assert r.status_code == 422 and "sin resultado" in r.json()["detail"]
    resultado(cliente, lab, orden, **HEMOGRAMA)
    assert cliente.post(f"/api/ingresos/{ingreso['id']}/egreso", json={"resumen": ""}, headers=medico).status_code == 200


def test_el_resultado_hecho_se_factura_con_el_resto(cliente, recepcion, medico, lab, ingreso, catalogo):
    orden = ordenar(cliente, medico, ingreso, catalogo["LAB-GLU"]).json()
    resultado(cliente, lab, orden, valores=[{"parametro": "Glucosa", "valor": "92", "unidad": "mg/dL", "ref_min": 70, "ref_max": 99}])
    f = cliente.post("/api/facturas", json={"ingreso_id": ingreso["id"]}, headers=recepcion)
    assert f.status_code == 201 and f.json()["total"] == 15000


# ------------------------------------------------------------------ permisos y consulta


def test_laboratorio_ve_la_cola_y_filtra(cliente, medico, lab, ingreso, catalogo):
    a = ordenar(cliente, medico, ingreso, catalogo["LAB-HEM"]).json()
    ordenar(cliente, medico, ingreso, catalogo["RX-TOR"])
    todas = cliente.get("/api/ordenes", params={"estado": "SOLICITADA"}, headers=lab).json()
    assert len(todas) == 2
    solo_lab = cliente.get("/api/ordenes", params={"area": "LABORATORIO"}, headers=lab).json()
    assert [o["id"] for o in solo_lab] == [a["id"]]


def test_recepcion_y_administrador_no_ven_ordenes(cliente, recepcion, admin, medico, ingreso, catalogo):
    ordenar(cliente, medico, ingreso, catalogo["LAB-HEM"])
    for headers in (recepcion, admin):
        assert cliente.get("/api/ordenes", headers=headers).status_code == 403


def test_laboratorio_no_accede_a_pacientes_ni_citas_ni_facturas(cliente, lab):
    for ruta in ("/api/pacientes", "/api/facturas", "/api/ingresos", "/api/cartera"):
        assert cliente.get(ruta, headers=lab).status_code == 403, ruta


def test_las_ordenes_y_resultados_quedan_en_la_bitacora(cliente, medico, lab, admin, ingreso, catalogo):
    orden = ordenar(cliente, medico, ingreso, catalogo["LAB-HEM"]).json()
    resultado(cliente, lab, orden, **HEMOGRAMA)
    entradas = cliente.get("/api/auditoria", params={"limite": 200}, headers=admin).json()
    acciones = {(e["entidad"], e["accion"]) for e in entradas}
    assert ("Orden", "CREACION") in acciones and ("Orden", "RESULTADO") in acciones


def test_el_administrador_puede_cambiar_el_area_de_apoyo(cliente, admin, catalogo):
    r = cliente.put(f"/api/procedimientos/{catalogo['NEB-001']['id']}", json={"area_apoyo": "DIAGNOSTICO"}, headers=admin)
    assert r.status_code == 200 and r.json()["area_apoyo"] == "DIAGNOSTICO"
