#!/usr/bin/env python3
"""
Simulador de conversación por consola — para probar el prototipo SIN una
cuenta de Meta Business ni claves de API (usa el modo MOCK de app/llm.py
si no hay ANTHROPIC_API_KEY ni GEMINI_API_KEY configuradas).

Uso:
    python test_local.py
"""

from app.conversation import handle_message

USER_ID = "cli-user"


def main():
    print("=== Simulador local de SorpresaBot ===")
    print("Escribe como si fueras el cliente por WhatsApp. Ctrl+C para salir.\n")

    respuestas = handle_message(USER_ID, "hola")
    for r in respuestas:
        print(f"🤖 {r}\n")

    while True:
        try:
            texto = input("🧑 Tú: ")
        except (EOFError, KeyboardInterrupt):
            print("\nHasta luego 👋")
            break
        respuestas = handle_message(USER_ID, texto)
        for r in respuestas:
            print(f"\n🤖 {r}\n")


if __name__ == "__main__":
    main()
