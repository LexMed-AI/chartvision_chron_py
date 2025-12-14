"""Authentication middleware for ERE API"""
import os
import secrets
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials


def get_api_key() -> str:
    """Get API key from environment or use default.

    Returns:
        API key string
    """
    return os.environ.get("API_KEY", "ere-api-key-2024")


async def verify_token(
    credentials: HTTPAuthorizationCredentials
) -> str:
    """Verify API token.

    Args:
        credentials: HTTP Bearer token credentials

    Returns:
        Verified token string

    Raises:
        HTTPException: 401 if token is invalid
    """
    expected_token = get_api_key()
    if not secrets.compare_digest(credentials.credentials, expected_token):
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials
