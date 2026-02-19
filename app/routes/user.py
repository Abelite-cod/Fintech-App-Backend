from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app import models, database, security
from app.schemas import UserOut

router = APIRouter()


# Get Current Logged-in User

@router.get("/me")
def get_current_user_profile(
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(database.get_db),
):
    wallet = (
        db.query(models.Wallet)
        .filter(models.Wallet.user_id == current_user.id)
        .first()
    )

    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role,
        "wallet_balance_kobo": wallet.balance_kobo if wallet else 0,
        "currency": wallet.currency if wallet else "NGN",
    }



@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    db: Session = Depends(database.get_db),
):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user
