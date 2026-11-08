"""Informational recurrence of distinct persisted PPE-violation observations."""

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parents[1]))
os.environ["DATABASE_URL"] = ""

from app.analytics import (
    get_work_area_recurrence, summarize_violation_records,
    summarize_work_area_recurrence,
)
from app.auth import get_current_user
from app.database import get_db
from app.db_models import Alert, DetectedHazardRecord, Observation, RiskAssessment
from app.main import app
from app.risk_agent import LABEL_TO_HAZARD


NOW = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)


def finding(
    hazard_id: int,
    observation_id: str,
    area: str | None,
    label: str = "no_helmet",
    *,
    hazard_type: str | None = None,
    observed_at: datetime = NOW,
    source: str = "image_upload:site_image",
    raw_metadata: dict | None = None,
) -> DetectedHazardRecord:
    observation = Observation(
        observation_id=observation_id,
        observed_at=observed_at,
        source=source,
        work_area=area,
        repeated_count=4,
        raw_metadata=raw_metadata,
    )
    record = DetectedHazardRecord(
        detected_hazard_id=hazard_id,
        observation_id=observation_id,
        observation=observation,
        source_label=label,
        hazard_type=hazard_type or LABEL_TO_HAZARD.get(label, "unknown_hazard"),
        detected_at=observed_at,
    )
    record.assessments = [RiskAssessment(
        assessment_id=hazard_id + 100,
        assessment_version=1,
        status="completed",
        risk_score=40,
        risk_band="High",
    )]
    record.alerts = [Alert(
        alert_id=hazard_id + 200,
        observation_id=observation_id,
        alert_type=record.hazard_type,
        message="existing alert",
        status="acknowledged",
    )]
    return record


