"""RF-19 a RF-22: pagadores y convenios, cartera con glosas y borrador del RIPS (RN-14 a RN-19)."""
from datetime import date, timedelta

import pytest


@pytest.fixture
def catalogo(cliente, recepcion) -> dict:
    return {p["codigo"]: p for p in cliente.get("/api/procedimientos", headers=recepcion).json()}


@pytest.fixture
def convenios(cliente, recepcion) -> dict:
    """Convenios demo por nombre."""
    resultado = {}
    for pagador in cliente.get("/api/pagadores", headers=recepcion).json():
        for convenio in pagador["convenios"]:
            resultado[convenio["nombre"]] = convenio
    return resultado


def admitir(cliente, recepcion, usuarios, paciente, convenio=None, autorizacion="", medico="dr.perez"):
    cuerpo = {
        "paciente_id": paciente["id"],
        "medico_id": usuarios[medico]["id"],
        "tipo": "AMBULATORIO",
        "motivo": "Control",
        "numero_autorizacion": autorizacion,
    }
    if convenio is not None:
        cuerpo["convenio_id"] = convenio["id"]
    return cliente.post("/api/ingresos", json=cuerpo, headers=recepcion)


def registrar(cliente, medico, ingreso_id, procedimiento, cantidad=1):
    r = cliente.post(
        f"/api/ingresos/{ingreso_id}/procedimientos",
        json={"procedimiento_id": procedimiento["id"], "cantidad": cantidad},
        headers=medico,
    )
    assert r.status_code == 201, r.text
    return r.json()


def cuenta_con_convenio(cliente, recepcion, medico, usuarios, pacientes, catalogo, convenio, codigos, autorizacion=""):
    """Admite al paciente 1 con el convenio, registra los procedimientos y devuelve (ingreso, factura)."""
    r = admitir(cliente, recepcion, usuarios, pacientes["1000000001"], convenio, autorizacion)
    assert r.status_code == 201, r.text
    ingreso = r.json()
    for codigo in codigos:
        registrar(cliente, medico, ingreso["id"], catalogo[codigo])
    f = cliente.post("/api/facturas", json={"ingreso_id": ingreso["id"]}, headers=recepcion)
    assert f.status_code == 201, f.text
    return ingreso, f.json()


@pytest.fixture
def factura_eps(cliente, recepcion, medico, usuarios, pacientes, catalogo, convenios) -> dict:
    """Factura del convenio Contributivo: 22.500 + 63.000 = 85.500; el paciente paga 5.000 y la EPS 80.500."""
    return cuenta_con_convenio(
        cliente, recepcion, medico, usuarios, pacientes, catalogo, convenios["Contributivo"], ["CUR-SIM", "RX-TOR"]
    )[1]


def url(factura, sufijo=""):
    return f"/api/facturas/{factura['id']}{sufijo}"


def radicar(cliente, recepcion, factura, **cuerpo):
    return cliente.post(url(factura, "/radicar"), json=cuerpo, headers=recepcion)


# ------------------------------------------------------------------ pagadores y convenios


def test_existen_el_particular_y_los_pagadores_demo(cliente, recepcion, convenios):
    pagadores = cliente.get("/api/pagadores", headers=recepcion).json()
    assert [p["nombre"] for p in pagadores][0] == "Particular"
    assert {"EPS Demo", "EPS Demo B", "Seguros Demo (SOAT)"} <= {p["nombre"] for p in pagadores}
    particular = convenios["Tarifa particular"]
    assert (particular["porcentaje_tarifa"], particular["copago_porcentaje"]) == (100, 100)


