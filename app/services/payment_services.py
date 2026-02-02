from sqlalchemy.orm import Session
from app import models
from app.services.idempotency_service import get_existing_transaction
from uuid import uuid4

def process_successful_payment(db: Session, payload: dict):
    data = payload["data"]

    reference = data["reference"]
    amount_kobo = data["amount"]  # already in kobo
    email = data["customer"]["email"]

    # Find user
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        return  # ignore unknown users

    wallet = db.query(models.Wallet)\
        .filter(models.Wallet.user_id == user.id)\
        .with_for_update()\
        .first()

    if not wallet:
        return

    # Idempotency: webhook retry safe
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
        currency="NGN"
    )

    db.add(tx)
    db.commit()
