"""RF-15 a RF-18: ingreso, procedimientos en la historia clínica, catálogo y facturación (RN-08 a RN-13)."""
import pytest


@pytest.fixture
def catalogo(cliente, recepcion) -> dict:
    """Catálogo demo por código."""
    return {p["codigo"]: p for p in cliente.get("/api/procedimientos", headers=recepcion).json()}


def admitir(cliente, recepcion, paciente_id, medico_id, **extra):
    cuerpo = {"paciente_id": paciente_id, "medico_id": medico_id, "tipo": "URGENCIAS", "motivo": "Dolor abdominal", **extra}
    return cliente.post("/api/ingresos", json=cuerpo, headers=recepcion)


@pytest.fixture
def ingreso(cliente, recepcion, usuarios, pacientes) -> dict:
    r = admitir(cliente, recepcion, pacientes["1000000001"]["id"], usuarios["dr.perez"]["id"])
    assert r.status_code == 201, r.text
    return r.json()


def registrar(cliente, medico, ingreso_id, procedimiento, cantidad=1, **extra):
    return cliente.post(
        f"/api/ingresos/{ingreso_id}/procedimientos",
        json={"procedimiento_id": procedimiento["id"], "cantidad": cantidad, **extra},
        headers=medico,
    )


# ------------------------------------------------------------------ listar pacientes


def test_sin_criterio_se_listan_todos_los_pacientes_ordenados(cliente, recepcion, medico):
    for headers in (recepcion, medico):
        r = cliente.get("/api/pacientes", headers=headers)
        assert r.status_code == 200
        nombres = [p["nombre_completo"] for p in r.json()]
        assert len(nombres) == 5
        assert nombres == [  # ordenados por apellido
            "Juan David Herrera Castro",
            "Ana Lucía Moreno Díaz",
            "Mariana Ortiz Peña",
            "Camila Andrea Rodríguez Silva",
            "Luis Fernando Vargas Mejía",
        ]
    assert cliente.get("/api/pacientes", params={"q": "  "}, headers=recepcion).json() == r.json()  # q vacío = todos


def test_listar_pacientes_queda_en_la_bitacora(cliente, recepcion, admin):
    cliente.get("/api/pacientes", headers=recepcion)
    hechos = {(r["usuario"], r["accion"], r["entidad"]) for r in cliente.get("/api/auditoria", headers=admin).json()}
    assert ("recepcion1", "LISTADO", "Paciente") in hechos


def test_el_administrador_no_lista_pacientes(cliente, admin):
    assert cliente.get("/api/pacientes", headers=admin).status_code == 403


# ------------------------------------------------------------------ ingreso


def test_recepcion_admite_al_paciente(cliente, ingreso, usuarios, pacientes):
    assert ingreso["estado"] == "ABIERTO"
    assert ingreso["tipo"] == "URGENCIAS"
    assert ingreso["paciente_nombre"] == pacientes["1000000001"]["nombre_completo"]
    assert ingreso["medico_nombre"] == "Dr. Andrés Pérez"
    assert ingreso["total"] == 0 and ingreso["procedimientos"] == []


def test_solo_recepcion_admite(cliente, medico, admin, usuarios, pacientes):
    cuerpo = {"paciente_id": pacientes["1000000001"]["id"], "medico_id": usuarios["dr.perez"]["id"], "motivo": "x"}
    for headers in (medico, admin):
        assert cliente.post("/api/ingresos", json=cuerpo, headers=headers).status_code == 403


def test_un_paciente_tiene_un_solo_ingreso_abierto(cliente, recepcion, ingreso, usuarios, pacientes):
    r = admitir(cliente, recepcion, pacientes["1000000001"]["id"], usuarios["dra.gomez"]["id"])
    assert r.status_code == 409  # RN-08
    assert r.json()["ingreso_abierto_id"] == ingreso["id"]
    # otro paciente sí puede ingresar
    assert admitir(cliente, recepcion, pacientes["1000000002"]["id"], usuarios["dr.perez"]["id"]).status_code == 201


