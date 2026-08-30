# SorpresaBot — Prototipo

Bot de WhatsApp (Meta Business Platform / WhatsApp Cloud API) que conversa
con la IA (Claude o Gemini) para armar mensajes, poemas o cuentos
personalizados según un catálogo de "personajes" y formatos.

Este código acompaña al documento `SorpresaBot_Plan_de_Negocio.docx`. Antes
de leer el código, conviene tener claro un punto del plan (sección 4): el
bot **solo conversa con quien le escribe primero** (el comprador). Nunca
manda un mensaje en frío a un tercero desconocido — eso es justo lo que
las políticas de WhatsApp Business prohíben. La entrega al destinatario se
hace en "Opción A": se le devuelve el contenido ya generado al comprador
para que lo reenvíe él mismo desde su WhatsApp personal.

## Estructura

```
app/
  main.py          servidor FastAPI: webhook de WhatsApp Cloud API
  conversation.py  máquina de estados de la conversación (el "cerebro")
  personas.py      catálogo de personajes y formatos (fácil de ampliar)
  llm.py           llamada a Claude / Gemini / modo mock sin API
  whatsapp.py      envío de mensajes por la Graph API de Meta
  storage.py       sesiones y entregas programadas en memoria
test_local.py      simulador de conversación por consola
test_scenario.py   prueba automática de todo el flujo
requirements.txt
.env.example
```

## 1. Probarlo YA, sin ninguna cuenta ni clave (modo mock)

```bash
pip install -r requirements.txt --break-system-packages   # o en un venv
python test_local.py
```

Vas a poder hablar con el bot por la terminal como si fueras el cliente de
WhatsApp. Sin `ANTHROPIC_API_KEY` ni `GEMINI_API_KEY` configuradas, el
contenido lo genera una plantilla fija (modo MOCK) en vez de una IA real —
así se prueba todo el flujo de catálogo, intake y entrega sin gastar nada.

También puedes correr la batería de pruebas automáticas:

```bash
python test_scenario.py
```

## 2. Probarlo con una IA real (Claude o Gemini)

```bash
cp .env.example .env
```

Edita `.env` y rellena `ANTHROPIC_API_KEY` (o `GEMINI_API_KEY`, no hacen
falta las dos). Vuelve a correr `python test_local.py`: ahora el contenido
lo escribe de verdad el modelo, en el tono de cada personaje.

## 3. Conectarlo a WhatsApp de verdad (Meta Business Platform)

