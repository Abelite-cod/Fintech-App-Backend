from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Optional
import uuid, requests, os
from app import database, models, schemas, security
from app.services import wallet_service, idempotency_service
from app import database, models, schemas, security
from app.services import wallet_service, idempotency_service

router = APIRouter()

PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")
PAYSTACK_BASE_URL = "https://api.paystack.co"



# ------------------------
# Create Wallet
# ------------------------
@router.post("/", response_model=schemas.WalletOut)
def create_wallet(
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(database.get_db),
):
    existing = (
        db.query(models.Wallet)
        .filter(models.Wallet.user_id == current_user.id)
        .first()
    )

    if existing:
        raise HTTPException(status_code=400, detail="Wallet already exists")

    wallet = models.Wallet(user_id=current_user.id, balance_kobo=0)
    db.add(wallet)
    db.commit()
    db.refresh(wallet)
    return wallet


# ------------------------
# Get My Wallet
# ------------------------
@router.get("/me", response_model=schemas.WalletOut)
def get_my_wallet(
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(database.get_db),
):
    wallet = (
        db.query(models.Wallet)
        .filter(models.Wallet.user_id == current_user.id)
        .first()
    )

    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    return wallet


# ------------------------
# Get Wallet by ID
# ------------------------
@router.get("/{wallet_id}", response_model=schemas.WalletOut)
def get_wallet(
    wallet_id: int,
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(database.get_db),
):
    wallet = wallet_service.get_wallet(db, wallet_id)

    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    if wallet.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    return wallet


# ------------------------
# Withdraw
# ------------------------
@router.post("/{wallet_id}/withdraw", response_model=schemas.WalletOut)
def withdraw(
    wallet_id: int,
    payload: schemas.WithdrawRequest,
    idempotency_key: str = Header(...),
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(database.get_db),
):
    if payload.amount_kobo <= 0:
        raise HTTPException(status_code=400, detail="Invalid amount")

    wallet = wallet_service.get_wallet(db, wallet_id)
    if not wallet or wallet.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Wallet not found")

    existing_tx = idempotency_service.get_existing_transaction(
        db, wallet_id, idempotency_key
    )
    if existing_tx:
        return wallet

    try:
        wallet_locked = (
            db.query(models.Wallet)
            .filter(models.Wallet.id == wallet_id)
            .with_for_update()
            .first()
        )

        if wallet_locked.balance_kobo < payload.amount_kobo:
            raise HTTPException(status_code=400, detail="Insufficient funds")

        wallet_locked.balance_kobo -= payload.amount_kobo

        tx = models.Transaction(
            wallet_id=wallet_id,
            amount_kobo=payload.amount_kobo,
            type="withdraw",
            currency="NGN",
            idempotency_key=idempotency_key,
        )

        db.add(tx)
        db.commit()
        db.refresh(wallet_locked)
        return wallet_locked

    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Duplicate transaction")


# ------------------------
# Deposit
# ------------------------
@router.post("/{wallet_id}/deposit", response_model=schemas.WalletOut)
def deposit(
    wallet_id: int,
    payload: schemas.DepositRequest,
    idempotency_key: str = Header(...),
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(database.get_db),
):
    if payload.amount_kobo <= 0:
        raise HTTPException(status_code=400, detail="Invalid amount")

    wallet = wallet_service.get_wallet(db, wallet_id)
    if not wallet or wallet.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Check your wallet ID")

    existing_tx = idempotency_service.get_existing_transaction(
        db, wallet_id, idempotency_key
    )
    if existing_tx:
        return wallet

    try:
        wallet_locked = (
            db.query(models.Wallet)
            .filter(models.Wallet.id == wallet_id)
            .with_for_update()
            .first()
        )

        wallet_locked.balance_kobo += payload.amount_kobo

        tx = models.Transaction(
            wallet_id=wallet_id,
            amount_kobo=payload.amount_kobo,
            type="deposit",
            currency="NGN",
            idempotency_key=idempotency_key,
        )

        db.add(tx)
        db.commit()
        db.refresh(wallet_locked)
        return wallet_locked

    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Duplicate transaction")


# ------------------------
# Transfer
# ------------------------

