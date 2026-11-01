"""Password hashing and token signing — stdlib only.

- Passwords: PBKDF2-HMAC-SHA256, 200k iterations, per-user random salt. Stored as
  "pbkdf2_sha256$iterations$salt_hex$hash_hex". No plaintext or reversible storage.
- Tokens: compact JWT (HS256) signed with SECRET_KEY. Stateless, 30-day expiry.
  The signature and expiry are verified on every request. In production set SECRET_KEY
  from the environment; a random fallback keeps local dev working but tokens then do
  not survive restarts (documented, intentional).
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time

ITERATIONS = 200_000
TOKEN_TTL_SECONDS = 30 * 24 * 3600

_SECRET_CACHE: bytes | None = None

def _secret_key() -> bytes:
    global _SECRET_CACHE
    if os.environ.get("SECRET_KEY"):
        return os.environ["SECRET_KEY"].encode()
    if _SECRET_CACHE is None:
        _SECRET_CACHE = secrets.token_bytes(32)
    return _SECRET_CACHE

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${dk.hex()}"

def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))

def make_token(user_id: str, role: str) -> str:
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64(json.dumps({"sub": user_id, "role": role,
                               "exp": int(time.time()) + TOKEN_TTL_SECONDS}).encode())
    signing = f"{header}.{payload}".encode()
    sig = _b64(hmac.new(_secret_key(), signing, hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"

def decode_token(token: str) -> dict | None:
    try:
        header, payload, sig = token.split(".")
        signing = f"{header}.{payload}".encode()
        expected = _b64(hmac.new(_secret_key(), signing, hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        claims = json.loads(_unb64(payload))
        if claims.get("exp", 0) < time.time():
            return None
        return claims
    except (ValueError, KeyError):
        return None
