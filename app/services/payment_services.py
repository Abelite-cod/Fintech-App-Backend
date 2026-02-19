from sqlalchemy.orm import Session
from app import models
from app.services.idempotency_service import get_existing_transaction
from uuid import uuid4
from datetime import datetime
import os
import requests
from dotenv import load_dotenv

load_dotenv()

USE_MOCK = os.getenv("USE_MOCK_PAYSTACK") == "true"
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")

BASE_URL = "https://api.paystack.co"

headers = {
    "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
    "Content-Type": "application/json"
}


def process_successful_payment(db: Session, payload: dict):
    data = payload.get("data", {})

    reference = data.get("reference")
    amount_kobo = data.get("amount")
    email = data.get("customer", {}).get("email")

    if not all([reference, amount_kobo, email]):
        return

    try:
        # Find user
        user = db.query(models.User)\
            .filter(models.User.email == email)\
            .first()

        if not user:
            return

        # Lock wallet row (CRITICAL for fintech)
        wallet = db.query(models.Wallet)\
            .filter(models.Wallet.user_id == user.id)\
            .with_for_update()\
            .first()

        if not wallet:
            return

        # Idempotency protection
        existing = get_existing_transaction(db, wallet.id, reference)
        if existing:
            return

        # Credit wallet
        wallet.balance_kobo += amount_kobo

        tx = models.Transaction(
            wallet_id=wallet.id,
            amount_kobo=amount_kobo,
            type="deposit",
            idempotency_key=reference,
            operation_id=str(uuid4()),
            currency="NGN",
            status="success",
            timestamp=datetime.utcnow()
        )

        db.add(tx)
        db.commit()

    except Exception:
        db.rollback()
        raise


def get_banks():
    if USE_MOCK:
        return {
            "status": True,
            "data": [
                {"name": "Mock Bank", "code": "000"}
            ]
        }

    response = requests.get(
        f"{BASE_URL}/bank?country=nigeria",
        headers=headers
    )

    return response.json()
