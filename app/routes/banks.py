from fastapi import APIRouter
from app.services.paystack_service import get_banks

router = APIRouter(prefix="/banks", tags=["Banks"])

@router.get("/")
def list_banks():
    response = get_banks()
    return response
