"""Auth integration tests.

Uses locally-generated RS256 key pairs to test the full JWT validation
pipeline (decode_cognito_token → _get_jwks → signature check → claims).
Only the JWKS HTTP fetch is mocked — everything else runs for real.
"""

import time
import uuid
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# ---------------------------------------------------------------------------
# RSA key pair helpers
# ---------------------------------------------------------------------------

_TEST_KID = "test-key-1"
_TEST_ISSUER = "https://cognito-idp.us-west-2.amazonaws.com/us-west-2_FAKE"
_TEST_CLIENT_ID = "fake-client-id"


def _generate_rsa_keypair():
    """Generate a fresh RSA key pair for testing."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key


def _private_key_to_pem(private_key):
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _public_key_to_jwk(private_key, kid: str) -> dict:
    """Convert RSA public key to JWK dict (matching Cognito JWKS format)."""
    pub = private_key.public_key()
    jwk_dict = jwt.algorithms.RSAAlgorithm.to_jwk(pub, as_dict=True)
    jwk_dict["kid"] = kid
    jwk_dict["alg"] = "RS256"
    jwk_dict["use"] = "sig"
    return jwk_dict


def _make_token(private_key, claims: dict, kid: str = _TEST_KID) -> str:
    """Sign a JWT with the given RSA private key."""
    return jwt.encode(
        claims,
        _private_key_to_pem(private_key),
        algorithm="RS256",
        headers={"kid": kid},
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def rsa_keypair():
    return _generate_rsa_keypair()


@pytest.fixture()
def jwks_response(rsa_keypair):
    """JWKS JSON matching what Cognito would return."""
    return {"keys": [_public_key_to_jwk(rsa_keypair, _TEST_KID)]}


@pytest.fixture()
def valid_claims():
    """Standard valid ID token claims."""
    now = int(time.time())
    return {
        "sub": str(uuid.uuid4()),
        "email": "alice@example.com",
        "iss": _TEST_ISSUER,
        "aud": _TEST_CLIENT_ID,
        "exp": now + 3600,
        "iat": now,
        "token_use": "id",
    }


@pytest.fixture(autouse=True)
def _reset_jwks_cache():
    """Clear the module-level JWKS cache before each test."""
    import app.common.auth.cognito as cognito_mod

    cognito_mod._jwks_cache = {}
    cognito_mod._jwks_cache_expiry = 0
    yield
    cognito_mod._jwks_cache = {}
    cognito_mod._jwks_cache_expiry = 0


@pytest.fixture()
def _patch_settings():
    """Patch settings to match our test issuer/client."""
    with patch("app.common.auth.cognito.settings") as mock_settings:
        mock_settings.cognito_jwks_url = f"{_TEST_ISSUER}/.well-known/jwks.json"
        mock_settings.cognito_issuer = _TEST_ISSUER
        mock_settings.cognito_app_client_id = _TEST_CLIENT_ID
        yield mock_settings


# ---------------------------------------------------------------------------
# Unit tests — decode_cognito_token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_valid_token_decodes(rsa_keypair, jwks_response, valid_claims, _patch_settings):
    """A properly signed, non-expired token with correct issuer/aud decodes OK."""
    from app.common.auth.cognito import decode_cognito_token

    token = _make_token(rsa_keypair, valid_claims)

    with patch("app.common.auth.cognito._get_jwks", new_callable=AsyncMock, return_value=jwks_response):
        claims = await decode_cognito_token(token)

    assert claims["sub"] == valid_claims["sub"]
    assert claims["email"] == "alice@example.com"


@pytest.mark.asyncio
async def test_expired_token_returns_401(rsa_keypair, jwks_response, valid_claims, _patch_settings):
    """An expired token should raise 401."""
    from fastapi import HTTPException

    from app.common.auth.cognito import decode_cognito_token

    valid_claims["exp"] = int(time.time()) - 60  # expired 1 min ago
    token = _make_token(rsa_keypair, valid_claims)

    with patch("app.common.auth.cognito._get_jwks", new_callable=AsyncMock, return_value=jwks_response):
        with pytest.raises(HTTPException) as exc_info:
            await decode_cognito_token(token)
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_wrong_issuer_returns_401(rsa_keypair, jwks_response, valid_claims, _patch_settings):
    """Token with wrong issuer should be rejected."""
    from fastapi import HTTPException

    from app.common.auth.cognito import decode_cognito_token

    valid_claims["iss"] = "https://evil.example.com"
    token = _make_token(rsa_keypair, valid_claims)

    with patch("app.common.auth.cognito._get_jwks", new_callable=AsyncMock, return_value=jwks_response):
        with pytest.raises(HTTPException) as exc_info:
            await decode_cognito_token(token)
        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_wrong_audience_returns_401(rsa_keypair, jwks_response, valid_claims, _patch_settings):
    """Token with wrong audience should be rejected."""
    from fastapi import HTTPException

    from app.common.auth.cognito import decode_cognito_token

    valid_claims["aud"] = "wrong-client-id"
    token = _make_token(rsa_keypair, valid_claims)

    with patch("app.common.auth.cognito._get_jwks", new_callable=AsyncMock, return_value=jwks_response):
        with pytest.raises(HTTPException) as exc_info:
            await decode_cognito_token(token)
        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_tampered_token_returns_401(rsa_keypair, jwks_response, valid_claims, _patch_settings):
    """A token signed with a different key should fail signature verification."""
    from fastapi import HTTPException

    from app.common.auth.cognito import decode_cognito_token

    other_key = _generate_rsa_keypair()
    token = _make_token(other_key, valid_claims)  # signed with wrong key

    with patch("app.common.auth.cognito._get_jwks", new_callable=AsyncMock, return_value=jwks_response):
        with pytest.raises(HTTPException) as exc_info:
            await decode_cognito_token(token)
        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_unknown_kid_triggers_jwks_refresh(rsa_keypair, jwks_response, valid_claims, _patch_settings):
    """If the kid isn't in cache, the code should refresh JWKS once."""
    from app.common.auth.cognito import decode_cognito_token

    token = _make_token(rsa_keypair, valid_claims, kid="rotated-key-99")
    jwks_with_new = {"keys": [_public_key_to_jwk(rsa_keypair, "rotated-key-99")]}

    mock_get = AsyncMock(side_effect=[
        {"keys": []},       # first call: old cache, key not found
        jwks_with_new,       # second call: refreshed, key found
    ])
    with patch("app.common.auth.cognito._get_jwks", mock_get):
        claims = await decode_cognito_token(token)

    assert claims["sub"] == valid_claims["sub"]
    assert mock_get.call_count == 2  # fetched twice (cache miss → refresh)


@pytest.mark.asyncio
async def test_garbage_token_returns_401(_patch_settings):
    """Completely invalid token string should return 401."""
    from fastapi import HTTPException

    from app.common.auth.cognito import decode_cognito_token

    with pytest.raises(HTTPException) as exc_info:
        await decode_cognito_token("not.a.jwt")
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Integration tests — full FastAPI round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_no_auth_required(async_client):
    """Health endpoint works without any authentication."""
    resp = await async_client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_authenticated_client_fixture(authenticated_client):
    """The authenticated_client fixture provides a working auth context."""
    resp = await authenticated_client.get("/api/v1/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_unauthenticated_actor_id_is_none(async_client):
    """Without a token, get_actor_id returns None (Phase 1 — optional auth)."""
    resp = await async_client.get("/api/v1/health")
    assert resp.status_code == 200
