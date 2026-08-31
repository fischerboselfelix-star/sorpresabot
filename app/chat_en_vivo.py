"""
Chat en vivo (Opción B): cuando el DESTINATARIO de un encargo —no el
comprador— escribe al número con el código que ha recibido en la landing
de regalo, la conversación entra aquí en vez de en app/conversation.py.

Aquí sí hablamos directamente con un tercero que no ha comprado nada, pero
es compatible con las políticas de WhatsApp Business porque es él/ella
quien inicia el contacto escribiendo primero (viene de un link que le ha
mandado el comprador por el canal que sea, no de un mensaje en frío de
este número).

app/main.py llama a manejar_mensaje(remitente, texto) ANTES que a
conversation.handle_message; si devuelve None, es que ese mensaje no es
parte de un chat en vivo y sigue el flujo normal del comprador.
"""

from . import storage
from .llm import generar_respuesta_chat_vivo, generar_saludo_chat_vivo
from .personas import persona_por_id


def manejar_mensaje(remitente: str, texto: str) -> list[str] | None:
    encargo_activo = storage.sesion_activa_para(remitente)
    if encargo_activo:
        return _continuar(remitente, encargo_activo, texto)

    encargo = storage.obtener_encargo_desde_texto(texto)
    if encargo:
        return _iniciar(remitente, encargo)

    return None


def _iniciar(remitente: str, encargo: storage.EncargoChatVivo) -> list[str]:
    persona = persona_por_id(encargo.persona_id)
    if persona is None:
        return ["Uy, esta sorpresa ha caducado 🙈 Pídele a quien te la envió que cree una nueva."]

    storage.vincular_sesion(remitente, encargo.codigo)
    saludo = generar_saludo_chat_vivo(
        persona["system_prompt"],
        {
            "destinatario": encargo.destinatario,
            "ocasion": encargo.ocasion,
            "anecdota": encargo.anecdota,
        },
    )
    storage.guardar_turno(encargo.codigo, "assistant", saludo)
    encargo.mensajes_restantes -= 1
    encargo.iniciado = True
    return [saludo]


def _continuar(remitente: str, encargo: storage.EncargoChatVivo, texto: str) -> list[str]:
    persona = persona_por_id(encargo.persona_id)

    if encargo.mensajes_restantes <= 0 or persona is None:
        storage.desvincular_sesion(remitente)
        nombre = persona["nombre"] if persona else "tu personaje"
        return [
            f"{nombre} se ha tenido que ir por hoy ✨ ¡Ojalá te haya gustado la sorpresa!",
            "(Si quieres regalar tú también una conversación así, escríbenos a este mismo número.)",
        ]

    historial_previo = list(encargo.historial)
    respuesta = generar_respuesta_chat_vivo(persona["system_prompt"], historial_previo, texto)

    storage.guardar_turno(encargo.codigo, "user", texto)
    storage.guardar_turno(encargo.codigo, "assistant", respuesta)
    encargo.mensajes_restantes -= 1

    mensajes = [respuesta]
    if encargo.mensajes_restantes <= 0:
        mensajes.append(
            "(Se han acabado los mensajes de esta sorpresa — ¡espero que os haya encantado! 💌)"
        )
        storage.desvincular_sesion(remitente)
    return mensajes