def test_validaciones_del_ingreso(cliente, recepcion, usuarios, pacientes):
    medico_id = usuarios["dr.perez"]["id"]
    paciente_id = pacientes["1000000001"]["id"]
    assert admitir(cliente, recepcion, paciente_id, medico_id, motivo="   ").status_code == 422
    assert admitir(cliente, recepcion, 9999, medico_id).status_code == 404
    assert admitir(cliente, recepcion, paciente_id, 9999).status_code == 404
    assert admitir(cliente, recepcion, paciente_id, usuarios["recepcion2"]["id"]).status_code == 404  # no es médico
    assert admitir(cliente, recepcion, paciente_id, medico_id, tipo="OTRO").status_code == 422


# ------------------------------------------------------------------ procedimientos


def test_el_medico_registra_procedimientos_y_la_cuenta_suma(cliente, medico, ingreso, catalogo):
    r = registrar(cliente, medico, ingreso["id"], catalogo["CUR-SIM"], observaciones="Herida en antebrazo")
    assert r.status_code == 201
    assert r.json()["valor_unitario"] == 25000 and r.json()["subtotal"] == 25000
    registrar(cliente, medico, ingreso["id"], catalogo["INY-IM"], cantidad=3)

    cuenta = cliente.get(f"/api/ingresos/{ingreso['id']}", headers=medico).json()
    assert cuenta["n_procedimientos"] == 2
    assert cuenta["total"] == 25000 + 3 * 12000
    assert cuenta["pendiente_facturar"] == cuenta["total"]
    assert [p["codigo"] for p in cuenta["procedimientos"]] == ["CUR-SIM", "INY-IM"]  # orden cronológico


def test_solo_el_medico_tratante_registra_procedimientos(cliente, recepcion, admin, otro_medico, ingreso, catalogo):
    assert registrar(cliente, otro_medico, ingreso["id"], catalogo["CUR-SIM"]).status_code == 403
    for headers in (recepcion, admin):
        assert registrar(cliente, headers, ingreso["id"], catalogo["CUR-SIM"]).status_code == 403


def test_validaciones_de_procedimiento(cliente, medico, ingreso, catalogo):
    assert registrar(cliente, medico, ingreso["id"], {"id": 9999}).status_code == 404
    assert registrar(cliente, medico, ingreso["id"], catalogo["CUR-SIM"], cantidad=0).status_code == 422
    assert registrar(cliente, medico, ingreso["id"], catalogo["CUR-SIM"], cantidad=100).status_code == 422
    assert registrar(cliente, medico, 9999, catalogo["CUR-SIM"]).status_code == 404


def test_el_valor_queda_fijo_aunque_cambie_la_tarifa(cliente, medico, admin, ingreso, catalogo):
    realizado = registrar(cliente, medico, ingreso["id"], catalogo["CUR-SIM"]).json()
    r = cliente.put(f"/api/procedimientos/{catalogo['CUR-SIM']['id']}", json={"tarifa": 99000}, headers=admin)
    assert r.status_code == 200 and r.json()["tarifa"] == 99000

    cuenta = cliente.get(f"/api/ingresos/{ingreso['id']}", headers=medico).json()
    assert cuenta["procedimientos"][0]["valor_unitario"] == 25000  # RN-10
    assert cuenta["total"] == realizado["subtotal"] == 25000
    nuevo = registrar(cliente, medico, ingreso["id"], catalogo["CUR-SIM"]).json()
    assert nuevo["valor_unitario"] == 99000


