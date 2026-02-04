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


def initiate_transfer(amount_kobo, bank_code, account_number, reference):

    if USE_MOCK:
        from app.mock_paystack.routes import mock_transfer
        return mock_transfer(reference, succeed=True)
    
    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET}",
        "Content-Type": "application/json"
    }

    # Step 1: Create recipient
    recipient = requests.post(
        f"{BASE_URL}/transferrecipient",
        json={
            "type": "nuban",
            "name": "User Withdrawal",
            "account_number": account_number,
            "bank_code": bank_code,
            "currency": "NGN"
        },
        headers=headers
    ).json()

    recipient_code = recipient["data"]["recipient_code"]

    # Step 2: Transfer
    transfer = requests.post(
        f"{BASE_URL}/transfer",
        json={
            "source": "balance",
            "amount": amount_kobo,
            "recipient": recipient_code,
            "reference": reference
        },
        headers=headers
    )

    return transfer.json()




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

