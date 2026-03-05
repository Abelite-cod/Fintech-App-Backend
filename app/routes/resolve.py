from fastapi import APIRouter, HTTPException
from app.services.paystack_service import resolve_bank_account

router = APIRouter(prefix="/resolve-account", tags=["Bank Resolution"])

@router.post("/")
def resolve_account(payload: dict):
    try:
        result = resolve_bank_account(
            account_number=payload["account_number"],
            bank_code=payload["bank_code"]
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))