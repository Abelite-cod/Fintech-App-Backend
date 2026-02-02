# app/routes/webhook.py
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
import hmac
import hashlib
import json
import os
import uuid
from datetime import datetime
from dotenv import load_dotenv

from app import models
from app.database import get_db
from app.services.wallet_service import create_wallet

router = APIRouter(prefix="/webhook", tags=["Webhook"])

# Load environment variables
load_dotenv()
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")

@router.post("/paystack")
async def paystack_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    signature = request.headers.get("x-paystack-signature", "")

    # 1️⃣ Verify webhook signature
    computed_signature = hmac.new(
        key=PAYSTACK_SECRET_KEY.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha512
    ).hexdigest()

    if not hmac.compare_digest(computed_signature, signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    # 2️⃣ Parse webhook payload
    payload = json.loads(body)
    event = payload.get("event")
    data = payload.get("data", {})

    if event != "charge.success":
        return {"status": "ignored", "message": f"Event {event} not processed"}

    amount_kobo = data.get("amount")  # amount in kobo
    email = data.get("customer", {}).get("email")
    reference = data.get("reference")  # use as idempotency_key

    if not all([amount_kobo, email, reference]):
        raise HTTPException(status_code=400, detail="Missing required fields")

    # 3️⃣ Find user
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 4️⃣ Get or create wallet
    wallet = db.query(models.Wallet).filter(models.Wallet.user_id == user.id).first()
    if not wallet:
        wallet = create_wallet(db, user.id)

    # 5️⃣ Idempotency check
    existing_tx = db.query(models.Transaction).filter_by(
        wallet_id=wallet.id,
        idempotency_key=reference
    ).first()

    if existing_tx:
        return {"status": "success", "message": "Transaction already processed"}

    try:
        # 6️⃣ Atomic update: credit wallet and create transaction
        wallet.balance_kobo += amount_kobo

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
        db.commit()  # commit both wallet and transaction together
        db.refresh(wallet)
        db.refresh(tx)

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to process transaction: {str(e)}")

    # 7️⃣ Return response to Paystack
    return {"status": "success", "message": "Wallet credited successfully"}