def test_la_recepcion_ve_la_cuenta_pero_no_las_observaciones_clinicas(cliente, recepcion, medico, ingreso, catalogo):
    registrar(cliente, medico, ingreso["id"], catalogo["CUR-SIM"], observaciones="Sutura previa con complicación")
    cliente.post(f"/api/ingresos/{ingreso['id']}/egreso", json={"resumen": "Alta sin complicaciones"}, headers=medico)

    para_medico = cliente.get(f"/api/ingresos/{ingreso['id']}", headers=medico).json()
    assert para_medico["procedimientos"][0]["observaciones"] == "Sutura previa con complicación"
    assert para_medico["resumen_egreso"] == "Alta sin complicaciones"

    para_recepcion = cliente.get(f"/api/ingresos/{ingreso['id']}", headers=recepcion)
    assert para_recepcion.status_code == 200
    assert para_recepcion.json()["total"] == 25000
    assert "complicación" not in para_recepcion.text and "Alta sin" not in para_recepcion.text  # RNF-01
    por_paciente = cliente.get(f"/api/pacientes/{ingreso['paciente_id']}/ingresos", headers=recepcion)
    assert "complicación" not in por_paciente.text


def test_anular_un_procedimiento_registrado_por_error(cliente, medico, recepcion, ingreso, catalogo):
    realizado = registrar(cliente, medico, ingreso["id"], catalogo["CUR-SIM"]).json()
    base = f"/api/ingresos/{ingreso['id']}/procedimientos/{realizado['id']}/anular"

    assert cliente.post(base, json={"motivo": " "}, headers=medico).status_code == 422
    assert cliente.post(base, json={"motivo": "Se registró al paciente equivocado"}, headers=recepcion).status_code == 403
    ok = cliente.post(base, json={"motivo": "Registrado por error"}, headers=medico)
    assert ok.status_code == 200 and ok.json()["anulado"] is True
    assert cliente.post(base, json={"motivo": "otra vez"}, headers=medico).status_code == 422

    cuenta = cliente.get(f"/api/ingresos/{ingreso['id']}", headers=medico).json()
    assert cuenta["total"] == 0 and cuenta["n_procedimientos"] == 0
    assert len(cuenta["procedimientos"]) == 1  # se conserva, marcado como anulado
    # y no se factura
    assert cliente.post("/api/facturas", json={"ingreso_id": ingreso["id"]}, headers=recepcion).status_code == 422


# ------------------------------------------------------------------ egreso


def test_egreso_cierra_el_ingreso_pero_permite_facturar_y_un_nuevo_ingreso(
    cliente, medico, otro_medico, recepcion, ingreso, catalogo, usuarios
):
    registrar(cliente, medico, ingreso["id"], catalogo["NEB-001"])
    assert cliente.post(f"/api/ingresos/{ingreso['id']}/egreso", json={}, headers=otro_medico).status_code == 403
    assert cliente.post(f"/api/ingresos/{ingreso['id']}/egreso", json={}, headers=recepcion).status_code == 403

    r = cliente.post(f"/api/ingresos/{ingreso['id']}/egreso", json={"resumen": "Mejoría"}, headers=medico)
    assert r.status_code == 200
    assert r.json()["estado"] == "EGRESADO" and r.json()["fecha_egreso"]

    # ya no se cargan procedimientos ni se repite el egreso (RN-09)
    assert registrar(cliente, medico, ingreso["id"], catalogo["NEB-001"]).status_code == 422
    assert cliente.post(f"/api/ingresos/{ingreso['id']}/egreso", json={}, headers=medico).status_code == 422
    # lo pendiente sí se factura
    assert cliente.post("/api/facturas", json={"ingreso_id": ingreso["id"]}, headers=recepcion).status_code == 201
    # y el paciente puede volver a ingresar
    assert admitir(cliente, recepcion, ingreso["paciente_id"], usuarios["dra.gomez"]["id"]).status_code == 201


