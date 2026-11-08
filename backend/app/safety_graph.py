"""Stateless LangGraph routing for completed Safety Agent assessments.

The Safety Agent remains responsible for inference and hazard assessment. This
graph receives its structured results and selects a review, no-finding, or
incomplete-assessment outcome without performing external side effects.
"""

from collections.abc import Sequence
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from .safety_agent import decide_alert


AssessmentStatus = Literal["completed", "pending", "invalid"]
RoutingDecision = Literal[
    "safety_review_required",
    "no_supported_ppe_violations",
    "assessment_pending",
]


class SafetyState(TypedDict, total=False):
    """Data carried through routing, retaining the Safety Agent's result objects."""

    detection_results: Any
    safety_assessment: Any
    findings: Sequence[Any]
    recommendations: Sequence[Any]
    alert_decision: Any
    assessment_status: AssessmentStatus
    routing_decision: RoutingDecision
    routing_status: str
    routing_reason: str
    decision: dict[str, str]


def _prepare_assessment(state: SafetyState) -> dict[str, Any]:
    """Expose fields from a real SafetyAssessment without rerunning assessment."""

    assessment = state.get("safety_assessment")
    if assessment is not None:
        required_fields = ("detections", "detected_hazards", "assessments", "recommendations")
        if not all(hasattr(assessment, field) for field in required_fields):
            return {"assessment_status": "invalid"}
        detections = assessment.detections
        findings = assessment.detected_hazards
        recommendations = assessment.recommendations
        if (
            detections is None
            or not hasattr(detections, "detections")
            or not isinstance(findings, Sequence)
            or isinstance(findings, (str, bytes))
            or not isinstance(recommendations, Sequence)
            or isinstance(recommendations, (str, bytes))
        ):
            return {"assessment_status": "invalid"}
        return {
            "detection_results": detections,
            "findings": findings,
            "recommendations": recommendations,
            "alert_decision": state.get("alert_decision") or decide_alert(assessment),
            "assessment_status": "completed",
        }

    # Also permit explicit, typed state input for callers and deterministic tests.
    status = state.get("assessment_status")
    findings = state.get("findings")
    if (
        status == "completed"
        and state.get("detection_results") is not None
        and hasattr(state["detection_results"], "detections")
        and isinstance(findings, Sequence)
        and not isinstance(findings, (str, bytes))
    ):
        return {}
    return {"assessment_status": "invalid" if status == "invalid" else "pending"}


def decide_route(state: SafetyState) -> Literal["Alert", "No_findings", "Assessment_pending"]:
    """Route findings to review; only a valid completed empty assessment is clear."""

    decision = state.get("alert_decision")
    if decision is not None:
        if decision.outcome == "pending":
            return "Assessment_pending"
        if decision.outcome in ("alert", "warning"):
            return "Alert"
        if decision.outcome == "no_alert" and state.get("assessment_status") == "completed":
            return "No_findings"
    findings = state.get("findings")
    if isinstance(findings, Sequence) and not isinstance(findings, (str, bytes)):
        if findings:
            return "Alert"
        detection_results = state.get("detection_results")
        if (
            state.get("assessment_status") == "completed"
            and detection_results is not None
            and hasattr(detection_results, "detections")
        ):
            return "No_findings"
    return "Assessment_pending"


def create_review_state(state: SafetyState) -> dict[str, Any]:
    """Represent supported PPE findings that need a human safety review."""

    decision = {
        "routing_decision": "safety_review_required",
        "routing_status": "review_required",
        "routing_reason": "The Safety Agent reported one or more supported PPE findings.",
    }
    return {**decision, "decision": decision}


def record_no_finding(state: SafetyState) -> dict[str, Any]:
    """Represent a completed assessment with no supported PPE violations."""

    decision = {
        "routing_decision": "no_supported_ppe_violations",
        "routing_status": "no_findings",
        "routing_reason": "The completed assessment returned no supported PPE findings.",
    }
    return {**decision, "decision": decision}


def record_incomplete_assessment(state: SafetyState) -> dict[str, Any]:
    """Keep a missing or malformed assessment distinct from a no-finding result."""

    decision = {
        "routing_decision": "assessment_pending",
        "routing_status": "pending",
        "routing_reason": "A valid completed Safety Agent assessment was not available.",
    }
    return {**decision, "decision": decision}


def _build_graph():
    builder = StateGraph(SafetyState)
    builder.add_node("assess_safety", _prepare_assessment)
    builder.add_node("create_review", create_review_state)
    builder.add_node("record_no_finding", record_no_finding)
    builder.add_node("record_incomplete_assessment", record_incomplete_assessment)
    builder.add_edge(START, "assess_safety")
    builder.add_conditional_edges(
        "assess_safety",
        decide_route,
        {
            "Alert": "create_review",
            "No_findings": "record_no_finding",
            "Assessment_pending": "record_incomplete_assessment",
        },
    )
    builder.add_edge("create_review", END)
    builder.add_edge("record_no_finding", END)
    builder.add_edge("record_incomplete_assessment", END)
    return builder.compile()


safety_graph = _build_graph()


def run_safety_graph(
    safety_assessment: Any = None,
    alert_decision: Any = None,
) -> SafetyState:
    """Invoke the compiled graph with existing Safety Agent outputs."""

    return safety_graph.invoke(
        {
            "safety_assessment": safety_assessment,
            "alert_decision": alert_decision,
        }
    )
