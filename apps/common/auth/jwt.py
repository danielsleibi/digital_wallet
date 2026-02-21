import jwt
from datetime import datetime, timedelta, timezone
from django.conf import settings
from apps.common.exceptions import AuthenticationError

def create_access_token(user_id: str) -> str:
    """Create a short-lived access token (1 hour)"""
    return _create_token(user_id, "access", timedelta(hours=1))

def create_refresh_token(user_id: str) -> str:
    """Create a long-lived refresh token (7 days)"""
    return _create_token(user_id, "refresh", timedelta(days=7))

def _create_token(user_id: str, token_type: str, delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iat": now,
        "exp": now + delta,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

def decode_token(token: str) -> dict:
    """
    Decode and verify a token.
    Raises AuthenticationError if invalid or expired.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except jwt.InvalidTokenError:
        raise AuthenticationError("Invalid token")
