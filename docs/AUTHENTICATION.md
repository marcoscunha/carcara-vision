# Authentication Architecture

This document describes how authentication works in Carcara Vision using Keycloak as the identity provider.

## Overview

Carcara Vision uses **Keycloak** for centralized identity and access management. The system implements the **OAuth2 Authorization Code flow with PKCE** (Proof Key for Code Exchange), which is the recommended approach for Single Page Applications (SPAs).

## Architecture

```
┌─────────────────┐                      ┌─────────────────┐
│                 │  1. Login redirect   │                 │
│    Frontend     │─────────────────────▶│    Keycloak     │
│    (React)      │                      │   (Port 8080)   │
│                 │◀─────────────────────│                 │
│                 │  2. Auth code + PKCE │                 │
└────────┬────────┘                      └────────┬────────┘
         │                                        │
         │ 3. Bearer token                        │
         │    (Authorization header)              │
         ▼                                        │
┌─────────────────┐                               │
│                 │  4. Validate JWT via JWKS     │
│    Backend      │◀──────────────────────────────┘
│   (FastAPI)     │
│                 │
└─────────────────┘
```

### Authentication Flow

1. **User initiates login** → Frontend redirects to Keycloak login page
2. **User authenticates** → Keycloak validates credentials and returns authorization code
3. **Token exchange** → Frontend exchanges code for access/refresh tokens (PKCE validates the exchange)
4. **API requests** → Frontend includes access token in `Authorization: Bearer <token>` header
5. **Token validation** → Backend validates JWT signature using Keycloak's JWKS endpoint

## Components

### Keycloak (Identity Provider)

**Container**: `keycloak` (Port 8080)

Keycloak provides:

- User authentication and session management
- JWT token issuance and validation
- Role-based access control (RBAC)
- Brute-force protection
- Password policies

#### Realm Configuration

| Setting                | Value      | Description                                     |
| ---------------------- | ---------- | ----------------------------------------------- |
| Realm                  | `carcara`  | Isolated authentication namespace               |
| SSL Required           | `none`     | Development mode (use `external` in production) |
| Access Token Lifespan  | 5 minutes  | Short-lived for security                        |
| SSO Session Idle       | 30 minutes | Idle timeout before re-auth required            |
| Brute Force Protection | Enabled    | Locks accounts after 5 failed attempts          |

#### Clients

| Client ID          | Type          | Purpose                          |
| ------------------ | ------------- | -------------------------------- |
| `carcara-frontend` | Public (PKCE) | React SPA authentication         |
| `carcara-backend`  | Bearer-only   | JWT validation (no direct login) |

### Frontend Authentication

**File**: `frontend/src/auth/`

The frontend uses `keycloak-js` library for:

- Initializing authentication on app load
- Redirecting to Keycloak login page
- Managing access and refresh tokens
- Silent token refresh (via iframe)
- Logout and session cleanup

```typescript
// Configuration (frontend/src/auth/keycloak.ts)
const keycloakConfig = {
  url: import.meta.env.VITE_KEYCLOAK_URL || `${window.location.protocol}//${window.location.hostname}:8280`,
  realm: "carcara",
  clientId: "carcara-frontend",
};
```

#### AuthProvider Context

The `AuthProvider` component wraps the application and exposes:

| Property/Method   | Type           | Description                                    |
| ----------------- | -------------- | ---------------------------------------------- |
| `isAuthenticated` | boolean        | User login status                              |
| `isLoading`       | boolean        | Auth initialization in progress                |
| `user`            | User \| null   | Current user info (id, username, email, roles) |
| `token`           | string \| null | Current access token                           |
| `login()`         | function       | Initiate login flow                            |
| `logout()`        | function       | End session                                    |
| `hasRole(role)`   | function       | Check user role                                |
| `isAdmin`         | boolean        | Shortcut for admin role check                  |

### Backend Authentication

**File**: `backend/src/core/security/oauth2.py`

The backend validates JWT tokens by:

1. Extracting the token from `Authorization` header
2. Fetching Keycloak's JWKS (JSON Web Key Set) for signature verification
3. Validating token signature, expiration, and issuer
4. Extracting user information and roles from token claims

#### Using Authentication in Endpoints

```python
from ...core.security import AuthenticatedUser, AdminUser

# Any authenticated user
@router.get("/streams")
async def list_streams(current_user: AuthenticatedUser):
    return {"user": current_user.username}

# Admin role required
@router.delete("/cameras/{id}")
async def delete_camera(camera_id: int, admin_user: AdminUser):
    # Only users with 'admin' role can access
    ...