1. Crea una cuenta en [Meta for Developers](https://developers.facebook.com/)
   y una app de tipo "Business". Añádele el producto **WhatsApp**.
2. Meta te da un número de prueba gratuito, un `Temporary access token` y
   un `Phone number ID`. Cópialos en tu `.env`:
   ```
   WHATSAPP_ACCESS_TOKEN=...
   WHATSAPP_PHONE_NUMBER_ID=...
   WHATSAPP_VERIFY_TOKEN=elige-cualquier-palabra
   ```
3. Levanta el servidor:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
4. Expón tu máquina a internet para que Meta pueda llamarte (en desarrollo,
   con [ngrok](https://ngrok.com/)):
   ```bash
   ngrok http 8000
   ```
5. En el panel de WhatsApp de tu app en Meta, configura el webhook con la
   URL que te da ngrok + `/webhook` (por ejemplo
   `https://abcd1234.ngrok.io/webhook`) y el mismo `WHATSAPP_VERIFY_TOKEN`
   que pusiste en `.env`. Suscríbete al campo `messages`.
6. Desde tu propio WhatsApp, escribe al número de prueba que te dio Meta.
   Debería contestarte el bot.

El access token temporal de Meta caduca en 24h — para algo más permanente
hace falta verificar el negocio y generar un token de sistema, pero para
probar el prototipo el temporal es suficiente.

## 3bis. Desplegarlo en Railway (en vez de ngrok)

Si ya tienes cuenta de Railway (como con el bot de inmobiliaria), es más
cómodo que ngrok porque la URL no cambia cada vez que reinicias:

1. Crea un **proyecto nuevo** en Railway para SorpresaBot (no reutilices el
   servicio del bot de inmobiliaria — así no interfieren entre sí).
2. Conéctalo a un repo de GitHub con este código (o usa `railway up` desde
   esta carpeta con la Railway CLI si prefieres no pasar por GitHub).
3. En el propio Railway, pestaña **Variables**, añade las mismas claves del
   `.env.example`: `ANTHROPIC_API_KEY` (o `GEMINI_API_KEY`),
   `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`,
   `WHATSAPP_VERIFY_TOKEN`. Railway ya define `PORT` automáticamente — el
   `Procfile` incluido ya lo usa (`uvicorn app.main:app --host 0.0.0.0 --port $PORT`).
4. Despliega y copia la URL pública que te da Railway (algo como
   `https://sorpresabot-production.up.railway.app`).
5. En [developers.facebook.com](https://developers.facebook.com/), en tu
   app → WhatsApp → Configuration, pon esa URL + `/webhook` como Callback
   URL, el mismo `WHATSAPP_VERIFY_TOKEN`, y suscríbete al campo `messages`.
6. **Importante con el número de pruebas de Meta**: solo puede enviar
   mensajes a números de teléfono que hayas añadido y verificado en la
   lista de destinatarios de prueba (API Setup → "To" → Manage phone
   number list, hasta 5 números). Añade el tuyo ahí o no te llegará nada
   aunque el servidor responda bien.
7. Escribe al número de prueba desde tu WhatsApp — debería contestarte el
   catálogo de personajes.

Nota: como el número es el mismo que usas para el bot de inmobiliaria, solo
uno de los dos webhooks puede estar activo a la vez en ese número — cambiar
de uno a otro es simplemente cambiar la Callback URL en el paso 5. Para
probar los dos en paralelo sin pisarse, lo más limpio es añadir un segundo
número de teléfono a la misma cuenta de WhatsApp Business (no hace falta
repetir la verificación del negocio).

### Persistencia con Supabase

El prototipo guarda sesiones y entregas programadas en memoria
(`app/storage.py`), lo cual es suficiente para probarlo, pero Railway puede
reiniciar el proceso y se perdería todo lo que hubiera en curso. Como ya
usas Supabase para el bot de inmobiliaria, el siguiente paso natural es
migrar `app/storage.py` a dos tablas de Supabase (`sesiones`, algo así como
`id_usuario, estado, datos_json` y `entregas_programadas` con
`id_usuario, contenido, destinatario, fecha_entrega, entregada`) en vez de
los diccionarios en memoria — la interfaz de las funciones
(`get_session`, `reset_session`, `programar_entrega`,
`entregas_pendientes`) se puede mantener igual para no tocar
`conversation.py` ni `main.py`.

## 4. Qué falta para pasar esto a producción

Este prototipo demuestra el mecanismo central (conversación con IA +
catálogo + entrega), pero antes de dar acceso a usuarios reales faltaría:

- **Pagos**: integrar Stripe Checkout (u otra pasarela) antes del paso de
  "ESPERANDO_FECHA", y no generar/entregar contenido hasta que el pago se
  confirme.
- **Persistencia real**: cambiar `app/storage.py` de memoria a una base de
  datos (SQLite para empezar, Postgres para producción), para no perder
  sesiones ni entregas programadas si el proceso se reinicia.
- **Programador de entregas robusto**: el bucle de `app/main.py` sirve para
  demostrar el concepto, pero en producción conviene una cola de tareas
  (por ejemplo APScheduler persistente, o Celery/RQ) para que las entregas
  programadas sobrevivan a un despliegue o reinicio del servidor.
- **Moderación**: los `system_prompt` de `app/personas.py` ya incluyen una
  instrucción explícita contra contenido cruel/dañino, pero conviene además
  revisar manualmente una muestra de los contenidos generados durante las
  primeras semanas.
- **Catálogo ampliable desde fuera del código**: mover `PERSONAS`,
  `FORMATOS` y `OCASIONES` de `app/personas.py` a la base de datos, para
  poder añadir personajes o creadores sin tocar el código.

## 5. Cómo cambiar de Claude a Gemini (o viceversa)

Toda la lógica de IA está aislada en `app/llm.py`. Solo hace falta rellenar
`GEMINI_API_KEY` en vez de `ANTHROPIC_API_KEY` (y descomentar
`google-generativeai` en `requirements.txt`) — el resto del código no
cambia, porque `conversation.py` solo llama a
`generar_contenido(...)` sin saber qué proveedor hay detrás.
