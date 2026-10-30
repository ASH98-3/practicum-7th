"""Password hashing (scrypt, stdlib) + server-side sessions in an HttpOnly cookie."""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, Response

from app.db import conn

SESSION_DAYS = 7
COOKIE_KW = dict(
    httponly=True,
    samesite="lax",
    path="/",
    max_age=SESSION_DAYS * 86400,
)


def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"{salt.hex()}:{h.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    salt_hex, h_hex = stored.split(":")
    h = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1)
    return hmac.compare_digest(h.hex(), h_hex)


def _h(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()   # DB never stores raw tokens


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def start_session(response: Response, user_id: int) -> None:
    token = secrets.token_urlsafe(32)
    exp = (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)).isoformat()
    with conn() as c:
        c.execute("INSERT INTO sessions VALUES(?,?,?)", (_h(token), user_id, exp))
    response.set_cookie("session", token, **COOKIE_KW)


def end_session(response: Response, token: Optional[str]) -> None:
    if token:
        with conn() as c:
            c.execute("DELETE FROM sessions WHERE token_hash=?", (_h(token),))
    response.delete_cookie("session", path="/")


def current_user(session: Optional[str] = Cookie(None)) -> dict:
    if not session:
        raise HTTPException(401, "Please log in.")
    with conn() as c:
        row = c.execute("SELECT u.*, s.expires_at FROM sessions s JOIN users u ON u.id=s.user_id "
                        "WHERE s.token_hash=?", (_h(session),)).fetchone()
    if not row or row["expires_at"] < _now():
        raise HTTPException(401, "Session expired. Please log in again.")
    return dict(row)


def require_role(role: str):
    def dep(user: dict = Depends(current_user)) -> dict:
        if user["role"] != role:
            raise HTTPException(403, f"This area is only for {role} accounts.")
        return user
    return dep
