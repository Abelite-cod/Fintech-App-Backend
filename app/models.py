from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
from enum import Enum
import uuid
 

# User table
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    username = Column(String, nullable=True)
    wallets = relationship("Wallet", back_populates="owner")
    role = Column(String, default="user") #user/admin

# Wallet table
class Wallet(Base):
    __tablename__ = "wallets"
    id = Column(Integer, primary_key=True, index=True)
    balance_kobo = Column(Integer, default=0, nullable=False)
    currency = Column(String, default="NGN", nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="wallets")
    transactions = relationship("Transaction", back_populates="wallet")

# Transaction table
class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    amount_kobo = Column(Integer, nullable=False)
    type = Column(String, nullable=False, index=True)
    status = Column(String, default="pending", index=True)
    wallet_id = Column(Integer, ForeignKey("wallets.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    idempotency_key = Column(String, nullable=False, index=True)
    operation_id = Column(String, default=lambda: str(uuid.uuid4()))
    currency = Column(String, default="NGN", nullable=False)
    wallet = relationship("Wallet", back_populates="transactions")

    __table_args__ = (
        UniqueConstraint(
            "wallet_id",
            "idempotency_key",
            name="uq_wallet_idempotency"
        ),
    )

class TransactionType(str, Enum):
    deposit = "deposit"
    withdraw = "withdraw"
    transfer_in = "transfer_in"
    transfer_out = "transfer_out"

class TransactionStatus(str, Enum):
    pending = "pending"
    success = "success"
    failed = "failed"
    reversed = "reversed"

class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True)
    provider = Column(String, index=True)  #paystack
    event = Column(String, index=True)
    reference = Column(String, index=True, unique=True)
    payload = Column(String)  
    received_at = Column(DateTime, default=datetime.utcnow)
