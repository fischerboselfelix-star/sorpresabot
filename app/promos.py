"""
Bucle viral: al terminar una experiencia (chat en vivo o búsqueda del
tesoro), se invita al DESTINATARIO a crear la suya propia con un código de
descuento — así cada entrega es también un canal de adquisición gratis, sin
gastar en publicidad.

Deliberadamente simple: un diccionario en memoria con un único código fijo,
no un sistema de cupones con base de datos. Si esto funciona y se quiere
tener varios códigos, caducidad, límite de usos, etc., el siguiente paso
sería mover esto a una tabla de verdad.
"""

import os

CODIGO_VIRAL = "REGALO10"

PROMOS: dict[str, dict] = {
    CODIGO_VIRAL: {"descuento_pct": 10, "origen": "viral"},
}


def obtener_promo(texto: str) -> dict | None:
    return PROMOS.get((texto or "").strip().upper())


def aplicar_descuento(precio: float, promo: dict | None) -> float:
    if not promo:
        return precio
    return round(precio * (1 - promo["descuento_pct"] / 100), 2)


def link_invitacion_viral() -> str | None:
    """
    Link que se manda al DESTINATARIO al terminar su experiencia, invitándole
    a crear la suya propia. Usa el mismo WHATSAPP_NUMERO_PUBLICO que ya se
    usa para el resto de links de wa.me (ver app/main.py y app/entregas.py).
    """
    numero = (os.getenv("WHATSAPP_NUMERO_PUBLICO") or "").strip()
    if not numero:
        return None
    return f"https://wa.me/{numero}?text={CODIGO_VIRAL}"


def mensaje_invitacion_viral() -> str:
    link = link_invitacion_viral()
    descuento = PROMOS[CODIGO_VIRAL]["descuento_pct"]
    if link:
        return (
            f"¿Te ha gustado? 💌 Crea tú también una sorpresa así para alguien especial, "
            f"con un {descuento}% de descuento:\n{link}"
        )
    return (
        f"¿Te ha gustado? 💌 Si quieres regalar tú también una experiencia así, "
        "escríbenos a este mismo número."
    )
