from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, security
from app.services.paystack_service import resolve_bank_account

router = APIRouter(prefix="/bank-accounts", tags=["Bank Accounts"])

@router.post("/")
def add_bank_account(
    bank_code: str,
    account_number: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(security.get_current_user)
):
    try:
        resolved = resolve_bank_account(account_number, bank_code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    existing = db.query(models.BankAccount).filter_by(
        user_id=user.id,
        bank_code=bank_code,
        account_number=account_number
    ).first()

    if existing:
        raise HTTPException(400, "Bank account already exists")

    bank_account = models.BankAccount(
        user_id=user.id,
        bank_code=bank_code,
        account_number=resolved["account_number"],
        account_name=resolved["account_name"]
    )

    db.add(bank_account)
    db.commit()
    db.refresh(bank_account)

    return {
        "message": "Bank account added successfully",
        "bank_account": {
            "id": bank_account.id,
            "account_name": bank_account.account_name,
            "account_number": bank_account.account_number,
            "bank_code": bank_account.bank_code
        }
    }
