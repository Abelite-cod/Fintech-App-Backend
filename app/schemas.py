from pydantic import BaseModel, EmailStr, computed_field
from datetime import datetime
from typing import Optional, Literal

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    phone_number: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    username: str
    email: EmailStr
    phone_number: str

    class Config:
        from_attributes = True


class UserInfo(BaseModel):
    phone_number: str

    model_config = {"from_attributes": True}


class WalletOut(BaseModel):
    id: int
    balance_kobo: int
    currency: str
    user_id: int
    owner: UserInfo  # <-- Nest user info

    @computed_field
    def balance_naira(self) -> float:
        return self.balance_kobo / 100

    model_config = {"from_attributes": True}


class TransactionCreate(BaseModel):
    amount_kobo: int
    type: str

class TransactionOut(BaseModel):
    id: int
    wallet_id: int
    amount_kobo: int
    type: str
    timestamp: datetime

    model_config = {
        "from_attributes":True
    }

    @computed_field
    def amount_naira(self) -> float:
        return self.amount_kobo / 100


class WithdrawRequest(BaseModel):
    amount_kobo: int

class DepositRequest(BaseModel):
    amount_kobo: int

# Request body schema for transfer
class TransferRequest(BaseModel):
    amount_kobo: int
    destination_type: Literal["wallet", "bank"]

    # Wallet transfer
    username: Optional[str] = None
    phone_number: Optional[str] = None

    # Bank transfer
    bank_code: Optional[str] = None
    account_number: Optional[str] = None 

class TransferResponse(BaseModel):
    sender_wallet: WalletOut
    recipient_wallet: Optional[WalletOut] = None

    # Bank transfers
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    recipient_name: Optional[str] = None

    amount_kobo: Optional[int] = None

    destination_type: Literal["wallet", "bank"]

    model_config = {
        "from_attributes": True
    }


class WalletLookupResponse(BaseModel):
    username: str
    phone_number: Optional[str] = None

    model_config = {"from_attributes": True}