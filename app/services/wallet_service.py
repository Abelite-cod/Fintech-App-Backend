from sqlalchemy.orm import Session
from app import models

def get_wallet(db: Session, wallet_id: int):
    return db.query(models.Wallet).filter(models.Wallet.id == wallet_id).first()

def create_wallet(db: Session, user_id: int):
    wallet = models.Wallet(
        user_id=user_id,
        balance_kobo=0
    )
    db.add(wallet)
    db.commit()
    db.refresh(wallet)
    return wallet

def credit_wallet(db: Session, wallet: models.Wallet, amount_kobo: int):
    wallet.balance_kobo += amount_kobo
    db.flush()
    return wallet