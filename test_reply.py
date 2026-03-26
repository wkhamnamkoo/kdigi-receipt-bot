import os
import requests
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
uid   = "U1ab9d0557d16189cb9465a431a41d24c"  # แทนด้วย User ID จริงค่ะ

res = requests.post(
    "https://api.line.me/v2/bot/message/push",
    headers={"Authorization": f"Bearer {token}",
             "Content-Type": "application/json"},
    json={"to": uid, "messages": [{"type": "text", "text": "test ค่ะ"}]},
    timeout=10,
)
print(f"Status  : {res.status_code}")
print(f"Response: {res.text}")