def test_solo_el_administrador_gestiona_pagadores_y_convenios(cliente, admin, recepcion, medico):
    nuevo = {"codigo": "eps-nueva", "nombre": "EPS Nueva", "tipo": "EPS", "nit": "800111222-3"}
    for headers in (recepcion, medico):
        assert cliente.post("/api/pagadores", json=nuevo, headers=headers).status_code == 403
    assert cliente.get("/api/pagadores", headers=medico).status_code == 403

    r = cliente.post("/api/pagadores", json=nuevo, headers=admin)
    assert r.status_code == 201 and r.json()["codigo"] == "EPS-NUEVA"
    assert cliente.post("/api/pagadores", json=nuevo, headers=admin).status_code == 409  # código repetido
    assert cliente.post("/api/pagadores", json={**nuevo, "codigo": "OTRA", "tipo": "PARTICULAR"}, headers=admin).status_code == 422
    assert cliente.post("/api/pagadores", json={**nuevo, "codigo": "x"}, headers=admin).status_code == 422

    pagador_id = r.json()["id"]
    condiciones = {"nombre": "Plan complementario", "porcentaje_tarifa": 95, "copago_porcentaje": 20, "cuota_moderadora": 3000}
    c = cliente.post(f"/api/pagadores/{pagador_id}/convenios", json=condiciones, headers=admin)
    assert c.status_code == 201 and c.json()["requiere_autorizacion"] is False
    for malo in (
        {**condiciones, "porcentaje_tarifa": 0},
        {**condiciones, "porcentaje_tarifa": 301},
        {**condiciones, "copago_porcentaje": 101},
        {**condiciones, "cuota_moderadora": -1},
        {**condiciones, "nombre": " "},
    ):
        assert cliente.post(f"/api/pagadores/{pagador_id}/convenios", json=malo, headers=admin).status_code == 422, malo

    cambio = cliente.put(f"/api/convenios/{c.json()['id']}", json={"copago_porcentaje": 30}, headers=admin)
    assert cambio.status_code == 200 and cambio.json()["copago_porcentaje"] == 30
    assert cliente.put("/api/convenios/9999", json={"copago_porcentaje": 5}, headers=admin).status_code == 404


def test_el_particular_es_fijo(cliente, admin, recepcion, convenios):
    pagadores = {p["nombre"]: p for p in cliente.get("/api/pagadores", headers=recepcion).json()}
    particular = pagadores["Particular"]
    assert cliente.post(f"/api/pagadores/{particular['id']}/desactivar", headers=admin).status_code == 422
    assert cliente.post(f"/api/pagadores/{particular['id']}/convenios", json={"nombre": "Otro"}, headers=admin).status_code == 422
    convenio_id = convenios["Tarifa particular"]["id"]
    assert cliente.put(f"/api/convenios/{convenio_id}", json={"copago_porcentaje": 0}, headers=admin).status_code == 422
    assert cliente.post(f"/api/convenios/{convenio_id}/desactivar", headers=admin).status_code == 422


def test_retirar_un_pagador_retira_sus_convenios(cliente, admin, recepcion, usuarios, pacientes, convenios):
    pagadores = {p["nombre"]: p for p in cliente.get("/api/pagadores", headers=recepcion).json()}
    assert cliente.post(f"/api/pagadores/{pagadores['EPS Demo']['id']}/desactivar", headers=admin).status_code == 204
    assert "EPS Demo" not in {p["nombre"] for p in cliente.get("/api/pagadores", headers=recepcion).json()}
    # ya no se puede admitir con un convenio retirado
    r = admitir(cliente, recepcion, usuarios, pacientes["1000000001"], convenios["Contributivo"])
    assert r.status_code == 404


# ------------------------------------------------------------------ admisión con convenio y valores


def test_sin_convenio_se_admite_como_particular(cliente, recepcion, usuarios, pacientes, convenios):
    ingreso = admitir(cliente, recepcion, usuarios, pacientes["1000000001"]).json()
    assert ingreso["convenio_id"] == convenios["Tarifa particular"]["id"]
    assert ingreso["pagador_nombre"] == "Particular"


