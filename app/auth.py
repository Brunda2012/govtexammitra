"""Authentication dependencies.

Multi-user: register/login issue HS256 tokens (app/security.py); requests present
"Authorization: Bearer <token>". resolve_user returns the authenticated user id or
None — routes decide whether auth is required. The old fixed "local" principal is
retained ONLY when the server runs with GOVTEXAMMITRA_LOCAL=1 (single-user mode);
the public deployment never sets it, so personal data is always user-scoped.
"""
import os
import sqlite3
import re

from starlette.requests import Request

from .security import decode_token

LOCAL_USER = "local"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def resolve_user(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        claims = decode_token(header[7:])
        if claims and claims.get("sub"):
            return claims["sub"]
        return None
    if os.environ.get("GOVTEXAMMITRA_LOCAL") == "1":
        return LOCAL_USER
    return None

def authenticate(conn: sqlite3.Connection, email: str, password: str) -> dict | None:
    row = conn.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),)).fetchone()
    if not row:
        return None
    from .security import verify_password
    if not verify_password(password, row["password_hash"]):
        return None
    return {"id": row["id"], "email": row["email"], "role": row["role"]}

def register(conn: sqlite3.Connection, email: str, password: str) -> dict:
    from .security import hash_password
    email = email.strip().lower()
    if not EMAIL_RE.match(email):
        raise ValueError("Enter a valid email address")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    import uuid
    uid = uuid.uuid4().hex
    if conn.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
        raise ValueError("An account with this email already exists")
    try:
        conn.execute("INSERT INTO users (id,email,password_hash,role) VALUES (?,?,?,?)",
                     (uid, email, hash_password(password), "user"))
        conn.commit()
    except Exception as exc:  # race with a concurrent registration (sqlite or psycopg)
        conn.rollback()
        if conn.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            raise ValueError("An account with this email already exists")
        raise exc
    return {"id": uid, "email": email, "role": "user"}
