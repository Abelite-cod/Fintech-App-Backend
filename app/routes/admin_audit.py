# routes/admin_audit.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app import database, security, models
from app.services.audit_service import recalculate_wallet_balance
router = APIRouter(prefix="/admin/audit", tags=["Admin Audit"])

@router.get("/wallet/{wallet_id}")
def audit_wallet(
    wallet_id: int,
    db: Session = Depends(database.get_db),
    admin = Depends(security.require_admin)
):
    return recalculate_wallet_balance(db, wallet_id)

@router.get("/mismatches")
def audit_all_wallets(
    db: Session = Depends(database.get_db),
    admin = Depends(security.require_admin)
):
    wallets = db.query(models.Wallet).all()
    broken = []

    for w in wallets:
        audit = recalculate_wallet_balance(db, w.id)
        if not audit["valid"]:
            broken.append(audit)

    return {
        "total_wallets": len(wallets),
        "mismatched_wallets": len(broken),
        "details": broken
    }


@router.post("/fix/{wallet_id}")
def fix_wallet_balance(
    wallet_id: int,
    db: Session = Depends(database.get_db),
    admin = Depends(security.require_admin)
):
    audit = recalculate_wallet_balance(db, wallet_id)

    if audit["valid"]:
        return {"message": "Wallet already valid"}

    db.query(models.Wallet)\
        .filter(models.Wallet.id == wallet_id)\
        .update({"balance": audit["calculated_balance"]})

    db.commit()

    return {
        "message": "Wallet corrected",
        "new_balance": audit["calculated_balance"]
    }
