# app/services/utils.py
import os
from datetime import datetime
import base64

def ts() -> str:
    from datetime import datetime
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

def data_url_to_bytes(data_url: str) -> bytes:
    if "," in data_url:
        header, b64 = data_url.split(",", 1)
        return base64.b64decode(b64)
    return base64.b64decode(data_url)

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)
