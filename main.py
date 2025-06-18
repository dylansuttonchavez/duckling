@app.get("/s/{session_id}", response_class=HTMLResponse)
async def confirmacion(request: Request, session_id: str):
    # ¿Ya fue usado este enlace?
    res = supabase.table("access_sessions").select("*").eq("session_id", session_id).single().execute()
    data = res.data

    if data and data["used"]:
        raise HTTPException(403, "Este enlace ya fue utilizado")

    # Verificar pago en Stripe
    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception:
        raise HTTPException(404, "Sesión no encontrada")

    if session.payment_status != "paid":
        raise HTTPException(403, "Pago no confirmado")

    # Registrar el acceso como usado (o insertarlo si es nuevo)
    if not data:
        supabase.table("access_sessions").insert({
            "session_id": session_id,
            "used": True,
        }).execute()
        
        # Enviar correo de confirmación solo en primer acceso
        customer_email = session.customer_details.email if session.customer_details else None
        if customer_email:
            enviar_correo_confirmacion(customer_email)
    else:
        # Si el registro existía pero no estaba marcado como usado
        supabase.table("access_sessions").update({"used": True}).eq("session_id", session_id).execute()

    # Renderizar página de confirmación
    customer_email = session.customer_details.email or ""
    customer_name = session.customer_details.name or "Alumno"

    return templates.TemplateResponse(
        "confirmation.html",
        {
            "request": request,
            "customer_email": customer_email,
            "customer_name": customer_name,
            "fecha_actual": datetime.utcnow().strftime("%m.%d.%Y")
        }
    )
