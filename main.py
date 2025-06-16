from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import stripe
import os
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

def enviar_correo_confirmacion(email_destino):
    mensaje = MIMEText("Tu inscripción en Duckling está confirmada — Aquí tienes todo el contenido")
    mensaje['Subject'] = 'Gracias por inscribirte en el Curso Intensivo para aprender a crear un spyware funcional. Las clases en vivo, grabaciones y todo el material descargable, incluyendo el certificado y los códigos fuente, se subirán y estarán disponibles en nuestra comunidad exclusiva de Discord. Puedes acceder al contenido y resolver dudas en este enlace: https://discord.gg/RvRtXDBkc3.'
    mensaje['From'] = 'dylan7138281@gmail.com'
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
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except stripe.error.SignatureVerificationError:
        return {"error": "Invalid signature"}

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        customer_email = session.get('customer_details', {}).get('email')

        if customer_email:
            enviar_correo_confirmacion(customer_email)

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
        success_url='https://discord.gg/RvRtXDBkc3/',
        cancel_url='https://duckling.so/'
    )
    return {"sessionId": session.id}

# python -m uvicorn main:app --reload
