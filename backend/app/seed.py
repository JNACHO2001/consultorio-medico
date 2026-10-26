"""Datos de demostración (ficticios) para poder probar el prototipo al arrancar.

Como los datos viven en memoria, se vuelven a cargar en cada arranque.
Se desactivan con SEMBRAR_DATOS_DEMO=false. Todos los usuarios demo comparten
la contraseña CONTRASENA_DEMO (por defecto "Salud2026*"): cámbiela en cualquier
despliegue que no sea una demostración.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from app.container import Contenedor
from app.core.tiempo import ahora_local
from app.domain.modelos import Rol

USUARIOS_DEMO = [
    ("admin", "Administrador del consultorio", Rol.ADMINISTRADOR, "", ""),
    ("recepcion1", "Laura Martínez", Rol.RECEPCION, "", ""),
    ("recepcion2", "Carlos Rincón", Rol.RECEPCION, "", ""),
    ("dr.perez", "Dr. Andrés Pérez", Rol.MEDICO, "Medicina general", "RM-1001"),
    ("dra.gomez", "Dra. Sofía Gómez", Rol.MEDICO, "Medicina general", "RM-1002"),
    ("dr.rojas", "Dr. Mateo Rojas", Rol.MEDICO, "Medicina general", "RM-1003"),
    ("dra.torres", "Dra. Valentina Torres", Rol.MEDICO, "Medicina interna", "RM-2001"),
]

PACIENTES_DEMO = [
    dict(tipo_documento="CC", numero_documento="1000000001", nombres="Camila Andrea",
         apellidos="Rodríguez Silva", fecha_nacimiento=date(1990, 3, 14), sexo="F",
         telefono="3000000001", correo="camila.demo@example.com", eps="EPS Demo", alergias="Penicilina"),
    dict(tipo_documento="CC", numero_documento="1000000002", nombres="Juan David",
         apellidos="Herrera Castro", fecha_nacimiento=date(1985, 11, 2), sexo="M",
         telefono="3000000002", correo="juan.demo@example.com", eps="EPS Demo", alergias=""),
    dict(tipo_documento="TI", numero_documento="1000000003", nombres="Mariana",
         apellidos="Ortiz Peña", fecha_nacimiento=date(2010, 7, 21), sexo="F",
         telefono="3000000003", correo="", eps="EPS Demo B", alergias="Ninguna conocida"),
    dict(tipo_documento="CC", numero_documento="1000000004", nombres="Luis Fernando",
         apellidos="Vargas Mejía", fecha_nacimiento=date(1972, 1, 30), sexo="M",
         telefono="", correo="luis.demo@example.com", eps="EPS Demo B", alergias="Ibuprofeno"),
    dict(tipo_documento="CE", numero_documento="2000000005", nombres="Ana Lucía",
         apellidos="Moreno Díaz", fecha_nacimiento=date(1998, 9, 9), sexo="F",
         telefono="3000000005", correo="ana.demo@example.com", eps="EPS Demo", alergias=""),
]

# Catálogo de procedimientos con tarifas ficticias (pesos colombianos).
CATALOGO_DEMO = [
    ("CON-GEN", "Consulta de medicina general", 60000),
    ("CON-ESP", "Consulta de medicina interna", 95000),
    ("CUR-SIM", "Curación simple", 25000),
    ("SUT-SIM", "Sutura de herida simple", 85000),
    ("INY-IM", "Aplicación de inyectología", 12000),
    ("NEB-001", "Nebulización", 30000),
    ("ECG-001", "Electrocardiograma", 55000),
    ("LAB-HEM", "Hemograma completo", 28000),
    ("LAB-GLU", "Glicemia en ayunas", 15000),
    ("RX-TOR", "Radiografía de tórax", 70000),
    ("OBS-HOR", "Observación por hora", 40000),
]


def sembrar_datos_demo(c: Contenedor) -> None:
    for nombre_usuario, nombre, rol, especialidad, registro in USUARIOS_DEMO:
        c.usuarios.crear_usuario(
            nombre_usuario, c.config.contrasena_demo, nombre, rol, especialidad, registro
        )

    for codigo, nombre, tarifa in CATALOGO_DEMO:
        c.catalogo.crear(codigo, nombre, tarifa)

    pacientes = [c.pacientes.registrar_paciente(**datos) for datos in PACIENTES_DEMO]

    # Dos citas para mañana con el primer médico, para que la agenda no arranque vacía.
    medico = c.repo_usuarios.obtener_por_nombre_usuario("dr.perez")
    manana: date = ahora_local(c.config.zona_horaria).date() + timedelta(days=1)
    inicio = datetime.combine(manana, c.config.jornada_inicio)
    c.citas.agendar_cita(pacientes[0].id, medico.id, inicio + timedelta(hours=1))
    c.citas.agendar_cita(pacientes[1].id, medico.id, inicio + timedelta(hours=2, minutes=30))
