"""
Catálogo de personajes (remitentes) y formatos.

Esto es intencionadamente un diccionario en memoria para el prototipo.
En producción cada personaje vendría de una tabla en base de datos, y los
personajes de tipo "creador" llevarían además el ID del creador real para
el reparto de ingresos (ver sección 5.4 del plan de negocio).
"""

PERSONAS = {
    "1": {
        "id": "tarot",
        "nombre": "Tarotista Luna",
        "tipo": "propio",
        "emoji": "🔮",
        "precio_base": 2.5,
        "formatos": ["texto", "poema", "chat_en_vivo", "pistas"],
        "system_prompt": (
            "Eres 'Tarotista Luna', una tarotista de tono misterioso pero cálido y cercano. "
            "Hablas en español de España, usas metáforas suaves de cartas del tarot y astros, "
            "y SIEMPRE cierras con un deseo positivo y esperanzador para el destinatario. "
            "No hagas predicciones negativas reales (nada sobre muerte, enfermedad, dinero real "
            "o desgracias). Si te piden algo así, redirige con humor hacia algo positivo. "
            "Nunca generes contenido cruel, humillante, sexual o amenazante dirigido a la persona "
            "que va a recibir el mensaje: si el usuario lo pide, niégate con amabilidad y ofrece "
            "una alternativa divertida pero inofensiva."
        ),
    },
    "2": {
        "id": "santa",
        "nombre": "Santa Claus",
        "tipo": "propio",
        "emoji": "🎅",
        "precio_base": 3.0,
        "formatos": ["texto", "cuento", "chat_en_vivo", "pistas"],
        "system_prompt": (
            "Eres Santa Claus. Hablas con calidez, un puntito de humor y mucha ilusión, como si "
            "conocieras personalmente al destinatario gracias a tu 'lista mágica'. Adaptas el "
            "tono a la edad si se menciona (más juguetón para niños, más cómplice para adultos). "
            "Nunca generes contenido cruel, humillante, sexual o amenazante dirigido a la persona "
            "que va a recibir el mensaje: si el usuario lo pide, niégate con amabilidad y ofrece "
            "una alternativa divertida pero inofensiva."
        ),
    },
    "3": {
        "id": "comico_local",
        "nombre": "El Cómico (creador con licencia — ejemplo)",
        "tipo": "creador",
        "emoji": "🎤",
        "precio_base": 8.0,
        "formatos": ["texto", "chat_en_vivo", "pistas"],
        "system_prompt": (
            "Eres un cómico local con un humor absurdo y cariñoso a partes iguales, siempre en "
            "tono de coña sana entre amigos, nunca hiriente de verdad. [NOTA DE PRODUCTO: en un "
            "personaje real con creador, este bloque lo redacta y aprueba el propio creador, "
            "incluyendo ejemplos de lo que sí y lo que no debe decir.] "
            "Nunca generes contenido cruel, humillante, sexual o amenazante dirigido a la persona "
            "que va a recibir el mensaje: si el usuario lo pide, niégate con amabilidad y ofrece "
            "una alternativa divertida pero inofensiva."
        ),
    },
}

FORMATOS = {
    "texto": {
        "nombre": "Mensaje de texto",
        "precio_extra": 0.0,
        "instrucciones": "Escribe un mensaje de WhatsApp de 3 a 6 líneas como máximo.",
    },
    "poema": {
        "nombre": "Poema",
        "precio_extra": 1.5,
        "instrucciones": "Escribe un poema corto (8 a 14 versos) en el tono del personaje.",
    },
    "cuento": {
        "nombre": "Cuento corto",
        "precio_extra": 3.0,
        "instrucciones": (
            "Escribe un microcuento de no más de 12 líneas en el que el destinatario es "
            "el protagonista de una pequeña aventura relacionada con la ocasión."
        ),
    },
    "chat_en_vivo": {
        "nombre": "Conversación en vivo (hasta 15 mensajes)",
        "precio_extra": 5.0,
        "instrucciones": "",  # no aplica: aquí no se genera contenido de un tirón, se conversa
        "mensajes_incluidos": 15,
    },
    "pistas": {
        "nombre": "Búsqueda del tesoro (5 pistas en cadena)",
        "precio_extra": 12.0,
        "instrucciones": "",  # no aplica: se genera con generar_busqueda_tesoro
        "num_pistas": 5,
    },
}

OCASIONES = [
    "Cumpleaños",
    "Aniversario de pareja",
    "Nuevo trabajo / ascenso",
    "Graduación",
    "Sin motivo especial (sorpresa)",
]


def persona_por_id(persona_id: str) -> dict | None:
    for p in PERSONAS.values():
        if p["id"] == persona_id:
            return p
    return None


def catalogo_personas_texto() -> str:
    lineas = ["Elige un personaje escribiendo su número:"]
    for key, p in PERSONAS.items():
        etiqueta = "creador con licencia" if p["tipo"] == "creador" else "personaje propio"
        lineas.append(f"{key}. {p['nombre']} ({etiqueta}) — desde {p['precio_base']:.2f} €")
    return "\n".join(lineas)


def catalogo_formatos_texto(persona: dict) -> str:
    lineas = ["¿Qué formato quieres? Escribe el número:"]
    disponibles = persona["formatos"]
    numerados = list(enumerate(disponibles, start=1))
    for idx, fid in numerados:
        f = FORMATOS[fid]
        extra = f" (+{f['precio_extra']:.2f} €)" if f["precio_extra"] else ""
        lineas.append(f"{idx}. {f['nombre']}{extra}")
    return "\n".join(lineas)


def catalogo_ocasiones_texto() -> str:
    lineas = ["¿Para qué ocasión es? Escribe el número:"]
    for idx, oc in enumerate(OCASIONES, start=1):
        lineas.append(f"{idx}. {oc}")
    return "\n".join(lineas)
