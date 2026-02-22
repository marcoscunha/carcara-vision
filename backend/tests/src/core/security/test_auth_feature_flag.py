from unittest import TestCase
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.core.security.oauth2 import AuthenticatedUser
from src.core.security.oauth2 import TokenPayload


class AuthFeatureFlagEndpointTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        app = FastAPI()

        @app.get("/protected")
        async def protected_endpoint(current_user: AuthenticatedUser):
            return {
                "id": current_user.id,
                "username": current_user.username,
                "roles": current_user.roles,
            }

        cls.client = TestClient(app)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client = None
        super().tearDownClass()

    def test_protected_endpoint_bypasses_auth_when_feature_flag_is_disabled(self):
        with patch("src.core.security.oauth2.settings.AUTH_ENABLED", False):
            response = self.client.get("/protected")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], "dev-user")
        self.assertEqual(data["username"], "dev")
        self.assertIn("admin", data["roles"])

    def test_protected_endpoint_returns_401_when_enabled_and_token_missing(self):
        with patch("src.core.security.oauth2.settings.AUTH_ENABLED", True):
            response = self.client.get("/protected")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json().get("detail"), "Not authenticated")

    def test_protected_endpoint_accepts_valid_token_when_enabled(self):
        token_payload = TokenPayload(
            sub="user-123",
            email="user@example.com",
            preferred_username="user123",
            roles=["operator"],
            exp=9999999999,
            iat=9999990000,
            iss="test-issuer",
        )

        with (
            patch("src.core.security.oauth2.settings.AUTH_ENABLED", True),
            patch("src.core.security.oauth2.decode_token", return_value=token_payload) as mock_decode,
        ):
            response = self.client.get("/protected", headers={"Authorization": "Bearer fake.jwt.token"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "user123")
        mock_decode.assert_called_once_with("fake.jwt.token")
