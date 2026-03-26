import os
import requests
from dotenv import load_dotenv

load_dotenv()

KLN_API_URL = os.getenv("KLN_API_URL")


def get_invoice_url(bank_transaction_no: str, amount: float) -> list | None:
    """เรียก KLN API เพื่อดึง list ใบเสร็จ"""
    try:
        response = requests.post(
            KLN_API_URL,
            json={"bankTransactionNo": bank_transaction_no, "amount": amount},
            timeout=10,
        )
        data = response.json()

        if data.get("statusCode") == 200 and data.get("result"):
            print(f"Invoice Result: {data['result']}")
            return data["result"]

        print(f"API Error: {data}")
        return None

    except Exception as e:
        print(f"Invoice Service Error: {e}")
        return None
