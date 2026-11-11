"""Validation of the Supabase JWT sent by the frontend (Authorization: Bearer <token>)."""

from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from ..audit import set_actor
from ..config import settings

bearer_scheme = HTTPBearer(auto_error=False)


class AuthUser(BaseModel):
    """The authenticated user, as stated by the token."""

    id: str
    email: str | None = None


@lru_cache
def _jwks_client() -> jwt.PyJWKClient:
    """Return the (cached) client that downloads Supabase's public signing keys."""
    return jwt.PyJWKClient(settings.supabase.jwks_url, cache_keys=True)


def get_signing_key(token: str, algorithm: str):
    """Return the key that must have signed `token`.

    Legacy projects sign with a shared secret (HS256); current ones use asymmetric keys
    published at supabase.jwks_url. Tests replace this function with a local key.
    """
    if algorithm == "HS256":
        if not settings.supabase.jwt_secret:
            raise jwt.InvalidAlgorithmError("HS256 no está habilitado")
        return settings.supabase.jwt_secret
    if algorithm not in settings.supabase.jwks_algorithms:
        raise jwt.InvalidAlgorithmError(f"Algoritmo no permitido: {algorithm}")
    return _jwks_client().get_signing_key_from_jwt(token).key


def decode_token(token: str) -> AuthUser:
    """Verify signature, expiry and audience of `token`; raise jwt.PyJWTError when invalid."""
    algorithm = jwt.get_unverified_header(token).get("alg", "")
    key = get_signing_key(token, algorithm)
    claims = jwt.decode(
        token, key, algorithms=[algorithm], audience=settings.supabase.jwt_audience,
        options={"require": ["exp", "sub"]},
    )
    return AuthUser(id=claims["sub"], email=claims.get("email"))


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthUser:
    """FastAPI dependency: return the logged-in user or answer 401."""
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED, "No autenticado", headers={"WWW-Authenticate": "Bearer"}
    )
    if credentials is None:
        raise unauthorized
    try:
        return decode_token(credentials.credentials)
    except (jwt.PyJWTError, OSError):  # OSError: the key server cannot be reached
        raise unauthorized from None


async def bind_actor(user: AuthUser = Depends(current_user)) -> None:
    """Record the logged-in user as the author of everything written during this request.

    It is async on purpose: a context variable set in a sync dependency would not reach the endpoint.
    """
    set_actor(user.email or user.id)
