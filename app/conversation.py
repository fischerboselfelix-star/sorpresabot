"""
Máquina de estados de la conversación con quien COMPRA el mensaje.

Importante sobre el diseño de cumplimiento (ver sección 4 del plan de
negocio): este bot solo conversa con la persona que le ha escrito a él
mismo (el comprador). La entrega al DESTINATARIO se hace en modo
"Opción A" — se le devuelve el contenido ya generado al comprador para
que sea él quien lo reenvíe desde su propio WhatsApp — precisamente para
no tener que enviar nunca un mensaje de este número a un desconocido que
no ha iniciado contacto. Es la opción más simple y la más segura para
empezar; las Opciones B y C del plan de negocio son evoluciones de este
mismo esqueleto, no una arquitectura distinta.

handle_message(user_id, texto) es la única función que usan tanto el
webhook real de WhatsApp (app/main.py) como el simulador local
(test_local.py), así que probar con el simulador prueba exactamente la
misma lógica que correría en producción.
"""

from datetime import datetime, timedelta

from . import storage
from .llm import generar_contenido
from .personas import PERSONAS, FORMATOS, OCASIONES, catalogo_personas_texto, catalogo_formatos_texto, catalogo_ocasiones_texto

COMANDOS_REINICIO = {"reiniciar", "cancelar", "empezar", "hola"}


def handle_message(user_id: str, texto: str) -> list[str]:
    texto = (texto or "").strip()
    sesion = storage.get_session(user_id)

    if texto.lower() in COMANDOS_REINICIO and sesion["estado"] != "INICIO":
        storage.reset_session(user_id)
        sesion = storage.get_session(user_id)

    estado = sesion["estado"]

    if estado == "INICIO":
        sesion["estado"] = "ESPERANDO_PERSONA"
        return [
            "¡Hola! 👋 Soy el asistente de SorpresaBot. Te ayudo a crear un mensaje, "
            "poema o cuento personalizado para regalarle a alguien.",
            catalogo_personas_texto(),
        ]

    if estado == "ESPERANDO_PERSONA":
        persona = PERSONAS.get(texto)
        if not persona:
            return ["No he reconocido esa opción 🙏", catalogo_personas_texto()]
        sesion["persona_id"] = persona["id"]
        sesion["estado"] = "ESPERANDO_FORMATO"
        return [f"Elegiste a {persona['nombre']}.", catalogo_formatos_texto(persona)]

    if estado == "ESPERANDO_FORMATO":
        persona = _persona_actual(sesion)
        try:
            idx = int(texto) - 1
            formato_id = persona["formatos"][idx]
        except (ValueError, IndexError):
            return ["No he reconocido esa opción 🙏", catalogo_formatos_texto(persona)]
        sesion["formato_id"] = formato_id
        sesion["estado"] = "ESPERANDO_OCASION"
        return [catalogo_ocasiones_texto()]

    if estado == "ESPERANDO_OCASION":
        try:
            idx = int(texto) - 1
            ocasion = OCASIONES[idx]
        except (ValueError, IndexError):
            return ["No he reconocido esa opción 🙏", catalogo_ocasiones_texto()]
        sesion["ocasion"] = ocasion
        sesion["estado"] = "ESPERANDO_DESTINATARIO"
        return ["¿Cómo se llama la persona que va a recibir el mensaje?"]

    if estado == "ESPERANDO_DESTINATARIO":
        sesion["destinatario"] = texto
        sesion["estado"] = "ESPERANDO_DETALLES"
        return [
            f"Perfecto. Cuéntame en una frase algo sobre {texto} o el tono que quieres "
            "(gracioso, cursi, formal...) — o escribe 'ninguno' si prefieres que me lo invente."
        ]

    if estado == "ESPERANDO_DETALLES":
        sesion["anecdota"] = "" if texto.lower() == "ninguno" else texto
        sesion["estado"] = "ESPERANDO_FECHA"
        return [
            "¿Cuándo quieres tenerlo listo? Escribe 'ahora' para generarlo ya, o una fecha y "
            "hora tipo '24/12/2026 20:00' para programarlo."
        ]

    if estado == "ESPERANDO_FECHA":
        fecha_entrega = _parsear_fecha(texto)
        if texto.lower() != "ahora" and fecha_entrega is None:
            return ["No he entendido la fecha. Escribe 'ahora' o algo tipo '24/12/2026 20:00'."]
        sesion["fecha_entrega"] = fecha_entrega
        contenido = _generar(sesion)
        sesion["contenido"] = contenido
        sesion["estado"] = "ESPERANDO_CONFIRMACION"
        precio = _precio_pedido(sesion)
        return [
            f"Esto es lo que he preparado (precio del pedido: {precio:.2f} €):",
            contenido,
            "¿Te vale así? Responde 'sí' para confirmar o 'no' para que lo vuelva a intentar.",
        ]

    if estado == "ESPERANDO_CONFIRMACION":
        if texto.lower() in ("no", "otra", "regenerar"):
            contenido = _generar(sesion)
            sesion["contenido"] = contenido
            return [contenido, "¿Mejor así? 'sí' para confirmar o 'no' para otra versión."]
        if texto.lower() in ("si", "sí", "vale", "ok"):
            return _entregar(user_id, sesion)
        return ["Responde 'sí' para confirmar o 'no' para otra versión."]

    # estado desconocido -> reiniciar de forma segura
    storage.reset_session(user_id)
    return handle_message(user_id, "hola")


def _persona_actual(sesion: dict) -> dict:
    for p in PERSONAS.values():
        if p["id"] == sesion["persona_id"]:
            return p
    raise KeyError("persona no encontrada en la sesión")


def _generar(sesion: dict) -> str:
    persona = _persona_actual(sesion)
    formato = FORMATOS[sesion["formato_id"]]
    detalles = {
        "destinatario": sesion["destinatario"],
        "ocasion": sesion["ocasion"],
        "anecdota": sesion.get("anecdota", ""),
    }
    return generar_contenido(persona["system_prompt"], formato["instrucciones"], detalles)


def _precio_pedido(sesion: dict) -> float:
    persona = _persona_actual(sesion)
    formato = FORMATOS[sesion["formato_id"]]
    return persona["precio_base"] + formato["precio_extra"]


def _parsear_fecha(texto: str):
    if texto.lower() == "ahora":
        return None
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto, fmt)
        except ValueError:
            continue
    return None


def _entregar(user_id: str, sesion: dict) -> list[str]:
    contenido = sesion["contenido"]
    destinatario = sesion["destinatario"]
    fecha_entrega = sesion.get("fecha_entrega")

    mensajes: list[str] = []

    if fecha_entrega is None:
        mensajes.append(
            "¡Listo! 🎉 Copia y reenvía tú mismo/a este mensaje a "
            f"{destinatario} desde tu WhatsApp:"
        )
        mensajes.append(contenido)
    else:
        storage.programar_entrega(user_id, contenido, destinatario, fecha_entrega)
        mensajes.append(
            f"Guardado ✅ Te lo recordaré aquí mismo el {fecha_entrega.strftime('%d/%m/%Y a las %H:%M')} "
            f"para que se lo reenvíes a {destinatario} en el momento justo."
        )

    mensajes.append("Si quieres crear otro, escribe 'hola' cuando quieras 🙂")
    storage.reset_session(user_id)
    return mensajes