def test_el_convenio_ajusta_la_tarifa_y_se_copia_al_registrar(cliente, recepcion, medico, admin, usuarios, pacientes, catalogo, convenios):
    ingreso = admitir(cliente, recepcion, usuarios, pacientes["1000000001"], convenios["Contributivo"]).json()
    realizado = registrar(cliente, medico, ingreso["id"], catalogo["CUR-SIM"])
    assert realizado["valor_unitario"] == 22500  # 25.000 al 90 %  (RN-14)
    # cambiar el convenio o la tarifa después no altera lo ya registrado (RN-10)
    cliente.put(f"/api/convenios/{convenios['Contributivo']['id']}", json={"porcentaje_tarifa": 50}, headers=admin)
    cliente.put(f"/api/procedimientos/{catalogo['CUR-SIM']['id']}", json={"tarifa": 99000}, headers=admin)
    cuenta = cliente.get(f"/api/ingresos/{ingreso['id']}", headers=recepcion).json()
    assert cuenta["procedimientos"][0]["valor_unitario"] == 22500
    assert cuenta["convenio_nombre"] == "Contributivo"


def test_un_convenio_con_autorizacion_la_exige_al_admitir(cliente, recepcion, usuarios, pacientes, convenios):
    r = admitir(cliente, recepcion, usuarios, pacientes["1000000001"], convenios["Subsidiado"])
    assert r.status_code == 422 and "autorización" in r.json()["detail"]  # RN-16
    r = admitir(cliente, recepcion, usuarios, pacientes["1000000001"], convenios["Subsidiado"], autorizacion="AUT-123")
    assert r.status_code == 201 and r.json()["numero_autorizacion"] == "AUT-123"


def test_el_particular_paga_todo_como_antes(cliente, recepcion, medico, usuarios, pacientes, catalogo, convenios):
    _, factura = cuenta_con_convenio(
        cliente, recepcion, medico, usuarios, pacientes, catalogo, convenios["Tarifa particular"], ["CUR-SIM"]
    )
    assert (factura["total"], factura["valor_paciente"], factura["valor_pagador"]) == (25000, 25000, 0)
    assert factura["pagador_nombre"] == "Particular" and factura["saldo"] == 25000
    r = cliente.post(url(factura, "/pagar"), json={"metodo_pago": "EFECTIVO"}, headers=recepcion).json()
    assert r["estado"] == "PAGADA" and r["saldo"] == 0 and r["pagado_paciente"] == 25000


def test_reparto_entre_paciente_y_pagador(cliente, factura_eps):
    assert factura_eps["total"] == 85500
    assert factura_eps["valor_paciente"] == 5000  # cuota moderadora
    assert factura_eps["valor_pagador"] == 80500
    assert factura_eps["pagador_nombre"] == "EPS Demo" and factura_eps["convenio_nombre"] == "Contributivo"


def test_copago_porcentual(cliente, recepcion, medico, usuarios, pacientes, catalogo, convenios):
    _, f = cuenta_con_convenio(
        cliente, recepcion, medico, usuarios, pacientes, catalogo, convenios["Subsidiado"], ["LAB-HEM"], "AUT-9"
    )
    assert f["total"] == 23800  # 28.000 al 85 %
    assert (f["valor_paciente"], f["valor_pagador"]) == (2380, 21420)  # copago del 10 %


def test_la_cuota_moderadora_se_cobra_una_sola_vez_por_ingreso(cliente, recepcion, medico, usuarios, pacientes, catalogo, convenios):
    ingreso = admitir(cliente, recepcion, usuarios, pacientes["1000000001"], convenios["Contributivo"]).json()
    a = registrar(cliente, medico, ingreso["id"], catalogo["CUR-SIM"])
    b = registrar(cliente, medico, ingreso["id"], catalogo["RX-TOR"])
    primera = cliente.post("/api/facturas", json={"ingreso_id": ingreso["id"], "procedimiento_ids": [a["id"]]}, headers=recepcion).json()
    segunda = cliente.post("/api/facturas", json={"ingreso_id": ingreso["id"], "procedimiento_ids": [b["id"]]}, headers=recepcion).json()
    assert primera["valor_paciente"] == 5000 and segunda["valor_paciente"] == 0
    assert segunda["valor_pagador"] == 63000


# ------------------------------------------------------------------ cobro al paciente y anulación


