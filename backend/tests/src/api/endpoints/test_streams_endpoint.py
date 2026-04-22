from unittest import TestCase
from unittest.mock import AsyncMock
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from src.core.security.oauth2 import settings as auth_settings
from src.db.base_class import Base
from src.db.session import get_db
from src.main import app
from src.models.camera import Camera
from src.models.stream import Stream


class StreamsEndpointTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        """Set up resources shared across all tests."""
        cls._previous_auth_enabled = auth_settings.AUTH_ENABLED
        auth_settings.AUTH_ENABLED = False

        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        Base.metadata.create_all(bind=cls.engine)

        def override_get_db():
            db = cls.TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app)
        cls.db = cls.TestingSessionLocal()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up resources shared across all tests."""
        cls.db.close()
        Base.metadata.drop_all(bind=cls.engine)
        app.dependency_overrides.clear()
        auth_settings.AUTH_ENABLED = cls._previous_auth_enabled
        cls.client = None
        cls.db = None
        super().tearDownClass()

    def setUp(self):
        """Set up resources for each individual test."""
        super().setUp()

    def tearDown(self) -> None:
        """Clean up resources for each individual test."""
        # Clean up any test data created in the database
        self.db.query(Stream).delete()
        self.db.query(Camera).delete()
        self.db.commit()
        super().tearDown()

    @patch("src.api.endpoints.streams.inference_worker_manager.start_worker")
    @patch("src.api.endpoints.streams.gstreamer_service.add_stream", new_callable=AsyncMock)
    def test_create_stream(self, add_stream_mock: AsyncMock, start_worker_mock):
        """Test creating a new stream."""
        # Arrange mocks
        add_stream_mock.return_value = True

        # Arrange
        camera = Camera(name="Camera 1", camera_type="local", device_id=4)
        self.db.add(camera)
        self.db.commit()

        camera = self.db.query(Camera).filter_by(name="Camera 1").first()

        payload = {"camera_id": camera.id, "stream_metadata": {}}

        # Act
        response = self.client.post("/api/v1/streams/", json=payload)

        # Assert
        self.assertEqual(response.status_code, 201, "Stream creation should return status code 201")
        self.assertIn("id", response.json(), "Response should contain the stream ID")
        self.assertEqual(response.json()["status"], "active")
        add_stream_mock.assert_awaited_once()
        start_worker_mock.assert_called_once()
        print(f"Created stream: {response.json()}")

    def test_list_streams(self):
        """Test listing all streams."""
        # Arrange
        camera = Camera(name="Camera 1", camera_type="local", device_id=4)
        self.db.add(camera)
        self.db.commit()

        camera = self.db.query(Camera).filter_by(name="Camera 1").first()

        self.db.add(Stream(camera_id=camera.id, status="active", stream_metadata={"resolution": "1920x1080"}))
        self.db.commit()

        # Act
        response = self.client.get("/api/v1/streams/")

        # Assert
        self.assertEqual(response.status_code, 200, "Listing streams should return status code 200")
        self.assertIsInstance(response.json(), list, "Response should be a list of streams")
        self.assertEqual(response.json()[0]["camera_id"], camera.id, "Stream should be linked to Camera 1")
        print(f"Streams: {response.json()}")

    def test_get_stream(self):
        """Test retrieving a specific stream by ID."""
        # Arrange
        camera = Camera(name="Camera 1", camera_type="local", device_id=4)
        self.db.add(camera)
        self.db.commit()
        camera = self.db.query(Camera).filter_by(name="Camera 1").first()

        stream = Stream(
            camera_id=camera.id,
            stream_name="camera_1_999_test",
            status="active",
            stream_metadata={"resolution": "1920x1080"},
        )
        self.db.add(stream)
        self.db.commit()
        stream = self.db.query(Stream).filter_by(camera_id=camera.id).first()

        # Act
        response = self.client.get(f"/api/v1/streams/{stream.id}")

        # Assert
        self.assertEqual(response.status_code, 200, "Retrieving a stream should return status code 200")
        self.assertEqual(response.json()["id"], stream.id, "Stream ID should match")
        print(f"Retrieved stream: {response.json()}")

    @patch("src.api.endpoints.streams.inference_worker_manager.stop_worker")
    @patch("src.api.endpoints.streams.gstreamer_service.remove_stream", new_callable=AsyncMock)
    def test_delete_stream(self, remove_stream_mock: AsyncMock, stop_worker_mock):
        """Test deleting a specific stream."""
        remove_stream_mock.return_value = True

        # Arrange
        camera = Camera(name="Camera 1", camera_type="local", device_id=4)
        self.db.add(camera)
        self.db.commit()
        camera = self.db.query(Camera).filter_by(name="Camera 1").first()

        stream = Stream(
            camera_id=camera.id,
            stream_name="camera_1_999_test",
            status="active",
            stream_metadata={"resolution": "1920x1080"},
        )
        self.db.add(stream)
        self.db.commit()
        stream = self.db.query(Stream).filter_by(camera_id=camera.id).first()

        # Act
        response = self.client.delete(f"/api/v1/streams/{stream.id}")

        # Assert
        self.assertEqual(response.status_code, 200, "Deleting a stream should return status code 200")
        self.assertIsNone(self.db.query(Stream).filter_by(id=stream.id).first(), "Stream should be deleted")
        remove_stream_mock.assert_awaited_once()
        stop_worker_mock.assert_called_once_with(stream.id)
        print("Stream deleted successfully.")
