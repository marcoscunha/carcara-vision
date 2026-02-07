from unittest import TestCase

from fastapi.testclient import TestClient

from src.db.session import get_db
from src.main import app
from src.models.camera import Camera
from src.models.stream import Stream


class StreamsEndpointTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        """Set up resources shared across all tests."""
        cls.client = TestClient(app)
        cls.db = next(get_db())
        super().setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up resources shared across all tests."""
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
        self.db.commit()
        super().tearDown()

    def test_create_stream(self):
        """Test creating a new stream."""
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
        print(f"Created stream: {response.json()}")

        # Clean
        self.db.query(Stream).filter_by(id=response.json()["id"]).delete()
        self.db.query(Camera).filter_by(id=camera.id).delete()
        self.db.commit()

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

        # Clean
        self.db.query(Stream).filter_by(camera_id=camera.id).delete()
        self.db.query(Camera).filter_by(id=camera.id).delete()
        self.db.commit()

    def test_get_stream(self):
        """Test retrieving a specific stream by ID."""
        # Arrange
        camera = Camera(name="Camera 1", camera_type="local", device_id=4)
        self.db.add(camera)
        self.db.commit()
        camera = self.db.query(Camera).filter_by(name="Camera 1").first()

        stream = Stream(camera_id=camera.id, status="active", stream_metadata={"resolution": "1920x1080"})
        self.db.add(stream)
        self.db.commit()
        stream = self.db.query(Stream).filter_by(camera_id=camera.id).first()

        # Act
        response = self.client.get(f"/api/v1/streams/{stream.id}")

        # Assert
        self.assertEqual(response.status_code, 200, "Retrieving a stream should return status code 200")
        self.assertEqual(response.json()["id"], stream.id, "Stream ID should match")
        print(f"Retrieved stream: {response.json()}")

        # Clean
        self.db.query(Stream).filter_by(id=stream.id).delete()
        self.db.query(Camera).filter_by(id=camera.id).delete()
        self.db.commit()

    def test_delete_stream(self):
        """Test deleting a specific stream."""
        # Arrange
        camera = Camera(name="Camera 1", camera_type="local", device_id=4)
        self.db.add(camera)
        self.db.commit()
        camera = self.db.query(Camera).filter_by(name="Camera 1").first()

        stream = Stream(camera_id=camera.id, status="active", stream_metadata={"resolution": "1920x1080"})
        self.db.add(stream)
        self.db.commit()
        stream = self.db.query(Stream).filter_by(camera_id=camera.id).first()

        # Act
        response = self.client.delete(f"/api/v1/streams/{stream.id}")

        # Assert
        self.assertEqual(response.status_code, 200, "Deleting a stream should return status code 200")
        self.assertIsNone(self.db.query(Stream).filter_by(id=stream.id).first(), "Stream should be deleted")
        print("Stream deleted successfully.")

        # Clean
        self.db.query(Camera).filter_by(id=camera.id).delete()
        self.db.commit()