def test_pagar_el_copago_deja_la_factura_abierta_para_el_pagador(cliente, recepcion, factura_eps):
    r = cliente.post(url(factura_eps, "/pagar"), json={"metodo_pago": "EFECTIVO"}, headers=recepcion).json()
    assert r["estado"] == "EMITIDA" and r["saldo_paciente"] == 0 and r["saldo_pagador"] == 80500
    # el paciente no vuelve a pagar
    again = cliente.post(url(factura_eps, "/pagar"), json={"metodo_pago": "EFECTIVO"}, headers=recepcion)
    assert again.status_code == 422 and "saldo" in again.json()["detail"]


def test_una_factura_radicada_o_con_pagos_no_se_anula(cliente, recepcion, factura_eps):
    assert radicar(cliente, recepcion, factura_eps).status_code == 200
    r = cliente.post(url(factura_eps, "/anular"), json={"motivo": "Error"}, headers=recepcion)
    assert r.status_code == 422 and "radicada" in r.json()["detail"]  # RN-17


def test_una_factura_con_pago_del_paciente_no_se_anula(cliente, recepcion, factura_eps):
    cliente.post(url(factura_eps, "/pagar"), json={"metodo_pago": "EFECTIVO"}, headers=recepcion)
    r = cliente.post(url(factura_eps, "/anular"), json={"motivo": "Error"}, headers=recepcion)
    assert r.status_code == 422 and "pagos" in r.json()["detail"]


# ------------------------------------------------------------------ radicación y abonos


def test_radicar_una_factura(cliente, recepcion, factura_eps):
    r = radicar(cliente, recepcion, factura_eps)
    assert r.status_code == 200
    assert r.json()["fecha_radicacion"] and r.json()["numero_radicacion"].startswith("RAD-")
    assert r.json()["dias_radicada"] == 0
    assert radicar(cliente, recepcion, factura_eps).status_code == 422  # ya radicada


def test_se_puede_indicar_el_numero_de_radicacion(cliente, recepcion, factura_eps):
    r = radicar(cliente, recepcion, factura_eps, numero_radicacion="  EPS-2026-001 ")
    assert r.json()["numero_radicacion"] == "EPS-2026-001"


def test_no_se_radica_lo_que_no_tiene_pagador(cliente, recepcion, medico, usuarios, pacientes, catalogo, convenios):
    _, particular = cuenta_con_convenio(
        cliente, recepcion, medico, usuarios, pacientes, catalogo, convenios["Tarifa particular"], ["CUR-SIM"]
    )
    assert radicar(cliente, recepcion, particular).status_code == 422
    assert radicar(cliente, recepcion, {"id": 9999}).status_code == 404


def test_abonos_del_pagador_hasta_saldar_la_factura(cliente, recepcion, factura_eps):
    sin_radicar = cliente.post(url(factura_eps, "/pagos-pagador"), json={"valor": 1000}, headers=recepcion)
    assert sin_radicar.status_code == 422  # RN-18
    radicar(cliente, recepcion, factura_eps)
    cliente.post(url(factura_eps, "/pagar"), json={"metodo_pago": "TARJETA"}, headers=recepcion)

    for malo in (0, -5, 80501):
        assert cliente.post(url(factura_eps, "/pagos-pagador"), json={"valor": malo}, headers=recepcion).status_code == 422, malo

    parcial = cliente.post(url(factura_eps, "/pagos-pagador"), json={"valor": 30000, "referencia": "TR-1"}, headers=recepcion).json()
    assert parcial["estado"] == "EMITIDA" and parcial["saldo_pagador"] == 50500 and parcial["pagado_pagador"] == 30000
    final = cliente.post(url(factura_eps, "/pagos-pagador"), json={"valor": 50500}, headers=recepcion).json()
    assert final["estado"] == "PAGADA" and final["saldo"] == 0 and final["fecha_pago"]
    assert [p["origen"] for p in final["pagos"]] == ["PACIENTE", "PAGADOR", "PAGADOR"]
    # una factura saldada no admite más pagos
    assert cliente.post(url(factura_eps, "/pagos-pagador"), json={"valor": 1}, headers=recepcion).status_code == 422


# ------------------------------------------------------------------ glosas


