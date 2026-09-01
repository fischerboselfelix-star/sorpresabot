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
import re


def _limpia(valor: str | None) -> str:
    """Quita espacios y saltos de línea accidentales (típico al copiar/pegar
    una clave en el panel de variables de Railway u otros paneles)."""
    return (valor or "").strip()


def _modo_activo() -> str:
    if _limpia(os.getenv("ANTHROPIC_API_KEY")):
        return "anthropic"
    if _limpia(os.getenv("GEMINI_API_KEY")):
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

    try:
        if modo == "anthropic":
            return _generar_anthropic(system_prompt, prompt_usuario)
        if modo == "gemini":
            return _generar_gemini(system_prompt, prompt_usuario)
    except Exception as e:
        # Red de seguridad: si la API de IA falla (clave mal copiada, límite
        # de uso, corte de red...), el bot no debe quedarse mudo — cae al
        # contenido de plantilla y deja rastro del error en los logs.
        print(f"[LLM-ERROR] Fallo generando con {modo}: {e!r}. Usando modo mock.")

    return _generar_mock(system_prompt, detalles, instrucciones_formato)


def _generar_anthropic(system_prompt: str, prompt_usuario: str, max_tokens: int = 500) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=_limpia(os.environ["ANTHROPIC_API_KEY"]))
    modelo = _limpia(os.getenv("ANTHROPIC_MODEL")) or "claude-sonnet-4-5"
    resp = client.messages.create(
        model=modelo,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt_usuario}],
    )
    return "".join(block.text for block in resp.content if block.type == "text").strip()


def _generar_gemini(system_prompt: str, prompt_usuario: str, max_tokens: int | None = None) -> str:
    import google.generativeai as genai

    genai.configure(api_key=_limpia(os.environ["GEMINI_API_KEY"]))
    modelo_nombre = _limpia(os.getenv("GEMINI_MODEL")) or "gemini-2.0-flash"
    modelo = genai.GenerativeModel(modelo_nombre, system_instruction=system_prompt)
    config = {"max_output_tokens": max_tokens} if max_tokens else None
    resp = modelo.generate_content(prompt_usuario, generation_config=config)
    return resp.text.strip()


def generar_saludo_chat_vivo(system_prompt: str, detalles: dict) -> str:
    """
    Primer mensaje del personaje cuando el DESTINATARIO le escribe por
    primera vez (chat en vivo, Opción B). A diferencia de generar_contenido,
    esto abre una conversación, no cierra un encargo.
    """
    prompt_usuario = (
        f"Te acaba de escribir por primera vez {detalles.get('destinatario')}. "
        f"Preséntate en el papel de tu personaje y dirígete a él/ella por su nombre. "
        f"El motivo es: {detalles.get('ocasion')}. "
        + (
            f"Detalle o anécdota a tener en cuenta si encaja de forma natural: "
            f"«{detalles.get('anecdota')}». "
            if detalles.get("anecdota")
            else ""
        )
        + "Sé breve (2 a 4 líneas), cercano/a, y termina con algo que invite a seguir "
        "charlando. No digas que eres una inteligencia artificial ni menciones que "
        "alguien ha pagado por esto — para ti esta conversación es real."
    )

    modo = _modo_activo()
    try:
        if modo == "anthropic":
            return _generar_anthropic(system_prompt, prompt_usuario)
        if modo == "gemini":
            return _generar_gemini(system_prompt, prompt_usuario)
    except Exception as e:
        print(f"[LLM-ERROR] Fallo generando saludo de chat en vivo con {modo}: {e!r}. Usando modo mock.")

    destinatario = detalles.get("destinatario") or "amigo/a"
    return (
        f"[MOCK — sin API de IA configurada] ¡Hola, {destinatario}! Soy tu personaje "
        "especial, listo para charlar contigo 😊 (configura ANTHROPIC_API_KEY o "
        "GEMINI_API_KEY para que esto lo escriba de verdad la IA)."
    )


