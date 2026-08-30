"""
Capa de generación de contenido.

Soporta tres modos, elegidos automáticamente según lo que haya configurado
en las variables de entorno (ver .env.example):

- ANTHROPIC_API_KEY definida  -> usa Claude (Anthropic)
- GEMINI_API_KEY definida     -> usa Gemini (Google)
- ninguna de las dos          -> modo MOCK, genera una respuesta de plantilla
                                 sin llamar a ninguna API. Así se puede probar
                                 todo el flujo de conversación sin gastar ni
                                 configurar nada.

Esta capa es intencionadamente independiente del resto del código: cambiar
de proveedor de IA no debería tocar ni la lógica de conversación ni la de
WhatsApp.
"""

import os


def _modo_activo() -> str:
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.getenv("GEMINI_API_KEY"):
        return "gemini"
    return "mock"


def generar_contenido(system_prompt: str, instrucciones_formato: str, detalles: dict) -> str:
    """
    detalles esperado: {
        "destinatario": str,
        "ocasion": str,
        "anecdota": str,
        "tono": str (opcional),
    }
    """
    prompt_usuario = (
        f"Ocasión: {detalles.get('ocasion')}\n"
        f"Destinatario: {detalles.get('destinatario')}\n"
        f"Anécdota / detalles que ha dado quien encarga el mensaje: {detalles.get('anecdota')}\n"
        f"Tono deseado (si se indicó): {detalles.get('tono') or 'el tuyo propio, el del personaje'}\n\n"
        f"{instrucciones_formato}\n"
        "Dirígete directamente al destinatario, usa su nombre si lo tienes, "
        "y no incluyas explicaciones fuera del propio mensaje (no digas 'aquí tienes tu mensaje', "
        "escribe directamente el contenido)."
    )

    modo = _modo_activo()

    if modo == "anthropic":
        return _generar_anthropic(system_prompt, prompt_usuario)
    if modo == "gemini":
        return _generar_gemini(system_prompt, prompt_usuario)
    return _generar_mock(system_prompt, detalles, instrucciones_formato)


def _generar_anthropic(system_prompt: str, prompt_usuario: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    modelo = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
    resp = client.messages.create(
        model=modelo,
        max_tokens=500,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt_usuario}],
    )
    return "".join(block.text for block in resp.content if block.type == "text").strip()


def _generar_gemini(system_prompt: str, prompt_usuario: str) -> str:
    import google.generativeai as genai

    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    modelo_nombre = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    modelo = genai.GenerativeModel(modelo_nombre, system_instruction=system_prompt)
    resp = modelo.generate_content(prompt_usuario)
    return resp.text.strip()


def _generar_mock(system_prompt: str, detalles: dict, instrucciones_formato: str) -> str:
    """
    Respuesta de plantilla, sin llamar a ninguna API, para poder probar todo
    el flujo (intake, catálogo, entrega) sin credenciales.
    """
    destinatario = detalles.get("destinatario") or "amigo/a"
    ocasion = (detalles.get("ocasion") or "esta ocasión").lower()
    anecdota = detalles.get("anecdota") or ""
    extra = f" Recordando esto que nos has contado: «{anecdota}»." if anecdota else ""
    return (
        f"[CONTENIDO DE EJEMPLO — MOCK, sin API de IA configurada]\n"
        f"¡Querido/a {destinatario}! Hoy es un día especial ({ocasion}) y quería que lo supieras: "
        f"te deseo toda la suerte y la alegría del mundo.{extra} "
        f"Que este momento se quede grabado con una sonrisa. Un abrazo enorme.\n"
        f"(Configura ANTHROPIC_API_KEY o GEMINI_API_KEY en .env para que esto lo genere "
        f"de verdad la IA en el tono del personaje elegido.)"
    )