def glosar(cliente, recepcion, factura, valor=20000, concepto="TARIFAS", motivo="Tarifa diferente a la pactada"):
    return cliente.post(url(factura, "/glosas"), json={"concepto": concepto, "motivo": motivo, "valor": valor}, headers=recepcion)


def test_las_glosas_se_registran_sobre_facturas_radicadas(cliente, recepcion, factura_eps):
    assert glosar(cliente, recepcion, factura_eps).status_code == 422  # RN-19: aún sin radicar
    radicar(cliente, recepcion, factura_eps)
    r = glosar(cliente, recepcion, factura_eps)
    assert r.status_code == 201
    glosa = r.json()["glosas"][0]
    assert glosa["id"] == 1 and glosa["estado"] == "ABIERTA" and glosa["valor"] == 20000
    assert r.json()["glosa_en_disputa"] == 20000

    for malo in ({"valor": 0}, {"valor": 70000}, {"motivo": "  "}, {"concepto": "INVENTADO"}):
        cuerpo = {"concepto": "TARIFAS", "motivo": "x", "valor": 1000, **malo}
        assert cliente.post(url(factura_eps, "/glosas"), json=cuerpo, headers=recepcion).status_code == 422, malo


def test_glosa_aceptada_baja_lo_que_se_cobra(cliente, recepcion, factura_eps):
    radicar(cliente, recepcion, factura_eps)
    glosar(cliente, recepcion, factura_eps, valor=20000)
    r = cliente.post(url(factura_eps, "/glosas/1/resolver"), json={"aceptada": True, "nota": "Error nuestro"}, headers=recepcion).json()
    assert r["glosas"][0]["estado"] == "ACEPTADA"
    assert r["glosado_aceptado"] == 20000 and r["glosa_en_disputa"] == 0 and r["saldo_pagador"] == 60500
    # el pagador paga lo que quedó y la factura se cierra una vez que el paciente también pagó
    cliente.post(url(factura_eps, "/pagos-pagador"), json={"valor": 60500}, headers=recepcion)
    assert cliente.get(url(factura_eps), headers=recepcion).json()["estado"] == "EMITIDA"  # falta el copago
    cerrada = cliente.post(url(factura_eps, "/pagar"), json={"metodo_pago": "EFECTIVO"}, headers=recepcion).json()
    assert cerrada["estado"] == "PAGADA" and cerrada["saldo"] == 0


def test_responder_y_levantar_una_glosa(cliente, recepcion, factura_eps):
    radicar(cliente, recepcion, factura_eps)
    glosar(cliente, recepcion, factura_eps, valor=30000)
    assert cliente.post(url(factura_eps, "/glosas/1/responder"), json={"respuesta": " "}, headers=recepcion).status_code == 422
    r = cliente.post(url(factura_eps, "/glosas/1/responder"), json={"respuesta": "Soporte adjunto"}, headers=recepcion).json()
    assert r["glosas"][0]["estado"] == "RESPONDIDA" and r["glosas"][0]["fecha_respuesta"]
    assert cliente.post(url(factura_eps, "/glosas/1/responder"), json={"respuesta": "otra"}, headers=recepcion).status_code == 422

    levantada = cliente.post(url(factura_eps, "/glosas/1/resolver"), json={"aceptada": False}, headers=recepcion).json()
    assert levantada["glosas"][0]["estado"] == "LEVANTADA"
    assert levantada["saldo_pagador"] == 80500 and levantada["glosa_en_disputa"] == 0
    assert cliente.post(url(factura_eps, "/glosas/1/resolver"), json={"aceptada": True}, headers=recepcion).status_code == 422
    assert cliente.post(url(factura_eps, "/glosas/9/resolver"), json={"aceptada": True}, headers=recepcion).status_code == 404


