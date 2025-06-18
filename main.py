from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from datetime import datetime
import stripe
import os
import smtplib
from email.mime.text import MIMEText
from supabase import create_client

load_dotenv()

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

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
                'unit_amount': 99900  # Stripe espera montos en centavos
            },
            'quantity': 1
        }],
        mode='payment',
        success_url='https://duckling.so/s/{CHECKOUT_SESSION_ID}',
        cancel_url='https://duckling.so/'
    )
    return {"sessionId": session.id}

@app.get("/s/{session_id}", response_class=HTMLResponse)
async def confirmacion(request: Request, session_id: str):
    # Verificar si el enlace ya fue usado
    res = supabase.table("access_sessions").select("*").eq("session_id", session_id).single().execute()
    data = res.data

    if data and data["used"]:
        raise HTTPException(403, "Este enlace ya fue utilizado")

    # Verificar estado del pago en Stripe
    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception:
        raise HTTPException(404, "Sesión no encontrada")

    if session.payment_status != "paid":
        raise HTTPException(403, "Pago no confirmado")

    # Insertar o actualizar acceso como usado
    if not data:
        supabase.table("access_sessions").insert({
            "session_id": session_id,
            "used": True,
        }).execute()

        # Enviar correo solo en primer acceso
        customer_email = session.customer_details.email if session.customer_details else None
        if customer_email:
            enviar_correo_confirmacion(customer_email)
    else:
        supabase.table("access_sessions").update({"used": True}).eq("session_id", session_id).execute()

    # Renderizar página de confirmación
    customer_email = session.customer_details.email or ""
    customer_name = session.customer_details.name or "Alumno"
    fecha_actual = datetime.utcnow().strftime("%m.%d.%Y")

    return templates.TemplateResponse(
        "confirmation.html",
        {
            "request": request,
            "customer_email": customer_email,
            "customer_name": customer_name,
            "fecha_actual": fecha_actual
        }
    )