def get_bank_name(bank_code: str) -> str:
    """Fetch bank name from Paystack API given a bank code."""
    try:
        response = requests.get(
            f"{PAYSTACK_BASE_URL}/bank?country=nigeria",
            headers={"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
        )
        banks = response.json().get("data", [])
        for bank in banks:
            if bank["code"] == bank_code:
                return bank["name"]
    except Exception:
        pass
    return "Unknown Bank"


@router.post("/transfer", response_model=schemas.TransferResponse)
def transfer(
    payload: schemas.TransferRequest,
    idempotency_key: str = Header(...),
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(database.get_db),
):
    if payload.amount_kobo <= 0:
        raise HTTPException(status_code=400, detail="Invalid amount")

    sender_wallet = db.query(models.Wallet).filter(models.Wallet.user_id == current_user.id).first()
    if not sender_wallet:
        raise HTTPException(status_code=404, detail="Sender wallet not found")

    # Check idempotency
    existing_tx = idempotency_service.get_existing_transaction(db, sender_wallet.id, idempotency_key)
    if existing_tx:
        return schemas.TransferResponse(
            sender_wallet=sender_wallet,
            destination_type=payload.destination_type
        )

    if payload.destination_type == "wallet":
        # Internal transfer
        if not payload.target_wallet_id:
            raise HTTPException(status_code=400, detail="Target wallet ID is required for internal transfer")

        receiver_wallet = wallet_service.get_wallet(db, payload.target_wallet_id)
        if not receiver_wallet:
            raise HTTPException(status_code=404, detail="Target wallet not found")

        operation_id = str(uuid.uuid4())
        wallets = (
            db.query(models.Wallet)
            .filter(models.Wallet.id.in_([sender_wallet.id, receiver_wallet.id]))
            .with_for_update()
            .all()
        )
        wallet_map = {w.id: w for w in wallets}
        sender = wallet_map[sender_wallet.id]
        receiver = wallet_map[receiver_wallet.id]

        if sender.balance_kobo < payload.amount_kobo:
            raise HTTPException(status_code=400, detail="Insufficient funds")

        sender.balance_kobo -= payload.amount_kobo
        receiver.balance_kobo += payload.amount_kobo

        tx_out = models.Transaction(
            wallet_id=sender.id,
            amount_kobo=payload.amount_kobo,
            type="transfer_out",
            idempotency_key=f"{idempotency_key}:out",
            operation_id=operation_id,
        )
        tx_in = models.Transaction(
            wallet_id=receiver.id,
            amount_kobo=payload.amount_kobo,
            type="transfer_in",
            idempotency_key=f"{idempotency_key}:in",
            operation_id=operation_id,
        )

        db.add_all([tx_out, tx_in])
        db.commit()
        db.refresh(sender)

        return schemas.TransferResponse(
            sender_wallet=sender,
            recipient_wallet=receiver,
            destination_type="wallet"
        )

    elif payload.destination_type == "bank":
        # External transfer
        if not payload.bank_code or not payload.account_number:
            raise HTTPException(status_code=400, detail="Bank code and account number are required for external transfer")

        if sender_wallet.balance_kobo < payload.amount_kobo:
            raise HTTPException(status_code=400, detail="Insufficient funds")

        # Lock sender wallet
        wallet_locked = db.query(models.Wallet).filter(models.Wallet.id == sender_wallet.id).with_for_update().first()
        wallet_locked.balance_kobo -= payload.amount_kobo

        tx = models.Transaction(
            wallet_id=wallet_locked.id,
            amount_kobo=payload.amount_kobo,
            type="transfer_out",
            idempotency_key=idempotency_key,
            operation_id=str(uuid.uuid4()),
            transfer_reference=str(uuid.uuid4()),  # for external reconciliation
            status="pending"
        )

        db.add(tx)
        db.commit()
        db.refresh(wallet_locked)

        bank_name = get_bank_name(payload.bank_code)
        account_name = None
        bank_account = db.query(models.BankAccount).filter_by(
            bank_code=payload.bank_code,
            account_number=payload.account_number
        ).first()
        if bank_account:
            account_name = bank_account.account_name
        return schemas.TransferResponse(
            sender_wallet=wallet_locked,
            bank_name=bank_name,
            account_number=payload.account_number,
            recipient_name=account_name,
            destination_type="bank",
            amount_kobo=payload.amount_kobo,

            
        )

    else:
        raise HTTPException(status_code=400, detail="Invalid destination type")
