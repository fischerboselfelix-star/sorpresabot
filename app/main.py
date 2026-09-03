"""
Servidor FastAPI: webhook de WhatsApp Cloud API (Meta Business Platform).

Endpoints:
- GET  /webhook  -> verificación de Meta (hub.challenge)
- POST /webhook  -> recepción de mensajes entrantes

Cómo probarlo sin una cuenta de Meta:
    python test_local.py
(simula una conversación completa por consola, usando exactamente la
misma lógica de app/conversation.py)

Cómo conectarlo a WhatsApp de verdad: ver README.md.
"""

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse

from . import chat_en_vivo, entregas, metricas, pagos, paginas, pistas, storage
from .conversation import handle_message
from .personas import persona_por_id
from .whatsapp import send_text

VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "cambia-esto")


def _limpia(valor: str | None) -> str:
    return (valor or "").strip()


async def _loop_entregas_programadas():
    """Revisa cada minuto si hay entregas programadas cuya hora ya llegó."""
    while True:
        for entrega in storage.entregas_pendientes():
            send_text(
                entrega.user_id,
                f"⏰ ¡Es la hora! Aquí tienes de nuevo el mensaje para {entrega.destinatario}:\n\n"
                f"{entrega.contenido}",
            )
            entrega.entregada = True
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    tarea = asyncio.create_task(_loop_entregas_programadas())
    yield
    tarea.cancel()


app = FastAPI(title="SorpresaBot", lifespan=lifespan)


@app.get("/webhook")
def verificar_webhook(request: Request):
    params = request.query_params
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == VERIFY_TOKEN:
        return Response(content=params.get("hub.challenge", ""), media_type="text/plain")
    return Response(status_code=403)


@app.post("/webhook")
async def recibir_mensaje(request: Request):
    payload = await request.json()

    try:
        entry = payload["entry"][0]
        cambio = entry["changes"][0]["value"]
        mensajes = cambio.get("messages")
        if not mensajes:
            # notificaciones de "leído"/estado, no mensajes de usuario: se ignoran
            return {"status": "ignorado"}

        mensaje = mensajes[0]
        remitente = mensaje["from"]
        texto = mensaje.get("text", {}).get("body", "")
    except (KeyError, IndexError):
        return {"status": "payload no reconocido"}

    # Primero comprobamos si es un DESTINATARIO entrando a una conversación
    # en vivo o a una búsqueda del tesoro (Opción B). Si no es ninguna de las
    # dos, sigue el flujo normal del comprador.
    respuestas = chat_en_vivo.manejar_mensaje(remitente, texto)
    if respuestas is None:
        respuestas = pistas.manejar_mensaje(remitente, texto)
    if respuestas is None:
        respuestas = handle_message(remitente, texto)

    for r in respuestas:
        send_text(remitente, r)

    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def landing():
    """Landing pública: la página que se promociona en redes/anuncios, con
    el botón que abre WhatsApp directamente con 'hola' precargado."""
    numero = _limpia(os.getenv("WHATSAPP_NUMERO_PUBLICO"))
    wa_link = f"https://wa.me/{numero}?text=hola" if numero else None
    return HTMLResponse(paginas.html_landing(wa_link))


@app.get("/status")
def salud():
    return {"status": "SorpresaBot activo"}


@app.get("/metricas", response_class=HTMLResponse)
def ver_metricas(clave: str = ""):
    """
    Panel simple del embudo hola -> pedido creado -> pedido pagado.
    Protegido con una clave compartida (METRICAS_CLAVE) pasada como
    ?clave=... en la URL — no es una autenticación seria, pero basta para
    que la URL no sea públicamente accesible por cualquiera que la adivine.
    """
    clave_esperada = _limpia(os.getenv("METRICAS_CLAVE"))
    if not clave_esperada:
        return HTMLResponse(
            "<p style='font-family:sans-serif;padding:24px;'>Configura la variable de entorno "
            "METRICAS_CLAVE para activar este panel.</p>",
            status_code=503,
        )
    if clave != clave_esperada:
        return HTMLResponse(
            "<p style='font-family:sans-serif;padding:24px;'>No autorizado.</p>", status_code=401
        )
    resumen = metricas.resumen_embudo(storage.EVENTOS)
    return HTMLResponse(paginas.html_metricas(resumen))


@app.post("/webhook/stripe")
async def webhook_stripe(request: Request):
    """
    Confirmación de pago real. Aquí, y solo aquí (o en el equivalente en
    modo simulado dentro de conversation.py cuando no hay Stripe
    configurado), se dispara la entrega de contenido de un pedido.
    """
    payload = await request.body()
    firma = request.headers.get("stripe-signature", "")

    try:
        evento = pagos.verificar_firma_webhook(payload, firma)
    except Exception as e:
        print(f"[STRIPE-ERROR] Webhook con firma inválida o payload mal formado: {e!r}")
        return Response(status_code=400)

    tipo_evento = evento["type"]
    if tipo_evento == "checkout.session.completed":
        objeto = evento["data"]["object"]
        metadata = objeto.get("metadata") or {}
        pedido_id = metadata.get("pedido_id")
        pedido = storage.marcar_pagado(pedido_id) if pedido_id else None
        if pedido:
            for mensaje in entregas.completar_pedido(pedido):
                send_text(pedido.user_id, mensaje)
        elif pedido_id:
            print(f"[STRIPE] Evento de pago para un pedido ya entregado o desconocido: {pedido_id}")

    return {"status": "ok"}


@app.get("/pago-ok", response_class=HTMLResponse)
def pago_ok(pedido: str = ""):
    return HTMLResponse(_html_estado_pago(
        "¡Pago recibido! 🎉",
        "Ya puedes volver a WhatsApp: en unos segundos te llega ahí mismo lo que necesitas "
        "para completar el regalo.",
    ))


@app.get("/pago-cancelado", response_class=HTMLResponse)
def pago_cancelado(pedido: str = ""):
    return HTMLResponse(_html_estado_pago(
        "Pago no completado 🙈",
        "No pasa nada — vuelve a WhatsApp y escribe 'hola' cuando quieras intentarlo de nuevo.",
    ))


def _html_estado_pago(titulo: str, cuerpo: str) -> str:
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SorpresaBot</title></head>
<body style="font-family:-apple-system,sans-serif;background:#1a1a2e;color:#fff;
display:flex;align-items:center;justify-content:center;height:100vh;margin:0;text-align:center;padding:24px;">
<div><h1 style="font-size:1.6rem;">{titulo}</h1>
<p style="opacity:.8;max-width:360px;">{cuerpo}</p></div>
</body></html>"""


@app.get("/r/{codigo}", response_class=HTMLResponse)
def pagina_regalo(codigo: str):
    """Landing de revelación: la abre el DESTINATARIO antes de escribir por WhatsApp."""
    tipo = "chat"
    encargo = storage.obtener_encargo(codigo)
    if encargo is None:
        encargo = storage.obtener_encargo_pistas(codigo)
        tipo = "pistas"
    if encargo is None:
        return HTMLResponse(_html_no_encontrado(), status_code=404)

    persona = persona_por_id(encargo.persona_id)
    numero = _limpia(os.getenv("WHATSAPP_NUMERO_PUBLICO"))
    wa_link = f"https://wa.me/{numero}?text={encargo.codigo}" if numero else None

    return HTMLResponse(_html_regalo(encargo, persona, wa_link, tipo))


def _html_no_encontrado() -> str:
    return """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SorpresaBot</title></head>
<body style="font-family:-apple-system,sans-serif;background:#1a1a2e;color:#fff;
display:flex;align-items:center;justify-content:center;height:100vh;margin:0;text-align:center;padding:24px;">
<div><h1 style="font-size:1.6rem;">Esta sorpresa ya no está disponible 🙈</h1>
<p style="opacity:.8;">El link puede haber caducado o el código no es correcto.</p></div>
</body></html>"""


def _html_regalo(encargo, persona: dict | None, wa_link: str | None, tipo: str = "chat") -> str:
    nombre_persona = persona["nombre"] if persona else "tu personaje sorpresa"
    emoji = persona.get("emoji", "🎁") if persona else "🎁"
    destinatario = encargo.destinatario

    if tipo == "pistas":
        emoji = "🗺️"
        subtitulo = (
            f"<strong>{nombre_persona}</strong> te ha preparado una búsqueda del tesoro, "
            "en vivo, por WhatsApp."
        )
        texto_boton = "🗺️ Empezar la búsqueda"
    else:
        subtitulo = (
            f"<strong>{nombre_persona}</strong> te está esperando para hablar contigo "
            "en persona, en vivo, por WhatsApp."
        )
        texto_boton = f"💬 Habla con {nombre_persona}"

    if wa_link:
        boton = f"""<a href="{wa_link}"
            style="display:inline-block;margin-top:28px;background:#25D366;color:#0b1a12;
            font-weight:700;font-size:1.05rem;padding:16px 30px;border-radius:999px;
            text-decoration:none;box-shadow:0 8px 24px rgba(37,211,102,.35);">
            {texto_boton}</a>"""
    else:
        boton = """<p style="opacity:.75;margin-top:28px;">
            (Falta configurar el número de WhatsApp para este botón.)</p>"""

    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Una sorpresa para {destinatario}</title></head>
<body style="margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
padding:24px;box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
background:radial-gradient(circle at 50% 0%, #3b2f6b 0%, #1a1a2e 60%);color:#fff;text-align:center;">
<div style="max-width:420px;">
<div style="font-size:4.5rem;line-height:1;">{emoji}</div>
<h1 style="font-size:1.5rem;margin:18px 0 6px;">Hola, {destinatario} 👋</h1>
<p style="font-size:1.05rem;opacity:.9;margin:0 0 4px;">Alguien te ha preparado algo especial.</p>
<p style="font-size:1.05rem;opacity:.9;margin:0;">{subtitulo}</p>
{boton}
<p style="font-size:.8rem;opacity:.55;margin-top:34px;">SorpresaBot · esta conversación es una
experiencia generada con IA</p>
</div>
</body></html>"""
