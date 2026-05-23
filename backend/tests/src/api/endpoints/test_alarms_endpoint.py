"""Tests for the alarms REST endpoints.

Covers CRUD for alarms, alarm events (list, ack, delete), and zones.
Focuses on regressions like the missing ``import os`` in delete_event.
"""

from datetime import datetime
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.core.security.oauth2 import settings as auth_settings
from src.db.base_class import Base
from src.db.session import get_db
from src.main import app
from src.models.alarm import Alarm, AlarmEvent, AlarmZone
from src.models.camera import Camera
from src.models.stream import Stream


def _make_trigger_config():
    return {"type": "class_present", "class_names": ["person"], "min_confidence": 0.5}


class AlarmEndpointTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._prev_auth = auth_settings.AUTH_ENABLED
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

        # Seed a camera + stream used by all tests
        cam = Camera(name="Test Camera", rtsp_url="rtsp://localhost/cam0")
        cls.db.add(cam)
        cls.db.flush()
        stream = Stream(
            camera_id=cam.id,
            stream_name="test-stream",
            status="active",
            stream_metadata={"model_name": "yolov8n", "task_type": "detect"},
        )
        cls.db.add(stream)
        cls.db.commit()
        cls.stream_id = stream.id
        super().setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.db.close()
        Base.metadata.drop_all(bind=cls.engine)
        app.dependency_overrides.clear()
        auth_settings.AUTH_ENABLED = cls._prev_auth
        super().tearDownClass()

    def tearDown(self) -> None:
        self.db.query(AlarmEvent).delete()
        self.db.query(Alarm).delete()
        self.db.query(AlarmZone).delete()
        self.db.commit()
        super().tearDown()

    # ── helpers ──────────────────────────────────────────────────────────────

    def _create_alarm(self, **kwargs) -> dict:
        payload = {
            "stream_id": self.stream_id,
            "name": "Test alarm",
            "severity": "warning",
            "trigger_config": _make_trigger_config(),
            "is_active": True,
            "store_events": True,
            "store_snapshot": True,
            **kwargs,
        }
        resp = self.client.post("/api/v1/alarms/", json=payload)
        self.assertEqual(resp.status_code, 201, resp.text)
        return resp.json()

    def _create_event(self, alarm_id: int, state: str = "open") -> AlarmEvent:
        ev = AlarmEvent(
            alarm_id=alarm_id,
            stream_id=self.stream_id,
            state=state,
            started_at=datetime.utcnow(),
            rule_snapshot=_make_trigger_config(),
        )
        self.db.add(ev)
        self.db.commit()
        self.db.refresh(ev)
        return ev

    # ── Alarm CRUD ────────────────────────────────────────────────────────────

    @patch("src.api.endpoints.alarms._notify_engine_reload")
    def test_create_alarm(self, mock_reload):
        alarm = self._create_alarm()
        self.assertEqual(alarm["name"], "Test alarm")
        self.assertEqual(alarm["stream_id"], self.stream_id)
        self.assertEqual(alarm["trigger_type"], "class_present")

    @patch("src.api.endpoints.alarms._notify_engine_reload")
    def test_list_alarms(self, mock_reload):
        self._create_alarm(name="A1")
        self._create_alarm(name="A2")
        resp = self.client.get("/api/v1/alarms/")
        self.assertEqual(resp.status_code, 200)
        names = [a["name"] for a in resp.json()]
        self.assertIn("A1", names)
        self.assertIn("A2", names)

    @patch("src.api.endpoints.alarms._notify_engine_reload")
    def test_get_alarm(self, mock_reload):
        alarm = self._create_alarm()
        resp = self.client.get(f"/api/v1/alarms/{alarm['id']}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["id"], alarm["id"])

    @patch("src.api.endpoints.alarms._notify_engine_reload")
    def test_update_alarm(self, mock_reload):
        alarm = self._create_alarm()
        resp = self.client.put(f"/api/v1/alarms/{alarm['id']}", json={"name": "Updated"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["name"], "Updated")

    @patch("src.api.endpoints.alarms._notify_engine_reload")
    def test_delete_alarm(self, mock_reload):
        alarm = self._create_alarm()
        resp = self.client.delete(f"/api/v1/alarms/{alarm['id']}")
        self.assertEqual(resp.status_code, 204)
        resp2 = self.client.get(f"/api/v1/alarms/{alarm['id']}")
        self.assertEqual(resp2.status_code, 404)

    # ── Alarm events ──────────────────────────────────────────────────────────

    @patch("src.api.endpoints.alarms._notify_engine_reload")
    def test_list_events(self, mock_reload):
        alarm = self._create_alarm()
        self._create_event(alarm["id"])
        self._create_event(alarm["id"])
        resp = self.client.get("/api/v1/alarms/events")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.json()), 2)

    @patch("src.api.endpoints.alarms._notify_engine_reload")
    def test_list_events_filtered_by_alarm(self, mock_reload):
        alarm = self._create_alarm()
        self._create_event(alarm["id"])
        resp = self.client.get(f"/api/v1/alarms/events?alarm_id={alarm['id']}")
        self.assertEqual(resp.status_code, 200)
        for ev in resp.json():
            self.assertEqual(ev["alarm_id"], alarm["id"])

    @patch("src.api.endpoints.alarms._notify_engine_reload")
    def test_ack_event(self, mock_reload):
        alarm = self._create_alarm()
        ev = self._create_event(alarm["id"], state="open")
        resp = self.client.post(
            f"/api/v1/alarms/events/{ev.id}/ack",
            json={"acknowledged_by": "tester", "note": "all clear"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["state"], "acknowledged")
        self.assertEqual(data["acknowledged_by"], "tester")

    @patch("src.api.endpoints.alarms._notify_engine_reload")
    def test_delete_event_no_snapshot(self, mock_reload):
        """DELETE /events/{id} — event with no snapshot file."""
        alarm = self._create_alarm()
        ev = self._create_event(alarm["id"])
        resp = self.client.delete(f"/api/v1/alarms/events/{ev.id}")
        self.assertEqual(resp.status_code, 204)
        # Confirm it's gone
        resp2 = self.client.get(f"/api/v1/alarms/events/{ev.id}")
        self.assertEqual(resp2.status_code, 404)

    @patch("src.api.endpoints.alarms._notify_engine_reload")
    def test_delete_event_with_snapshot_file(self, mock_reload):
        """DELETE /events/{id} — removes snapshot file when it exists."""
        import tempfile
        import os

        alarm = self._create_alarm()
        ev = self._create_event(alarm["id"])

        # Plant a temporary file as the snapshot
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"FAKEJPEG")
            snap_path = f.name

        self.db.query(AlarmEvent).filter(AlarmEvent.id == ev.id).update({"snapshot_path": snap_path})
        self.db.commit()

        resp = self.client.delete(f"/api/v1/alarms/events/{ev.id}")
        self.assertEqual(resp.status_code, 204)
        # File must be cleaned up
        self.assertFalse(os.path.isfile(snap_path), "Snapshot file should be deleted")

    @patch("src.api.endpoints.alarms._notify_engine_reload")
    def test_delete_event_with_missing_snapshot_file(self, mock_reload):
        """DELETE /events/{id} — succeeds even if snapshot path points to a missing file."""
        alarm = self._create_alarm()
        ev = self._create_event(alarm["id"])

        self.db.query(AlarmEvent).filter(AlarmEvent.id == ev.id).update(
            {"snapshot_path": "/tmp/nonexistent_alarm_snapshot_xyz.jpg"}
        )
        self.db.commit()

        resp = self.client.delete(f"/api/v1/alarms/events/{ev.id}")
        self.assertEqual(resp.status_code, 204)

    @patch("src.api.endpoints.alarms._notify_engine_reload")
    def test_delete_event_not_found(self, mock_reload):
        """DELETE /events/{id} — 404 for unknown event."""
        resp = self.client.delete("/api/v1/alarms/events/999999")
        self.assertEqual(resp.status_code, 404)

    @patch("src.api.endpoints.alarms._notify_engine_reload")
    def test_has_snapshot_false_when_file_missing(self, mock_reload):
        """has_snapshot computed field is False when file doesn't exist on disk."""
        alarm = self._create_alarm()
        ev = self._create_event(alarm["id"])
        self.db.query(AlarmEvent).filter(AlarmEvent.id == ev.id).update({"snapshot_path": "/tmp/nonexistent_xyz.jpg"})
        self.db.commit()
        resp = self.client.get("/api/v1/alarms/events")
        self.assertEqual(resp.status_code, 200)
        event_data = next((e for e in resp.json() if e["id"] == ev.id), None)
        self.assertIsNotNone(event_data)
        self.assertFalse(event_data["has_snapshot"])

    @patch("src.api.endpoints.alarms._notify_engine_reload")
    def test_has_snapshot_true_when_file_exists(self, mock_reload):
        """has_snapshot computed field is True when file exists on disk."""
        import os
        import tempfile

        alarm = self._create_alarm()

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"FAKEJPEG")
            snap_path = f.name

        # Create event directly with snapshot_path already set
        ev = AlarmEvent(
            alarm_id=alarm["id"],
            stream_id=self.stream_id,
            state="open",
            started_at=datetime.utcnow(),
            rule_snapshot=_make_trigger_config(),
            snapshot_path=snap_path,
        )
        self.db.add(ev)
        self.db.commit()
        self.db.refresh(ev)

        resp = self.client.get("/api/v1/alarms/events")
        self.assertEqual(resp.status_code, 200)
        event_data = next((e for e in resp.json() if e["id"] == ev.id), None)
        self.assertIsNotNone(event_data)
        self.assertTrue(event_data["has_snapshot"])

        os.unlink(snap_path)

    # ── Zones ─────────────────────────────────────────────────────────────────

    def test_create_zone(self):
        resp = self.client.post(
            "/api/v1/alarms/zones",
            json={
                "stream_id": self.stream_id,
                "name": "Zone A",
                "polygon": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
            },
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["name"], "Zone A")

    def test_list_zones(self):
        self.client.post(
            "/api/v1/alarms/zones",
            json={
                "stream_id": self.stream_id,
                "name": "Zone B",
                "polygon": [[0, 0], [1, 0], [1, 1], [0, 1]],
            },
        )
        resp = self.client.get(f"/api/v1/alarms/zones?stream_id={self.stream_id}")
        self.assertEqual(resp.status_code, 200)
        names = [z["name"] for z in resp.json()]
        self.assertIn("Zone B", names)

    def test_delete_zone(self):
        resp = self.client.post(
            "/api/v1/alarms/zones",
            json={
                "stream_id": self.stream_id,
                "name": "Zone C",
                "polygon": [[0, 0], [1, 0], [1, 1]],
            },
        )
        zone_id = resp.json()["id"]
        del_resp = self.client.delete(f"/api/v1/alarms/zones/{zone_id}")
        self.assertEqual(del_resp.status_code, 204)
