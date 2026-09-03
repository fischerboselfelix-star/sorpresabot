"""
Páginas HTML "de escaparate": la landing pública (GET /) y el panel de
métricas (GET /metricas). Separadas de las páginas de regalo/pago que ya
vivían en app/main.py porque tienen un propósito distinto — promoción y
seguimiento, no la propia experiencia del regalo.
"""

from .personas import FORMATOS, PERSONAS

_FUENTE = "-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif"


def html_landing(wa_link: str | None) -> str:
    precio_min = min(p["precio_base"] for p in PERSONAS.values())

    tarjetas_personajes = "".join(
        f"""<div style="background:rgba(255,255,255,.06);border-radius:16px;padding:20px;text-align:center;">
            <div style="font-size:2.2rem;">{p['emoji']}</div>
            <div style="font-weight:700;margin-top:8px;">{p['nombre']}</div>
            <div style="opacity:.7;font-size:.85rem;margin-top:2px;">desde {p['precio_base']:.2f} €</div>
        </div>"""
        for p in PERSONAS.values()
    )

    tarjetas_formatos = "".join(
        f"""<div style="background:rgba(255,255,255,.06);border-radius:16px;padding:20px;">
            <div style="font-weight:700;">{f['nombre']}</div>
            <div style="opacity:.7;font-size:.85rem;margin-top:4px;">
                {"incluido en el precio base" if not f["precio_extra"] else f"+{f['precio_extra']:.2f} €"}
            </div>
        </div>"""
        for f in FORMATOS.values()
    )

    if wa_link:
        boton = f"""<a href="{wa_link}"
            style="display:inline-block;background:#25D366;color:#0b1a12;font-weight:700;
            font-size:1.05rem;padding:16px 34px;border-radius:999px;text-decoration:none;
            box-shadow:0 8px 24px rgba(37,211,102,.35);">💬 Empezar en WhatsApp</a>"""
    else:
        boton = """<p style="opacity:.75;">(Falta configurar el número de WhatsApp para este botón.)</p>"""

    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SorpresaBot — regalos personalizados con IA por WhatsApp</title>
<meta name="description" content="Crea un mensaje, una conversación en vivo o una búsqueda del tesoro personalizada para alguien especial, generada con IA y entregada por WhatsApp. Desde {precio_min:.2f} €.">
</head>
<body style="margin:0;font-family:{_FUENTE};background:#1a1a2e;color:#fff;">

