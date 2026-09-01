"""
Búsqueda del tesoro: el DESTINATARIO va desbloqueando pistas encadenadas al
responder, hasta llegar al mensaje final ("tesoro"). Mismo patrón que
app/chat_en_vivo.py — es él/ella quien inicia el contacto (viene del link de
la landing de regalo), así que cumple igual con las políticas de WhatsApp
Business: este número nunca escribe primero a un desconocido.

app/main.py llama a manejar_mensaje(remitente, texto) tras comprobar que no
es un chat en vivo; si esto también devuelve None, sigue el flujo normal
del comprador.
"""

from . import storage
from .personas import persona_por_id


def manejar_mensaje(remitente: str, texto: str) -> list[str] | None:
    encargo_activo = storage.sesion_pistas_activa_para(remitente)
    if encargo_activo:
        return _avanzar(remitente, encargo_activo)

    encargo = storage.obtener_encargo_pistas_desde_texto(texto)
    if encargo:
        return _iniciar(remitente, encargo)

    return None


def _iniciar(remitente: str, encargo: storage.EncargoPistas) -> list[str]:
    persona = persona_por_id(encargo.persona_id)
    nombre = persona["nombre"] if persona else "tu personaje"
    total = len(encargo.pistas)

    if total == 0:
        return ["Uy, esta búsqueda del tesoro ha caducado 🙈 Pídele a quien te la envió que cree una nueva."]

    storage.vincular_sesion_pistas(remitente, encargo.codigo)
    return [
        f"🗝️ ¡Empieza la búsqueda del tesoro de {nombre}! Son {total} pistas — respóndeme lo que "
        "se te ocurra para cada una (no hace falta acertar del todo, lo importante es jugar) y así "
        "vamos avanzando juntos/as.",
        f"Pista 1 de {total}:",
        encargo.pistas[0],
    ]


def _avanzar(remitente: str, encargo: storage.EncargoPistas) -> list[str]:
    total = len(encargo.pistas)

    if encargo.completado or total == 0:
        storage.desvincular_sesion_pistas(remitente)
        return ["¡Ya habéis llegado al final de esta búsqueda del tesoro! 🏆✨"]

    reaccion = (
        encargo.reacciones[encargo.indice_actual]
        if encargo.indice_actual < len(encargo.reacciones)
        else "¡Muy bien! Sigamos:"
    )
    encargo.indice_actual += 1

    if encargo.indice_actual >= total:
        encargo.completado = True
        storage.desvincular_sesion_pistas(remitente)
        return [reaccion, "🏆 ¡Has llegado al final! Aquí tienes tu tesoro:", encargo.tesoro]

    return [
        reaccion,
        f"Pista {encargo.indice_actual + 1} de {total}:",
        encargo.pistas[encargo.indice_actual],
    ]
