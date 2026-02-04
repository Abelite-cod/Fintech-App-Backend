import requests
import json

def send_webhook(event: str, reference: str, amount_kobo: int, email: str):
    payload = {
        "event": event,
        "data": {
            "reference": reference,
            "amount": amount_kobo,
            "currency": "NGN",
            "customer": {
                "email": email
            }
        }
    }

    requests.post(
        "http://localhost:8000/webhook/paystack",
        json=payload,
        headers={
            "x-paystack-signature": "mock"
        }
    )
