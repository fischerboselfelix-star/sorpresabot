"""
Entrega del contenido de un pedido YA PAGADO.

completar_pedido(pedido) construye los mensajes a enviar al comprador —
es la misma lógica que antes vivía en app/conversation.py (_entregar,
_entregar_chat_en_vivo, _entregar_pistas), pero ahora solo se ejecuta
después de que el pago esté confirmado: o bien porque llega el webhook
"checkout.session.completed" de Stripe (ver /webhook/stripe en
app/main.py), o bien, en modo simulado sin Stripe configurado, al
instante tras crear el pedido (ver app/pagos.py y app/conversation.py).

Para "pistas" en concreto esto también evita gastar en generación con IA
si el comprador nunca llega a pagar: las pistas y el tesoro se generan
aquí, no antes.
"""

import os

from . import storage
from .llm import generar_busqueda_tesoro
from .personas import FORMATOS, persona_por_id


def completar_pedido(pedido: "storage.PedidoPendiente") -> list[str]:
    if pedido.tipo == "chat_en_vivo":
        return _completar_chat_en_vivo(pedido)
    if pedido.tipo == "pistas":
        return _completar_pistas(pedido)
    return _completar_simple(pedido)


def _completar_simple(pedido: "storage.PedidoPendiente") -> list[str]:
    mensajes: list[str] = []

    if pedido.fecha_entrega is None:
        mensajes.append(
            "¡Pago recibido! 🎉 Copia y reenvía tú mismo/a este mensaje a "
            f"{pedido.destinatario} desde tu WhatsApp:"
        )
        mensajes.append(pedido.contenido)
    else:
        storage.programar_entrega(pedido.user_id, pedido.contenido, pedido.destinatario, pedido.fecha_entrega)
        mensajes.append(
            "¡Pago recibido! ✅ Te lo recordaré aquí mismo el "
            f"{pedido.fecha_entrega.strftime('%d/%m/%Y a las %H:%M')} para que se lo reenvíes a "
            f"{pedido.destinatario} en el momento justo."
        )

    mensajes.append("Si quieres crear otro, escribe 'hola' cuando quieras 🙂")
    return mensajes


def _completar_chat_en_vivo(pedido: "storage.PedidoPendiente") -> list[str]:
    persona = persona_por_id(pedido.persona_id)
    formato = FORMATOS[pedido.formato_id]
    mensajes_incluidos = formato.get("mensajes_incluidos", 15)
    nombre = persona["nombre"] if persona else "tu personaje"

    codigo = storage.crear_encargo_chat_vivo(
        persona_id=pedido.persona_id,
        destinatario=pedido.destinatario,
        ocasion=pedido.ocasion,
        anecdota=pedido.anecdota,
        comprador_user_id=pedido.user_id,
        mensajes_incluidos=mensajes_incluidos,
    )
    link = _link_regalo(codigo)

    return [
        "¡Pago recibido! 🎉",
        f"Mándale este link a {pedido.destinatario} (por SMS, WhatsApp, donde prefieras):\n{link}",
        f"Cuando lo abra y le escriba a {nombre}, tendrá una conversación en vivo de hasta "
        f"{mensajes_incluidos} mensajes con él/ella — no es un texto para reenviar, es él/ella "
        "hablando de verdad con el personaje.",
        "Si quieres crear otro, escribe 'hola' cuando quieras 🙂",
    ]


def _completar_pistas(pedido: "storage.PedidoPendiente") -> list[str]:
    persona = persona_por_id(pedido.persona_id)
    formato = FORMATOS[pedido.formato_id]
    num_pistas = formato.get("num_pistas", 5)
    nombre = persona["nombre"] if persona else "tu personaje"

    resultado = generar_busqueda_tesoro(
        persona["system_prompt"] if persona else "",
        {
            "destinatario": pedido.destinatario,
            "ocasion": pedido.ocasion,
            "tema": pedido.anecdota,
            "anecdota": pedido.anecdota,
        },
        num_pistas=num_pistas,
    )

    codigo = storage.crear_encargo_pistas(
        persona_id=pedido.persona_id,
        destinatario=pedido.destinatario,
        ocasion=pedido.ocasion,
        tema=pedido.anecdota,
        anecdota=pedido.anecdota,
        comprador_user_id=pedido.user_id,
        pistas=resultado["pistas"],
        tesoro=resultado["tesoro"],
    )
    link = _link_regalo(codigo)

    return [
        "¡Pago recibido! 🎉",
        f"Mándale este link a {pedido.destinatario} (por SMS, WhatsApp, donde prefieras):\n{link}",
        f"Cuando lo abra y le escriba a {nombre}, empezará una búsqueda del tesoro de "
        f"{num_pistas} pistas encadenadas, con una sorpresa final al terminar.",
        "Si quieres crear otro, escribe 'hola' cuando quieras 🙂",
    ]


def _link_regalo(codigo: str) -> str:
    base = os.getenv("PUBLIC_BASE_URL")
    if not base:
        dominio = os.getenv("RAILWAY_PUBLIC_DOMAIN")
        base = f"https://{dominio}" if dominio else "http://localhost:8000"
    return f"{base.rstrip('/')}/r/{codigo}"
