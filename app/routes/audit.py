from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import database, models, security
from app.services.audit_service import verify_wallet_balance

router = APIRouter(prefix="/audit", tags=["Audit"])

@router.get("/wallet/{wallet_id}")
def audit_wallet(
    wallet_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_user),
):
    wallet = db.query(models.Wallet).filter(models.Wallet.id == wallet_id).first()

    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    if wallet.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    return verify_wallet_balance(db, wallet)
