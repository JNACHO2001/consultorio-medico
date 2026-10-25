"""Gestión de pacientes (CU-02, CU-03; RF-01 a RF-04)."""
from __future__ import annotations

import re
import threading
from datetime import date, datetime, timezone
from typing import Any, Optional

from app.domain.excepciones import Duplicado, NoEncontrado, ReglaNegocio
from app.domain.modelos import CambioPaciente, Paciente
from app.repositories.interfaces import IPacienteRepository

TIPOS_DOCUMENTO = {"CC", "TI", "CE", "PA", "RC"}
CAMPOS_EDITABLES = (
    "nombres",
    "apellidos",
    "fecha_nacimiento",
    "sexo",
    "telefono",
    "correo",
    "eps",
    "alergias",
)
_PATRON_DOCUMENTO = re.compile(r"^[A-Za-z0-9]{4,20}$")
_PATRON_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _limpiar(valor: Optional[str]) -> str:
    return (valor or "").strip()


def _validar_campo(campo: str, valor: Any) -> Any:
    """Valida y normaliza un dato del paciente. Devuelve el valor limpio."""
    if campo in ("nombres", "apellidos"):
        valor = _limpiar(valor)
        if not valor:
            raise ReglaNegocio(f"El campo {campo} es obligatorio.")
    elif campo == "fecha_nacimiento":
        if not isinstance(valor, date) or valor > date.today():
            raise ReglaNegocio("La fecha de nacimiento no es válida.")
    elif campo == "correo":
        valor = _limpiar(valor)
        if valor and not _PATRON_CORREO.match(valor):
            raise ReglaNegocio("El correo electrónico no es válido.")
    elif campo in ("sexo", "telefono", "eps", "alergias"):
        valor = _limpiar(valor)
    return valor


def _resumen(paciente: Paciente) -> dict[str, Any]:
    return {
        "id": paciente.id,
        "tipo_documento": paciente.tipo_documento,
        "numero_documento": paciente.numero_documento,
        "nombre_completo": paciente.nombre_completo,
    }


class PacienteService:
    def __init__(self, pacientes: IPacienteRepository) -> None:
        self._pacientes = pacientes
        self._lock = threading.Lock()

    def registrar_paciente(
        self,
        *,
        tipo_documento: str,
        numero_documento: str,
        nombres: str,
        apellidos: str,
        fecha_nacimiento: date,
        sexo: str = "",
        telefono: str = "",
        correo: str = "",
        eps: str = "",
        alergias: str = "",
    ) -> Paciente:
        tipo = _limpiar(tipo_documento).upper()
        numero = _limpiar(numero_documento)
        if tipo not in TIPOS_DOCUMENTO:
            raise ReglaNegocio(f"Tipo de documento no válido. Use: {', '.join(sorted(TIPOS_DOCUMENTO))}.")
        if not _PATRON_DOCUMENTO.match(numero):
            raise ReglaNegocio("El número de documento debe tener entre 4 y 20 letras o números.")

        paciente = Paciente(
            tipo_documento=tipo,
            numero_documento=numero,
            nombres=_validar_campo("nombres", nombres),
            apellidos=_validar_campo("apellidos", apellidos),
            fecha_nacimiento=_validar_campo("fecha_nacimiento", fecha_nacimiento),
            sexo=_validar_campo("sexo", sexo),
            telefono=_validar_campo("telefono", telefono),
            correo=_validar_campo("correo", correo),
            eps=_validar_campo("eps", eps),
            alergias=_validar_campo("alergias", alergias),
        )
        with self._lock:  # RN-01: la verificación y el guardado deben ser una sola operación
            existente = self._pacientes.obtener_por_documento(tipo, numero)
            if existente is not None:
                raise Duplicado(
                    "Ya existe un paciente con ese documento.",
                    {"paciente_existente": _resumen(existente)},
                )
            return self._pacientes.agregar(paciente)

    def buscar_paciente(self, criterio: str) -> list[Paciente]:
        criterio = _limpiar(criterio)
        if not criterio:
            raise ReglaNegocio("Ingrese un documento o un nombre para buscar.")
        return self._pacientes.buscar(criterio)

    def obtener_paciente(self, paciente_id: int) -> Paciente:
        paciente = self._pacientes.obtener_por_id(paciente_id)
        if paciente is None:
            raise NoEncontrado("El paciente no existe.")
        return paciente

    def actualizar_paciente(self, paciente_id: int, usuario_id: int, **cambios: Any) -> Paciente:
        """Actualiza datos conservando el historial de cambios (RF-04).

        El tipo y número de documento no se pueden cambiar: son la identidad (RN-01).
        """
        paciente = self.obtener_paciente(paciente_id)
        ahora = datetime.now(timezone.utc)
        hubo_cambios = False
        for campo, nuevo in cambios.items():
            if campo not in CAMPOS_EDITABLES or nuevo is None:
                continue
            nuevo = _validar_campo(campo, nuevo)
            anterior = getattr(paciente, campo)
            if anterior == nuevo:
                continue
            paciente.historial_cambios.append(
                CambioPaciente(
                    campo=campo,
                    valor_anterior=str(anterior) if anterior not in (None, "") else None,
                    valor_nuevo=str(nuevo),
                    usuario_id=usuario_id,
                    fecha=ahora,
                )
            )
            setattr(paciente, campo, nuevo)
            hubo_cambios = True
        return self._pacientes.actualizar(paciente) if hubo_cambios else paciente
