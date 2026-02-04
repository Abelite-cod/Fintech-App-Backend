from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid

from app.database import get_db
from app import models, security

router = APIRouter(prefix="/withdrawals", tags=["Withdrawals"])


@router.post("/")
def request_withdrawal(
    amount_kobo: int,
    bank_account_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(security.get_current_user)
):
    wallet = db.query(models.Wallet).filter_by(user_id=user.id).first()

    if wallet.balance_kobo < amount_kobo:
        raise HTTPException(400, "Insufficient funds")

    bank_account = db.query(models.BankAccount).filter_by(
        id=bank_account_id,
        user_id=user.id
    ).first()

    if not bank_account:
        raise HTTPException(404, "Bank account not found")

    reference = str(uuid.uuid4())

    try:
        wallet.balance_kobo -= amount_kobo

        tx = models.Transaction(
            wallet_id=wallet.id,
            amount_kobo=amount_kobo,
            type="withdraw",
            status="pending",
            idempotency_key=reference
        )

        db.add(tx)
        db.commit()

    except:
        db.rollback()
        raise HTTPException(500, "Withdrawal failed")

    return {
        "message": "Withdrawal requested",
        "reference": reference,
        "bank_account": bank_account.account_name
    }
