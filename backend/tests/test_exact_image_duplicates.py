"""Exact image retry protection for the persisted assessment route."""

import hashlib
import io
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.exc import IntegrityError

sys.path.insert(0, str(Path(__file__).parents[1]))
os.environ["DATABASE_URL"] = ""

from app.analytics import summarize_violation_records, summarize_work_area_recurrence
from app.auth import get_current_user
from app.database import get_db
from app.db_models import Observation
from app.detector import BoundingBox, MockHazardDetector
from app.main import app, get_hazard_detector


def png_bytes(color: tuple[int, int, int] = (100, 120, 140)) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (16, 16), color).save(output, format="PNG")
    return output.getvalue()


class RecordingSession:
    """Record the ORM bundle and enforce its existing observation primary key."""

    def __init__(self) -> None:
        self.records: dict[str, Observation] = {}
        self.pending: Observation | None = None
        self.add_count = 0
        self.flush_count = 0

    def get(self, model: type, key: str) -> Observation | None:
        assert model is Observation
        return self.records.get(key)

    def add(self, record: Observation) -> None:
        self.pending = record
        self.add_count += 1

    def flush(self) -> None:
        self.flush_count += 1
        if self.pending is not None:
            if self.pending.observation_id in self.records:
                raise IntegrityError("duplicate observation_id", {}, Exception("primary key"))
            self.records[self.pending.observation_id] = self.pending
            self.pending = None

    def rollback(self) -> None:
        self.pending = None


class ExactImageDuplicateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.storage_patch = patch("app.image_storage.OBSERVATION_IMAGE_ROOT", Path(self.directory.name))
        self.storage_patch.start()
        self.session = RecordingSession()
        self.detector = MockHazardDetector(canned_boxes=[
            BoundingBox(class_name="Person", confidence=0.95),
            BoundingBox(class_name="NO-Hardhat", confidence=0.9),
        ])
        app.dependency_overrides[get_current_user] = lambda: object()
        app.dependency_overrides[get_db] = lambda: self.session
        app.dependency_overrides[get_hazard_detector] = lambda: self.detector
        self.client = TestClient(app)
        self.image = png_bytes()

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.storage_patch.stop()
        self.directory.cleanup()

    def upload(self, observation_id: str, image: bytes | None = None, **params: str | None):
        query = "&".join(f"{key}={value}" for key, value in {
            "observation_id": observation_id,
            "duration_minutes": "30",
            "repeated_count": "3",
            "work_area": "North",
            **params,
        }.items() if value is not None)
        return self.client.post(
            f"/assessments/image?{query}",
            content=self.image if image is None else image,
            headers={"Content-Type": "image/png"},
        )

    def analytics(self):
        hazards = []
        for record in self.session.records.values():
            for hazard in record.detected_hazards:
                hazard.detected_hazard_id = len(hazards) + 1
                hazard.observation_id = record.observation_id
                hazards.append(hazard)
        return summarize_violation_records(hazards)

    def test_first_upload_and_exact_retry_do_not_duplicate_records_or_analytics(self):
        first = self.upload("inspection-a")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["safety_decision"]["outcome"], "alert")
        record = self.session.records["inspection-a"]
        self.assertEqual(record.raw_metadata["image"]["sha256"], hashlib.sha256(self.image).hexdigest())
        self.assertEqual((len(record.detected_hazards), len(record.detected_hazards[0].assessments),
                          len(record.alerts)), (1, 1, 1))
        self.assertEqual(len(record.detected_hazards[0].recommendations), 0)
        original_metadata = dict(record.raw_metadata)
        original_file = next(Path(self.directory.name).rglob("original.png"))
        original_bytes = original_file.read_bytes()
        before = self.analytics()

        with patch.object(self.detector, "detect", wraps=self.detector.detect) as detect:
            duplicate = self.upload("inspection-a")
            again = self.upload("inspection-a")
            detect.assert_not_called()
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(duplicate.json(), again.json())
        self.assertEqual(duplicate.json()["detail"], {
            "code": "duplicate_image_submission",
            "observation_id": "inspection-a",
            "message": "This exact image submission already exists.",
        })
        self.assertEqual((len(self.session.records), self.session.add_count), (1, 1))
        self.assertEqual((len(record.detected_hazards), len(record.detected_hazards[0].assessments),
                          len(record.alerts)), (1, 1, 1))
        self.assertEqual(len(record.detected_hazards[0].recommendations), 0)
        self.assertEqual(record.raw_metadata, original_metadata)
        self.assertEqual(original_file.read_bytes(), original_bytes)
        after = self.analytics()
        self.assertEqual((before.total_violations, after.total_violations), (1, 1))
        self.assertEqual((before.open_alert_count, after.open_alert_count), (1, 1))
        self.assertEqual(after.violations_by_work_area[0].violation_count, 1)
        self.assertEqual(record.repeated_count, 3)  # Retry is not recurrence.

    def test_same_bytes_with_distinct_observation_id_is_a_new_context(self):
        self.assertEqual(self.upload("inspection-a").status_code, 200)
        self.assertEqual(self.upload("inspection-b").status_code, 200)
        self.assertEqual(len(self.session.records), 2)
        self.assertEqual(self.analytics().total_violations, 2)

    def test_rejected_exact_retry_does_not_become_historical_recurrence(self):
        self.assertEqual(self.upload("inspection-a").status_code, 200)
        self.assertEqual(self.upload("inspection-a").status_code, 409)
        records = []
        for observation in self.session.records.values():
            for hazard in observation.detected_hazards:
                hazard.observation_id = observation.observation_id
                records.append(hazard)
        group = summarize_work_area_recurrence(records).groups[0]
        self.assertEqual(group.observation_count, 1)
        self.assertFalse(group.is_repeated)
        self.assertEqual(self.session.records["inspection-a"].repeated_count, 3)

    def test_changed_bytes_or_submission_inputs_are_not_classified_as_exact_retry(self):
        self.assertEqual(self.upload("inspection-a").status_code, 200)
        different_bytes = self.upload("inspection-a", png_bytes((101, 120, 140)))
        changed_context = self.upload("inspection-a", work_area="South")
        self.assertEqual(different_bytes.status_code, 409)
        self.assertEqual(changed_context.status_code, 409)
        self.assertIsInstance(different_bytes.json()["detail"], str)
        self.assertIsInstance(changed_context.json()["detail"], str)
        self.assertEqual(len(self.session.records), 1)

    def test_hash_uses_original_upload_bytes_not_annotation(self):
        # A valid PNG with trailing bytes decodes to the same pixels and overlay.
        second_image = self.image + b"different-original-byte-stream"
        self.assertEqual(self.upload("inspection-a").status_code, 200)
        self.assertEqual(self.upload("inspection-b", second_image).status_code, 200)
        first = self.session.records["inspection-a"].raw_metadata["image"]
        second = self.session.records["inspection-b"].raw_metadata["image"]
        self.assertEqual(first["sha256"], hashlib.sha256(self.image).hexdigest())
        self.assertEqual(second["sha256"], hashlib.sha256(second_image).hexdigest())
        self.assertNotEqual(first["sha256"], second["sha256"])

    def test_historical_observation_without_fingerprint_remains_valid(self):
        old = Observation(
            observation_id="inspection-old", observed_at=datetime.now(timezone.utc),
            source="image_upload:old", raw_metadata={"image": {"storage_key": "old"}},
        )
        self.session.records["inspection-old"] = old
        response = self.upload("inspection-old")
        self.assertEqual(response.status_code, 409)
        self.assertIsInstance(response.json()["detail"], str)
        self.assertIs(self.session.records["inspection-old"], old)
        self.assertEqual(self.session.add_count, 0)

    def test_warning_and_pending_remain_history_without_alerts(self):
        warning = self.upload("warning", repeated_count="0", duration_minutes="1")
        pending = self.upload("pending", repeated_count=None, duration_minutes=None)
        self.assertEqual(warning.status_code, 200)
        self.assertEqual(pending.status_code, 200)
        self.assertEqual(warning.json()["safety_decision"]["outcome"], "warning")
        self.assertEqual(pending.json()["safety_decision"]["outcome"], "pending")
        self.assertEqual(self.upload("warning", repeated_count="0", duration_minutes="1").status_code, 409)
        self.assertEqual(self.upload("pending", repeated_count=None, duration_minutes=None).status_code, 409)
        self.assertEqual(len(self.session.records), 2)
        self.assertEqual(sum(len(record.alerts) for record in self.session.records.values()), 0)
        self.assertEqual(self.analytics().total_violations, 2)

    def test_primary_key_race_maps_to_duplicate_without_writing_images(self):
        winning = Observation(
            observation_id="raced", observed_at=datetime.now(timezone.utc),
            source="image_upload:site_image",
            raw_metadata={
                "image": {"sha256": hashlib.sha256(self.image).hexdigest()},
                "image_submission": {
                    "work_area": "North", "people_count_override": None,
                    "duration_minutes": 30, "repeated_count": 3,
                },
            },
        )
        original_flush = self.session.flush

        def raced_flush():
            self.session.records["raced"] = winning
            raise IntegrityError("duplicate observation_id", {}, Exception("primary key"))

        self.session.flush = raced_flush
        with patch("app.main._build_image_metadata") as store:
            response = self.upload("raced")
            store.assert_not_called()
        self.session.flush = original_flush
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["code"], "duplicate_image_submission")
        self.assertIs(self.session.records["raced"], winning)


if __name__ == "__main__":
    unittest.main()
