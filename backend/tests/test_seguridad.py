"""RF-11, RF-12, RF-13 y RNF-01/02: sesiones, roles, usuarios y bitácora de auditoría."""
import dataclasses

from fastapi.testclient import TestClient

from app.main import crear_app
from tests.conftest import CLAVE_DEMO, hora, iniciar_sesion

USUARIO_NUEVO = {
    "nombre_usuario": "recepcion3",
    "contrasena": "Clave12345",
    "nombre_completo": "Marta Díaz",
    "rol": "RECEPCION",
}


def test_login_correcto_e_incorrecto(cliente):
    ok = cliente.post("/api/auth/login", json={"usuario": "admin", "contrasena": CLAVE_DEMO})
    assert ok.status_code == 200
    assert ok.json()["usuario"]["rol"] == "ADMINISTRADOR"
    assert "contrasena_hash" not in ok.text

    for cuerpo in (
        {"usuario": "admin", "contrasena": "incorrecta"},
        {"usuario": "no-existe", "contrasena": CLAVE_DEMO},
    ):
        r = cliente.post("/api/auth/login", json=cuerpo)
        assert r.status_code == 401
        assert r.json()["detail"] == "Usuario o contraseña incorrectos."  # no revela cuál falló


def test_sin_token_o_con_token_invalido_no_hay_acceso(cliente):
    assert cliente.get("/api/pacientes", params={"q": "a"}).status_code == 401
    assert cliente.get("/api/pacientes", params={"q": "a"}, headers={"Authorization": "Bearer basura"}).status_code == 401


def test_cerrar_sesion_invalida_el_token(cliente, recepcion):
    assert cliente.get("/api/auth/me", headers=recepcion).status_code == 200
    assert cliente.post("/api/auth/logout", headers=recepcion).status_code == 204
    assert cliente.get("/api/auth/me", headers=recepcion).status_code == 401


def test_la_sesion_expira(config):
    app = crear_app(dataclasses.replace(config, token_minutos=-1))
    with TestClient(app) as cliente:
        headers = iniciar_sesion(cliente, "admin")
        r = cliente.get("/api/auth/me", headers=headers)
        assert r.status_code == 401
        assert "expiró" in r.json()["detail"]


def test_cada_rol_solo_entra_a_sus_modulos(cliente, recepcion, medico, admin):
    assert cliente.get("/api/usuarios", headers=recepcion).status_code == 403
    assert cliente.get("/api/usuarios", headers=medico).status_code == 403
    assert cliente.get("/api/usuarios", headers=admin).status_code == 200
    for headers in (recepcion, medico):
        assert cliente.get("/api/auditoria", headers=headers).status_code == 403
    assert cliente.get("/api/auditoria", headers=admin).status_code == 200


def test_administrador_crea_usuarios_con_rol(cliente, admin):
    r = cliente.post("/api/usuarios", json=USUARIO_NUEVO, headers=admin)
    assert r.status_code == 201
    assert r.json()["rol"] == "RECEPCION"
    assert "contrasena" not in r.text

    nueva = iniciar_sesion(cliente, "recepcion3", "Clave12345")
    assert cliente.get("/api/pacientes", params={"q": "camila"}, headers=nueva).status_code == 200  # puede lo de su rol
    assert cliente.get("/api/usuarios", headers=nueva).status_code == 403  # no lo demás


def test_crear_medico_con_especialidad(cliente, admin):
    cuerpo = {**USUARIO_NUEVO, "nombre_usuario": "dr.nuevo", "rol": "MEDICO", "especialidad": "Cardiología"}
    r = cliente.post("/api/usuarios", json=cuerpo, headers=admin)
    assert r.status_code == 201
    assert r.json()["especialidad"] == "Cardiología"


def test_listado_de_medicos_incluye_al_nuevo(cliente, admin, recepcion):
    cliente.post("/api/usuarios", json={**USUARIO_NUEVO, "nombre_usuario": "dr.nuevo", "rol": "MEDICO"}, headers=admin)
    nombres = [m["nombre_completo"] for m in cliente.get("/api/medicos", headers=recepcion).json()]
    assert "Marta Díaz" in nombres
    assert len(nombres) == 5  # 4 médicos demo + el nuevo


