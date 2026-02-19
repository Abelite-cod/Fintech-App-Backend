from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app import database, models, schemas, security
from app.services import wallet_service, transaction_service
from datetime import datetime
router = APIRouter()

@router.get("/my", response_model=List[schemas.TransactionOut])
def get_my_transactions(
    limit: int = 20,
    offset: int=0,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_user),
):
    limit = min(limit,100)
    transactions = (
        db.query(models.Transaction)
        .join(models.Wallet)
        .filter(models.Wallet.user_id == current_user.id)
        .order_by(models.Transaction.timestamp.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return transactions


@router.get("/wallet/{wallet_id}/transactions", response_model=list[schemas.TransactionOut])
def get_wallet_transactions(
    wallet_id: int,
    limit: int = 20,
    offset: int=0,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_user),
):
    limit = min(limit, 100)
    wallet = wallet_service.get_wallet(db, wallet_id)
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    if wallet.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    transactions = (
        db.query(models.Transaction)
        .filter(models.Transaction.wallet_id == wallet_id)
        .order_by(models.Transaction.timestamp.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return transactions



@router.get("/statement")
def account_statement(
    from_date: datetime,
    to_date: datetime,
    db: Session = Depends(database.get_db),
    user=Depends(security.get_current_user)
):
    wallet = db.query(models.Wallet).filter_by(user_id=user.id).first()
    if not wallet:
        return {
            "from": from_date,
            "to": to_date,
            "count": 0,
            "transactions": []
        }
    txs = (
        db.query(models.Transaction)
        .filter(
            models.Transaction.wallet_id == wallet.id,
            models.Transaction.timestamp.between(from_date, to_date)
        )
        .order_by(models.Transaction.timestamp.asc())
        .all()
    )
    

    return {
        "from": from_date,
        "to": to_date,
        "count": len(txs),
        "transactions": txs
    }

    

