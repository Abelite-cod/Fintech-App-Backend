from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, security
from app.services.paystack_service import initiate_transfer
import traceback

router = APIRouter(prefix="/admin/withdrawals", tags=["Admin Withdrawals"])


@router.post("/{transaction_id}/send")
def send_withdrawal(
    transaction_id: int,
    db: Session = Depends(get_db),
    admin = Depends(security.require_admin)
):
    try:
        tx = db.query(models.Transaction).filter_by(id=transaction_id).first()
        if not tx:
            raise HTTPException(status_code=404, detail="Transaction not found")
        if tx.status != "pending":
            raise HTTPException(status_code=400, detail=f"Transaction status invalid: {tx.status}")

        # Use real bank_code/account_number from user's linked bank
        user_bank = db.query(models.BankAccount).filter_by(user_id=tx.wallet.user_id).first()
        if not user_bank:
            raise HTTPException(status_code=400, detail="User bank account not found")

        response = initiate_transfer(
            amount_kobo=tx.amount_kobo,
            bank_code=user_bank.bank_code,
            account_number=user_bank.account_number,
            reference=tx.idempotency_key
        )

        if response.get("status") is True:
            tx.transfer_reference = response["data"]["reference"]
            db.commit()
            print(f"[Transfer Initiated] Tx:{tx.id} Ref:{tx.transfer_reference}")
            return {"status": "transfer initiated"}
        else:
            db.rollback()
            print("[Transfer Failed Response]", response)
            raise HTTPException(status_code=400, detail="Paystack transfer unavailable. Business upgrade required.")

    except Exception as e:
        db.rollback()
        print("[Admin Withdrawal Error]", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Withdrawal send failed")
