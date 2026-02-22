# Auth Feature-Flag Documentation

## Overview

The backend now supports a clean authentication feature flag (`AUTH_ENABLED`) that allows you to disable authentication for local development without requiring manual endpoint modifications.

## Configuration

### Environment Variable

```bash
# Set in your .env or docker-compose.yml:
AUTH_ENABLED=false   # Disable auth (uses dev user)
AUTH_ENABLED=true    # Enable auth (requires valid JWT tokens)
```

### Default Behavior

- **Default value**: `true` (authentication enabled)
- **Location**: `backend/src/core/config.py` line 31

## How It Works

### When AUTH_ENABLED=false

1. Missing tokens bypass authentication
2. All protected endpoints automatically return a dev user:
   ```json
   {
     "id": "dev-user",
     "username": "dev",
     "email": "dev@local",
     "roles": ["admin"]
   }
   ```
3. No token validation occurs
4. Admin role checks pass silently

### When AUTH_ENABLED=true

1. Missing token → `401 Unauthorized`
2. Invalid/expired token → `401 Unauthorized`
3. Missing admin role → `403 Forbidden`
4. Valid JWT token → User extracted from token claims

## Implementation Details

### Key File: `backend/src/core/security/oauth2.py`

The dependency behavior changed from:

```python
# OLD (forced 401 before flag check)
oauth2_scheme = OAuth2AuthorizationCodeBearer(auto_error=True)
```

To:

```python
# NEW (optional token, flag-aware)
oauth2_scheme = OAuth2AuthorizationCodeBearer(auto_error=False)
```

Then in `get_current_user()`:

```python
if not settings.AUTH_ENABLED:
    return DEV_USER  # Bypass auth

if token is None:
    raise HTTPException(status_code=401, detail="Not authenticated")

# Token validation only runs when AUTH_ENABLED=true
```

## Protected Endpoints

All endpoints using these dependency types are auth-gated:

**Requires authentication:**

- `AuthenticatedUser` — any valid user
- `AdminUser` — valid user + admin role

**Example endpoint:**

```python
@router.post("/cameras/")
async def create_camera(
    current_user: AuthenticatedUser,  # Automatically checked
    db: Session = Depends(get_db),
):
    return {"created_by": current_user.username}
```

When `AUTH_ENABLED=false`, `current_user` is auto-populated with dev user.

## Testing

### New Tests: `backend/tests/src/core/security/test_auth_feature_flag.py`

Three focused tests validate the feature flag:

1. **test_protected_endpoint_bypasses_auth_when_feature_flag_is_disabled**
   - Verifies endpoint works without token when `AUTH_ENABLED=false`

2. **test_protected_endpoint_returns_401_when_enabled_and_token_missing**
   - Verifies 401 when token missing and `AUTH_ENABLED=true`

3. **test_protected_endpoint_accepts_valid_token_when_enabled**
   - Verifies valid token extraction when `AUTH_ENABLED=true`

### Run Tests

```bash
cd backend
./.venv/bin/python -m pytest tests/src/core/security/ -v
```

**Status**: ✅ All tests pass (3/3 auth tests + 30 hardware tests)

## Frontend Integration

When using the backend locally with `AUTH_ENABLED=false`:

- Frontend should skip Keycloak login flow
- Frontend should pass any arbitrary auth header (or none)
- API calls will succeed because backend serves DEV_USER

## Troubleshooting

### Still Getting 401?

1. Verify `AUTH_ENABLED` is set to `false` in backend
2. Check backend logs: `logger.info(f"AUTH_ENABLED: {settings.AUTH_ENABLED}")`
3. Ensure environment variables are reloaded (restart backend)

### How to Verify It Works

```bash
# With AUTH_ENABLED=false
curl -X GET http://localhost:8000/api/v1/cameras/

# Should succeed even without Authorization header

# With AUTH_ENABLED=true
curl -X GET http://localhost:8000/api/v1/cameras/

# Should return 401
```

## Dependencies Modified

- `backend/src/core/security/oauth2.py` — Made token extraction optional
- `backend/src/core/config.py` — Already has AUTH_ENABLED flag (no change needed)

## No Breaking Changes

- All existing protected endpoints work unchanged
- Keycloak integration still works when `AUTH_ENABLED=true`
- Backward compatible — existing deployments unaffected
