from sqlalchemy.orm import Session
from app import models

TX_SIGN = {
    "deposit": 1,
    "withdraw": -1,
    "transfer_in": 1,
    "transfer_out": -1,
}

def verify_wallet_balance(db: Session, wallet: models.Wallet) -> dict:
    transactions = (
        db.query(models.Transaction)
        .filter(models.Transaction.wallet_id == wallet.id)
        .all()
    )

    calculated_balance = sum(
        tx.amount_kobo * TX_SIGN.get(tx.type, 0)
        for tx in transactions
    )

    is_valid = calculated_balance == wallet.balance_kobo

    return {
        "wallet_id": wallet.id,
        "stored_balance_kobo": wallet.balance_kobo,
        "calculated_balance_kobo": calculated_balance,
        "valid": is_valid,
    }

def recalculate_wallet_balance(db: Session, wallet_id: int):
    txs = (
        db.query(models.Transaction)
        .filter(models.Transaction.wallet_id == wallet_id)
        .all()
    )

    calculated_balance = 0

    for tx in txs:
        calculated_balance += tx.amount_kobo * TX_SIGN.get(tx.type, 0)

    wallet = db.query(models.Wallet).filter_by(id=wallet_id).first()

    difference = (
        calculated_balance - wallet.balance_kobo
        if wallet else None
    )

    return {
        "wallet_id": wallet_id,
        "stored_balance_kobo": wallet.balance_kobo if wallet else None,
        "calculated_balance_kobo": calculated_balance,
        "difference_kobo": difference,
        "valid": difference == 0,
        "transaction_count": len(txs),
    }