def test_el_pagador_solo_paga_lo_que_no_esta_glosado(cliente, recepcion, factura_eps):
    radicar(cliente, recepcion, factura_eps)
    glosar(cliente, recepcion, factura_eps, valor=30000)
    assert cliente.post(url(factura_eps, "/pagos-pagador"), json={"valor": 50501}, headers=recepcion).status_code == 422
    ok = cliente.post(url(factura_eps, "/pagos-pagador"), json={"valor": 50500}, headers=recepcion).json()
    assert ok["saldo_pagador"] == 30000 and ok["estado"] == "EMITIDA"  # queda la glosa en disputa
    # no se puede glosar más de lo que queda libre
    assert glosar(cliente, recepcion, factura_eps, valor=1).status_code == 422


def test_la_factura_no_se_cierra_con_glosas_en_disputa(cliente, recepcion, factura_eps):
    cliente.post(url(factura_eps, "/pagar"), json={"metodo_pago": "EFECTIVO"}, headers=recepcion)
    radicar(cliente, recepcion, factura_eps)
    glosar(cliente, recepcion, factura_eps, valor=80500)  # glosan todo
    r = cliente.post(url(factura_eps, "/glosas/1/resolver"), json={"aceptada": True}, headers=recepcion).json()
    assert r["saldo"] == 0 and r["estado"] == "PAGADA"  # todo aceptado, sin nada más que cobrar


# ------------------------------------------------------------------ cartera


def test_la_cartera_resume_por_pagador_y_antiguedad(cliente, recepcion, admin, medico, usuarios, pacientes, catalogo, convenios, factura_eps):
    # la factura de la EPS queda sin radicar; una segunda del mismo pagador se radica
    ingreso_b = admitir(cliente, recepcion, usuarios, pacientes["1000000002"], convenios["Contributivo"]).json()
    registrar(cliente, medico, ingreso_b["id"], catalogo["LAB-GLU"])  # 15.000 al 90 % = 13.500
    segunda = cliente.post("/api/facturas", json={"ingreso_id": ingreso_b["id"]}, headers=recepcion).json()
    radicar(cliente, recepcion, segunda)
    glosar(cliente, recepcion, segunda, valor=4000)

    for headers in (recepcion, admin):
        filas = cliente.get("/api/cartera", headers=headers).json()
        assert [f["pagador_nombre"] for f in filas] == ["EPS Demo"]
        fila = filas[0]
        assert fila["n_facturas"] == 2
        assert fila["facturado"] == 80500 + 8500  # la segunda: 13.500 - 5.000 de cuota
        assert fila["en_disputa"] == 4000 and fila["saldo"] == 89000
        assert fila["tramos"]["sin_radicar"] == 80500 and fila["tramos"]["d0_30"] == 8500

    detalle = cliente.get(f"/api/cartera/{filas[0]['pagador_id']}", headers=admin).json()
    assert len(detalle["facturas"]) == 2 and detalle["resumen"]["saldo"] == 89000
    assert cliente.get("/api/cartera/9999", headers=admin).status_code == 404


def test_las_anuladas_y_las_de_particulares_no_entran_en_la_cartera(cliente, recepcion, medico, usuarios, pacientes, catalogo, convenios):
    _, eps = cuenta_con_convenio(cliente, recepcion, medico, usuarios, pacientes, catalogo, convenios["Contributivo"], ["CUR-SIM"])
    cliente.post(url(eps, "/anular"), json={"motivo": "Error"}, headers=recepcion)
    ingreso = admitir(cliente, recepcion, usuarios, pacientes["1000000002"]).json()
    registrar(cliente, medico, ingreso["id"], catalogo["CUR-SIM"])
    cliente.post("/api/facturas", json={"ingreso_id": ingreso["id"]}, headers=recepcion)
    assert cliente.get("/api/cartera", headers=recepcion).json() == []


def test_la_edad_de_la_cartera_corre_desde_la_radicacion(app, cliente, recepcion, factura_eps):
    radicar(cliente, recepcion, factura_eps)
    fila = cliente.get("/api/cartera", headers=recepcion).json()[0]
    assert fila["tramos"]["d0_30"] == 80500
    # se envejece la radicación 45 días y la cartera pasa al tramo de 31 a 60
    c = app.state.contenedor
    guardada = c.repo_facturas.obtener_por_id(factura_eps["id"])
    guardada.fecha_radicacion = guardada.fecha_radicacion - timedelta(days=45)
    c.repo_facturas.actualizar(guardada)
    fila = cliente.get("/api/cartera", headers=recepcion).json()[0]
    assert fila["tramos"]["d31_60"] == 80500 and fila["tramos"]["d0_30"] == 0
    assert cliente.get(url(factura_eps), headers=recepcion).json()["dias_radicada"] == 45


