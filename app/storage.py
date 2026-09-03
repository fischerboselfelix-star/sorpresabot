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
import uuid
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

# --- Búsqueda del tesoro ("pistas"): mismo patrón que el chat en vivo, pero
# con una secuencia de pistas pre-generada que se va desvelando.
ENCARGOS_PISTAS: dict[str, "EncargoPistas"] = {}
SESIONES_PISTAS: dict[str, str] = {}  # teléfono destinatario -> código

# --- Pedidos pendientes de pago: se crea uno justo cuando el comprador
# confirma qué quiere, ANTES de generar/entregar nada. Solo cuando el
# webhook de Stripe confirma el pago (o, en modo simulado sin Stripe
# configurado, al instante — ver app/pagos.py) se genera y entrega el
# contenido de verdad, vía app/entregas.py.
PEDIDOS_PENDIENTES: dict[str, "PedidoPendiente"] = {}

# --- Métricas: registro simple de eventos del embudo (hola -> pedido creado
# -> pedido pagado), para poder medir conversión y saber si merece la pena
# invertir en promoción. En memoria, como el resto del prototipo: se pierde
# al reiniciar el servidor — ver GET /metricas en app/main.py.
EVENTOS: list["Evento"] = []

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


@dataclass
class EncargoPistas:
    codigo: str
    persona_id: str
    destinatario: str
    ocasion: str
    tema: str
    anecdota: str
    comprador_user_id: str
    pistas: list[str]
    tesoro: str
    indice_actual: int = 0
    completado: bool = False
    creado_en: datetime = field(default_factory=datetime.now)


@dataclass
class Evento:
    tipo: str  # "hola" | "pedido_creado" | "pedido_pagado"
    user_id: str
    en: datetime = field(default_factory=datetime.now)
    tipo_pedido: str = ""  # "simple" | "chat_en_vivo" | "pistas" (solo pedidos)
    precio: float = 0.0  # solo pedidos
    origen: str = "directo"  # "directo" | "viral" (de qué venía el 'hola' inicial)


@dataclass
class PedidoPendiente:
    pedido_id: str
    user_id: str
    tipo: str  # "simple" | "chat_en_vivo" | "pistas"
    precio: float
    destinatario: str
    ocasion: str
    anecdota: str
    persona_id: str = ""
    formato_id: str = ""
    contenido: str = ""  # solo para "simple": ya generado en la vista previa
    fecha_entrega: Optional[datetime] = None
    pagado: bool = False
    origen: str = "directo"  # "directo" | "viral" — para medir el bucle viral en /metricas
    creado_en: datetime = field(default_factory=datetime.now)


def registrar_evento(
    tipo: str, user_id: str, tipo_pedido: str = "", precio: float = 0.0, origen: str = "directo"
) -> None:
    EVENTOS.append(Evento(tipo=tipo, user_id=user_id, tipo_pedido=tipo_pedido, precio=precio, origen=origen))


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
    """Un único pool de códigos para chat en vivo y pistas: así nunca chocan
    entre sí y la landing page puede buscar el código en cualquiera de los dos."""
    alfabeto = string.ascii_uppercase + string.digits
    while True:
        codigo = "".join(random.choices(alfabeto, k=6))
        if codigo not in ENCARGOS and codigo not in ENCARGOS_PISTAS:
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


def crear_encargo_pistas(
    persona_id: str,
    destinatario: str,
    ocasion: str,
    tema: str,
    anecdota: str,
    comprador_user_id: str,
    pistas: list[str],
    tesoro: str,
) -> str:
    codigo = _generar_codigo()
    ENCARGOS_PISTAS[codigo] = EncargoPistas(
        codigo=codigo,
        persona_id=persona_id,
        destinatario=destinatario,
        ocasion=ocasion,
        tema=tema,
        anecdota=anecdota,
        comprador_user_id=comprador_user_id,
        pistas=pistas,
        tesoro=tesoro,
    )
    return codigo


def obtener_encargo_pistas(codigo: str) -> Optional[EncargoPistas]:
    return ENCARGOS_PISTAS.get((codigo or "").strip().upper())


def obtener_encargo_pistas_desde_texto(texto: str) -> Optional[EncargoPistas]:
    texto_norm = (texto or "").upper()
    directo = ENCARGOS_PISTAS.get(texto_norm.strip())
    if directo:
        return directo
    for candidato in _CODIGO_RE.findall(texto_norm):
        if candidato in ENCARGOS_PISTAS:
            return ENCARGOS_PISTAS[candidato]
    return None


def sesion_pistas_activa_para(telefono: str) -> Optional[EncargoPistas]:
    codigo = SESIONES_PISTAS.get(telefono)
    return ENCARGOS_PISTAS.get(codigo) if codigo else None


def vincular_sesion_pistas(telefono: str, codigo: str) -> None:
    SESIONES_PISTAS[telefono] = codigo


def desvincular_sesion_pistas(telefono: str) -> None:
    SESIONES_PISTAS.pop(telefono, None)


def crear_pedido_pendiente(
    user_id: str,
    tipo: str,
    precio: float,
    destinatario: str,
    ocasion: str,
    anecdota: str,
    persona_id: str = "",
    formato_id: str = "",
    contenido: str = "",
    fecha_entrega: Optional[datetime] = None,
    origen: str = "directo",
) -> PedidoPendiente:
    pedido_id = uuid.uuid4().hex[:12]
    pedido = PedidoPendiente(
        pedido_id=pedido_id,
        user_id=user_id,
        tipo=tipo,
        precio=precio,
        destinatario=destinatario,
        ocasion=ocasion,
        anecdota=anecdota,
        persona_id=persona_id,
        formato_id=formato_id,
        contenido=contenido,
        fecha_entrega=fecha_entrega,
        origen=origen,
    )
    PEDIDOS_PENDIENTES[pedido_id] = pedido
    registrar_evento("pedido_creado", user_id=user_id, tipo_pedido=tipo, precio=precio, origen=origen)
    return pedido


def obtener_pedido(pedido_id: str) -> Optional[PedidoPendiente]:
    return PEDIDOS_PENDIENTES.get(pedido_id)


def marcar_pagado(pedido_id: str) -> Optional[PedidoPendiente]:
    """Idempotente a propósito: Stripe puede reenviar el mismo evento de
    webhook más de una vez, y no queremos entregar el pedido dos veces."""
    pedido = PEDIDOS_PENDIENTES.get(pedido_id)
    if pedido and not pedido.pagado:
        pedido.pagado = True
        registrar_evento(
            "pedido_pagado",
            user_id=pedido.user_id,
            tipo_pedido=pedido.tipo,
            precio=pedido.precio,
            origen=pedido.origen,
        )
        return pedido
    return None
