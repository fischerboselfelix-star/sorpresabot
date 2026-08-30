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

from . import storage
from .conversation import handle_message
from .whatsapp import send_text

VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "cambia-esto")


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

    respuestas = handle_message(remitente, texto)
    for r in respuestas:
        send_text(remitente, r)

    return {"status": "ok"}


@app.get("/")
def salud():
    return {"status": "SorpresaBot activo"}