def generar_respuesta_chat_vivo(system_prompt: str, historial: list[dict], mensaje_nuevo: str) -> str:
    """
    Continúa una conversación ya empezada. `historial` es una lista de
    {"role": "user"|"assistant", "texto": str} en orden cronológico, sin
    incluir todavía `mensaje_nuevo`.
    """
    modo = _modo_activo()
    try:
        if modo == "anthropic":
            return _continuar_anthropic(system_prompt, historial, mensaje_nuevo)
        if modo == "gemini":
            return _continuar_gemini(system_prompt, historial, mensaje_nuevo)
    except Exception as e:
        print(f"[LLM-ERROR] Fallo continuando chat en vivo con {modo}: {e!r}. Usando modo mock.")

    return (
        "[MOCK — sin API de IA configurada] (Aquí tu personaje seguiría la conversación "
        "de verdad — configura ANTHROPIC_API_KEY o GEMINI_API_KEY para probarlo.)"
    )


def _continuar_anthropic(system_prompt: str, historial: list[dict], mensaje_nuevo: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=_limpia(os.environ["ANTHROPIC_API_KEY"]))
    modelo = _limpia(os.getenv("ANTHROPIC_MODEL")) or "claude-sonnet-4-5"
    mensajes = [{"role": h["role"], "content": h["texto"]} for h in historial]
    mensajes.append({"role": "user", "content": mensaje_nuevo})
    resp = client.messages.create(
        model=modelo,
        max_tokens=400,
        system=system_prompt,
        messages=mensajes,
    )
    return "".join(block.text for block in resp.content if block.type == "text").strip()


def _continuar_gemini(system_prompt: str, historial: list[dict], mensaje_nuevo: str) -> str:
    import google.generativeai as genai

    genai.configure(api_key=_limpia(os.environ["GEMINI_API_KEY"]))
    modelo_nombre = _limpia(os.getenv("GEMINI_MODEL")) or "gemini-2.0-flash"
    modelo = genai.GenerativeModel(modelo_nombre, system_instruction=system_prompt)
    historial_gemini = [
        {"role": ("model" if h["role"] == "assistant" else "user"), "parts": [h["texto"]]}
        for h in historial
    ]
    chat = modelo.start_chat(history=historial_gemini)
    resp = chat.send_message(mensaje_nuevo)
    return resp.text.strip()


def generar_busqueda_tesoro(system_prompt: str, detalles: dict, num_pistas: int = 5) -> dict:
    """
    Genera de un tirón el esqueleto de una búsqueda del tesoro: num_pistas
    pistas encadenadas y un mensaje final ("tesoro") de cierre. Las
    reacciones a cada respuesta del destinatario NO se generan aquí — se
    generan en vivo, una a una, con generar_reaccion_pista, para que
    reaccionen a lo que la persona ha escrito de verdad en vez de ser un
    "¡genial, siguiente!" genérico. Devuelve {"pistas": [...], "tesoro": "..."}.
    """
    tema = detalles.get("tema") or detalles.get("anecdota") or "sorpréndeme, tú eliges el hilo"
    prompt_usuario = (
        f"Vas a preparar una búsqueda del tesoro en forma de pistas encadenadas para "
        f"{detalles.get('destinatario')}, por motivo de: {detalles.get('ocasion')}. "
        f"Tema o contexto que te ha dado quien encarga esto: «{tema}». "
        f"Escribe exactamente {num_pistas} pistas, cada una un acertijo o adivinanza corta "
        "(2 a 4 líneas) en tu papel de personaje, encadenadas por el tema, con un poco más de "
        "intriga cada vez. No hace falta que tengan una única solución objetiva: son para generar "
        "diversión y curiosidad, no para resolverse con precisión matemática. Termina con un "
        "TESORO: un mensaje final especial, cálido y memorable (4 a 8 líneas), como cierre de "
        "toda la experiencia, en tu papel de personaje. Responde EXACTAMENTE en este formato, "
        "una línea por cada elemento, sin nada más antes ni después:\n"
        + "\n".join(f"PISTA {i + 1}: <texto>" for i in range(num_pistas))
        + "\nTESORO: <texto>"
    )

    modo = _modo_activo()
    texto = None
    try:
        if modo == "anthropic":
            texto = _generar_anthropic(system_prompt, prompt_usuario, max_tokens=1500)
        elif modo == "gemini":
            texto = _generar_gemini(system_prompt, prompt_usuario, max_tokens=1500)
    except Exception as e:
        print(f"[LLM-ERROR] Fallo generando búsqueda del tesoro con {modo}: {e!r}. Usando modo mock.")

    if texto:
        parseado = _parsear_busqueda_tesoro(texto, num_pistas)
        if parseado:
            return parseado
        print(
            "[LLM-ERROR] No se pudo interpretar el formato de la búsqueda del tesoro generada. "
            f"Usando modo mock. Texto crudo recibido:\n{texto[:1500]}"
        )

    return _busqueda_tesoro_mock(detalles, num_pistas)


