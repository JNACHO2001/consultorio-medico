"""RF-25 a RF-27: factura electrónica DIAN (simulada), notas crédito, recibos y caja (RN-24 a RN-26)."""
import dataclasses
import re
import xml.etree.ElementTree as ET
from datetime import datetime

import pytest

from app.services.dian import calcular_cude, calcular_cufe
from tests.conftest import iniciar_sesion
from tests.test_convenios_cartera_rips import (  # noqa: F401  (fixtures y ayudas compartidas)
    catalogo,
    convenios,
    cuenta_con_convenio,
    factura_eps,
    glosar,
    radicar,
    url,
)


@pytest.fixture
def config(config):
    """Aquí la factura electrónica y la caja sí son obligatorias, como en producción."""
    return dataclasses.replace(config, dian_obligatoria=True, caja_obligatoria=True)


def emitir(cliente, headers, factura):
    return cliente.post(f"/api/electronica/facturas/{factura['id']}/emitir", headers=headers)


def nota(cliente, headers, factura, **cuerpo):
    return cliente.post(f"/api/electronica/facturas/{factura['id']}/notas-credito", json=cuerpo, headers=headers)


def abrir_caja(cliente, headers, base=50000):
    r = cliente.post("/api/caja/apertura", json={"base_inicial": base}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


# ------------------------------------------------------------------ CUFE y XML


def test_el_cufe_es_un_sha384_determinista():
    fecha = datetime(2026, 11, 7, 10, 30, 0)
    args = ("SETP990000001", fecha, 85500, 80500, "900000000", "31", "800000001",
            "fc8eac422eba16e22ffd8c6f94b3f40a6e38162c", "2")
    cufe = calcular_cufe(*args)
    assert re.fullmatch(r"[0-9a-f]{96}", cufe) and cufe == calcular_cufe(*args)
    assert cufe != calcular_cufe(*(args[:3] + (85501,) + args[4:]))  # cualquier cambio en el valor lo cambia
    cude = calcular_cude("NC1", fecha, 20000, 20000, "900000000", "800000001", "75315", "2")
    assert re.fullmatch(r"[0-9a-f]{96}", cude)


def test_la_factura_se_emite_al_pagador_con_su_cufe_y_xml(cliente, recepcion, factura_eps):
    r = emitir(cliente, recepcion, factura_eps)
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["estado"] == "ACEPTADO" and doc["numero"] == "SETP990000000"
    assert doc["adquirente_es_pagador"] is True and doc["adquirente_documento"] == "800000001"
    assert doc["adquirente_dv"] == "1" and doc["valor"] == 80500 and doc["valor_bruto"] == 85500
    assert re.fullmatch(r"[0-9a-f]{96}", doc["cufe"]) and doc["cufe"] in doc["qr"]
    assert [e["estado"] for e in doc["eventos"]] == ["GENERADO", "ACEPTADO"]

    xml = cliente.get(f"/api/electronica/documentos/{doc['id']}/xml", headers=recepcion)
    assert xml.status_code == 200 and "xml" in xml.headers["content-type"]
    raiz = ET.fromstring(xml.text.split("?>", 1)[-1])  # XML bien formado
    assert raiz.tag.endswith("Invoice") and doc["cufe"] in xml.text

    factura = cliente.get(url(factura_eps), headers=recepcion).json()
    assert factura["factura_electronica"]["id"] == doc["id"] and factura["dian_obligatoria"] is True


def test_la_factura_particular_se_emite_al_paciente(cliente, recepcion, medico, usuarios, pacientes, catalogo, convenios):
    _, factura = cuenta_con_convenio(
        cliente, recepcion, medico, usuarios, pacientes, catalogo, convenios["Tarifa particular"], ["CON-GEN"]
    )
    doc = emitir(cliente, recepcion, factura).json()
    assert doc["adquirente_es_pagador"] is False and doc["adquirente_documento"] == "1000000001"
    assert doc["valor"] == factura["total"] and doc["estado"] == "ACEPTADO"


def test_no_se_emite_dos_veces(cliente, recepcion, factura_eps):
    assert emitir(cliente, recepcion, factura_eps).status_code == 201
    assert emitir(cliente, recepcion, factura_eps).status_code == 409


def test_no_se_emite_con_la_factura_anulada(cliente, recepcion, medico, usuarios, pacientes, catalogo, convenios):
    _, factura = cuenta_con_convenio(cliente, recepcion, medico, usuarios, pacientes, catalogo, convenios["Tarifa particular"], ["CON-GEN"])
    cliente.post(url(factura, "/anular"), json={"motivo": "Error"}, headers=recepcion)
    assert emitir(cliente, recepcion, factura).status_code == 422


# ------------------------------------------------------------------ rechazo y reintento


def test_un_pagador_sin_nit_es_rechazado_y_se_puede_reintentar(
    cliente, admin, recepcion, medico, usuarios, pacientes, catalogo
):
    pagador = cliente.post("/api/pagadores", json={"codigo": "SIN-NIT", "nombre": "Aseguradora sin NIT", "tipo": "EPS"}, headers=admin).json()
    convenio = cliente.post(
        f"/api/pagadores/{pagador['id']}/convenios",
        json={"nombre": "Plan", "porcentaje_tarifa": 100, "copago_porcentaje": 0, "cuota_moderadora": 0},
        headers=admin,
    ).json()
    _, factura = cuenta_con_convenio(cliente, recepcion, medico, usuarios, pacientes, catalogo, convenio, ["CON-GEN"])
    doc = emitir(cliente, recepcion, factura).json()
    assert doc["estado"] == "RECHAZADO" and "SIM-04" in doc["mensaje_respuesta"]
    assert emitir(cliente, recepcion, factura).status_code == 409  # se reintenta, no se emite otra

    # sin corregir el NIT sigue rechazada, con la misma numeración
    otra_vez = cliente.post(f"/api/electronica/documentos/{doc['id']}/reintentar", headers=recepcion).json()
    assert otra_vez["estado"] == "RECHAZADO" and otra_vez["numero"] == doc["numero"] and otra_vez["intentos"] == 2

    # radicar sigue bloqueado mientras no haya factura aceptada (RN-22)
    r = radicar(cliente, recepcion, factura)
    assert r.status_code == 422 and "factura electrónica" in r.json()["detail"]

    cliente.put(f"/api/pagadores/{pagador['id']}", json={"nit": "900123456-7"}, headers=admin)
    # el adquirente se resuelve al reintentar: ahora sí queda aceptada
    aceptada = cliente.post(f"/api/electronica/documentos/{doc['id']}/reintentar", headers=recepcion).json()
    assert aceptada["estado"] == "ACEPTADO" and aceptada["intentos"] == 3
    assert [e["estado"] for e in aceptada["eventos"]].count("RECHAZADO") == 2
    assert cliente.post(f"/api/electronica/documentos/{doc['id']}/reintentar", headers=recepcion).status_code == 422
    assert radicar(cliente, recepcion, factura).status_code == 200


def test_sin_factura_electronica_no_se_radica(cliente, recepcion, factura_eps):
    r = radicar(cliente, recepcion, factura_eps)
    assert r.status_code == 422 and "factura electrónica" in r.json()["detail"]
    emitir(cliente, recepcion, factura_eps)
    assert radicar(cliente, recepcion, factura_eps).status_code == 200


# ------------------------------------------------------------------ notas crédito


def test_nota_credito_por_glosa_aceptada(cliente, recepcion, factura_eps):
    fe = emitir(cliente, recepcion, factura_eps).json()
    radicar(cliente, recepcion, factura_eps)
    glosar(cliente, recepcion, factura_eps, valor=20000)
    assert nota(cliente, recepcion, factura_eps, concepto="GLOSA", glosa_id=1).status_code == 422  # aún abierta
    cliente.post(url(factura_eps, "/glosas/1/resolver"), json={"aceptada": True, "nota": "Error nuestro"}, headers=recepcion)

    r = nota(cliente, recepcion, factura_eps, concepto="GLOSA", glosa_id=1)
    assert r.status_code == 201, r.text
    nc = r.json()
    assert nc["tipo"] == "NOTA_CREDITO" and nc["numero"] == "NC1" and nc["valor"] == 20000
    assert nc["estado"] == "ACEPTADO" and nc["documento_referencia_id"] == fe["id"]
    assert re.fullmatch(r"[0-9a-f]{96}", nc["cufe"]) and nc["cufe"] != fe["cufe"]
    assert nota(cliente, recepcion, factura_eps, concepto="GLOSA", glosa_id=1).status_code == 409  # una sola por glosa
    assert nota(cliente, recepcion, factura_eps, concepto="GLOSA", glosa_id=99).status_code == 404

    factura = cliente.get(url(factura_eps), headers=recepcion).json()
    assert [n["numero"] for n in factura["notas_credito"]] == ["NC1"]


def test_nota_credito_exige_factura_aceptada_y_motivo(cliente, recepcion, factura_eps):
    assert nota(cliente, recepcion, factura_eps, concepto="ANULACION", motivo="x").status_code == 422
    emitir(cliente, recepcion, factura_eps)
    assert nota(cliente, recepcion, factura_eps, concepto="ANULACION", motivo=" ").status_code == 422


def test_la_factura_con_factura_electronica_se_anula_con_nota_credito(cliente, recepcion, medico, usuarios, pacientes, catalogo, convenios):
    _, factura = cuenta_con_convenio(cliente, recepcion, medico, usuarios, pacientes, catalogo, convenios["Tarifa particular"], ["CON-GEN"])
    fe = emitir(cliente, recepcion, factura).json()
    r = cliente.post(url(factura, "/anular"), json={"motivo": "Paciente equivocado"}, headers=recepcion)
    assert r.status_code == 200, r.text
    anulada = r.json()
    assert anulada["estado"] == "ANULADA" and "nota crédito NC1" in anulada["motivo_anulacion"]
    ncs = anulada["notas_credito"]
    assert len(ncs) == 1 and ncs[0]["concepto"] == "ANULACION" and ncs[0]["valor"] == fe["valor"]


def test_la_anulacion_directa_sigue_igual_sin_factura_electronica(cliente, recepcion, medico, usuarios, pacientes, catalogo, convenios):
    _, factura = cuenta_con_convenio(cliente, recepcion, medico, usuarios, pacientes, catalogo, convenios["Tarifa particular"], ["CON-GEN"])
    r = cliente.post(url(factura, "/anular"), json={"motivo": "Error"}, headers=recepcion)
    assert r.status_code == 200 and r.json()["notas_credito"] == []


# ------------------------------------------------------------------ caja y recibos


def test_cobrar_al_paciente_exige_caja_abierta(cliente, recepcion, factura_eps):
    r = cliente.post(url(factura_eps, "/pagar"), json={"metodo_pago": "EFECTIVO"}, headers=recepcion)
    assert r.status_code == 422 and "caja" in r.json()["detail"].lower()
    caja = abrir_caja(cliente, recepcion)
    pagada = cliente.post(url(factura_eps, "/pagar"), json={"metodo_pago": "EFECTIVO"}, headers=recepcion).json()
    pago = pagada["pagos"][0]
    assert pago["recibo_numero"] == "RC-000001" and pago["caja_id"] == caja["id"] and pago["valor"] == 5000


def test_una_sola_caja_abierta_por_cajero(cliente, recepcion):
    abrir_caja(cliente, recepcion)
    assert cliente.post("/api/caja/apertura", json={"base_inicial": 0}, headers=recepcion).status_code == 409
    otra = iniciar_sesion(cliente, "recepcion2")
    assert cliente.post("/api/caja/apertura", json={"base_inicial": 0}, headers=otra).status_code == 201
    assert cliente.post("/api/caja/apertura", json={"base_inicial": -1}, headers=otra).status_code == 422


def test_cierre_de_caja_cuadra_y_registra_diferencias(cliente, recepcion, factura_eps):
    caja = abrir_caja(cliente, recepcion, base=50000)
    cliente.post(url(factura_eps, "/pagar"), json={"metodo_pago": "EFECTIVO"}, headers=recepcion)
    actual = cliente.get("/api/caja/actual", headers=recepcion).json()
    assert actual["n_recibos"] == 1 and actual["efectivo_esperado_actual"] == 55000
    assert [r["recibo_numero"] for r in actual["recibos"]] == ["RC-000001"]

    cierre = f"/api/caja/{caja['id']}/cierre"
    sobrante = cliente.post(cierre, json={"efectivo_contado": 56000}, headers=recepcion)
    assert sobrante.status_code == 422 and "diferencia" in sobrante.json()["detail"]  # exige explicación
    r = cliente.post(cierre, json={"efectivo_contado": 56000, "observaciones": "Sobran 1.000"}, headers=recepcion)
    assert r.status_code == 200
    cerrada = r.json()
    assert cerrada["estado"] == "CERRADA" and cerrada["efectivo_esperado"] == 55000 and cerrada["diferencia"] == 1000
    assert cerrada["por_metodo"] == {"EFECTIVO": 5000}
    assert cliente.post(cierre, json={"efectivo_contado": 55000}, headers=recepcion).status_code == 422  # ya cerrada
    assert cliente.get("/api/caja/actual", headers=recepcion).json() is None
    # cerrada la caja, hay que abrir otra para cobrar
    _ = abrir_caja(cliente, recepcion)


def test_el_cierre_exacto_no_pide_observaciones(cliente, recepcion):
    caja = abrir_caja(cliente, recepcion, base=20000)
    r = cliente.post(f"/api/caja/{caja['id']}/cierre", json={"efectivo_contado": 20000}, headers=recepcion)
    assert r.status_code == 200 and r.json()["diferencia"] == 0


def test_los_abonos_del_pagador_tambien_llevan_recibo(cliente, recepcion, factura_eps):
    emitir(cliente, recepcion, factura_eps)
    radicar(cliente, recepcion, factura_eps)
    r = cliente.post(url(factura_eps, "/pagos-pagador"), json={"valor": 10000}, headers=recepcion).json()
    assert r["pagos"][0]["recibo_numero"] == "RC-000001" and r["pagos"][0]["caja_id"] is None


def test_permisos_de_caja_y_facturacion_electronica(cliente, admin, medico, recepcion, factura_eps):
    assert cliente.post("/api/caja/apertura", json={"base_inicial": 0}, headers=medico).status_code == 403
    assert cliente.post("/api/caja/apertura", json={"base_inicial": 0}, headers=admin).status_code == 403  # el administrador audita
    caja = abrir_caja(cliente, recepcion)
    assert cliente.get("/api/caja", headers=admin).status_code == 200
    assert cliente.get(f"/api/caja/{caja['id']}", headers=admin).status_code == 200
    otra = iniciar_sesion(cliente, "recepcion2")
    assert cliente.get(f"/api/caja/{caja['id']}", headers=otra).status_code == 403
    assert cliente.post(f"/api/caja/{caja['id']}/cierre", json={"efectivo_contado": 0}, headers=otra).status_code == 403
    assert cliente.get("/api/electronica/documentos", headers=medico).status_code == 403
    assert emitir(cliente, medico, factura_eps).status_code == 403
    assert cliente.get("/api/electronica/documentos", headers=admin).status_code == 200
    assert cliente.get("/api/electronica/proveedor", headers=admin).json()["obligatoria"] is True


def test_el_rips_avisa_si_falta_la_factura_electronica(cliente, admin, recepcion, factura_eps):
    from datetime import date, timedelta

    periodo = {"desde": str(date.today() - timedelta(days=1)), "hasta": str(date.today() + timedelta(days=1))}
    codigos = lambda: {i["codigo"] for i in cliente.get("/api/rips", params=periodo, headers=admin).json()["inconsistencias"]}  # noqa: E731
    assert "SIN_FACTURA_ELECTRONICA" in codigos()
    emitir(cliente, recepcion, factura_eps)
    assert "SIN_FACTURA_ELECTRONICA" not in codigos()
