"""Persisted account authentication and role checks for the FastAPI service."""

import base64
import binascii
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .db_models import UserAccount


TOKEN_ISSUER = "safesite-risk-intelligence"
TOKEN_AUDIENCE = "safesite-api"
TOKEN_TTL_SECONDS = 60 * 60
PASSWORD_SCHEME = "scrypt"
_bearer = HTTPBearer(auto_error=False)


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not normalized or len(normalized) > 255 or "@" not in normalized:
        raise ValueError("A valid email address is required")
    return normalized


def hash_password(password: str) -> str:
    encoded = password.encode("utf-8")
    if len(password) < 8 or len(encoded) > 1024:
        raise ValueError("Password must contain at least 8 characters and at most 1024 UTF-8 bytes")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(encoded, salt=salt, n=16384, r=8, p=1, dklen=32)
    return f"{PASSWORD_SCHEME}$16384$8$1${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        scheme, n, r, p, salt_hex, digest_hex = stored_hash.split("$")
        if scheme != PASSWORD_SCHEME or (n, r, p) != ("16384", "8", "1"):
            return False
        encoded = password.encode("utf-8")
        if len(encoded) > 1024:
            return False
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.scrypt(
            encoded, salt=bytes.fromhex(salt_hex), n=16384, r=8, p=1, dklen=len(expected)
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, MemoryError):
        return False


def _signing_secret() -> bytes:
    secret = os.getenv("SAFESITE_JWT_SECRET", "").encode("utf-8")
    if len(secret) < 32:
        raise HTTPException(status_code=503, detail="Authentication is not configured")
    return secret


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _decode_b64(value: str) -> bytes:
    return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)


def issue_access_token(user_id: str) -> str:
    """Issue a short-lived HS256 JWT containing identity, not an authoritative role."""

    now = int(time.time())
    header = _b64(b'{"alg":"HS256","typ":"JWT"}')
    payload = _b64(json.dumps({
        "sub": user_id, "iss": TOKEN_ISSUER, "aud": TOKEN_AUDIENCE,
        "iat": now, "exp": now + TOKEN_TTL_SECONDS,
    }, separators=(",", ":")).encode("utf-8"))
    content = f"{header}.{payload}"
    signature = _b64(hmac.digest(_signing_secret(), content.encode("ascii"), "sha256"))
    return f"{content}.{signature}"


def decode_access_token(token: str) -> str:
    """Validate JWT signature, fixed algorithm, issuer, audience, and expiration."""

    try:
        header, payload, signature = token.split(".")
        if len(token) > 4096 or not all((header, payload, signature)):
            raise ValueError("Malformed token")
        content = f"{header}.{payload}".encode("ascii")
        expected = hmac.digest(_signing_secret(), content, "sha256")
        if not hmac.compare_digest(_decode_b64(signature), expected):
            raise ValueError("Invalid signature")
        decoded_header = json.loads(_decode_b64(header))
        claims = json.loads(_decode_b64(payload))
        now = int(time.time())
        if decoded_header != {"alg": "HS256", "typ": "JWT"}:
            raise ValueError("Unsupported JWT header")
        if (claims.get("iss") != TOKEN_ISSUER or claims.get("aud") != TOKEN_AUDIENCE
                or type(claims.get("exp")) is not int or claims["exp"] <= now
                or type(claims.get("iat")) is not int or claims["iat"] > now
                or not isinstance(claims.get("sub"), str) or not claims["sub"]):
            raise ValueError("Invalid JWT claims")
        return claims["sub"]
    except HTTPException:
        raise
    except (ValueError, TypeError, AttributeError, UnicodeError, binascii.Error) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session | None, Depends(get_db)],
) -> UserAccount:
    if credentials is None:
        raise HTTPException(
            status_code=401, detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = decode_access_token(credentials.credentials)
    if db is None:
        raise HTTPException(status_code=503, detail="Database is not configured")
    user = db.get(UserAccount, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=401, detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_safety_manager(
    user: Annotated[UserAccount, Depends(get_current_user)],
) -> UserAccount:
    if user.role not in {"safety_officer", "admin"}:
        raise HTTPException(status_code=403, detail="Safety Officer or Admin role required")
    return user


def require_admin(
    user: Annotated[UserAccount, Depends(get_current_user)],
) -> UserAccount:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


def find_user_by_email(db: Session, email: str) -> UserAccount | None:
    return db.execute(select(UserAccount).where(UserAccount.email == email)).scalar_one_or_none()
