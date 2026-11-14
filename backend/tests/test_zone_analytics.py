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

from app.analytics import get_finding_observation_page, get_safety_analytics, summarize_violation_records
from app.analytics import validate_recurrence_window
from app.database import get_db
from app.db_models import Alert, DetectedHazardRecord, Observation, RiskAssessment
from app.main import app
from app.auth import get_current_user
from app.scoring import risk_band
from sqlalchemy.dialects import postgresql


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
    def test_distinct_observations_latest_assessments_and_alert_units(self) -> None:
        observation = Observation(observation_id="shared", observed_at=NOW, source="test", work_area="Zone A")
        helmet = make_record(10, "shared", "Zone A", "no_helmet", "High", "open")
        vest = make_record(11, "shared", "Zone A", "no_vest", None, "dismissed")
        helmet.observation = observation
        vest.observation = observation
        observation.detected_hazards = [helmet, vest]
        helmet.assessments = [
            RiskAssessment(assessment_id=1001, assessment_version=1, status="completed", risk_score=35, risk_band="Low"),
            RiskAssessment(assessment_id=1002, assessment_version=2, status="completed", risk_score=60, risk_band="incorrect historical band"),
        ]
        result = summarize_violation_records([helmet, vest])
        area = result.violations_by_work_area[0]

        self.assertEqual(result.total_violations, 2)
        self.assertEqual(result.unique_observation_count, 1)
        self.assertEqual(area.observation_count, 1)
        self.assertEqual(result.valid_latest_completed_assessment_count, 1)
        self.assertEqual(result.pending_latest_assessment_count, 1)
        self.assertEqual(result.provisional_observation_count, 1)
        self.assertEqual(result.overall_observation_risk_distribution[risk_band(60)], 1)
        self.assertEqual(result.individual_alert_count, 2)
        self.assertEqual(result.alert_status_counts["open"], 1)
        self.assertEqual(result.alert_status_counts["dismissed"], 1)
        self.assertEqual(result.safety_case_count, 1)
        self.assertEqual(len(area.violation_metrics), 2)

    def test_latest_missing_or_malformed_assessment_is_incomplete_not_a_score(self) -> None:
        record = make_record(20, "obs-invalid", "Zone A", "no_helmet", "High", "open")
        record.assessments = [
            RiskAssessment(assessment_id=2001, assessment_version=1, status="completed", risk_score=70, risk_band="High"),
            RiskAssessment(assessment_id=2002, assessment_version=2, status="completed", risk_score=None, risk_band="High"),
        ]
        result = summarize_violation_records([record])
        self.assertEqual(result.valid_latest_completed_assessment_count, 0)
        self.assertEqual(result.incomplete_latest_assessment_count, 1)
        self.assertEqual(result.overall_observation_risk_distribution["High"], 0)

    def test_zone_window_uses_timezone_aware_half_open_bounds(self) -> None:
        start = datetime(2026, 3, 15, 5, tzinfo=timezone.utc)
        end = datetime(2026, 3, 16, 5, tzinfo=timezone.utc)
        normalized = validate_recurrence_window(start, end)
        self.assertEqual(normalized, (start, end))
        with self.assertRaises(ValueError):
            validate_recurrence_window(datetime(2026, 3, 15), end)
        with self.assertRaises(ValueError):
            validate_recurrence_window(end, start)

    def test_supporting_observation_page_deduplicates_and_uses_stable_pagination(self) -> None:
        first = Observation(observation_id="obs-new", observed_at=NOW, source="test", work_area="Zone A")
        second = Observation(observation_id="obs-old", observed_at=NOW, source="test", work_area="Zone A")
        page_result = MagicMock()
        page_result.all.return_value = [MagicMock(observation_id="obs-new"), MagicMock(observation_id="obs-old")]
        detail_result = MagicMock()
        detail_result.scalars.return_value.all.return_value = [first, second]
        matches = MagicMock()
        matches.all.return_value = [("obs-new", 12), ("obs-new", 13), ("obs-old", 14)]
        session = MagicMock()
        session.scalar.side_effect = [2, 3]
        session.execute.side_effect = [page_result, detail_result, matches]

        result = get_finding_observation_page(
            session, work_area="Zone A", hazard_type="missing_safety_helmet",
            start=NOW, end=NOW.replace(day=16), sort="newest", limit=2, offset=4,
        )
        page_compiled = session.execute.call_args_list[0].args[0].compile(dialect=postgresql.dialect())
        page_sql = str(page_compiled)
        self.assertEqual(result["total_observations"], 2)
        self.assertEqual(result["total_matching_findings"], 3)
        self.assertEqual([item[0].observation_id for item in result["items"]], ["obs-new", "obs-old"])
        self.assertEqual(result["items"][0][1], [12, 13])
        self.assertIn("OFFSET", page_sql.upper())
        self.assertIn("LIMIT", page_sql.upper())
        self.assertIn("missing_safety_helmet", page_compiled.params.values())
        self.assertIn("no_helmet", page_compiled.params.values())
        self.assertIn("Zone A", page_compiled.params.values())
        self.assertIn(NOW, page_compiled.params.values())
        self.assertIn(NOW.replace(day=16), page_compiled.params.values())
        self.assertIn(" DESC", page_sql.upper())
        self.assertEqual(session.execute.call_count, 3)

    def test_recurrence_supporting_page_uses_same_named_area_exclusions(self) -> None:
        observation = Observation(observation_id="obs-recurrence", observed_at=NOW, source="test", work_area="Zone A")
        page_result = MagicMock()
        page_result.all.return_value = [MagicMock(observation_id="obs-recurrence")]
        detail_result = MagicMock()
        detail_result.scalars.return_value.all.return_value = [observation]
        matches = MagicMock()
        matches.all.return_value = [("obs-recurrence", 12)]
        session = MagicMock()
        session.scalar.side_effect = [1, 1]
        session.execute.side_effect = [page_result, detail_result, matches]

        result = get_finding_observation_page(
            session, work_area="Zone A", hazard_type="missing_safety_helmet",
            start=NOW, end=NOW.replace(day=16), area_mode="recurrence", sort="oldest", limit=10, offset=0,
        )
        page_query = session.execute.call_args_list[0].args[0]
        compiled = page_query.compile(dialect=postgresql.dialect())
        sql = str(compiled).lower()

        self.assertEqual(result["total_observations"], 1)
        self.assertEqual([item.observation_id for item, _ in result["items"]], ["obs-recurrence"])
        self.assertIn("not (observations.work_area is null", sql)
        self.assertIn("lower(trim(observations.work_area)) in", sql)
        self.assertIn("trim(observations.work_area) =", sql)
        parameters = [value for item in compiled.params.values() for value in (item if isinstance(item, list) else [item])]
        self.assertIn("Zone A", parameters)
        self.assertIn("unspecified", parameters)
        self.assertIn("unknown", parameters)
        self.assertIn("unassigned work area", parameters)

    def test_analytics_and_supporting_observation_endpoints_are_authenticated(self) -> None:
        client = TestClient(app)
        self.assertEqual(client.get("/analytics/zones").status_code, 401)
        self.assertEqual(client.get("/analytics/finding-observations").status_code, 401)

    @patch("app.main.get_finding_observation_page")
    def test_supporting_observation_api_forwards_filters_and_returns_empty_totals(self, query: MagicMock) -> None:
        query.return_value = {"items": [], "total_observations": 0, "total_matching_findings": 0, "limit": 5, "offset": 10}
        app.dependency_overrides[get_db] = lambda: MagicMock()
        app.dependency_overrides[get_current_user] = lambda: object()
        try:
            response = TestClient(app).get(
                "/analytics/finding-observations?work_area=Zone%20A&hazard_type=missing_safety_helmet&start=2026-03-15T00:00:00Z&end=2026-03-16T00:00:00Z&area_mode=recurrence&sort=oldest&limit=5&offset=10"
            )
            invalid_category = TestClient(app).get("/analytics/finding-observations?hazard_type=unknown")
        finally:
            app.dependency_overrides.clear()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total_observations"], 0)
        self.assertEqual(response.json()["items"], [])
        self.assertEqual(invalid_category.status_code, 422)
        query.assert_called_once()
        self.assertEqual(query.call_args.kwargs["work_area"], "Zone A")
        self.assertEqual(query.call_args.kwargs["hazard_type"], "missing_safety_helmet")
        self.assertEqual(query.call_args.kwargs["area_mode"], "recurrence")
        self.assertEqual(query.call_args.kwargs["sort"], "oldest")
        self.assertEqual(query.call_args.kwargs["limit"], 5)
        self.assertEqual(query.call_args.kwargs["offset"], 10)

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
        self.assertEqual(result.alert_status_counts, {"open": 2, "acknowledged": 1, "resolved": 2, "dismissed": 0})

    def test_empty_database_returns_safe_empty_snapshot(self) -> None:
        result = summarize_violation_records([])

        self.assertEqual(result.total_violations, 0)
        self.assertEqual(result.violations_by_work_area, ())
        self.assertIsNone(result.highest_violation_area)
        self.assertIsNone(result.lowest_violation_area)
        self.assertIsNone(result.most_common_violation)
        self.assertEqual(result.risk_level_distribution, {level: 0 for level in ("Low", "Moderate", "High", "Critical", "pending")})
        self.assertEqual(result.unresolved_alert_count, 0)

    def test_unknown_work_areas_stay_in_the_explicit_unspecified_bucket(self) -> None:
        result = summarize_violation_records([
            make_record(30, "unknown-1", None, "no_helmet", None, "open"),
            make_record(31, "unknown-2", "  ", "no_vest", None, "resolved"),
            make_record(32, "unknown-3", " UNKNOWN ", "no_mask", None, "dismissed"),
            make_record(33, "named-1", "Zone A", "no_boots", None, "acknowledged"),
        ])
        areas = {item.work_area: item for item in result.violations_by_work_area}
        self.assertEqual(areas["Unspecified"].observation_count, 3)
        self.assertEqual(areas["Unspecified"].violation_count, 3)
        self.assertEqual(areas["Zone A"].observation_count, 1)

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