class WorkAreaRecurrenceTests(unittest.TestCase):
    def test_two_observations_repeat_but_two_rows_in_one_observation_count_once(self):
        records = [
            finding(1, "obs-a", "North"),
            finding(2, "obs-a", "North"),
            finding(3, "obs-b", "North"),
        ]
        result = summarize_work_area_recurrence(records)
        self.assertEqual(len(result.groups), 1)
        group = result.groups[0]
        self.assertEqual(group.hazard_type, "missing_safety_helmet")
        self.assertEqual(group.observation_count, 2)
        self.assertTrue(group.is_repeated)
        self.assertEqual(group.observation_ids, ("obs-a", "obs-b"))
        self.assertEqual(result.repeated_work_area_count, 1)
        self.assertEqual(result.work_areas_by_observation_count[0].observation_count, 2)
        # Existing zone analytics intentionally retain hazard-row semantics.
        self.assertEqual(summarize_violation_records(records).total_violations, 3)

    def test_one_observation_is_observed_not_repeated(self):
        group = summarize_work_area_recurrence([finding(1, "obs-a", "North")]).groups[0]
        self.assertEqual(group.observation_count, 1)
        self.assertFalse(group.is_repeated)

    def test_area_and_canonical_hazard_type_form_separate_groups(self):
        records = [
            finding(1, "obs-a", "North"),
            finding(2, "obs-b", "South"),
            finding(3, "obs-c", "North", "no_vest"),
        ]
        result = summarize_work_area_recurrence(records)
        self.assertEqual(
            {(group.work_area, group.hazard_type, group.observation_count)
             for group in result.groups},
            {
                ("North", "missing_safety_helmet", 1),
                ("South", "missing_safety_helmet", 1),
                ("North", "missing_safety_vest", 1),
            },
        )
        self.assertEqual(result.repeated_work_area_count, 0)
        self.assertEqual(result.work_areas_by_observation_count[0].observation_count, 2)

    def test_blank_null_and_unspecified_areas_are_not_named_recurrence(self):
        records = [
            finding(1, "obs-a", None),
            finding(2, "obs-b", "  "),
            finding(3, "obs-c", "Unspecified"),
            finding(4, "obs-d", " unspecified "),
            finding(5, "obs-e", "Named"),
        ]
        result = summarize_work_area_recurrence(records)
        self.assertEqual([group.work_area for group in result.groups], ["Named"])
        self.assertEqual(result.groups[0].observation_ids, ("obs-e",))

    def test_trims_outer_whitespace_but_preserves_case_and_internal_spelling(self):
        records = [
            finding(1, "obs-a", "  Zone A  "),
            finding(2, "obs-b", "Zone A"),
            finding(3, "obs-c", "zone a"),
            finding(4, "obs-d", "Zone-A"),
            finding(5, "obs-e", "Zone  A"),
        ]
        result = summarize_work_area_recurrence(records)
        self.assertEqual(
            {group.work_area: group.observation_count for group in result.groups},
            {"Zone A": 2, "zone a": 1, "Zone-A": 1, "Zone  A": 1},
        )
        self.assertEqual(result.repeated_work_area_count, 1)

    def test_unsupported_or_malformed_label_type_pairs_are_excluded(self):
        records = [
            finding(1, "obs-a", "North", "no_helmet"),
            finding(2, "obs-b", "North", "not_a_supported_label"),
            finding(3, "obs-c", "North", "no_helmet", hazard_type="missing_safety_vest"),
        ]
        group = summarize_work_area_recurrence(records).groups[0]
        self.assertEqual(group.observation_ids, ("obs-a",))
        self.assertFalse(group.is_repeated)

    def test_legacy_no_hash_and_json_observations_are_evidence(self):
        records = [
            finding(1, "legacy-image", "North", raw_metadata={"image": {"storage_key": "old"}}),
            finding(2, "json-observation", "North", source="api_test", raw_metadata=None),
        ]
        group = summarize_work_area_recurrence(records).groups[0]
        self.assertEqual(group.observation_count, 2)
        self.assertEqual(group.observation_ids, ("json-observation", "legacy-image"))

    def test_equal_image_hashes_under_distinct_observation_ids_still_count(self):
        metadata = {"image": {"sha256": "a" * 64}}
        records = [
            finding(1, "assessment-one", "North", raw_metadata=metadata),
            finding(2, "assessment-two", "North", raw_metadata=metadata),
        ]
        group = summarize_work_area_recurrence(records).groups[0]
        self.assertEqual(group.observation_count, 2)
        self.assertEqual(group.observation_ids, ("assessment-one", "assessment-two"))
        self.assertTrue(group.is_repeated)

    def test_explicit_half_open_window_and_timezone_conversion(self):
        start = NOW - timedelta(hours=1)
        end = NOW + timedelta(hours=1)
        records = [
            finding(1, "before", "North", observed_at=start - timedelta(microseconds=1)),
            finding(2, "at-start", "North", observed_at=start),
            finding(3, "inside", "North", observed_at=NOW),
            finding(4, "at-end", "North", observed_at=end),
        ]
        offset = timezone(timedelta(hours=5, minutes=30))
        result = summarize_work_area_recurrence(
            records, start=start.astimezone(offset), end=end.astimezone(offset),
        )
        self.assertEqual(result.window_start, start)
        self.assertEqual(result.window_end, end)
        self.assertEqual(result.groups[0].observation_ids, ("at-start", "inside"))
        self.assertEqual(summarize_work_area_recurrence(records).groups[0].observation_count, 4)

    def test_deterministic_count_descending_then_area_and_type_order(self):
        records = [
            finding(5, "z-1", "Z", "no_vest"),
            finding(4, "a-2", "A", "no_vest"),
            finding(3, "a-1", "A", "no_helmet"),
            finding(2, "z-2", "Z", "no_vest"),
            finding(1, "a-3", "A", "no_helmet"),
            finding(6, "a-4", "A", "no_vest"),
        ]
        result = summarize_work_area_recurrence(reversed(records))
        self.assertEqual(
            [(group.work_area, group.hazard_type, group.observation_count) for group in result.groups],
            [
                ("A", "missing_safety_helmet", 2),
                ("A", "missing_safety_vest", 2),
                ("Z", "missing_safety_vest", 2),
            ],
        )
        self.assertEqual(
            [(area.work_area, area.observation_count) for area in result.work_areas_by_observation_count],
            [("A", 4), ("Z", 2)],
        )

    def test_read_only_aggregate_preserves_repetition_scores_alerts_and_old_metrics(self):
        records = [finding(1, "obs-a", "North"), finding(2, "obs-a", "North")]
        before = [
            (record.observation.repeated_count, record.assessments[0].risk_score,
             record.assessments[0].risk_band, record.alerts[0].status)
            for record in records
        ]
        old_analytics = summarize_violation_records(records)
        recurrence = summarize_work_area_recurrence(records)
        self.assertEqual(recurrence.groups[0].observation_count, 1)
        self.assertEqual(old_analytics.total_violations, 2)
        self.assertEqual(summarize_violation_records(records), old_analytics)
        self.assertEqual([
            (record.observation.repeated_count, record.assessments[0].risk_score,
             record.assessments[0].risk_band, record.alerts[0].status)
            for record in records
        ], before)
        self.assertEqual([len(record.alerts) for record in records], [1, 1])

    def test_query_filters_observed_at_and_does_not_write(self):
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = [finding(1, "obs-a", "A")]
        result = get_work_area_recurrence(
            session, start=NOW - timedelta(days=1), end=NOW + timedelta(days=1),
        )
        self.assertEqual(result.groups[0].observation_count, 1)
        statement = session.execute.call_args.args[0]
        sql = str(statement)
        self.assertIn("observations.observed_at >=", sql)
        self.assertIn("observations.observed_at <", sql)
        session.add.assert_not_called()
        session.flush.assert_not_called()
        session.commit.assert_not_called()

    def test_endpoint_exposes_bounds_groups_lineage_and_unbounded_history(self):
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = [
            finding(1, "obs-a", "North"), finding(2, "obs-b", "North"),
        ]
        app.dependency_overrides[get_db] = lambda: session
        app.dependency_overrides[get_current_user] = lambda: object()
        try:
            client = TestClient(app)
            bounded = client.get(
                "/analytics/work-area-recurrence?start=2026-11-05T11:00:00Z&end=2026-11-05T13:00:00Z"
            )
            unbounded = client.get("/analytics/work-area-recurrence")
        finally:
            app.dependency_overrides.clear()
        self.assertEqual(bounded.status_code, 200)
        body = bounded.json()
        self.assertEqual(body["window_start"], "2026-11-05T11:00:00Z")
        self.assertEqual(body["window_end"], "2026-11-05T13:00:00Z")
        self.assertEqual(body["groups"][0]["observation_ids"], ["obs-a", "obs-b"])
        self.assertEqual(body["groups"][0]["observation_count"], 2)
        self.assertTrue(body["groups"][0]["is_repeated"])
        self.assertEqual(body["repeated_work_area_count"], 1)
        self.assertEqual(body["counting_unit"], "distinct_observation_id")
        self.assertTrue(body["informational_only"])
        self.assertEqual(unbounded.status_code, 200)
        self.assertIsNone(unbounded.json()["window_start"])
        self.assertIsNone(unbounded.json()["window_end"])
        session.add.assert_not_called()

    def test_endpoint_rejects_naive_or_inverted_window_and_requires_db(self):
        app.dependency_overrides[get_current_user] = lambda: object()
        app.dependency_overrides[get_db] = lambda: MagicMock()
        try:
            client = TestClient(app)
            naive = client.get("/analytics/work-area-recurrence?start=2026-11-05T11:00:00")
            inverted = client.get(
                "/analytics/work-area-recurrence?start=2026-11-05T13:00:00Z&end=2026-11-05T11:00:00Z"
            )
            app.dependency_overrides[get_db] = lambda: None
            no_db = client.get("/analytics/work-area-recurrence")
        finally:
            app.dependency_overrides.clear()
        self.assertEqual(naive.status_code, 422)
        self.assertEqual(inverted.status_code, 422)
        self.assertEqual(no_db.status_code, 503)


if __name__ == "__main__":
    unittest.main()
