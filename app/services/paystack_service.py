import requests
import os
from dotenv import load_dotenv

load_dotenv()
PAYSTACK_SECRET = os.getenv("PAYSTACK_SECRET_KEY")
USE_MOCK = os.getenv("USE_MOCK_PAYSTACK") == "true"
BASE_URL = "https://api.paystack.co"

headers = {
    "Authorization": f"Bearer {PAYSTACK_SECRET}",
    "Content-Type": "application/json"
}


def initiate_transfer(amount_kobo: int, bank_code: str, account_number: str, reference: str):

    if USE_MOCK:
        from app.mock_paystack.routes import mock_transfer
        return mock_transfer(reference, succeed=True)

    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET}",
        "Content-Type": "application/json"
    }

    # 1️⃣ Create transfer recipient
    recipient_resp = requests.post(
        f"{BASE_URL}/transferrecipient",
        json={
            "type": "nuban",
            "name": "Wallet Withdrawal",
            "account_number": account_number,
            "bank_code": bank_code,
            "currency": "NGN"
        },
        headers=headers,
        timeout=15
    ).json()

    if not recipient_resp.get("status"):
        raise ValueError(recipient_resp.get("message"))

    recipient_code = recipient_resp["data"]["recipient_code"]

    # 2️⃣ Initiate transfer
    transfer_resp = requests.post(
        f"{BASE_URL}/transfer",
        json={
            "source": "balance",
            "amount": amount_kobo,
            "recipient": recipient_code,
            "reference": reference
        },
        headers=headers,
        timeout=15
    ).json()

    if not transfer_resp.get("status"):
        raise ValueError(transfer_resp.get("message"))

    return transfer_resp

def get_transfer_status(reference: str):
    """Fetch the current status of a transfer from Paystack."""
    if USE_MOCK:
        from app.mock_paystack.routes import mock_transfer_status
        return mock_transfer_status(reference)

    response = requests.get(
        f"{BASE_URL}/transfer/{reference}",
        headers=headers,
        timeout=15
    )

    data = response.json()
    if not data.get("status"):
        raise ValueError(data.get("message", "Failed to fetch transfer status"))

    # Paystack returns data.status as 'success', 'failed', or 'pending'
    return {
        "status": data["data"]["status"],
        "amount_kobo": data["data"]["amount"]
    }


def resolve_bank_account(account_number: str, bank_code: str):
    response = requests.get(
        f"{BASE_URL}/bank/resolve",
        params={
            "account_number": account_number,
            "bank_code": bank_code
        },
        headers=headers,
        timeout=15
    )

    data = response.json()

    if not data.get("status"):
        raise ValueError(data.get("message", "Account resolution failed"))

    return {
    "account_name": data["data"]["account_name"],
    "account_number": data["data"]["account_number"],
    "bank_code": bank_code
}
    
