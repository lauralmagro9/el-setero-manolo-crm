"""Tests for the JWT authentication of the API."""

import jwt
import pytest

from crm.api import auth
from crm.api.auth import get_signing_key as real_get_signing_key
from crm.config import settings

from tests.utils.auth import generate_key, make_token


class TestAuthentication:
    """Tests for the current_user dependency."""

    def test_0_health_is_public(self, anonymous_client):
        """The liveness probe does not need a token."""
        assert anonymous_client.get("/health").status_code == 200

    def test_1_missing_token_is_rejected(self, anonymous_client):
        """A request without Authorization header gets 401."""
        assert anonymous_client.get("/api/companies").status_code == 401

    def test_2_valid_token_is_accepted(self, client):
        """A correctly signed, unexpired token with the right audience is accepted."""
        assert client.get("/api/companies").status_code == 200

    def test_3_token_signed_with_another_key_is_rejected(self, anonymous_client):
        """A token signed by an unknown key fails signature verification."""
        token = make_token(generate_key())
        response = anonymous_client.get("/api/companies", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401

    def test_4_expired_token_is_rejected(self, anonymous_client, signing_key):
        """A token whose expiry is in the past gets 401."""
        token = make_token(signing_key, expires_in=-10)
        response = anonymous_client.get("/api/companies", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401

    def test_5_wrong_audience_is_rejected(self, anonymous_client, signing_key):
        """A token issued for another audience gets 401."""
        token = make_token(signing_key, audience="other")
        response = anonymous_client.get("/api/companies", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401

    def test_6_garbage_token_is_rejected(self, anonymous_client):
        """A string that is not a JWT gets 401."""
        response = anonymous_client.get("/api/companies", headers={"Authorization": "Bearer nope"})
        assert response.status_code == 401

    def test_7_hs256_is_rejected_without_legacy_secret(self):
        """HS256 tokens are refused unless supabase.jwt_secret is configured."""
        token = make_token("a-shared-secret-of-sufficient-length!", algorithm="HS256")
        with pytest.raises(jwt.InvalidAlgorithmError):
            real_get_signing_key(token, "HS256")

    def test_8_hs256_is_accepted_with_legacy_secret(self, monkeypatch):
        """With supabase.jwt_secret set, the shared secret is the verification key."""
        monkeypatch.setitem(settings.supabase.as_dict(), "jwt_secret", "a-shared-secret-of-sufficient-length!")
        assert real_get_signing_key("t", "HS256") == "a-shared-secret-of-sufficient-length!"

    def test_9_unlisted_algorithm_is_rejected(self):
        """Algorithms outside supabase.jwks_algorithms (e.g. ES384) are refused."""
        with pytest.raises(jwt.InvalidAlgorithmError):
            real_get_signing_key("t", "ES384")

    def test_10_decode_token_returns_id_and_email(self, signing_key):
        """decode_token exposes the subject and the email of the token."""
        user = auth.decode_token(make_token(signing_key, email="manolo@example.com"))
        assert user.id == "11111111-1111-1111-1111-111111111111"
        assert user.email == "manolo@example.com"
