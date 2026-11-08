# Experimental Safety Graph

The experimental image upload route reuses the existing Safety Agent for YOLO
inference, supported PPE findings, recommendations, and the alert proposal.
[`backend/app/safety_graph.py`](../backend/app/safety_graph.py) receives those
results and applies conditional routing. It does not load a model, repeat
inference, score risk, persist data, or send notifications.

## State

`SafetyState` carries the original `detection_results`, the `safety_assessment`,
its `findings` and `recommendations`, the Safety Agent's `alert_decision`, and
`assessment_status`. The graph adds `routing_decision`, `routing_status`,
`routing_reason`, and a structured `decision` object. Detection and assessment
objects are retained as returned by the Safety Agent.

## Nodes and routing

- `assess_safety` adapts an already completed Safety Agent result into graph
  state; it does not perform a second assessment.
- `create_review` reports that supported PPE findings need review.
- `record_no_finding` reports that a completed assessment found no supported
  PPE violations.
- `record_incomplete_assessment` reports missing, malformed, or unscored assessment data.
- `decide_route` uses the shared policy outcome: `alert` and `warning` route
  to human review; `pending` routes to incomplete assessment; `no_alert`
  routes to no supported findings only for a structurally completed assessment.
  This is review routing, not notification delivery.

`backend/app/main.py` invokes `run_safety_graph` after the Safety Agent and adds
the graph's routing fields to `/experimental/safety/detect`. The upload remains
temporary and is deleted after inference. The experimental route has no database
dependency or notification call. The Experimental Safety Viewer renders the
backend's routing status, decision, and reason from the response.

## Tests

Run graph, existing Safety Agent, endpoint, and broad backend tests with:

```powershell
.\.venv-yolo\Scripts\python.exe -m unittest backend.tests.test_safety_graph -v
.\.venv-yolo\Scripts\python.exe -m unittest backend.tests.test_safety_file -v
.\.venv-yolo\Scripts\python.exe -m unittest backend.tests.test_experimental_safety -v
.\.venv-yolo\Scripts\python.exe -m unittest discover backend/tests
```
