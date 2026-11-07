"""Caja del cajero y recibos de caja (RF-27).

Cada pago recibido de un paciente o de un pagador genera un recibo de caja con consecutivo.
Los pagos que recibe el cajero quedan en su turno de caja; al cerrarlo se cuenta el efectivo y
se compara con lo que el sistema espera (RN-22 a RN-24).
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Optional

from app.config import Configuracion
from app.core.auditoria import auditar
from app.core.tiempo import ahora_local
from app.domain.excepciones import Conflicto, NoEncontrado, Prohibido, ReglaNegocio
from app.domain.modelos import Caja, EstadoCaja, Factura, MetodoPago, PagoFactura, Rol, Usuario
from app.repositories.interfaces import IAuditoriaRepository, ICajaRepository, IFacturaRepository

BASE_MAXIMA = 100_000_000


@dataclass
class ResumenCaja:
    por_metodo: dict[str, int] = field(default_factory=dict)
    n_recibos: int = 0
    total: int = 0
    efectivo_esperado: int = 0


class CajaService:
    def __init__(
        self,
        cajas: ICajaRepository,
        facturas: IFacturaRepository,
        auditoria: IAuditoriaRepository,
        config: Configuracion,
    ) -> None:
        self._cajas = cajas
        self._facturas = facturas
        self._auditoria = auditoria
        self._config = config
        self._lock = threading.Lock()
        self._siguiente_recibo = 1

    # ------------------------------------------------------------------ recibos

    def nuevo_recibo(self) -> str:
        """Consecutivo del recibo de caja, único para todos los cajeros."""
        with self._lock:
            numero = self._siguiente_recibo
            self._siguiente_recibo += 1
        return f"RC-{numero:06d}"

    def caja_para_cobrar(self, usuario: Optional[Usuario]) -> Optional[Caja]:
        """Caja abierta del cajero. Con `caja_obligatoria`, cobrar sin caja abierta no se permite (RN-23)."""
        caja = self._cajas.obtener_abierta_de(usuario.id) if usuario is not None else None
        if caja is None and self._config.caja_obligatoria and usuario is not None:
            raise ReglaNegocio("Abra su caja antes de cobrar: el pago debe quedar en un turno de caja.")
        return caja

    # --------------------------------------------------------------------- turno

    def abrir(self, cajero: Usuario, base_inicial: int) -> Caja:
        if not isinstance(base_inicial, int) or isinstance(base_inicial, bool) or not 0 <= base_inicial <= BASE_MAXIMA:
            raise ReglaNegocio("La base inicial debe ser un valor entero en pesos, de cero en adelante.")
        with self._lock:
            if self._cajas.obtener_abierta_de(cajero.id) is not None:
                raise Conflicto("Ya tiene una caja abierta: ciérrela antes de abrir otra.")
            caja = self._cajas.agregar(
                Caja(
                    cajero_id=cajero.id,
                    fecha_apertura=ahora_local(self._config.zona_horaria),
                    base_inicial=base_inicial,
                )
            )
        auditar(self._auditoria, "Caja", "APERTURA", caja.id)
        return caja

    def actual(self, cajero: Usuario) -> Optional[Caja]:
        return self._cajas.obtener_abierta_de(cajero.id)

    def obtener(self, caja_id: int) -> Caja:
        caja = self._cajas.obtener_por_id(caja_id)
        if caja is None:
            raise NoEncontrado("La caja no existe.")
        return caja

    def listar(self, usuario: Usuario) -> list[Caja]:
        """El cajero ve sus turnos; el administrador ve todos."""
        return self._cajas.buscar(None if usuario.rol == Rol.ADMINISTRADOR else usuario.id)

    def ver(self, caja_id: int, usuario: Usuario) -> Caja:
        caja = self.obtener(caja_id)
        if usuario.rol != Rol.ADMINISTRADOR and caja.cajero_id != usuario.id:
            raise Prohibido("Esa caja es de otro cajero.")
        return caja

    def recibos(self, caja_id: int) -> list[tuple[Factura, PagoFactura]]:
        encontrados = [
            (f, p) for f in self._facturas.buscar() for p in f.pagos if p.caja_id == caja_id
        ]
        encontrados.sort(key=lambda par: par[1].fecha)
        return encontrados

    def resumen(self, caja: Caja) -> ResumenCaja:
        recibos = self.recibos(caja.id)
        por_metodo: dict[str, int] = {}
        for _, pago in recibos:
            por_metodo[pago.metodo.value] = por_metodo.get(pago.metodo.value, 0) + pago.valor
        return ResumenCaja(
            por_metodo=por_metodo,
            n_recibos=len(recibos),
            total=sum(por_metodo.values()),
            efectivo_esperado=caja.base_inicial + por_metodo.get(MetodoPago.EFECTIVO.value, 0),
        )

    def cerrar(self, caja_id: int, cajero: Usuario, efectivo_contado: int, observaciones: str = "") -> Caja:
        """Cierra el turno comparando el efectivo contado con el esperado (base + cobros en efectivo)."""
        if not isinstance(efectivo_contado, int) or isinstance(efectivo_contado, bool) or efectivo_contado < 0:
            raise ReglaNegocio("El efectivo contado debe ser un valor entero en pesos, de cero en adelante.")
        observaciones = (observaciones or "").strip()
        with self._lock:
            caja = self.obtener(caja_id)
            if caja.cajero_id != cajero.id:
                raise Prohibido("Solo el cajero de este turno puede cerrarlo.")
            if caja.estado != EstadoCaja.ABIERTA:
                raise ReglaNegocio("La caja ya está cerrada.")
            resumen = self.resumen(caja)
            diferencia = efectivo_contado - resumen.efectivo_esperado
            if diferencia != 0 and not observaciones:
                raise ReglaNegocio("El efectivo no coincide con lo esperado: explique la diferencia en las observaciones.")
            caja.estado = EstadoCaja.CERRADA
            caja.fecha_cierre = ahora_local(self._config.zona_horaria)
            caja.efectivo_esperado = resumen.efectivo_esperado
            caja.efectivo_contado = efectivo_contado
            caja.diferencia = diferencia
            caja.observaciones = observaciones
            caja.por_metodo = resumen.por_metodo
            cerrada = self._cajas.actualizar(caja)
        auditar(self._auditoria, "Caja", "CIERRE", cerrada.id)
        return cerrada