def test_listado_de_ingresos_con_filtros(cliente, recepcion, medico, otro_medico, usuarios, pacientes, ingreso):
    admitir(cliente, recepcion, pacientes["1000000002"]["id"], usuarios["dra.gomez"]["id"])

    todos = cliente.get("/api/ingresos", headers=recepcion).json()
    assert len(todos) == 2
    suyos = cliente.get("/api/ingresos", params={"medico_id": usuarios["dr.perez"]["id"]}, headers=medico).json()
    assert [i["id"] for i in suyos] == [ingreso["id"]]
    assert cliente.get("/api/ingresos", params={"estado": "EGRESADO"}, headers=recepcion).json() == []
    assert cliente.get("/api/ingresos", params={"estado": "ABIERTO"}, headers=recepcion).json() != []


# ------------------------------------------------------------------ facturación


def test_facturar_todos_los_pendientes(cliente, medico, recepcion, ingreso, catalogo):
    registrar(cliente, medico, ingreso["id"], catalogo["CUR-SIM"])
    registrar(cliente, medico, ingreso["id"], catalogo["INY-IM"], cantidad=2)

    r = cliente.post("/api/facturas", json={"ingreso_id": ingreso["id"]}, headers=recepcion)
    assert r.status_code == 201
    factura = r.json()
    assert factura["estado"] == "EMITIDA"
    assert factura["numero"] == f"FAC-{factura['id']:06d}"
    assert factura["total"] == 25000 + 2 * 12000
    assert [(linea["codigo"], linea["subtotal"]) for linea in factura["lineas"]] == [("CUR-SIM", 25000), ("INY-IM", 24000)]
    assert factura["paciente_nombre"] and factura["emitida_por"] == "Laura Martínez"

    cuenta = cliente.get(f"/api/ingresos/{ingreso['id']}", headers=recepcion).json()
    assert cuenta["pendiente_facturar"] == 0 and cuenta["total"] == 49000
    assert {p["factura_numero"] for p in cuenta["procedimientos"]} == {factura["numero"]}
    # RN-12: nada más por facturar
    assert cliente.post("/api/facturas", json={"ingreso_id": ingreso["id"]}, headers=recepcion).status_code == 422


def test_facturar_procedimientos_elegidos_uno_por_uno(cliente, medico, recepcion, ingreso, catalogo):
    a = registrar(cliente, medico, ingreso["id"], catalogo["ECG-001"]).json()
    b = registrar(cliente, medico, ingreso["id"], catalogo["LAB-HEM"]).json()

    primera = cliente.post("/api/facturas", json={"ingreso_id": ingreso["id"], "procedimiento_ids": [a["id"]]}, headers=recepcion)
    assert primera.status_code == 201 and primera.json()["total"] == 55000
    # el mismo procedimiento no se factura otra vez
    repetida = cliente.post("/api/facturas", json={"ingreso_id": ingreso["id"], "procedimiento_ids": [a["id"]]}, headers=recepcion)
    assert repetida.status_code == 422
    segunda = cliente.post("/api/facturas", json={"ingreso_id": ingreso["id"], "procedimiento_ids": [b["id"]]}, headers=recepcion)
    assert segunda.status_code == 201 and segunda.json()["total"] == 28000
    assert segunda.json()["id"] != primera.json()["id"]
    # un procedimiento duplicado en la misma solicitud o ajeno al ingreso se rechaza
    assert cliente.post("/api/facturas", json={"ingreso_id": ingreso["id"], "procedimiento_ids": [b["id"], b["id"]]}, headers=recepcion).status_code == 422
    assert cliente.post("/api/facturas", json={"ingreso_id": ingreso["id"], "procedimiento_ids": [9999]}, headers=recepcion).status_code == 422


def test_facturacion_sin_ingreso_o_sin_procedimientos(cliente, recepcion, ingreso):
    assert cliente.post("/api/facturas", json={"ingreso_id": 9999}, headers=recepcion).status_code == 404
    assert cliente.post("/api/facturas", json={"ingreso_id": ingreso["id"]}, headers=recepcion).status_code == 422


