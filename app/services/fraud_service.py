from sqlalchemy.orm import SessionTransaction, Session
from app import models
from datetime import datetime, timedelta

class FraudService:
    HIGH_AMOUNT_THRESHOLD = 50
    MAX_TRANSFER_SCORE = 30
    SELF_TRANSFER_SCORE = 100
    FRAUD_THRESHOLD = 60


    @staticmethod
    def calculate_SCORE(db: Session, sender_wallet_id: int, reciever_wallet_id: int, amount:float):
        score = 0
        reasons =[]

        if amount >= 10000:
            score += FraudService.HIGH_AMOUNT_THRESHOLD
            reasons.append("High Transaction AMpunt")

        if sender_wallet_id == reciever_wallet_id:
            score +=FraudService.SELF_TRANSFER_SCORE
            reasons.append("Self Transfer Attempt")

        one_minute_ago = datetime.utcnow() - timedelta(minutes=1)
        recent_transfers = (db.query (models.Transaction).filter(
            models.Transaction.sender_wallet_id == sender_wallet_id,
            models.Transaction.created_at >= one_minute_ago,
            models.Transaction.type == "transfer"
        )
        .count()
    )
        if recent_transfers >= 3:
            score += FraudService.MAX_TRANSFER_SCORE
            reasons.append("Too may trasfers within one minute")

        return score, reasons
    
    @staticmethod
    def is_flagged(score: int):
        return score >= FraudService.FRAUD_THRESHOLD

        