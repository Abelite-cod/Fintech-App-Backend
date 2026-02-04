from fastapi import APIRouter
import uuid
from datetime import datetime
from app.database import get_db
from app import models
from sqlalchemy.orm import Session

router = APIRouter(prefix="/mock/paystack", tags=["Mock Paystack"])

@router.post("/pay")
def mock_payment(email: str, amount_kobo: int):
    reference = f"MOCK_{uuid.uuid4().hex[:12]}"

    return {
        "status": True,
        "message": "Payment initialized",
        "data": {
            "reference": reference,
            "authorization_url": "http://localhost/mock"
        }
    }

def mock_transfer(reference: str, succeed: bool = True):
    """
    Mock transfer for local dev.
    Auto-updates the transaction in SQLite.
    """
    db: Session = next(get_db())

    tx = db.query(models.Transaction).filter_by(idempotency_key=reference).first()
    if not tx:
        return {"status": False, "message": "Transaction not found"}

    if succeed:
        # Mark transaction as success
        tx.status = "success"
        db.commit()
        return {
            "status": True,
            "data": {
                "reference": reference,
                "status": "success"
            }
        }
    else:
        # Mark transaction failed + revert wallet
        wallet = db.query(models.Wallet).filter_by(id=tx.wallet_id).first()
        wallet.balance_kobo += tx.amount_kobo
        tx.status = "failed"
        db.commit()
        return {"status": False, "message": "Transfer failed"}
