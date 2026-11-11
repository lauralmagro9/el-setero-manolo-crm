"""Helpers to sign Supabase-like JWTs with a throw-away key."""

import time

import jwt
from cryptography.hazmat.primitives.asymmetric import ec


def generate_key() -> ec.EllipticCurvePrivateKey:
    """Return a new EC private key (Supabase signs with ES256)."""
    return ec.generate_private_key(ec.SECP256R1())


def make_token(
    key,
    *,
    email: str | None = "laura@example.com",
    audience: str = "authenticated",
    expires_in: int = 3600,
    algorithm: str = "ES256",
    subject: str = "11111111-1111-1111-1111-111111111111",
) -> str:
    """Sign a token like the ones Supabase Auth issues."""
    claims = {"sub": subject, "aud": audience, "exp": int(time.time()) + expires_in}
    if email:
        claims["email"] = email
    return jwt.encode(claims, key, algorithm=algorithm)