<section style="padding:64px 24px 48px;text-align:center;
background:radial-gradient(circle at 50% 0%, #3b2f6b 0%, #1a1a2e 65%);">
  <div style="font-size:3.5rem;">🎁</div>
  <h1 style="font-size:2rem;margin:14px 0 10px;">Sorprende a alguien con un regalo que de verdad recordará</h1>
  <p style="opacity:.85;font-size:1.05rem;max-width:480px;margin:0 auto 28px;">
    Mensajes, conversaciones en vivo y búsquedas del tesoro personalizadas con IA,
    en el papel de un personaje — y entregadas directamente por WhatsApp.
  </p>
  {boton}
  <p style="opacity:.5;font-size:.8rem;margin-top:18px;">Desde {precio_min:.2f} € · pago seguro con tarjeta</p>
</section>

<section style="padding:48px 24px;max-width:720px;margin:0 auto;">
  <h2 style="text-align:center;font-size:1.3rem;margin-bottom:28px;">Cómo funciona</h2>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;">
    <div style="text-align:center;">
      <div style="font-size:1.8rem;">1️⃣</div>
      <p style="opacity:.85;font-size:.9rem;">Escríbele al bot por WhatsApp y elige personaje y formato</p>
    </div>
    <div style="text-align:center;">
      <div style="font-size:1.8rem;">2️⃣</div>
      <p style="opacity:.85;font-size:.9rem;">Cuéntale la ocasión y un detalle sobre esa persona</p>
    </div>
    <div style="text-align:center;">
      <div style="font-size:1.8rem;">3️⃣</div>
      <p style="opacity:.85;font-size:.9rem;">Paga con tarjeta y recibe el regalo listo para compartir</p>
    </div>
  </div>
</section>

<section style="padding:24px;max-width:720px;margin:0 auto;">
  <h2 style="text-align:center;font-size:1.3rem;margin-bottom:20px;">Elige un personaje</h2>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:14px;">
    {tarjetas_personajes}
  </div>
</section>

<section style="padding:24px;max-width:720px;margin:0 auto 48px;">
  <h2 style="text-align:center;font-size:1.3rem;margin-bottom:20px;">Tres formas de sorprender</h2>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;">
    {tarjetas_formatos}
  </div>
</section>

<section style="text-align:center;padding:0 24px 64px;">
  {boton}
  <p style="opacity:.4;font-size:.75rem;margin-top:32px;">SorpresaBot · contenido generado con IA ·
  pagos procesados de forma segura con Stripe</p>
</section>

</body></html>"""


def html_metricas(resumen: dict) -> str:
    filas_por_tipo = "".join(
        f"""<tr>
            <td style="padding:8px 12px;border-bottom:1px solid rgba(255,255,255,.1);">{tipo}</td>
            <td style="padding:8px 12px;border-bottom:1px solid rgba(255,255,255,.1);text-align:right;">{datos['pedidos']}</td>
            <td style="padding:8px 12px;border-bottom:1px solid rgba(255,255,255,.1);text-align:right;">{datos['ingresos']:.2f} €</td>
        </tr>"""
        for tipo, datos in resumen["por_tipo"].items()
    ) or """<tr><td colspan="3" style="padding:12px;opacity:.6;">Todavía no hay pedidos pagados.</td></tr>"""

    filas_eventos = "".join(
        f"""<tr>
            <td style="padding:6px 12px;border-bottom:1px solid rgba(255,255,255,.08);font-size:.8rem;opacity:.7;">
                {e.en.strftime('%d/%m %H:%M')}</td>
            <td style="padding:6px 12px;border-bottom:1px solid rgba(255,255,255,.08);font-size:.85rem;">{e.tipo}</td>
            <td style="padding:6px 12px;border-bottom:1px solid rgba(255,255,255,.08);font-size:.8rem;opacity:.7;">
                {e.tipo_pedido or '—'}</td>
            <td style="padding:6px 12px;border-bottom:1px solid rgba(255,255,255,.08);font-size:.8rem;text-align:right;">
                {f'{e.precio:.2f} €' if e.precio else '—'}</td>
        </tr>"""
        for e in resumen["ultimos_eventos"]
    ) or """<tr><td colspan="4" style="padding:12px;opacity:.6;">Sin eventos todavía.</td></tr>"""

    def _tarjeta(etiqueta: str, valor: str) -> str:
        return f"""<div style="background:rgba(255,255,255,.06);border-radius:14px;padding:18px;text-align:center;">
            <div style="font-size:1.6rem;font-weight:700;">{valor}</div>
            <div style="opacity:.65;font-size:.8rem;margin-top:4px;">{etiqueta}</div>
        </div>"""

    tarjetas = "".join([
        _tarjeta("Escribieron 'hola'", str(resumen["holas"])),
        _tarjeta("Llegaron a pagar (pedido creado)", str(resumen["pedidos_creados"])),
        _tarjeta("Pagaron", str(resumen["pedidos_pagados"])),
        _tarjeta("Ingresos totales", f"{resumen['ingresos_totales']:.2f} €"),
        _tarjeta("Conversión hola → pedido", f"{resumen['tasa_hola_a_pedido']:.0f} %"),
        _tarjeta("Conversión pedido → pago", f"{resumen['tasa_pedido_a_pago']:.0f} %"),
        _tarjeta("Conversión hola → pago", f"{resumen['tasa_hola_a_pago']:.0f} %"),
    ])

    origen_directo = resumen["por_origen"]["directo"]
    origen_viral = resumen["por_origen"]["viral"]

    def _fila_origen(etiqueta: str, datos: dict) -> str:
        return f"""<tr>
            <td style="padding:8px 12px;border-bottom:1px solid rgba(255,255,255,.1);">{etiqueta}</td>
            <td style="padding:8px 12px;border-bottom:1px solid rgba(255,255,255,.1);text-align:right;">{datos['holas']}</td>
            <td style="padding:8px 12px;border-bottom:1px solid rgba(255,255,255,.1);text-align:right;">{datos['pedidos_creados']}</td>
            <td style="padding:8px 12px;border-bottom:1px solid rgba(255,255,255,.1);text-align:right;">{datos['pedidos_pagados']}</td>
            <td style="padding:8px 12px;border-bottom:1px solid rgba(255,255,255,.1);text-align:right;">{datos['ingresos']:.2f} €</td>
        </tr>"""

    filas_origen = _fila_origen("Directo (link normal)", origen_directo) + _fila_origen(
        "Bucle viral (código REGALO10)", origen_viral
    )

    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SorpresaBot — métricas</title></head>
<body style="margin:0;font-family:{_FUENTE};background:#1a1a2e;color:#fff;padding:32px 20px 60px;">
<div style="max-width:760px;margin:0 auto;">
<h1 style="font-size:1.4rem;">Métricas del embudo</h1>
<p style="opacity:.6;font-size:.85rem;margin-top:-8px;">
  En memoria — se reinician con cada despliegue. Refresca la página para ver datos nuevos.</p>

<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:24px 0 36px;">
  {tarjetas}
</div>

<h2 style="font-size:1.05rem;margin-bottom:10px;">Directo vs. bucle viral</h2>
<table style="width:100%;border-collapse:collapse;margin-bottom:36px;">
<thead><tr>
  <th style="text-align:left;padding:8px 12px;opacity:.6;font-size:.8rem;">Origen</th>
  <th style="text-align:right;padding:8px 12px;opacity:.6;font-size:.8rem;">Holas</th>
  <th style="text-align:right;padding:8px 12px;opacity:.6;font-size:.8rem;">Pedidos creados</th>
  <th style="text-align:right;padding:8px 12px;opacity:.6;font-size:.8rem;">Pagados</th>
  <th style="text-align:right;padding:8px 12px;opacity:.6;font-size:.8rem;">Ingresos</th>
</tr></thead>
<tbody>{filas_origen}</tbody>
</table>

<h2 style="font-size:1.05rem;margin-bottom:10px;">Ingresos por tipo de producto</h2>
<table style="width:100%;border-collapse:collapse;margin-bottom:36px;">
<thead><tr>
  <th style="text-align:left;padding:8px 12px;opacity:.6;font-size:.8rem;">Tipo</th>
  <th style="text-align:right;padding:8px 12px;opacity:.6;font-size:.8rem;">Pedidos pagados</th>
  <th style="text-align:right;padding:8px 12px;opacity:.6;font-size:.8rem;">Ingresos</th>
</tr></thead>
<tbody>{filas_por_tipo}</tbody>
</table>

<h2 style="font-size:1.05rem;margin-bottom:10px;">Últimos eventos</h2>
<table style="width:100%;border-collapse:collapse;">
<thead><tr>
  <th style="text-align:left;padding:6px 12px;opacity:.6;font-size:.75rem;">Cuándo</th>
  <th style="text-align:left;padding:6px 12px;opacity:.6;font-size:.75rem;">Evento</th>
  <th style="text-align:left;padding:6px 12px;opacity:.6;font-size:.75rem;">Producto</th>
  <th style="text-align:right;padding:6px 12px;opacity:.6;font-size:.75rem;">Precio</th>
</tr></thead>
<tbody>{filas_eventos}</tbody>
</table>
</div>
</body></html>"""