def test_permisos_de_cartera(cliente, medico, recepcion, factura_eps):
    assert cliente.get("/api/cartera", headers=medico).status_code == 403
    assert cliente.get("/api/cartera").status_code == 401
    for sufijo, cuerpo in (("/radicar", {}), ("/pagos-pagador", {"valor": 1}), ("/glosas", {"concepto": "TARIFAS", "motivo": "x", "valor": 1})):
        assert cliente.post(url(factura_eps, sufijo), json=cuerpo, headers=medico).status_code == 403


# ------------------------------------------------------------------ diagnóstico y catálogo con CUPS


def test_el_medico_registra_el_diagnostico_y_recepcion_no_lo_ve(cliente, recepcion, medico, otro_medico, usuarios, pacientes):
    ingreso = admitir(cliente, recepcion, usuarios, pacientes["1000000001"]).json()
    ruta = f"/api/ingresos/{ingreso['id']}/diagnostico"
    for malo in ("J0", "9999", "j 00 1", ""):
        assert cliente.put(ruta, json={"codigo_cie10": malo}, headers=medico).status_code == 422, malo
    assert cliente.put(ruta, json={"codigo_cie10": "J00"}, headers=recepcion).status_code == 403
    assert cliente.put(ruta, json={"codigo_cie10": "J00"}, headers=otro_medico).status_code == 403
    r = cliente.put(ruta, json={"codigo_cie10": "k297"}, headers=medico)
    assert r.status_code == 200 and r.json()["diagnostico_principal"] == "K297"
    assert cliente.get(f"/api/ingresos/{ingreso['id']}", headers=recepcion).json()["diagnostico_principal"] is None


def test_el_catalogo_guarda_cups_y_clase_de_servicio(cliente, admin):
    base = {"codigo": "ECO-001", "nombre": "Ecografía", "tarifa": 100000}
    r = cliente.post("/api/procedimientos", json={**base, "cups": "881201", "tipo_servicio": "PROCEDIMIENTO"}, headers=admin)
    assert r.status_code == 201 and r.json()["cups"] == "881201"
    for malo in ("12345", "ABCDEF", "1234567"):
        assert cliente.post("/api/procedimientos", json={**base, "codigo": "ECO-002", "cups": malo}, headers=admin).status_code == 422, malo
    cambio = cliente.put(f"/api/procedimientos/{r.json()['id']}", json={"tipo_servicio": "OTRO_SERVICIO", "cups": ""}, headers=admin)
    assert cambio.status_code == 200 and cambio.json()["tipo_servicio"] == "OTRO_SERVICIO" and cambio.json()["cups"] == ""


# ------------------------------------------------------------------ RIPS


def periodo():
    hoy = date.today()
    return {"desde": (hoy - timedelta(days=1)).isoformat(), "hasta": (hoy + timedelta(days=1)).isoformat()}


def codigos(rips):
    return {(i["codigo"], i["nivel"]) for i in rips["inconsistencias"]}


def test_el_rips_avisa_de_lo_que_falta(cliente, recepcion, medico, admin, usuarios, pacientes, catalogo, convenios):
    _, factura = cuenta_con_convenio(
        cliente, recepcion, medico, usuarios, pacientes, catalogo, convenios["Contributivo"], ["CON-GEN", "CUR-SIM"]
    )
    r = cliente.get("/api/rips", params=periodo(), headers=admin)
    assert r.status_code == 200
    rips = r.json()
    assert rips["borrador"] is True and rips["resumen"]["facturas"] == 1
    assert rips["resumen"]["listoParaReportar"] is False
    assert {("SIN_DIAGNOSTICO", "ERROR"), ("SIN_CUPS", "ERROR"), ("NO_RADICADA", "AVISO")} <= codigos(rips)
    registro = rips["facturas"][0]
    assert registro["numFactura"] == factura["numero"]
    assert registro["usuario"]["numDocumentoIdentificacion"] == "1000000001"
    assert [s["codigoInterno"] for s in registro["servicios"]["consultas"]] == ["CON-GEN"]
    assert [s["codigoInterno"] for s in registro["servicios"]["procedimientos"]] == ["CUR-SIM"]
    assert registro["servicios"]["consultas"][0]["codServicio"] == "890201"


