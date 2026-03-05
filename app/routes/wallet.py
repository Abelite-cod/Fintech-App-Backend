from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from typing import Optional
import uuid
import requests
import os

from app import database, models, schemas, security
from app.services import wallet_service, idempotency_service
from app.services.paystack_service import resolve_bank_account, initiate_transfer, get_transfer_status

router = APIRouter()

PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")
PAYSTACK_BASE_URL = "https://api.paystack.co"


# -------------------- Utility --------------------
def lock_wallet(db: Session, wallet_id: int):
    """Lock a wallet row for updates to prevent race conditions."""
    return (
        db.query(models.Wallet)
        .filter(models.Wallet.id == wallet_id)
        .with_for_update()
        .first()
    )



# -------------------- BANKS --------------------
@router.get("/banks")
def list_banks():
    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
    response = requests.get(f"{PAYSTACK_BASE_URL}/bank?country=nigeria", headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to fetch banks")
    return response.json()["data"]


# -------------------- WALLET LOOKUP --------------------
@router.get("/wallet/lookup", response_model=schemas.WalletLookupResponse)
def lookup_wallet(
    username: Optional[str] = None,
    phone_number: Optional[str] = None,
    db: Session = Depends(database.get_db),
):
    if not username and not phone_number:
        raise HTTPException(status_code=400, detail="Provide username or phone_number")

    query = db.query(models.User)
    if username:
        user = query.filter(models.User.username == username).first()
    else:
        user = query.filter(models.User.phone_number == phone_number).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "username": user.username,
        "phone_number": user.phone_number or "",
    }


