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
USE_MOCK = os.getenv("USE_MOCK_PAYSTACK") == "true"

@router.post("/paystack")
async def paystack_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()

    if USE_MOCK:
        return {"status": "mocked"}

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

    try:

        # ==============================
        # HANDLE DEPOSIT
        # ==============================
        if event == "charge.success":

            reference = data.get("reference")
            amount_kobo = data.get("amount")
            email = data.get("customer", {}).get("email")

            if not all([reference, amount_kobo, email]):
                raise HTTPException(status_code=400, detail="Missing fields")

            # Idempotent webhook event
            existing_event = db.query(models.WebhookEvent)\
                .filter_by(reference=reference)\
                .first()

            if existing_event:
                return {"status": "ok", "message": "Already processed"}

            db.add(models.WebhookEvent(
                provider="paystack",
                event=event,
                reference=reference,
                payload=json.dumps(payload)
            ))
            db.flush()

            user = db.query(models.User)\
                .filter_by(email=email)\
                .first()

            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            wallet = db.query(models.Wallet)\
                .filter_by(user_id=user.id)\
                .with_for_update()\
                .first()

            if not wallet:
                wallet = models.Wallet(user_id=user.id)
                db.add(wallet)
                db.flush()

            tx = models.Transaction(
                wallet_id=wallet.id,
                amount_kobo=amount_kobo,
                type="deposit",
                idempotency_key=reference,
                operation_id=str(uuid.uuid4()),
                currency="NGN",
                timestamp=datetime.utcnow(),
                status="success"
            )

            db.add(tx)
            credit_wallet(db, wallet, amount_kobo)

            db.commit()
            return {"status": "success"}

        # ==============================
        # HANDLE TRANSFER EVENTS
        # ==============================
        if event in ["transfer.success", "transfer.failed"]:

            reference = data.get("reference")

            # Prevent duplicate webhook execution
            existing_event = db.query(models.WebhookEvent)\
                .filter_by(reference=reference)\
                .first()

            if existing_event:
                return {"status": "ok", "message": "Already processed"}

            db.add(models.WebhookEvent(
                provider="paystack",
                event=event,
                reference=reference,
                payload=json.dumps(payload)
            ))
            db.flush()

            tx = db.query(models.Transaction)\
                .filter(models.Transaction.transfer_reference == reference)\
                .with_for_update()\
                .first()

            if not tx:
                return {"status": "ignored"}

            if event == "transfer.success":
                tx.status = "success"

            elif event == "transfer.failed":
                tx.status = "failed"

                wallet = db.query(models.Wallet)\
                    .filter(models.Wallet.id == tx.wallet_id)\
                    .with_for_update()\
                    .first()

                wallet.balance_kobo += tx.amount_kobo

            db.commit()
            return {"status": "processed"}

        return {"status": "ignored"}

    except Exception:
        db.rollback()
        raise