def test_usuarios_duplicados_y_contrasenas_debiles(cliente, admin):
    assert cliente.post("/api/usuarios", json=USUARIO_NUEVO, headers=admin).status_code == 201
    assert cliente.post("/api/usuarios", json=USUARIO_NUEVO, headers=admin).status_code == 409

    for contrasena in ("corta1", "solo-letras-largas", "123456789"):
        r = cliente.post("/api/usuarios", json={**USUARIO_NUEVO, "nombre_usuario": "otro", "contrasena": contrasena}, headers=admin)
        assert r.status_code == 422, contrasena


def test_usuario_desactivado_no_puede_entrar_pero_se_conserva(cliente, admin, usuarios):
    id_ = usuarios["recepcion2"]["id"]
    assert cliente.post(f"/api/usuarios/{id_}/desactivar", headers=admin).status_code == 204

    r = cliente.post("/api/auth/login", json={"usuario": "recepcion2", "contrasena": CLAVE_DEMO})
    assert r.status_code == 401
    listado = {u["nombre_usuario"]: u for u in cliente.get("/api/usuarios", headers=admin).json()}
    assert listado["recepcion2"]["activo"] is False  # borrado lógico: sigue existiendo


def test_el_administrador_no_puede_desactivarse_a_si_mismo(cliente, admin, usuarios):
    r = cliente.post(f"/api/usuarios/{usuarios['admin']['id']}/desactivar", headers=admin)
    assert r.status_code == 422


def test_la_bitacora_registra_quien_consulto_o_modifico_datos(cliente, recepcion, medico, admin, usuarios, pacientes, fecha):
    cita = cliente.post(
        "/api/citas",
        json={"paciente_id": pacientes["1000000001"]["id"], "medico_id": usuarios["dr.perez"]["id"], "fecha_hora": hora(fecha, "09:00")},
        headers=recepcion,
    ).json()
    consulta = cliente.post("/api/consultas", json={"cita_id": cita["id"], "motivo": "Control"}, headers=medico).json()
    cliente.get(f"/api/pacientes/{pacientes['1000000001']['id']}/historial", headers=medico)
    cliente.put(f"/api/pacientes/{pacientes['1000000001']['id']}", json={"telefono": "3112223344"}, headers=recepcion)

    bitacora = cliente.get("/api/auditoria", params={"limite": 1000}, headers=admin).json()
    hechos = {(r["usuario"], r["accion"], r["entidad"]) for r in bitacora}

    assert ("dr.perez", "CREACION", "Consulta") in hechos
    assert ("dr.perez", "LECTURA", "HistoriaClinica") in hechos
    assert ("recepcion1", "MODIFICACION", "Paciente") in hechos
    assert ("recepcion1", "INICIO_SESION", "Sesion") in hechos
    creacion = next(r for r in bitacora if r["accion"] == "CREACION" and r["entidad"] == "Consulta")
    assert creacion["id_entidad"] == consulta["id"]
    assert creacion["fecha_hora"]


def test_la_bitacora_registra_inicios_de_sesion_fallidos_y_se_puede_filtrar(cliente, admin):
    cliente.post("/api/auth/login", json={"usuario": "admin", "contrasena": "mal"})

    fallidos = cliente.get("/api/auditoria", params={"accion": "INICIO_SESION_FALLIDO"}, headers=admin).json()
    assert [r["usuario"] for r in fallidos] == ["admin"]
    assert cliente.get("/api/auditoria", params={"usuario": "nadie"}, headers=admin).json() == []


def test_la_bitacora_no_se_puede_modificar_por_la_api(cliente, admin):
    assert cliente.delete("/api/auditoria", headers=admin).status_code == 405
    assert cliente.post("/api/auditoria", headers=admin).status_code == 405


def test_las_respuestas_de_la_api_no_se_guardan_en_cache(cliente, recepcion):
    r = cliente.get("/api/pacientes", params={"q": "camila"}, headers=recepcion)
    assert r.headers["cache-control"] == "no-store"


def test_endpoint_de_salud_sin_autenticacion(cliente):
    r = cliente.get("/health")
    assert r.status_code == 200
    assert r.json()["estado"] == "ok"
    assert set(r.json()["componentes"].values()) == {"ok"}