def test_el_rips_queda_listo_con_diagnostico_cups_y_radicacion(cliente, recepcion, medico, admin, usuarios, pacientes, catalogo, convenios):
    ingreso, factura = cuenta_con_convenio(
        cliente, recepcion, medico, usuarios, pacientes, catalogo, convenios["Contributivo"], ["CON-GEN", "ECG-001"]
    )
    cliente.put(f"/api/ingresos/{ingreso['id']}/diagnostico", json={"codigo_cie10": "I10X"}, headers=medico)
    radicar(cliente, recepcion, factura)
    rips = cliente.get("/api/rips", params=periodo(), headers=admin).json()
    assert rips["resumen"]["listoParaReportar"] is True and rips["inconsistencias"] == []
    assert rips["resumen"]["valorFacturado"] == factura["valor_pagador"]
    assert rips["facturas"][0]["servicios"]["procedimientos"][0]["codDiagnosticoPrincipal"] == "I10X"
    assert rips["prestador"]["nit"]


def test_el_rips_solo_incluye_facturas_con_pagador_en_el_periodo(cliente, recepcion, medico, admin, usuarios, pacientes, catalogo, convenios):
    cuenta_con_convenio(cliente, recepcion, medico, usuarios, pacientes, catalogo, convenios["Contributivo"], ["CUR-SIM"])
    ingreso = admitir(cliente, recepcion, usuarios, pacientes["1000000002"]).json()  # particular
    registrar(cliente, medico, ingreso["id"], catalogo["CUR-SIM"])
    cliente.post("/api/facturas", json={"ingreso_id": ingreso["id"]}, headers=recepcion)

    assert cliente.get("/api/rips", params=periodo(), headers=admin).json()["resumen"]["facturas"] == 1
    pasado = {"desde": "2020-01-01", "hasta": "2020-01-31"}
    assert cliente.get("/api/rips", params=pasado, headers=admin).json()["resumen"]["facturas"] == 0
    otro_pagador = cliente.get("/api/rips", params={**periodo(), "pagador_id": 9999}, headers=admin).json()
    assert otro_pagador["resumen"]["facturas"] == 0


def test_validacion_y_permisos_del_rips(cliente, recepcion, medico, admin):
    assert cliente.get("/api/rips", params=periodo(), headers=recepcion).status_code == 403
    assert cliente.get("/api/rips", params=periodo(), headers=medico).status_code == 403
    assert cliente.get("/api/rips", params=periodo()).status_code == 401
    assert cliente.get("/api/rips", params={"desde": "2026-02-01", "hasta": "2026-01-01"}, headers=admin).status_code == 422
    assert cliente.get("/api/rips", params={"desde": "2020-01-01", "hasta": "2026-01-01"}, headers=admin).status_code == 422
    assert cliente.get("/api/rips", params={"desde": "no-es-fecha", "hasta": "2026-01-01"}, headers=admin).status_code == 422


def test_la_bitacora_registra_el_rips_y_la_cartera(cliente, recepcion, admin, factura_eps):
    radicar(cliente, recepcion, factura_eps)
    cliente.get("/api/rips", params=periodo(), headers=admin)
    hechos = {(r["usuario"], r["accion"], r["entidad"]) for r in cliente.get("/api/auditoria", params={"limite": 1000}, headers=admin).json()}
    assert ("admin", "GENERACION", "Rips") in hechos
    assert ("recepcion1", "MODIFICACION", "Factura") in hechos