def test_solo_recepcion_factura_y_el_administrador_solo_consulta(cliente, medico, admin, recepcion, ingreso, catalogo):
    registrar(cliente, medico, ingreso["id"], catalogo["CUR-SIM"])
    for headers in (medico, admin):
        assert cliente.post("/api/facturas", json={"ingreso_id": ingreso["id"]}, headers=headers).status_code == 403
    factura = cliente.post("/api/facturas", json={"ingreso_id": ingreso["id"]}, headers=recepcion).json()

    assert cliente.get("/api/facturas", headers=admin).status_code == 200
    assert cliente.get(f"/api/facturas/{factura['id']}", headers=admin).status_code == 200
    assert cliente.get("/api/facturas", headers=medico).status_code == 403
    assert cliente.post(f"/api/facturas/{factura['id']}/pagar", json={"metodo_pago": "EFECTIVO"}, headers=admin).status_code == 403
    assert cliente.post(f"/api/facturas/{factura['id']}/anular", json={"motivo": "x"}, headers=admin).status_code == 403


def test_pagar_una_factura(cliente, medico, recepcion, ingreso, catalogo):
    registrar(cliente, medico, ingreso["id"], catalogo["CUR-SIM"])
    factura = cliente.post("/api/facturas", json={"ingreso_id": ingreso["id"]}, headers=recepcion).json()
    url = f"/api/facturas/{factura['id']}"

    assert cliente.post(f"{url}/pagar", json={"metodo_pago": "BITCOIN"}, headers=recepcion).status_code == 422
    r = cliente.post(f"{url}/pagar", json={"metodo_pago": "TARJETA"}, headers=recepcion)
    assert r.status_code == 200
    assert r.json()["estado"] == "PAGADA" and r.json()["metodo_pago"] == "TARJETA" and r.json()["fecha_pago"]
    # no se paga dos veces ni se anula una factura pagada
    assert cliente.post(f"{url}/pagar", json={"metodo_pago": "EFECTIVO"}, headers=recepcion).status_code == 422
    assert cliente.post(f"{url}/anular", json={"motivo": "x"}, headers=recepcion).status_code == 422


def test_anular_una_factura_libera_sus_procedimientos(cliente, medico, recepcion, ingreso, catalogo):
    registrar(cliente, medico, ingreso["id"], catalogo["CUR-SIM"])
    factura = cliente.post("/api/facturas", json={"ingreso_id": ingreso["id"]}, headers=recepcion).json()
    url = f"/api/facturas/{factura['id']}/anular"

    assert cliente.post(url, json={"motivo": "  "}, headers=recepcion).status_code == 422
    r = cliente.post(url, json={"motivo": "Error en el valor"}, headers=recepcion)
    assert r.status_code == 200 and r.json()["estado"] == "ANULADA" and r.json()["motivo_anulacion"] == "Error en el valor"
    assert cliente.post(url, json={"motivo": "otra vez"}, headers=recepcion).status_code == 422

    cuenta = cliente.get(f"/api/ingresos/{ingreso['id']}", headers=recepcion).json()
    assert cuenta["pendiente_facturar"] == 25000  # RN-13: vuelve a quedar pendiente
    nueva = cliente.post("/api/facturas", json={"ingreso_id": ingreso["id"]}, headers=recepcion)
    assert nueva.status_code == 201 and nueva.json()["id"] != factura["id"]
    # un procedimiento ya facturado no se puede anular
    realizado_id = cuenta["procedimientos"][0]["id"]
    r = cliente.post(
        f"/api/ingresos/{ingreso['id']}/procedimientos/{realizado_id}/anular", json={"motivo": "x"}, headers=medico
    )
    assert r.status_code == 422 and "factur" in r.json()["detail"]


