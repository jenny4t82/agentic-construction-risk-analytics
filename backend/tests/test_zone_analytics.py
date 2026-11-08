"""Focused tests for persisted zone-level safety analytics."""

import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parents[1]))
os.environ["DATABASE_URL"] = ""

from app.analytics import get_safety_analytics, summarize_violation_records
from app.database import get_db
from app.db_models import Alert, DetectedHazardRecord, Observation, RiskAssessment
from app.main import app
from app.auth import get_current_user


NOW = datetime(2026, 3, 15, tzinfo=timezone.utc)


def make_record(
    hazard_id: int,
    observation_id: str,
    work_area: str | None,
    source_label: str,
    risk_band: str | None,
    alert_status: str,
) -> DetectedHazardRecord:
    observation = Observation(
        observation_id=observation_id,
        observed_at=NOW,
        source="analytics_test",
        work_area=work_area,
    )
    hazard = DetectedHazardRecord(
        detected_hazard_id=hazard_id,
        observation_id=observation_id,
        hazard_type={
            "no_helmet": "missing_safety_helmet",
            "no_vest": "missing_safety_vest",
            "no_mask": "missing_protective_mask",
            "no_boots": "missing_safety_boots",
        }[source_label],
        source_label=source_label,
        detected_at=NOW,
        observation=observation,
    )
    assessment = RiskAssessment(
        assessment_id=hazard_id + 100,
        assessment_version=1,
        status="completed" if risk_band else "pending",
        risk_band=risk_band,
        risk_score=40 if risk_band else None,
    )
    alert = Alert(
        alert_id=hazard_id + 200,
        observation_id=observation_id,
        detected_hazard_id=hazard_id,
        alert_type=hazard.hazard_type,
        message="analytics test alert",
        status=alert_status,
    )
    hazard.assessments = [assessment]
    hazard.alerts = [alert]
    return hazard


class ZoneAnalyticsTests(unittest.TestCase):
    def test_multiple_areas_highest_lowest_and_common_violations(self) -> None:
        records = [
            make_record(1, "obs-1", "Zone A", "no_helmet", "High", "open"),
            make_record(2, "obs-2", "Zone A", "no_vest", "Moderate", "resolved"),
            make_record(3, "obs-3", "Zone B", "no_helmet", None, "acknowledged"),
            make_record(4, "obs-4", "Zone B", "no_mask", "Critical", "open"),
            make_record(5, "obs-5", "Zone C", "no_boots", "Low", "resolved"),
        ]

        result = summarize_violation_records(records)

        self.assertEqual(result.total_violations, 5)
        self.assertEqual([area.work_area for area in result.violations_by_work_area], ["Zone A", "Zone B", "Zone C"])
        self.assertEqual(result.highest_violation_area.work_area, "Zone A")
        self.assertEqual(result.lowest_violation_area.work_area, "Zone C")
        self.assertEqual(result.most_common_violation.violation_type, "missing_safety_helmet")
        self.assertEqual(result.most_common_violation.count, 2)
        self.assertEqual(result.violations_by_work_area[0].most_common_violation.violation_type, "missing_safety_helmet")
        self.assertEqual(result.violations_by_work_area[1].most_common_violation.violation_type, "missing_protective_mask")

    def test_risk_distribution_and_open_resolved_alert_counts(self) -> None:
        records = [
            make_record(1, "obs-1", "A", "no_helmet", "High", "open"),
            make_record(2, "obs-2", "A", "no_vest", "Moderate", "resolved"),
            make_record(3, "obs-3", "B", "no_helmet", None, "acknowledged"),
            make_record(4, "obs-4", "B", "no_mask", "Critical", "open"),
            make_record(5, "obs-5", "C", "no_boots", "Low", "resolved"),
        ]

        result = summarize_violation_records(records)

        self.assertEqual(
            result.risk_level_distribution,
            {"Low": 1, "Moderate": 1, "High": 1, "Critical": 1, "pending": 1},
        )
        self.assertEqual(result.open_alert_count, 2)
        self.assertEqual(result.unresolved_alert_count, 3)
        self.assertEqual(result.resolved_alert_count, 2)

    def test_empty_database_returns_safe_empty_snapshot(self) -> None:
        result = summarize_violation_records([])

        self.assertEqual(result.total_violations, 0)
        self.assertEqual(result.violations_by_work_area, ())
        self.assertIsNone(result.highest_violation_area)
        self.assertIsNone(result.lowest_violation_area)
        self.assertIsNone(result.most_common_violation)
        self.assertEqual(result.risk_level_distribution, {level: 0 for level in ("Low", "Moderate", "High", "Critical", "pending")})
        self.assertEqual(result.unresolved_alert_count, 0)

    def test_database_query_path_loads_records_before_summarizing(self) -> None:
        record = make_record(1, "obs-1", "Zone A", "no_helmet", "High", "open")
        scalar_result = MagicMock()
        scalar_result.scalars.return_value.all.return_value = [record]
        session = MagicMock()
        session.execute.return_value = scalar_result

        result = get_safety_analytics(session)

        self.assertEqual(result.total_violations, 1)
        session.execute.assert_called_once()

    @patch("app.main.get_safety_analytics")
    def test_zone_analytics_endpoint_returns_lineage(self, get_analytics: MagicMock) -> None:
        record = make_record(1, "obs-1", "Zone A", "no_helmet", "High", "open")
        get_analytics.return_value = summarize_violation_records([record])
        app.dependency_overrides[get_db] = lambda: MagicMock()
        app.dependency_overrides[get_current_user] = lambda: object()
        try:
            response = TestClient(app).get("/analytics/zones")
        finally:
            app.dependency_overrides.clear()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total_violations"], 1)
        self.assertEqual(payload["violations_by_work_area"][0]["observation_ids"], ["obs-1"])
        self.assertFalse(payload["zone_identifier_is_validated_entity"])


if __name__ == "__main__":
    unittest.main()