def _parsear_busqueda_tesoro(texto: str, num_pistas: int) -> dict | None:
    """
    Tolerante a variaciones típicas del modelo: markdown alrededor de las
    etiquetas (**PISTA 1:**), mayúsculas/minúsculas, preámbulo antes de la
    primera etiqueta... Solo falla (None) si de verdad faltan piezas.
    """
    # Ancladas a principio de línea (tras markdown/espacios) para no confundir
    # una mención de pasada a "el tesoro" en una frase con la etiqueta real.
    inicio = r"(?:^|\n)[ \t]*[*_#]*[ \t]*"
    etiqueta_pista = inicio + r"PISTA\s*(\d+)[.:]?[*_#\s]*"
    etiqueta_tesoro = inicio + r"TESORO[.:]?[*_#\s]*"
    limite_interno = r"PISTA\s*\d+|TESORO"
    limite = rf"(?={inicio}(?:{limite_interno})|\Z)"

    def _limpiar(s: str) -> str:
        return s.strip(" \n\t*_-")

    pistas_por_numero: dict[int, str] = {}
    for m in re.finditer(rf"{etiqueta_pista}(.+?){limite}", texto, re.S | re.I):
        pistas_por_numero[int(m.group(1))] = _limpiar(m.group(2))

    tesoro = ""
    for m in re.finditer(rf"{etiqueta_tesoro}(.+?){limite}", texto, re.S | re.I):
        tesoro = _limpiar(m.group(1))  # se queda con la última ocurrencia, por si acaso

    pistas = [pistas_por_numero.get(i, "") for i in range(1, num_pistas + 1)]
    if not tesoro or any(not p for p in pistas):
        return None

    return {"pistas": pistas, "tesoro": tesoro}


def _busqueda_tesoro_mock(detalles: dict, num_pistas: int) -> dict:
    destinatario = detalles.get("destinatario") or "amigo/a"
    tema = detalles.get("tema") or detalles.get("anecdota") or "un recuerdo especial"
    pistas = [
        f"[MOCK — sin API de IA configurada] Pista {i + 1} para {destinatario}, sobre «{tema}»..."
        for i in range(num_pistas)
    ]
    tesoro = (
        f"[MOCK — sin API de IA configurada] ¡Enhorabuena, {destinatario}! Has llegado al final "
        "del tesoro. 🎉 (Configura ANTHROPIC_API_KEY o GEMINI_API_KEY para que esto lo escriba "
        "de verdad la IA.)"
    )
    return {"pistas": pistas, "tesoro": tesoro}


def generar_reaccion_pista(system_prompt: str, detalles: dict) -> str:
    """
    Reacción EN VIVO a lo que el destinatario acaba de responder a una
    pista concreta — para que se sienta escuchado/a de verdad en vez de un
    "¡genial, siguiente!" repetido siempre igual. No juzga si acertó o no
    (las pistas no tienen una única solución "correcta"): solo comenta algo
    concreto de lo que dijo y anima a seguir.
    """
    prompt_usuario = (
        f"Le acabas de dar esta pista a {detalles.get('destinatario')}: «{detalles.get('pista')}». "
        f"Te ha respondido: «{detalles.get('respuesta')}». Reacciona en una sola frase corta "
        "(6 a 15 palabras), en tu papel de personaje, mencionando algo concreto de lo que ha "
        "dicho — no hace falta juzgar si ha acertado o no, el objetivo es que se sienta "
        "escuchado/a y con ganas de seguir jugando. No repitas ni reveles la siguiente pista, "
        "solo la reacción."
    )

    modo = _modo_activo()
    try:
        if modo == "anthropic":
            return _generar_anthropic(system_prompt, prompt_usuario, max_tokens=120)
        if modo == "gemini":
            return _generar_gemini(system_prompt, prompt_usuario, max_tokens=120)
    except Exception as e:
        print(f"[LLM-ERROR] Fallo generando reacción a pista con {modo}: {e!r}. Usando reacción genérica.")

    return "¡Muy bien! Sigamos, aquí tienes la siguiente pista:"


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