def test_listado_de_facturas_con_filtros(cliente, medico, recepcion, admin, ingreso, catalogo):
    registrar(cliente, medico, ingreso["id"], catalogo["CUR-SIM"])
    factura = cliente.post("/api/facturas", json={"ingreso_id": ingreso["id"]}, headers=recepcion).json()
    cliente.post(f"/api/facturas/{factura['id']}/pagar", json={"metodo_pago": "EFECTIVO"}, headers=recepcion)

    assert len(cliente.get("/api/facturas", headers=admin).json()) == 1
    assert len(cliente.get("/api/facturas", params={"estado": "PAGADA"}, headers=admin).json()) == 1
    assert cliente.get("/api/facturas", params={"estado": "EMITIDA"}, headers=admin).json() == []
    assert len(cliente.get("/api/facturas", params={"paciente_id": ingreso["paciente_id"]}, headers=admin).json()) == 1
    assert cliente.get("/api/facturas", params={"paciente_id": 9999}, headers=admin).json() == []
    assert cliente.get("/api/facturas/9999", headers=admin).status_code == 404


# ------------------------------------------------------------------ catálogo e historia clínica


def test_catalogo_lo_gestiona_el_administrador(cliente, admin, recepcion, medico):
    nuevo = {"codigo": "eco-001", "nombre": "Ecografía abdominal", "tarifa": 120000}
    assert cliente.post("/api/procedimientos", json=nuevo, headers=recepcion).status_code == 403
    r = cliente.post("/api/procedimientos", json=nuevo, headers=admin)
    assert r.status_code == 201 and r.json()["codigo"] == "ECO-001"
    assert cliente.post("/api/procedimientos", json=nuevo, headers=admin).status_code == 409

    for malo in (
        {**nuevo, "codigo": "ECO-002", "tarifa": 0},
        {**nuevo, "codigo": "ECO-002", "tarifa": -5},
        {**nuevo, "codigo": "ECO-002", "nombre": " "},
        {**nuevo, "codigo": "x"},
    ):
        assert cliente.post("/api/procedimientos", json=malo, headers=admin).status_code == 422, malo

    assert "ECO-001" in {p["codigo"] for p in cliente.get("/api/procedimientos", headers=medico).json()}
    assert cliente.post(f"/api/procedimientos/{r.json()['id']}/desactivar", headers=admin).status_code == 204
    assert "ECO-001" not in {p["codigo"] for p in cliente.get("/api/procedimientos", headers=medico).json()}


def test_procedimientos_aparecen_en_la_historia_del_paciente(cliente, medico, recepcion, ingreso, catalogo):
    registrar(cliente, medico, ingreso["id"], catalogo["RX-TOR"], observaciones="Sin hallazgos")
    r = cliente.get(f"/api/pacientes/{ingreso['paciente_id']}/ingresos", headers=medico)
    assert r.status_code == 200
    assert r.json()[0]["procedimientos"][0]["nombre"] == "Radiografía de tórax"
    assert r.json()[0]["procedimientos"][0]["observaciones"] == "Sin hallazgos"
    assert cliente.get("/api/pacientes/9999/ingresos", headers=medico).status_code == 404


def test_la_bitacora_registra_ingresos_procedimientos_y_facturas(cliente, medico, recepcion, admin, ingreso, catalogo):
    registrar(cliente, medico, ingreso["id"], catalogo["CUR-SIM"])
    factura = cliente.post("/api/facturas", json={"ingreso_id": ingreso["id"]}, headers=recepcion).json()
    cliente.post(f"/api/facturas/{factura['id']}/pagar", json={"metodo_pago": "EFECTIVO"}, headers=recepcion)

    hechos = {(r["usuario"], r["accion"], r["entidad"]) for r in cliente.get("/api/auditoria", params={"limite": 1000}, headers=admin).json()}
    assert ("recepcion1", "CREACION", "Ingreso") in hechos
    assert ("dr.perez", "CREACION", "Procedimiento") in hechos
    assert ("recepcion1", "CREACION", "Factura") in hechos
    assert ("recepcion1", "MODIFICACION", "Factura") in hechos
    assert ("recepcion1", "MODIFICACION", "Procedimiento") in hechos  # se marcó como facturado
