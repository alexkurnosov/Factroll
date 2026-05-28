"""
Auth0 JWT validation for the MCP HTTP layer.

Validates Bearer tokens against Auth0's JWKS endpoint. The extracted `sub`
claim is used as the canonical user identifier passed into core operations.

Set AUTH_DISABLED=true in .env to skip validation during local development.
"""
from contextvars import ContextVar

import httpx
from fastapi import HTTPException, Request
from jose import JWTError, jwt

from factroll.config import settings

# Per-request context populated by auth_middleware before each tool call.
current_user_id: ContextVar[str] = ContextVar("current_user_id", default="anonymous")
current_surface_id: ContextVar[str] = ContextVar("current_surface_id", default="default")

_jwks_cache: dict | None = None


async def _get_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache is None:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://{settings.auth0_domain}/.well-known/jwks.json",
                timeout=10,
            )
            resp.raise_for_status()
            _jwks_cache = resp.json()
    return _jwks_cache


async def validate_token(token: str) -> dict:
    """Validate an Auth0 Bearer token and return its claims."""
    jwks = await _get_jwks()

    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token header")

    rsa_key = next(
        (
            {"kty": k["kty"], "kid": k["kid"], "use": k["use"], "n": k["n"], "e": k["e"]}
            for k in jwks["keys"]
            if k["kid"] == unverified_header.get("kid")
        ),
        None,
    )
    if rsa_key is None:
        raise HTTPException(status_code=401, detail="No matching signing key")

    try:
        return jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=settings.auth0_audience,
            issuer=f"https://{settings.auth0_domain}/",
        )
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=f"Token invalid: {exc}") from exc


async def auth_middleware(request: Request, call_next):
    """
    FastAPI middleware that:
    1. Validates the Bearer token (unless AUTH_DISABLED).
    2. Sets current_user_id and current_surface_id context vars for the
       duration of the request so MCP tool handlers can read them.

    surface_id = Mcp-Session-Id header (echoed back by the client after
    the server assigns it on the first response). On first contact, the
    header is absent and a fresh UUID from the connection will be assigned
    by FastMCP; the client will echo it on subsequent requests.
    """
    import uuid as _uuid

    if settings.auth_disabled:
        user_id = "dev-user"
    else:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing Bearer token")
        claims = await validate_token(auth_header.removeprefix("Bearer "))
        user_id = claims["sub"]

    surface_id = request.headers.get("Mcp-Session-Id") or str(_uuid.uuid4())

    token_uid = current_user_id.set(user_id)
    token_sid = current_surface_id.set(surface_id)
    try:
        return await call_next(request)
    finally:
        current_user_id.reset(token_uid)
        current_surface_id.reset(token_sid)
