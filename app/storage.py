"""
Almacenamiento en memoria para el prototipo.

En producción esto sería una base de datos (SQLite para empezar, Postgres
al escalar) con las tablas de sesiones, pedidos y entregas programadas.
Aquí se usan diccionarios/listas en memoria a propósito, para que el
prototipo se pueda leer y probar sin montar infraestructura.
"""

import random
import re
import string
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

SESSIONS: dict[str, dict] = {}
ENTREGAS_PROGRAMADAS: list["EntregaProgramada"] = []

# --- Chat en vivo (Opción B): encargos identificados por un código, y qué
# número de teléfono tiene ahora mismo una conversación en vivo abierta con
# qué encargo. Todo en memoria, igual que el resto del prototipo.
ENCARGOS: dict[str, "EncargoChatVivo"] = {}
SESIONES_CHAT_VIVO: dict[str, str] = {}  # teléfono destinatario -> código

_CODIGO_RE = re.compile(r"[A-Z0-9]{6}")


@dataclass
class EntregaProgramada:
    user_id: str
    contenido: str
    destinatario: str
    fecha_entrega: datetime
    entregada: bool = False


@dataclass
class EncargoChatVivo:
    codigo: str
    persona_id: str
    destinatario: str
    ocasion: str
    anecdota: str
    comprador_user_id: str
    mensajes_restantes: int
    iniciado: bool = False
    historial: list[dict] = field(default_factory=list)
    creado_en: datetime = field(default_factory=datetime.now)


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


def _generar_codigo() -> str:
    alfabeto = string.ascii_uppercase + string.digits
    while True:
        codigo = "".join(random.choices(alfabeto, k=6))
        if codigo not in ENCARGOS:
            return codigo


def crear_encargo_chat_vivo(
    persona_id: str,
    destinatario: str,
    ocasion: str,
    anecdota: str,
    comprador_user_id: str,
    mensajes_incluidos: int,
) -> str:
    codigo = _generar_codigo()
    ENCARGOS[codigo] = EncargoChatVivo(
        codigo=codigo,
        persona_id=persona_id,
        destinatario=destinatario,
        ocasion=ocasion,
        anecdota=anecdota,
        comprador_user_id=comprador_user_id,
        mensajes_restantes=mensajes_incluidos,
    )
    return codigo


def obtener_encargo(codigo: str) -> Optional[EncargoChatVivo]:
    """Búsqueda exacta por código (para la landing page, que ya lo recibe limpio en la URL)."""
    return ENCARGOS.get((codigo or "").strip().upper())


def obtener_encargo_desde_texto(texto: str) -> Optional[EncargoChatVivo]:
    """
    Búsqueda tolerante para mensajes de WhatsApp: la persona puede escribir
    solo el código, o WhatsApp puede haber dejado texto alrededor si lo editó
    antes de enviar (el link precompleta el mensaje, pero es editable).
    """
    texto_norm = (texto or "").upper()
    directo = ENCARGOS.get(texto_norm.strip())
    if directo:
        return directo
    for candidato in _CODIGO_RE.findall(texto_norm):
        if candidato in ENCARGOS:
            return ENCARGOS[candidato]
    return None


def sesion_activa_para(telefono: str) -> Optional[EncargoChatVivo]:
    codigo = SESIONES_CHAT_VIVO.get(telefono)
    return ENCARGOS.get(codigo) if codigo else None


def vincular_sesion(telefono: str, codigo: str) -> None:
    SESIONES_CHAT_VIVO[telefono] = codigo


def desvincular_sesion(telefono: str) -> None:
    SESIONES_CHAT_VIVO.pop(telefono, None)


def guardar_turno(codigo: str, role: str, texto: str) -> None:
    encargo = ENCARGOS.get(codigo)
    if encargo:
        encargo.historial.append({"role": role, "texto": texto})
