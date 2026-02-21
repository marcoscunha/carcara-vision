"""OAuth2/Keycloak authentication module.

This module provides JWT token validation and user authentication
using Keycloak as the identity provider.

Usage:
    from ...core.security import AuthenticatedUser, AdminUser

    @router.get("/protected")
    def protected_endpoint(current_user: AuthenticatedUser):
        return {"user": current_user.username}

    @router.delete("/admin-only")
    def admin_endpoint(admin_user: AdminUser):
        # Only admin role can access this
        return {"admin": admin_user.username}
"""

import logging
from typing import Annotated

import httpx
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from fastapi.security import OAuth2AuthorizationCodeBearer
from jose import JWTError
from jose import jwt
from pydantic import BaseModel

from ..config import settings

logger = logging.getLogger(__name__)


class TokenPayload(BaseModel):
    """JWT token payload from Keycloak."""

    sub: str  # Subject (User ID)
    email: str | None = None
    preferred_username: str | None = None
    roles: list[str] = []
    exp: int  # Expiration timestamp
    iat: int | None = None  # Issued at
    iss: str | None = None  # Issuer


class CurrentUser(BaseModel):
    """Authenticated user information extracted from token."""

    id: str
    username: str
    email: str | None = None
    roles: list[str] = []

    @property
    def is_admin(self) -> bool:
        """Check if user has admin role."""
        return "admin" in self.roles

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role."""
        return role in self.roles


DEV_USER = CurrentUser(
    id="dev-user",
    username="dev",
    email="dev@local",
    roles=["admin"],
)


# OAuth2 scheme configuration
# This is used by FastAPI to generate OpenAPI docs and extract the token
oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"{settings.KEYCLOAK_INTERNAL_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/auth",
    tokenUrl=f"{settings.KEYCLOAK_INTERNAL_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/token",
    auto_error=True,
)


class JWKSClient:
    """Client for fetching and caching JWKS from Keycloak."""

    _cache: dict | None = None
    _cache_url: str | None = None

    @classmethod
    def get_jwks(cls) -> dict:
        """Fetch JWKS from Keycloak (cached)."""
        jwks_url = f"{settings.KEYCLOAK_INTERNAL_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/certs"

        # Return cached if URL hasn't changed
        if cls._cache is not None and cls._cache_url == jwks_url:
            return cls._cache

        try:
            response = httpx.get(jwks_url, timeout=10.0)
            response.raise_for_status()
            cls._cache = response.json()
            cls._cache_url = jwks_url
            logger.info(f"Fetched JWKS from {jwks_url}")
            return cls._cache
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch JWKS from {jwks_url}: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service unavailable",
            )

    @classmethod
    def clear_cache(cls) -> None:
        """Clear JWKS cache (useful for testing or key rotation)."""
        cls._cache = None
        cls._cache_url = None


def decode_token(token: str) -> TokenPayload:
    """Decode and validate JWT token from Keycloak.

    Args:
        token: JWT access token string

    Returns:
        TokenPayload with user information

    Raises:
        HTTPException: If token is invalid or expired
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Get JWKS for token verification
        jwks = JWKSClient.get_jwks()

        # Get the key ID from token header
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        alg = unverified_header.get("alg", "RS256")

        if not kid:
            logger.warning("Token missing 'kid' header")
            raise credentials_exception

        # Find matching key in JWKS
        rsa_key = None
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                rsa_key = key
                break

        if not rsa_key:
            logger.warning(f"No matching key found for kid: {kid}")
            # Clear cache and retry once (in case of key rotation)
            JWKSClient.clear_cache()
            jwks = JWKSClient.get_jwks()
            for key in jwks.get("keys", []):
                if key.get("kid") == kid:
                    rsa_key = key
                    break

        if not rsa_key:
            raise credentials_exception

        # Build expected issuer URL
        # Note: Use the public-facing URL for issuer validation
        issuer = f"{settings.KEYCLOAK_ISSUER_URL}/realms/{settings.KEYCLOAK_REALM}"

        # Decode and validate token
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=[alg],
            audience="account",  # Keycloak default audience
            issuer=issuer,
            options={
                "verify_aud": False,  # Keycloak doesn't always set audience
                "verify_iss": True,
                "verify_exp": True,
            },
        )

        # Extract roles from token
        # Keycloak can put roles in different places depending on config
        roles = []

        # Check realm_access.roles (default location)
        realm_access = payload.get("realm_access", {})
        roles.extend(realm_access.get("roles", []))

        # Also check custom 'roles' claim (from our protocol mapper)
        custom_roles = payload.get("roles", [])
        if isinstance(custom_roles, list):
            roles.extend(custom_roles)

        # Deduplicate roles
        roles = list(set(roles))

        return TokenPayload(
            sub=payload.get("sub"),
            email=payload.get("email"),
            preferred_username=payload.get("preferred_username"),
            roles=roles,
            exp=payload.get("exp"),
            iat=payload.get("iat"),
            iss=payload.get("iss"),
        )

    except JWTError as e:
        logger.warning(f"JWT validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> CurrentUser:
    """FastAPI dependency to get current authenticated user.

    Args:
        token: JWT token from Authorization header (injected by FastAPI)

    Returns:
        CurrentUser with user information

    Raises:
        HTTPException 401: If token is invalid or expired
    """
    if not settings.AUTH_ENABLED:
        return DEV_USER

    payload = decode_token(token)

    return CurrentUser(
        id=payload.sub,
        username=payload.preferred_username or payload.sub,
        email=payload.email,
        roles=payload.roles,
    )


async def get_admin_user(current_user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    """FastAPI dependency to require admin role.

    Args:
        current_user: Authenticated user (injected by FastAPI)

    Returns:
        CurrentUser if user has admin role

    Raises:
        HTTPException 403: If user doesn't have admin role
    """
    if not settings.AUTH_ENABLED:
        return DEV_USER

    if not current_user.is_admin:
        logger.warning(f"User {current_user.username} attempted admin access without role")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


# Type aliases for cleaner dependency injection in endpoints
AuthenticatedUser = Annotated[CurrentUser, Depends(get_current_user)]
AdminUser = Annotated[CurrentUser, Depends(get_admin_user)]


# Optional: Dependency for endpoints that can work with or without auth
async def get_optional_user(
    token: Annotated[
        str | None,
        Depends(
            OAuth2AuthorizationCodeBearer(
                authorizationUrl=f"{settings.KEYCLOAK_INTERNAL_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/auth",
                tokenUrl=f"{settings.KEYCLOAK_INTERNAL_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/token",
                auto_error=False,
            )
        ),
    ] = None,
) -> CurrentUser | None:
    """Get current user if authenticated, None otherwise.

    Useful for endpoints that behave differently based on auth status.
    """
    if not settings.AUTH_ENABLED:
        return DEV_USER

    if token is None:
        return None

    try:
        payload = decode_token(token)
        return CurrentUser(
            id=payload.sub,
            username=payload.preferred_username or payload.sub,
            email=payload.email,
            roles=payload.roles,
        )
    except HTTPException:
        return None


OptionalUser = Annotated[CurrentUser | None, Depends(get_optional_user)]
