"""Fixtures compartidas: cada prueba arranca una aplicación nueva con datos demo."""
import dataclasses
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import cargar_configuracion
from app.core.contexto import establecer_usuario
from app.main import crear_app

CLAVE_DEMO = "Salud2026*"


@pytest.fixture(autouse=True)
def limpiar_contexto():
    establecer_usuario(None)
    yield
    establecer_usuario(None)


@pytest.fixture
def config():
    return dataclasses.replace(
        cargar_configuracion(),
        secret_key="clave-solo-para-pruebas-0123456789-abcdef",
        iteraciones_hash=1000,  # hash rápido: solo para pruebas
        recordatorios_automaticos=False,
    )


@pytest.fixture
def app(config):
    return crear_app(config)


@pytest.fixture
def cliente(app):
    with TestClient(app) as c:
        yield c


def iniciar_sesion(cliente, usuario: str, contrasena: str = CLAVE_DEMO) -> dict:
    r = cliente.post("/api/auth/login", json={"usuario": usuario, "contrasena": contrasena})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def recepcion(cliente):
    return iniciar_sesion(cliente, "recepcion1")


@pytest.fixture
def medico(cliente):
    return iniciar_sesion(cliente, "dr.perez")


@pytest.fixture
def otro_medico(cliente):
    return iniciar_sesion(cliente, "dra.gomez")


@pytest.fixture
def admin(cliente):
    return iniciar_sesion(cliente, "admin")


@pytest.fixture
def usuarios(cliente, admin) -> dict:
    """Usuarios demo por nombre de usuario (con su id)."""
    r = cliente.get("/api/usuarios", headers=admin)
    return {u["nombre_usuario"]: u for u in r.json()}


@pytest.fixture
def pacientes(cliente, recepcion) -> dict:
    """Pacientes demo por número de documento."""
    resultado = {}
    for documento in ("1000000001", "1000000002", "1000000003"):
        r = cliente.get("/api/pacientes", params={"q": documento}, headers=recepcion)
        resultado[documento] = r.json()[0]
    return resultado


@pytest.fixture
def fecha() -> date:
    """Un día futuro sin citas sembradas (las demo son para mañana)."""
    return date.today() + timedelta(days=30)


def hora(dia: date, hhmm: str) -> str:
    return f"{dia.isoformat()}T{hhmm}:00"
