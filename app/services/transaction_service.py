from sqlalchemy.orm import Session
from app import models
from datetime import datetime

def create_transaction(db: Session, wallet_id: int, amount_kobo: int, type: str):
    transaction = models.Transaction(
        wallet_id=wallet_id,
        amount_kobo=amount_kobo,
        type=type,
        timestamp=datetime.utcnow()
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction
