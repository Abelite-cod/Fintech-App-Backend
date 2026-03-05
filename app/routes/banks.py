from fastapi import APIRouter, HTTPException
from app.services.paystack_service import get_banks

router = APIRouter(prefix="/banks", tags=["Banks"])

@router.get("/")
def list_banks():
    response = get_banks()

    if not response.get("status"):
        raise HTTPException(status_code=400, detail="Failed to fetch banks")

    return [
        {
            "name": bank["name"],
            "code": bank["code"]
        }
        for bank in response["data"]
    ]