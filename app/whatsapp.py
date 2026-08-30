"""
Envío de mensajes vía WhatsApp Cloud API (Meta Business Platform).

Si no hay credenciales configuradas (WHATSAPP_ACCESS_TOKEN /
WHATSAPP_PHONE_NUMBER_ID), en vez de fallar, se imprime en consola lo que
se habría enviado — así el prototipo se puede probar de principio a fin
sin tener aún una cuenta de Meta Business dada de alta.
"""

import os
import requests

GRAPH_API_VERSION = "v20.0"


def send_text(to: str, body: str) -> None:
    token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

    if not token or not phone_id:
        print(f"\n[WHATSAPP-SIMULADO -> {to}]\n{body}\n")
        return

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_id}/messages"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=15)
    if resp.status_code >= 300:
        print(f"[WHATSAPP-ERROR] {resp.status_code}: {resp.text}")
