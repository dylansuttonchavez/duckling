from fastapi import FastAPI, Request, Response, HTTPException, Cookie
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from datetime import datetime, timedelta
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
async def confirmacion(request: Request, session_id: str, response: Response, access_confirmacion: str = Cookie(None)):
    now = datetime.utcnow()

    if access_confirmacion == session_id:
        res = supabase.table("access_sessions").select("expires_at").eq("session_id", session_id).single().execute()
        data = res.data
        if not data or datetime.fromisoformat(data["expires_at"]) < now:
            supabase.table("access_sessions").delete().eq("session_id", session_id).execute()
            response.delete_cookie("access_confirmacion")
            raise HTTPException(403, "Acceso expirado")
    else:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
        except Exception:
            raise HTTPException(404, "Sesión no encontrada")
        if session.payment_status != "paid":
            raise HTTPException(403, "Pago no confirmado")

        expires_at = (now + timedelta(minutes=10)).isoformat()
        insert_result = supabase.table("access_sessions") \
            .insert({"session_id": session_id, "expires_at": expires_at}) \
            .on_conflict("session_id") \
            .do_nothing() \
            .execute()

        response.set_cookie("access_confirmacion", session_id, httponly=True, max_age=600)

        # Solo enviar correo si realmente se insertó el registro (es decir, si no existía antes)
        if insert_result.data:
            customer_email = session.customer_details.email if session.customer_details else None
            if customer_email:
                enviar_correo_confirmacion(customer_email)

    # Obtener detalles para mostrar
    if 'session' not in locals():
        session = stripe.checkout.Session.retrieve(session_id)

    customer_email = session.customer_details.email if session.customer_details else ""
    customer_name = session.customer_details.name if session.customer_details else "Alumno"

    return templates.TemplateResponse("confirmation.html", {
        "request": request,
        "customer_email": customer_email,
        "customer_name": customer_name,
        "fecha_actual": now.strftime("%m.%d.%Y")
    }, response=response)
