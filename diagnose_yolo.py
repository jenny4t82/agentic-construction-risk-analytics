r"""Compare YOLO PPE detections at multiple confidence thresholds.

This diagnostic does not modify the application or model. Run it with the
project's YOLO environment from the repository root:

    .\.venv-yolo\Scripts\python.exe diagnose_yolo.py
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from PIL import Image
from ultralytics import YOLO


PROJECT_ROOT = Path(__file__).resolve().parent
CHECKPOINT = PROJECT_ROOT / "weights" / "best.pt"
IMAGE_PATHS = (
    Path(r"C:\Users\ALL AtoZ\OneDrive\Pictures\construct1.png"),
    Path(r"C:\Users\ALL AtoZ\OneDrive\Pictures\construct2.jpg"),
)
CONFIDENCE_THRESHOLDS = (0.25, 0.15, 0.05)


def class_name_for(names: Any, class_id: int) -> str:
    """Return the checkpoint's original class name for an ID."""

    if isinstance(names, Mapping):
        return str(names.get(class_id, class_id))
    if isinstance(names, Sequence) and not isinstance(names, (str, bytes)):
        if 0 <= class_id < len(names):
            return str(names[class_id])
    return str(class_id)


def scalar(value: Any) -> float:
    """Convert an Ultralytics tensor scalar without rounding its value."""

    item = getattr(value, "item", None)
    return float(item() if callable(item) else value)


def inspect_image(model: YOLO, image_path: Path) -> dict[str, Any]:
    """Run the same checkpoint once at each threshold and retain raw boxes."""

    entry: dict[str, Any] = {"image": str(image_path), "threshold_results": []}
    if not image_path.is_file():
        entry["error"] = "Image path does not exist or is not a file."
        return entry

    try:
        with Image.open(image_path) as image:
            image.load()
            entry["image_size"] = {"width": image.width, "height": image.height}
    except Exception as error:
        entry["error"] = f"Image could not be decoded: {error}"
        return entry

    for threshold in CONFIDENCE_THRESHOLDS:
        threshold_result: dict[str, Any] = {
            "confidence_threshold": threshold,
            "total_detections": 0,
            "detections": [],
        }
        try:
            predictions = model.predict(
                source=str(image_path),
                conf=threshold,
                verbose=False,
            )
            for prediction in predictions or ():
                boxes = getattr(prediction, "boxes", None)
                if boxes is None:
                    continue
                names = getattr(prediction, "names", model.names)
                for index in range(len(boxes)):
                    class_id = int(scalar(boxes.cls[index]))
                    confidence = scalar(boxes.conf[index])
                    coordinates = boxes.xyxy[index].tolist()
                    if len(coordinates) != 4:
                        continue
                    threshold_result["detections"].append(
                        {
                            "class_name": class_name_for(names, class_id),
                            "class_id": class_id,
                            "confidence": confidence,
                            "bounding_box_xyxy": [float(value) for value in coordinates],
                        }
                    )
            threshold_result["total_detections"] = len(threshold_result["detections"])
        except Exception as error:
            threshold_result["error"] = f"Inference failed: {error}"
        entry["threshold_results"].append(threshold_result)
    return entry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        type=Path,
        help="Also write the JSON report to this path; existing files are never overwritten.",
    )
    args = parser.parse_args()

    report_path: Path | None = args.report
    if report_path is not None:
        if not report_path.is_absolute():
            report_path = PROJECT_ROOT / report_path
        if report_path.exists():
            print(f"Refusing to overwrite existing report: {report_path}", file=sys.stderr)
            return 2

    if not CHECKPOINT.is_file():
        print(json.dumps({"error": f"Checkpoint not found: {CHECKPOINT}"}, indent=2))
        return 1

    try:
        model = YOLO(str(CHECKPOINT))
    except Exception as error:
        print(json.dumps({"error": f"Could not load checkpoint: {error}"}, indent=2))
        return 1

    report = {
        "checkpoint": str(CHECKPOINT),
        "class_names": model.names,
        "confidence_thresholds": CONFIDENCE_THRESHOLDS,
        "images": [inspect_image(model, image_path) for image_path in IMAGE_PATHS],
    }
    report_text = json.dumps(report, indent=2, ensure_ascii=False)
    print(report_text)
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
