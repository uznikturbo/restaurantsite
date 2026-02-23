import base64
import hashlib
import os

from dotenv import load_dotenv

load_dotenv()

# ── Flask config ───────────────────────────────────────────────────────────────


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URI")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024

# ── LiqPay ─────────────────────────────────────────────────────────────────────

LIQPAY_PUBLIC_KEY = os.getenv("LIQPAY_PUBLIC_KEY")
LIQPAY_PRIVATE_KEY = os.getenv("LIQPAY_PRIVATE_KEY")
SERVER_URL = os.getenv("SERVER_URL")

# ── File uploads ───────────────────────────────────────────────────────────────

UPLOAD = "static/images"
os.makedirs(UPLOAD, exist_ok=True)
ALLOWED_EXT = {"png", "jpg", "jpeg", "webp"}


# ── Helpers ────────────────────────────────────────────────────────────────────

def verify_liqpay_signature(data_b64: str, signature: str) -> bool:
    if not LIQPAY_PRIVATE_KEY:
        return False
    key = LIQPAY_PRIVATE_KEY.encode("utf-8")
    data = data_b64.encode("utf-8")
    expected = base64.b64encode(
        hashlib.sha1(key + data + key).digest()
    ).decode("ascii")
    return expected == signature


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT