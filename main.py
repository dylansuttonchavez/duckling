from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from dotenv import load_dotenv
import stripe
import os
import smtplib
from email.mime.text import MIMEText

load_dotenv()

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def send_confirmation_email(recipient_email):
    message = MIMEText(
        'Gracias por inscribirte en el Curso Intensivo para aprender a crear un spyware funcional. '
        'Las clases en vivo, grabaciones y todo el material descargable, incluyendo el certificado '
        'y los códigos fuente, se subirán y estarán disponibles en nuestra comunidad exclusiva de Discord. '
        'Puedes acceder al contenido y resolver dudas en este enlace: https://discord.gg/RvRtXDBkc3.'
    )
    message['Subject'] = "Tu inscripción en Duckling está confirmada — Aquí tienes todo el contenido"
    message['From'] = os.environ.get("EMAIL_SENDER")
    message['To'] = recipient_email

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(os.environ.get("EMAIL_SENDER"), os.environ.get("EMAIL_PASSWORD"))
        server.send_message(message)

@app.post("/webhook")
async def stripe_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    endpoint_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        email = session.get("customer_details", {}).get("email")
        if email:
            background_tasks.add_task(send_confirmation_email, email)

    return {"status": "success"}

@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "stripe_public_key": os.environ.get("STRIPE_PUBLIC_KEY")
    })

@app.get("/legal", response_class=HTMLResponse)
async def legal(request: Request):
    return templates.TemplateResponse("legal.html", {"request": request})

@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return RedirectResponse(url="/")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail or "Unexpected error"}
    )

@app.get("/access", response_class=HTMLResponse)
async def access(request: Request):
    return templates.TemplateResponse("access.html", {"request": request})

@app.post("/create-checkout-session")
def create_checkout_session():
    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'mxn',
                'product_data': {'name': 'Curso Intensivo Spyware'},
                'unit_amount': 222
            },
            'quantity': 1
        }],
        mode='payment',
        success_url='https://duckling.so/access/',
        cancel_url='https://duckling.so/'
    )
    return {"sessionId": session.id}
