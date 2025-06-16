from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import stripe
import os

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

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
                'unit_amount': 22300
            },
            'quantity': 1
        }],
        mode='payment',
        success_url='https://duckling.so/',
        cancel_url='https://duckling.so/'
    )
    return {"sessionId": session.id}
