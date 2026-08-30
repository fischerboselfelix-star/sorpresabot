"""
Almacenamiento en memoria para el prototipo.

En producción esto sería una base de datos (SQLite para empezar, Postgres
al escalar) con las tablas de sesiones, pedidos y entregas programadas.
Aquí se usan diccionarios/listas en memoria a propósito, para que el
prototipo se pueda leer y probar sin montar infraestructura.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

SESSIONS: dict[str, dict] = {}
ENTREGAS_PROGRAMADAS: list["EntregaProgramada"] = []


@dataclass
class EntregaProgramada:
    user_id: str
    contenido: str
    destinatario: str
    fecha_entrega: datetime
    entregada: bool = False


def get_session(user_id: str) -> dict:
    if user_id not in SESSIONS:
        SESSIONS[user_id] = {"estado": "INICIO"}
    return SESSIONS[user_id]


def reset_session(user_id: str) -> None:
    SESSIONS[user_id] = {"estado": "INICIO"}


def programar_entrega(user_id: str, contenido: str, destinatario: str, fecha_entrega: datetime) -> None:
    ENTREGAS_PROGRAMADAS.append(
        EntregaProgramada(user_id=user_id, contenido=contenido, destinatario=destinatario, fecha_entrega=fecha_entrega)
    )


def entregas_pendientes(ahora: Optional[datetime] = None) -> list[EntregaProgramada]:
    ahora = ahora or datetime.now()
    return [e for e in ENTREGAS_PROGRAMADAS if not e.entregada and e.fecha_entrega <= ahora]
