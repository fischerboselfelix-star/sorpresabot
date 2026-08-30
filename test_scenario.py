#!/usr/bin/env python3
"""
Prueba automática (no interactiva) de principio a fin: simula un pedido
completo y un pedido programado, y comprueba que el flujo llega a entregar
contenido. Sirve como verificación rápida tras tocar el código.

Uso:
    python test_scenario.py
"""

from app import storage
from app.conversation import handle_message

FALLOS = []


def check(cond, mensaje):
    estado = "OK " if cond else "FALLO"
    print(f"[{estado}] {mensaje}")
    if not cond:
        FALLOS.append(mensaje)


def escenario_pedido_inmediato():
    user = "escenario-1"
    storage.reset_session(user)

    r = handle_message(user, "hola")
    check("Elige un personaje" in r[0] or "personaje" in r[1].lower(), "Saludo inicial muestra catálogo de personajes")

    r = handle_message(user, "1")  # Tarotista Luna
    check("formato" in r[1].lower(), "Tras elegir personaje se pide formato")

    r = handle_message(user, "1")  # texto
    check("ocasión" in r[0].lower(), "Tras elegir formato se pide ocasión")

    r = handle_message(user, "1")  # Cumpleaños
    check("llama" in r[0].lower(), "Tras elegir ocasión se pide nombre del destinatario")

    r = handle_message(user, "Marta")
    check("Marta" in r[0], "El nombre del destinatario se recoge correctamente")

    r = handle_message(user, "le encanta el senderismo")
    check("cuándo" in r[0].lower() or "listo" in r[0].lower(), "Tras detalles se pregunta por la fecha de entrega")

    r = handle_message(user, "ahora")
    check(any("precio del pedido" in x.lower() for x in r), "Se genera contenido y se muestra el precio")
    check(len(r) >= 2 and len(r[1]) > 0, "El contenido generado no está vacío")

    r = handle_message(user, "si")
    check(any("reenvía" in x.lower() for x in r), "La entrega inmediata devuelve el contenido para reenviar (Opción A)")

    sesion = storage.get_session(user)
    check(sesion["estado"] == "INICIO", "La sesión se reinicia tras completar el pedido")


def escenario_pedido_programado():
    user = "escenario-2"
    storage.reset_session(user)

    handle_message(user, "hola")
    handle_message(user, "2")  # Santa Claus
    handle_message(user, "1")  # texto
    handle_message(user, "5")  # Sin motivo especial
    handle_message(user, "Pablo")
    handle_message(user, "ninguno")
    r = handle_message(user, "24/12/2026 20:00")
    check(any("precio del pedido" in x.lower() for x in r), "Pedido programado también genera contenido antes de confirmar")

    r = handle_message(user, "si")
    check(any("recordaré" in x.lower() for x in r), "La confirmación con fecha futura programa un recordatorio en vez de entregar ya")

    pendientes = storage.entregas_pendientes(ahora=None)
    programadas = [e for e in storage.ENTREGAS_PROGRAMADAS if e.user_id == user]
    check(len(programadas) == 1, "La entrega programada queda guardada en storage")
    check(programadas[0].destinatario == "Pablo", "La entrega programada guarda el destinatario correcto")


def escenario_regenerar_y_reiniciar():
    user = "escenario-3"
    storage.reset_session(user)
    handle_message(user, "hola")
    handle_message(user, "3")  # Cómico local
    handle_message(user, "1")  # único formato disponible
    handle_message(user, "3")  # Nuevo trabajo
    handle_message(user, "Sara")
    handle_message(user, "ninguno")
    r1 = handle_message(user, "ahora")
    contenido_1 = r1[1]

    r2 = handle_message(user, "no")  # pedir otra versión
    check(len(r2) >= 1, "Regenerar devuelve una nueva propuesta")

    r3 = handle_message(user, "reiniciar")
    check("personaje" in r3[1].lower(), "'reiniciar' vuelve al catálogo de personajes en cualquier punto")


if __name__ == "__main__":
    escenario_pedido_inmediato()
    print()
    escenario_pedido_programado()
    print()
    escenario_regenerar_y_reiniciar()

    print("\n=== RESUMEN ===")
    if FALLOS:
        print(f"{len(FALLOS)} comprobación(es) fallida(s):")
        for f in FALLOS:
            print(f" - {f}")
        raise SystemExit(1)
    else:
        print("Todas las comprobaciones han pasado ✅")
