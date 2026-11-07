import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from applications.database import get_db
from applications.models import StaffUser

SESSION_COOKIE = "tracksure_session"
CSRF_COOKIE = "tracksure_csrf"
SESSION_MAX_AGE = 12 * 60 * 60
PASSWORD_ITERATIONS = 260_000


def get_secret_key() -> bytes:
    secret = os.environ.get("TRACKSURE_SECRET_KEY", "")
    if len(secret) < 32:
        raise HTTPException(
            status_code=503,
            detail="Authentication is not configured. Set TRACKSURE_SECRET_KEY to at least 32 characters.",
        )
    return secret.encode("utf-8")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    return ".".join(
        (
            str(PASSWORD_ITERATIONS),
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(derived).decode("ascii"),
        )
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        iterations, salt_text, expected_text = stored_hash.split(".")
        salt = base64.urlsafe_b64decode(salt_text)
        expected = base64.urlsafe_b64decode(expected_text)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, int(iterations)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def _encode_token(user_id: int, secret: bytes) -> str:
    payload = json.dumps(
        {"sub": user_id, "exp": int(time.time()) + SESSION_MAX_AGE},
        separators=(",", ":"),
    ).encode("utf-8")
    encoded = base64.urlsafe_b64encode(payload).rstrip(b"=")
    signature = hmac.new(secret, encoded, hashlib.sha256).digest()
    return (
        encoded.decode("ascii")
        + "."
        + base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
    )


def _decode_token(token: str, secret: bytes) -> int | None:
    try:
        encoded_text, signature_text = token.split(".", 1)
        encoded = encoded_text.encode("ascii")
        signature = base64.urlsafe_b64decode(
            signature_text + "=" * (-len(signature_text) % 4)
        )
        expected = hmac.new(secret, encoded, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            return None
        payload = base64.urlsafe_b64decode(
            encoded_text + "=" * (-len(encoded_text) % 4)
        )
        data = json.loads(payload)
        if int(data["exp"]) <= int(time.time()):
            return None
        return int(data["sub"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


def set_login_cookies(response, user_id: int, request: Request) -> str:
    secret = get_secret_key()
    csrf_token = secrets.token_urlsafe(32)
    secure = request.url.scheme == "https"
    response.set_cookie(
        SESSION_COOKIE,
        _encode_token(user_id, secret),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=secure,
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=SESSION_MAX_AGE,
        httponly=False,
        secure=secure,
        samesite="strict",
        path="/",
    )
    return csrf_token


def clear_login_cookies(response, request: Request) -> None:
    secure = request.url.scheme == "https"
    response.delete_cookie(
        SESSION_COOKIE, path="/", secure=secure, httponly=True, samesite="strict"
    )
    response.delete_cookie(
        CSRF_COOKIE, path="/", secure=secure, httponly=False, samesite="strict"
    )


def verify_csrf(request: Request) -> None:
    cookie_token = request.cookies.get(CSRF_COOKIE, "")
    header_token = request.headers.get("x-csrf-token", "")
    if not cookie_token or not header_token or not hmac.compare_digest(
        cookie_token, header_token
    ):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")


def get_current_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> StaffUser:
    user = get_optional_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Login required")
    return user


def get_optional_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> StaffUser | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    user_id = _decode_token(token, get_secret_key())
    if user_id is None:
        return None
    user = db.query(StaffUser).filter(StaffUser.id == user_id).first()
    if user is None or not user.is_active:
        return None
    return user


def require_operator(
    user: Annotated[StaffUser, Depends(get_current_user)],
) -> StaffUser:
    if user.role not in {"admin", "operator"}:
        raise HTTPException(status_code=403, detail="Operator access required")
    return user


def require_admin(
    user: Annotated[StaffUser, Depends(get_current_user)],
) -> StaffUser:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required")
    return user
