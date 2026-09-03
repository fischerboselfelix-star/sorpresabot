"""
Cálculo del embudo (hola -> pedido creado -> pedido pagado) a partir de
storage.EVENTOS. Separado de app/main.py para poder probarlo sin FastAPI
(ver test_scenario.py y cualquier prueba ad-hoc).

storage.EVENTOS es en memoria, así que estas cifras se reinician cada vez
que se reinicia el servidor (igual que el resto del prototipo) — es
suficiente para ver conversión y decidir dónde invertir en promoción, pero
no sustituye a una analítica persistente si esto crece.
"""

from collections import defaultdict

from . import storage


def resumen_embudo(eventos: list["storage.Evento"]) -> dict:
    holas = [e for e in eventos if e.tipo == "hola"]
    creados = [e for e in eventos if e.tipo == "pedido_creado"]
    pagados = [e for e in eventos if e.tipo == "pedido_pagado"]

    usuarios_hola = {e.user_id for e in holas}
    usuarios_pagados = {e.user_id for e in pagados}

    ingresos_totales = sum(e.precio for e in pagados)

    por_tipo: dict[str, dict] = defaultdict(lambda: {"pedidos": 0, "ingresos": 0.0})
    for e in pagados:
        d = por_tipo[e.tipo_pedido or "otro"]
        d["pedidos"] += 1
        d["ingresos"] += e.precio

    def _tasa(numerador: int, denominador: int) -> float:
        return (numerador / denominador * 100) if denominador else 0.0

    def _segmento(origen: str) -> dict:
        h = [e for e in holas if e.origen == origen]
        c = [e for e in creados if e.origen == origen]
        p = [e for e in pagados if e.origen == origen]
        return {
            "holas": len(h),
            "pedidos_creados": len(c),
            "pedidos_pagados": len(p),
            "ingresos": sum(e.precio for e in p),
        }

    return {
        "holas": len(holas),
        "usuarios_unicos_hola": len(usuarios_hola),
        "pedidos_creados": len(creados),
        "pedidos_pagados": len(pagados),
        "usuarios_unicos_pagados": len(usuarios_pagados),
        "ingresos_totales": ingresos_totales,
        "tasa_hola_a_pedido": _tasa(len(creados), len(holas)),
        "tasa_pedido_a_pago": _tasa(len(pagados), len(creados)),
        "tasa_hola_a_pago": _tasa(len(pagados), len(holas)),
        "por_tipo": dict(por_tipo),
        "por_origen": {
            "directo": _segmento("directo"),
            "viral": _segmento("viral"),
        },
        "ultimos_eventos": sorted(eventos, key=lambda e: e.en, reverse=True)[:30],
    }
