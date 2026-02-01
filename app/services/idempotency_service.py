from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app import models


def get_existing_transaction(
    db: Session,
    wallet_id: int,
    idempotency_key: str,
):
    return (
        db.query(models.Transaction)
        .filter(
            models.Transaction.wallet_id == wallet_id,
            models.Transaction.idempotency_key == idempotency_key,
        )
        .first()
    )


def save_transaction(db: Session, tx: models.Transaction):
    try:
        db.add(tx)
        db.flush()  # IMPORTANT: flush before commit
        return tx
    except IntegrityError:
        db.rollback()
        raise
