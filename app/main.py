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

from . import chat_en_vivo, storage
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
    # en vivo (Opción B). Si no lo es, sigue el flujo normal del comprador.
    respuestas = chat_en_vivo.manejar_mensaje(remitente, texto)
    if respuestas is None:
        respuestas = handle_message(remitente, texto)

    for r in respuestas:
        send_text(remitente, r)

    return {"status": "ok"}


@app.get("/")
def salud():
    return {"status": "SorpresaBot activo"}


@app.get("/r/{codigo}", response_class=HTMLResponse)
def pagina_regalo(codigo: str):
    """Landing de revelación: la abre el DESTINATARIO antes de escribir por WhatsApp."""
    encargo = storage.obtener_encargo(codigo)
    if encargo is None:
        return HTMLResponse(_html_no_encontrado(), status_code=404)

    persona = persona_por_id(encargo.persona_id)
    numero = _limpia(os.getenv("WHATSAPP_NUMERO_PUBLICO"))
    wa_link = f"https://wa.me/{numero}?text={encargo.codigo}" if numero else None

    return HTMLResponse(_html_regalo(encargo, persona, wa_link))


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


def _html_regalo(encargo, persona: dict | None, wa_link: str | None) -> str:
    nombre_persona = persona["nombre"] if persona else "tu personaje sorpresa"
    emoji = persona.get("emoji", "🎁") if persona else "🎁"
    destinatario = encargo.destinatario

    if wa_link:
        boton = f"""<a href="{wa_link}"
            style="display:inline-block;margin-top:28px;background:#25D366;color:#0b1a12;
            font-weight:700;font-size:1.05rem;padding:16px 30px;border-radius:999px;
            text-decoration:none;box-shadow:0 8px 24px rgba(37,211,102,.35);">
            💬 Habla con {nombre_persona}</a>"""
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
<p style="font-size:1.05rem;opacity:.9;margin:0;"><strong>{nombre_persona}</strong> te está esperando
para hablar contigo en persona, en vivo, por WhatsApp.</p>
{boton}
<p style="font-size:.8rem;opacity:.55;margin-top:34px;">SorpresaBot · esta conversación es una
experiencia generada con IA</p>
</div>
</body></html>"""
