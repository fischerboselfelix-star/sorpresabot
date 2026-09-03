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

from . import entregas, pagos, promos, storage
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
        promo = promos.obtener_promo(texto)
        sesion["estado"] = "ESPERANDO_PERSONA"
        if promo:
            sesion["promo"] = promo
        storage.registrar_evento("hola", user_id=user_id, origen=(promo["origen"] if promo else "directo"))

        mensajes = []
        if promo:
            mensajes.append(
                f"🎉 ¡Código aplicado! Tienes un {promo['descuento_pct']}% de descuento en tu pedido."
            )
        mensajes += [
            "¡Hola! 👋 Soy el asistente de SorpresaBot. Te ayudo a crear un mensaje, "
            "poema o cuento personalizado para regalarle a alguien.",
            catalogo_personas_texto(),
        ]
        return mensajes

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

        if sesion["formato_id"] == "chat_en_vivo":
            # No hay nada que previsualizar ni programar: es una conversación
            # en vivo, así que se entrega el link directamente.
            return _entregar_chat_en_vivo(user_id, sesion)

        if sesion["formato_id"] == "pistas":
            return _entregar_pistas(user_id, sesion)

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
            return _solicitar_pago_simple(user_id, sesion)
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
    precio = persona["precio_base"] + formato["precio_extra"]
    return promos.aplicar_descuento(precio, sesion.get("promo"))


def _origen_pedido(sesion: dict) -> str:
    promo = sesion.get("promo")
    return promo["origen"] if promo else "directo"


def _parsear_fecha(texto: str):
    if texto.lower() == "ahora":
        return None
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto, fmt)
        except ValueError:
            continue
    return None


def _solicitar_pago_simple(user_id: str, sesion: dict) -> list[str]:
    """
    El contenido ya se generó como vista previa (ESPERANDO_FECHA), pero NO
    se entrega aquí: se crea un pedido pendiente y se cobra antes. Solo
    cuando el pago se confirma (o al instante, en modo simulado sin Stripe
    configurado) se ejecuta la entrega real, en app/entregas.py.
    """
    pedido = storage.crear_pedido_pendiente(
        user_id=user_id,
        tipo="simple",
        precio=_precio_pedido(sesion),
        destinatario=sesion["destinatario"],
        ocasion=sesion["ocasion"],
        anecdota=sesion.get("anecdota", ""),
        contenido=sesion["contenido"],
        fecha_entrega=sesion.get("fecha_entrega"),
        origen=_origen_pedido(sesion),
    )
    storage.reset_session(user_id)
    return _iniciar_cobro(pedido, descripcion=f"Mensaje personalizado para {sesion['destinatario']}")


def _entregar_chat_en_vivo(user_id: str, sesion: dict) -> list[str]:
    """
    A diferencia del resto, aquí NO se crea el encargo (ni el link de
    regalo) hasta que el pago está confirmado: eso ocurre en
    app/entregas.py, para no repartir links de una experiencia que nadie
    ha pagado todavía.
    """
    persona = _persona_actual(sesion)
    pedido = storage.crear_pedido_pendiente(
        user_id=user_id,
        tipo="chat_en_vivo",
        precio=_precio_pedido(sesion),
        destinatario=sesion["destinatario"],
        ocasion=sesion["ocasion"],
        anecdota=sesion.get("anecdota", ""),
        persona_id=persona["id"],
        formato_id=sesion["formato_id"],
        origen=_origen_pedido(sesion),
    )
    storage.reset_session(user_id)
    return _iniciar_cobro(
        pedido, descripcion=f"Conversación en vivo con {persona['nombre']} para {sesion['destinatario']}"
    )


def _entregar_pistas(user_id: str, sesion: dict) -> list[str]:
    """
    Igual que en el chat en vivo: las pistas y el tesoro se generan con IA
    solo tras el pago (app/entregas.py), no aquí — así no se gasta en
    generación si el comprador no llega a pagar.
    """
    persona = _persona_actual(sesion)
    pedido = storage.crear_pedido_pendiente(
        user_id=user_id,
        tipo="pistas",
        precio=_precio_pedido(sesion),
        destinatario=sesion["destinatario"],
        ocasion=sesion["ocasion"],
        anecdota=sesion.get("anecdota", ""),
        persona_id=persona["id"],
        formato_id=sesion["formato_id"],
        origen=_origen_pedido(sesion),
    )
    storage.reset_session(user_id)
    return _iniciar_cobro(
        pedido, descripcion=f"Búsqueda del tesoro de {persona['nombre']} para {sesion['destinatario']}"
    )


def _iniciar_cobro(pedido: "storage.PedidoPendiente", descripcion: str) -> list[str]:
    try:
        url_pago = pagos.iniciar_pago(pedido.pedido_id, descripcion, pedido.precio, pedido.user_id)
    except Exception as e:
        # Fallo real de Stripe (clave mal copiada, cuenta con restricciones,
        # corte de red...): NO se entrega el pedido gratis, se avisa y ya
        # está — el pedido queda en PEDIDOS_PENDIENTES por si se quiere
        # reintentar el cobro manualmente.
        print(f"[STRIPE-ERROR] No se pudo iniciar el cobro del pedido {pedido.pedido_id}: {e!r}")
        return [
            "Se ha guardado el pedido pero ha habido un problema preparando el cobro 😕 "
            "Escribe 'hola' para intentarlo de nuevo en un momento."
        ]

    if url_pago:
        return [
            f"¡Casi listo! 🎉 Precio: {pedido.precio:.2f} €.",
            f"Para confirmarlo, paga aquí de forma segura:\n{url_pago}",
            "En cuanto se confirme el pago te mando aquí mismo lo que necesites para entregarlo "
            "— normalmente tarda solo unos segundos.",
        ]

    # Modo simulado (sin STRIPE_SECRET_KEY configurada): se entrega al
    # instante, igual que hacía el prototipo antes de tener cobro real —
    # así las pruebas locales (test_scenario.py) y el desarrollo siguen
    # funcionando sin necesitar una cuenta de Stripe.
    storage.marcar_pagado(pedido.pedido_id)
    return entregas.completar_pedido(pedido)