```

#### Dependency Types

| Dependency          | Description                  |
| ------------------- | ---------------------------- |
| `AuthenticatedUser` | Any valid authenticated user |
| `AdminUser`         | User must have `admin` role  |

## Roles

| Role    | Description                      |
| ------- | -------------------------------- |
| `admin` | Full access to all API endpoints |

_Additional roles can be defined in Keycloak and enforced via custom dependencies._

## Default Credentials

| Service                | Username | Password   | URL                         |
| ---------------------- | -------- | ---------- | --------------------------- |
| Keycloak Admin Console | `admin`  | `admin`    | http://localhost:8280/admin |
| Carcara Application    | `admin`  | `admin123` | http://localhost:8221       |

> **Warning**: Change these credentials before deploying to production.

## Configuration

### Environment Variables

#### Backend

| Variable                | Default                 | Description                                                       |
| ----------------------- | ----------------------- | ----------------------------------------------------------------- |
| `AUTH_ENABLED`          | `false` (dev `.env`)    | Enables/disables backend JWT enforcement (`true` in production)   |
| `KEYCLOAK_INTERNAL_URL` | `http://keycloak:8080`  | Keycloak URL reachable from backend container (Docker network)    |
| `KEYCLOAK_ISSUER_URL`   | `http://localhost:8280` | Public Keycloak URL used in token issuer validation (browser URL) |
| `KEYCLOAK_REALM`        | `carcara`               | Realm name                                                        |

#### Frontend

| Variable                  | Default                 | Description                              |
| ------------------------- | ----------------------- | ---------------------------------------- |
| `VITE_AUTH_ENABLED`       | `false` (dev `.env`)    | Enables/disables Keycloak flow in SPA    |
| `VITE_KEYCLOAK_URL`       | `http://localhost:8280` | Keycloak server URL (browser accessible) |
| `VITE_KEYCLOAK_REALM`     | `carcara`               | Realm name                               |
| `VITE_KEYCLOAK_CLIENT_ID` | `carcara-frontend`      | OAuth2 client ID                         |

### Development Auth Toggle

For local development, you can disable authentication in both backend and frontend:

- `AUTH_ENABLED=false`
- `VITE_AUTH_ENABLED=false`

To re-enable full Keycloak flow in development, set both to `true`.

> `VITE_*` variables are build-time values. After changing `VITE_AUTH_ENABLED` you must rebuild/restart the frontend container.

## Security Considerations

### PKCE (Proof Key for Code Exchange)

PKCE prevents authorization code interception attacks by:

1. Frontend generates a random `code_verifier`
2. Frontend sends `code_challenge` (SHA256 hash of verifier) with auth request
3. Keycloak returns authorization code
4. Frontend sends `code_verifier` with token exchange request
5. Keycloak validates the verifier matches the original challenge

### Token Storage

- Access tokens are kept in memory (not localStorage)
- Refresh tokens use secure httpOnly cookies when possible
- Silent refresh maintains session without user interaction

### CORS Configuration

The backend allows requests from configured origins:

- `http://localhost:8221` (production frontend)
- `http://localhost:5173` (Vite dev server)

## Troubleshooting

### "Not authenticated" error

1. Verify Keycloak is running: `docker compose ps keycloak`
2. Check token in browser DevTools → Network → Request Headers
3. Verify `KEYCLOAK_INTERNAL_URL` is accessible from backend container

### Remote access (Jetson or LAN host)

When opening the frontend from another machine, do **not** keep localhost defaults.

Set:

- `VITE_KEYCLOAK_URL=http://<jetson-ip>:8280`
- `KEYCLOAK_ISSUER_URL=http://<jetson-ip>:8280`
- `KC_HOSTNAME=<jetson-ip>`
- `VITE_AUTH_ENABLED=true` (only when you want Keycloak enabled)

Keep:

- `KEYCLOAK_INTERNAL_URL=http://keycloak:8080`

If the browser still redirects to `http://localhost:8280`, rebuild frontend because `VITE_*` values are embedded at build time:

- `docker compose up -d --build frontend`

### Token validation fails

1. Clear JWKS cache (restart backend)
2. Check Keycloak logs: `docker compose logs keycloak`
3. Verify realm configuration matches backend settings

### Silent refresh fails

1. Check `silent-check-sso.html` is served correctly
2. Verify redirect URIs in Keycloak client configuration
3. Check browser console for iframe errors

## Production Deployment

Before deploying to production:

1. **Enable HTTPS**: Set `sslRequired: "external"` in realm
2. **Change credentials**: Update admin and default user passwords
3. **Configure redirect URIs**: Update allowed origins for production domains
4. **Enable persistent storage**: Use external database for Keycloak (PostgreSQL recommended)
5. **Set token lifespans**: Adjust based on security requirements
