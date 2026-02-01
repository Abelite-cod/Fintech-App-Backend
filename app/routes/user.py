from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app import models, database, security
from app.schemas import UserCreate, UserOut

router = APIRouter()







@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(database.get_db)):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user
