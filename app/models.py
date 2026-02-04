from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
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
    bank_accounts = relationship("BankAccount", backref="user")

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
    transfer_reference = Column(String, nullable=True, index=True)

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


class BankAccount(Base):
    __tablename__ = "bank_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    bank_code = Column(String(10), nullable=False)
    account_number = Column(String(20), nullable=False)
    account_name = Column(String(100), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "bank_code",
            "account_number",
            name="uq_user_bank_account"
        ),
    )
