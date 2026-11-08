"""Unit tests for stateless Safety Agent conditional routing."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.safety_agent import Detection, DetectionResult, assess_safety, decide_alert
from app.safety_graph import (
    create_review_state,
    decide_route,
    record_no_finding,
    run_safety_graph,
    safety_graph,
)


def _detection_result(*labels: str) -> DetectionResult:
    return DetectionResult(
        image_path=Path("unit-test-image.jpg"),
        image_width=320,
        image_height=240,
        detections=tuple(
            Detection(label, 0.9, (1.0, 2.0, 30.0, 40.0)) for label in labels
        ),
    )


class SafetyGraphTests(unittest.TestCase):
    def test_findings_route_to_review_node(self) -> None:
        assessment = assess_safety(_detection_result("NO-Hardhat"))
        route_state = {
            "assessment_status": "completed",
            "detection_results": assessment.detections,
            "findings": assessment.detected_hazards,
        }

        self.assertEqual(decide_route(route_state), "Alert")
        self.assertEqual(create_review_state(route_state)["routing_decision"], "safety_review_required")
        result = run_safety_graph(assessment)
        self.assertEqual(result["routing_decision"], "assessment_pending")
        self.assertEqual(result["routing_status"], "pending")

    def test_completed_empty_assessment_routes_to_no_finding_node(self) -> None:
        assessment = assess_safety(_detection_result("Person", "Hardhat"))
        route_state = {
            "assessment_status": "completed",
            "detection_results": assessment.detections,
            "findings": (),
        }

        self.assertEqual(decide_route(route_state), "No_findings")
        self.assertEqual(record_no_finding(route_state)["routing_decision"], "no_supported_ppe_violations")
        result = run_safety_graph(assessment)
        self.assertEqual(result["routing_decision"], "no_supported_ppe_violations")
        self.assertEqual(result["routing_status"], "no_findings")

    def test_incomplete_or_invalid_assessment_is_not_no_findings(self) -> None:
        self.assertEqual(decide_route({"findings": ()}), "Assessment_pending")
        self.assertEqual(
            decide_route({"assessment_status": "invalid", "findings": []}),
            "Assessment_pending",
        )
        self.assertEqual(
            decide_route({"assessment_status": "completed", "findings": None}),
            "Assessment_pending",
        )
        self.assertEqual(
            decide_route(
                {
                    "assessment_status": "completed",
                    "findings": (),
                    "detection_results": None,
                }
            ),
            "Assessment_pending",
        )
        incomplete_result = safety_graph.invoke(
            {"assessment_status": "completed", "findings": (), "detection_results": None}
        )
        self.assertEqual(incomplete_result["routing_status"], "pending")
        result = safety_graph.invoke({})
        self.assertEqual(result["routing_decision"], "assessment_pending")
        self.assertEqual(result["routing_status"], "pending")

    def test_compiled_graph_preserves_yolo_results_and_agent_outputs(self) -> None:
        detection_results = _detection_result("NO-Hardhat", "Person")
        assessment = assess_safety(detection_results)
        alert_decision = decide_alert(assessment)
        result = run_safety_graph(assessment, alert_decision)

        self.assertIs(result["detection_results"], detection_results)
        self.assertEqual(result["findings"], assessment.detected_hazards)
        self.assertEqual(result["recommendations"], assessment.recommendations)
        self.assertIs(result["alert_decision"], alert_decision)
        self.assertEqual(
            [d.class_name for d in result["detection_results"].detections],
            ["NO-Hardhat", "Person"],
        )

    def test_graph_does_not_create_persistence_or_notification_side_effects(self) -> None:
        # The compiled graph is pure orchestration over the supplied assessment.
        result = run_safety_graph(assess_safety(_detection_result()))
        self.assertNotIn("observation_record", result)
        self.assertNotIn("notification_sent", result)
        self.assertEqual(result["routing_status"], "no_findings")


if __name__ == "__main__":
    unittest.main()
