from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from datetime import datetime, timedelta
import stripe
import redis
import os
import json
import smtplib
from email.mime.text import MIMEText

# Cargar variables de entorno
load_dotenv()

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

# Conexión Redis (localhost por defecto)
redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Función para enviar email
def enviar_correo_confirmacion(email_destino):
    mensaje = MIMEText(
        'Gracias por inscribirte en el Curso Intensivo para aprender a crear un spyware funcional. '
        'Las clases en vivo, grabaciones y todo el material descargable, incluyendo el certificado '
        'y los códigos fuente, se subirán y estarán disponibles en nuestra comunidad exclusiva de Discord. '
        'Puedes acceder al contenido y resolver dudas en este enlace: https://discord.gg/RvRtXDBkc3.'
    )
    mensaje['Subject'] = "Tu inscripción en Duckling está confirmada — Aquí tienes todo el contenido"
    mensaje['From'] = 'dylan718281@gmail.com'
    mensaje['To'] = email_destino

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login('dylan718281@gmail.com', os.environ.get("EMAIL_PASSWORD"))
        server.send_message(mensaje)

@app.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    endpoint_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Firma inválida")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        session_id = session["id"]
        expire = timedelta(minutes=10)

        # Guardar acceso en Redis con expiración
        redis_client.setex(f"session:{session_id}", expire, json.dumps({
            "used": False
        }))

        # Enviar correo
        email = session.get("customer_details", {}).get("email")
        if email:
            enviar_correo_confirmacion(email)

    return {"status": "success"}

@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "stripe_public_key": os.environ.get("STRIPE_PUBLIC_KEY")
    })

@app.post("/create-checkout-session")
def create_checkout_session():
    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'mxn',
                'product_data': {'name': 'Curso Intensivo Spyware'},
                'unit_amount': 999
            },
            'quantity': 1
        }],
        mode='payment',
        success_url='https://duckling.so/s/{CHECKOUT_SESSION_ID}',
        cancel_url='https://duckling.so/'
    )
    return {"sessionId": session.id}

@app.get("/s/{session_id}", response_class=HTMLResponse)
async def confirmacion(request: Request, session_id: str, response: Response):
    key = f"session:{session_id}"
    data = redis_client.get(key)

    if not data:
        raise HTTPException(status_code=410, detail="El enlace ha expirado o no existe")

    session_data = json.loads(data)

    if session_data.get("used"):
        raise HTTPException(status_code=403, detail="Este enlace ya fue utilizado")

    # Validar con Stripe que el pago esté confirmado
    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Sesión inválida")

    if session.payment_status != "paid":
        raise HTTPException(status_code=403, detail="Pago no confirmado")

    # Marcar como usado (actualiza TTL restante)
    session_data["used"] = True
    ttl = redis_client.ttl(key)
    redis_client.setex(key, ttl, json.dumps(session_data))

    customer_email = session.customer_details.email if session.customer_details else ""
    customer_name = session.customer_details.name if session.customer_details else "Alumno"

    return templates.TemplateResponse("confirmation.html", {
        "request": request,
        "customer_email": customer_email,
        "customer_name": customer_name,
        "fecha_actual": datetime.utcnow().strftime("%m.%d.%Y")
    }, response=response)
