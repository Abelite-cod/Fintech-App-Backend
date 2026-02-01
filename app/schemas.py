from pydantic import BaseModel, EmailStr, computed_field
from datetime import datetime

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    username: str
    email: EmailStr

    class Config:
        from_attributes = True


class WalletOut(BaseModel):
    id: int
    balance_kobo: int
    user_id: int
    currency: str = "NGN"

    # Computed field for balance in Naira
    @computed_field
    def balance_naira(self) -> float:
        return self.balance_kobo / 100

    model_config = {
        "from_attributes": True  # Allows creation from ORM objects
    }



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
    target_wallet_id: int
    amount_kobo: int

    