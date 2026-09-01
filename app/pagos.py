"""
Cobro con Stripe.

Modo real (STRIPE_SECRET_KEY configurada): por cada pedido se crea una
Stripe Checkout Session con el precio calculado dinámicamente, y se
devuelve la URL para que el comprador pague con tarjeta. El contenido
(texto, chat en vivo o búsqueda del tesoro) NO se genera ni se entrega en
este punto — solo cuando llega el webhook "checkout.session.completed"
confirmando que el pago se ha completado de verdad (ver /webhook/stripe
en app/main.py y app/entregas.py).

Modo simulado (sin STRIPE_SECRET_KEY, para desarrollo/pruebas): no se crea
ninguna sesión real. iniciar_pago() devuelve None y quien la llama
interpreta eso como "no hay pasarela de pago configurada, entregar
directamente" — igual que app/llm.py cae a contenido de plantilla cuando
no hay clave de IA configurada. Así el prototipo se puede seguir probando
de principio a fin (test_scenario.py, pruebas locales) sin una cuenta de
Stripe.
"""

import json
import os


def _limpia(valor: str | None) -> str:
    """Quita espacios y saltos de línea accidentales, típico al copiar/pegar
    una clave en el panel de variables de Railway."""
    return (valor or "").strip()


def modo_activo() -> str:
    return "stripe" if _limpia(os.getenv("STRIPE_SECRET_KEY")) else "mock"


def _url_base() -> str:
    base = _limpia(os.getenv("PUBLIC_BASE_URL"))
    if base:
        return base.rstrip("/")
    dominio = _limpia(os.getenv("RAILWAY_PUBLIC_DOMAIN"))
    return f"https://{dominio}" if dominio else "http://localhost:8000"


def iniciar_pago(pedido_id: str, descripcion: str, precio_eur: float, user_id: str) -> str | None:
    """
    Devuelve la URL de pago de Stripe, o None si no hay Stripe configurado
    (modo simulado). Si Stripe SÍ está configurado pero la llamada a su API
    falla (clave mal copiada, cuenta con restricciones, corte de red...),
    deja que la excepción suba: quien llama a esto NO debe interpretar un
    fallo real como "modo simulado", porque eso entregaría el pedido gratis.
    """
    if modo_activo() != "stripe":
        return None

    import stripe

    stripe.api_key = _limpia(os.getenv("STRIPE_SECRET_KEY"))
    base = _url_base()

    session = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=[
            {
                "price_data": {
                    "currency": "eur",
                    "unit_amount": round(precio_eur * 100),
                    "product_data": {"name": descripcion},
                },
                "quantity": 1,
            }
        ],
        metadata={"pedido_id": pedido_id, "user_id": user_id},
        success_url=f"{base}/pago-ok?pedido={pedido_id}",
        cancel_url=f"{base}/pago-cancelado?pedido={pedido_id}",
    )
    return session.url


def verificar_firma_webhook(payload: bytes, sig_header: str):
    """
    Valida que el webhook viene de verdad de Stripe (comprobando la firma
    con STRIPE_WEBHOOK_SECRET) y devuelve el evento ya verificado. Si no hay
    STRIPE_WEBHOOK_SECRET configurado (por ejemplo, en pruebas locales antes
    de tener el endpoint dado de alta en el panel de Stripe), se procesa el
    JSON directamente sin verificar firma — NUNCA hacer esto en producción
    con dinero real sin haber configurado el secreto del webhook.
    """
    secreto = _limpia(os.getenv("STRIPE_WEBHOOK_SECRET"))
    if secreto:
        import stripe

        return stripe.Webhook.construct_event(payload, sig_header, secreto)
    return json.loads(payload)
