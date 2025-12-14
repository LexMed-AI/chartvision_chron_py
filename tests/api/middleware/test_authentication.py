"""Tests for authentication middleware"""
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api.middleware.authentication import verify_token, get_api_key


class TestAuthentication:
    """Test API token verification"""

    @pytest.mark.asyncio
    async def test_verify_token_with_valid_token(self):
        """Should accept valid API token"""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=get_api_key()
        )
        result = await verify_token(credentials)
        assert result == get_api_key()

    @pytest.mark.asyncio
    async def test_verify_token_with_invalid_token(self):
        """Should reject invalid API token"""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="invalid-token"
        )
        with pytest.raises(HTTPException) as exc_info:
            await verify_token(credentials)
        assert exc_info.value.status_code == 401
        assert "Invalid authentication credentials" in str(exc_info.value.detail)

    def test_get_api_key_from_env(self, monkeypatch):
        """Should read API key from environment"""
        monkeypatch.setenv("API_KEY", "custom-api-key-123")
        assert get_api_key() == "custom-api-key-123"

    def test_get_api_key_default(self, monkeypatch):
        """Should use default API key if env not set"""
        monkeypatch.delenv("API_KEY", raising=False)
        assert get_api_key() == "ere-api-key-2024"