# -------------------- CREATE WALLET --------------------
@router.post("/", response_model=schemas.WalletOut)
def create_wallet(
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(database.get_db),
):
    existing = db.query(models.Wallet).filter_by(user_id=current_user.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Wallet already exists")

    wallet = models.Wallet(user_id=current_user.id, balance_kobo=0)
    db.add(wallet)
    db.commit()
    db.refresh(wallet)
    return wallet


# -------------------- GET MY WALLET --------------------
@router.get("/me", response_model=schemas.WalletOut)
def get_my_wallet(
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(database.get_db),
):
    wallet = db.query(models.Wallet).filter_by(user_id=current_user.id).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return wallet



# -------------------- DEPOSIT --------------------
@router.post("/{wallet_id}/deposit", response_model=schemas.WalletOut)
def deposit(
    wallet_id: int,
    payload: schemas.DepositRequest,
    idempotency_key: str = Header(...),
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(database.get_db),
):
    # Validate amount
    if payload.amount_kobo <= 0:
        raise HTTPException(status_code=400, detail="Invalid amount")

    # Fetch wallet with owner eagerly loaded
    wallet = (
        db.query(models.Wallet)
        .options(joinedload(models.Wallet.owner))
        .filter(
            models.Wallet.id == wallet_id,
            models.Wallet.user_id == current_user.id
        )
        .first()
    )
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    # Check idempotency
    existing_tx = idempotency_service.get_existing_transaction(db, wallet_id, idempotency_key)
    if existing_tx:
        return wallet  # return previous successful transaction

    try:
        # Lock wallet for update
        wallet_locked = lock_wallet(db, wallet_id)
        wallet_locked.balance_kobo += payload.amount_kobo

        # Create transaction
        tx = models.Transaction(
            wallet_id=wallet_locked.id,
            amount_kobo=payload.amount_kobo,
            type="deposit",  # or use TransactionType.deposit if using Enum
            currency="NGN",
            idempotency_key=idempotency_key,
            status="success",
        )
        db.add(tx)
        db.commit()
        db.refresh(wallet_locked)

        return wallet_locked

    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Duplicate transaction")



# -------------------- WITHDRAW --------------------
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

    # Fetch wallet with owner eagerly loaded
    wallet = (
        db.query(models.Wallet)
        .options(joinedload(models.Wallet.owner))
        .filter(
            models.Wallet.id == wallet_id,
            models.Wallet.user_id == current_user.id
        )
        .first()
    )
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    # Check idempotency
    existing_tx = idempotency_service.get_existing_transaction(db, wallet_id, idempotency_key)
    if existing_tx:
        return wallet  # return previous successful transaction

    try:
        wallet_locked = lock_wallet(db, wallet_id)
        if wallet_locked.balance_kobo < payload.amount_kobo:
            raise HTTPException(status_code=400, detail="Insufficient funds")

        wallet_locked.balance_kobo -= payload.amount_kobo

        tx = models.Transaction(
            wallet_id=wallet_locked.id,
            amount_kobo=payload.amount_kobo,
            type="withdraw",  # or TransactionType.withdraw
            currency="NGN",
            idempotency_key=idempotency_key,
            status="success",
        )
        db.add(tx)
        db.commit()
        db.refresh(wallet_locked)
        return wallet_locked

    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Duplicate transaction")

# -------------------- TRANSFER --------------------
@router.post("/transfer", response_model=schemas.TransferResponse)
def transfer(
    payload: schemas.TransferRequest,
    idempotency_key: str = Header(...),
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(database.get_db),
):
    if payload.amount_kobo <= 0:
        raise HTTPException(status_code=400, detail="Invalid amount")

    # Fetch sender wallet with owner
    sender_wallet = (
        db.query(models.Wallet)
        .options(joinedload(models.Wallet.owner))
        .filter(models.Wallet.user_id == current_user.id)
        .first()
    )
    if not sender_wallet:
        raise HTTPException(status_code=404, detail="Sender wallet not found")

    # Idempotency check
    existing_tx = idempotency_service.get_existing_transaction(db, sender_wallet.id, idempotency_key)
    if existing_tx:
        return schemas.TransferResponse(
            sender_wallet=sender_wallet,
            destination_type=payload.destination_type,
        )

    # ---------- WALLET TO WALLET ----------
    if payload.destination_type == "wallet":
        if not payload.username and not payload.phone_number:
            raise HTTPException(status_code=400, detail="Provide username or phone number")

        query = db.query(models.User)
        recipient_user = (
            query.filter(models.User.username == payload.username).first()
            if payload.username
            else query.filter(models.User.phone_number == payload.phone_number).first()
        )
        if not recipient_user:
            raise HTTPException(status_code=404, detail="Recipient not found")
        if recipient_user.id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot send to yourself")

        # Fetch recipient wallet with owner
        recipient_wallet = (
            db.query(models.Wallet)
            .options(joinedload(models.Wallet.owner))
            .filter_by(user_id=recipient_user.id)
            .first()
        )
        if not recipient_wallet:
            raise HTTPException(status_code=404, detail="Recipient wallet not found")

        # Lock both wallets
        wallets = (
            db.query(models.Wallet)
            .options(joinedload(models.Wallet.owner))
            .filter(models.Wallet.id.in_([sender_wallet.id, recipient_wallet.id]))
            .with_for_update()
            .all()
        )
        wallet_map = {w.id: w for w in wallets}
        sender = wallet_map[sender_wallet.id]
        receiver = wallet_map[recipient_wallet.id]

        if sender.balance_kobo < payload.amount_kobo:
            raise HTTPException(status_code=400, detail="Insufficient funds")

        try:
            sender.balance_kobo -= payload.amount_kobo
            receiver.balance_kobo += payload.amount_kobo

            db.add_all([
                models.Transaction(
                    wallet_id=sender.id,
                    amount_kobo=payload.amount_kobo,
                    type="transfer_out",
                    idempotency_key=f"{idempotency_key}:out",
                    operation_id=str(uuid.uuid4()),
                    status="success",
                ),
                models.Transaction(
                    wallet_id=receiver.id,
                    amount_kobo=payload.amount_kobo,
                    type="transfer_in",
                    idempotency_key=f"{idempotency_key}:in",
                    operation_id=str(uuid.uuid4()),
                    status="success",
                ),
            ])
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="Duplicate transaction")

        return schemas.TransferResponse(
            sender_wallet=sender,
            recipient_wallet=receiver,
            destination_type="wallet",
            amount_kobo=payload.amount_kobo,
        )

    # ---------- BANK TRANSFER ----------
    if payload.destination_type == "bank":

        if not payload.bank_code or not payload.account_number:
            raise HTTPException(status_code=400, detail="Bank details required")

        if sender_wallet.balance_kobo < payload.amount_kobo:
            raise HTTPException(status_code=400, detail="Insufficient funds")

        # Resolve account first
        try:
            resolved = resolve_bank_account(
                payload.account_number,
                payload.bank_code
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

        account_name = resolved.get("account_name", "Unknown")

        reference = str(uuid.uuid4())

        try:
            # Lock wallet
            wallet_locked = lock_wallet(db, sender_wallet.id)

            if wallet_locked.balance_kobo < payload.amount_kobo:
                raise HTTPException(status_code=400, detail="Insufficient funds")

            # Create pending transaction FIRST
            tx = models.Transaction(
                wallet_id=wallet_locked.id,
                amount_kobo=payload.amount_kobo,
                type=models.TransactionType.transfer_out.value,
                idempotency_key=idempotency_key,
                transfer_reference=reference,
                status=models.TransactionStatus.pending.value,
            )

            db.add(tx)
            db.flush()

            # Initiate transfer with Paystack
            initiate_transfer(
                amount_kobo=payload.amount_kobo,
                bank_code=payload.bank_code,
                account_number=payload.account_number,
                reference=reference
            )

            # Debit wallet only if Paystack accepted request
            wallet_locked.balance_kobo -= payload.amount_kobo

            db.commit()
            db.refresh(wallet_locked)

        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(e))

        return schemas.TransferResponse(
            sender_wallet=wallet_locked,
            bank_name="Resolved Bank",
            account_number=payload.account_number,
            recipient_name=account_name,
            destination_type="bank",
            amount_kobo=payload.amount_kobo,
        )
    raise HTTPException(status_code=400, detail="Invalid destination type")


@router.get("/transfer/status/{reference}")
def transfer_status(
    reference: str,
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(database.get_db),
):
    tx = (
        db.query(models.Transaction)
        .join(models.Wallet)
        .filter(
            models.Transaction.transfer_reference == reference,
            models.Wallet.user_id == current_user.id
        )
        .first()
    )

    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

   
    if tx.status == models.TransactionStatus.pending.value:
        try:
            ps_data = get_transfer_status(reference)
            tx.status = ps_data.get("status", tx.status)
            db.commit()
            db.refresh(tx)
        except Exception as e:
            print(f"Paystack verification failed: {e}")

    return {
        "reference": reference,
        "status": tx.status,
        "amount_kobo": tx.amount_kobo
    }