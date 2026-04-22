"""Shared FastAPI dependencies (auth, etc.)."""
from fastapi import Header, HTTPException, status

from app.config import get_settings


async def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """Enforce a shared API key on sensitive endpoints.

    - If the server has no `API_KEY` configured, we deliberately 503 rather
      than silently leaving the endpoint open. This forces the operator to
      make an explicit choice.
    - If the caller does not present the correct key, we 401.
    """
    settings = get_settings()
    if not settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API_KEY is not configured on the server; this endpoint is disabled.",
        )
    if not x_api_key or x_api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
