from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
import hmac, hashlib, json, os, uuid
from dotenv import load_dotenv
from datetime import datetime

from app.database import get_db
from app import models
from app.services.wallet_service import credit_wallet

router = APIRouter(prefix="/webhook", tags=["Webhook"])

load_dotenv()
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")


@router.post("/paystack")
async def paystack_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    signature = request.headers.get("x-paystack-signature", "")

    computed = hmac.new(
        PAYSTACK_SECRET_KEY.encode(),
        body,
        hashlib.sha512
    ).hexdigest()

    if not hmac.compare_digest(computed, signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    payload = json.loads(body)
    event = payload.get("event")
    data = payload.get("data", {})

    if event != "charge.success":
        return {"status": "ignored"}

    reference = data.get("reference")
    amount_kobo = data.get("amount")
    email = data.get("customer", {}).get("email")

    if not all([reference, amount_kobo, email]):
        raise HTTPException(status_code=400, detail="Missing fields")

    # ---- Save webhook event (idempotent)
    existing_event = db.query(models.WebhookEvent)\
        .filter_by(reference=reference)\
        .first()

    if existing_event:
        return {"status": "ok", "message": "Webhook already processed"}

    db.add(models.WebhookEvent(
        provider="paystack",
        event=event,
        reference=reference,
        payload=json.dumps(payload)
    ))
    db.flush()

    # ---- Find user
    user = db.query(models.User).filter_by(email=email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    wallet = db.query(models.Wallet).filter_by(user_id=user.id).first()
    if not wallet:
        wallet = models.Wallet(user_id=user.id)
        db.add(wallet)
        db.flush()

    # ---- Create transaction (PENDING)
    tx = models.Transaction(
        wallet_id=wallet.id,
        amount_kobo=amount_kobo,
        type="deposit",
        idempotency_key=reference,
        operation_id=str(uuid.uuid4()),
        currency="NGN",
        timestamp=datetime.utcnow()
    )

    db.add(tx)
    db.flush()

    # ---- Credit wallet
    credit_wallet(db, wallet, amount_kobo)
    tx.status = "success"

    db.commit()

    return {"status": "success", "message": "Wallet credited successfully"}
