from pathlib import Path
from pprint import pprint

from backend.app.safety_agent import (
    load_model,
    detect_objects,
    assess_safety,
    decide_alert,
)

PROJECT_ROOT = Path(__file__).resolve().parent
IMAGE_PATH = PROJECT_ROOT / "runs" / "detect" / "predict-3" / "construction_test2.jpg"


def main():
    print("=" * 60)
    print("REAL CONSTRUCTION IMAGE - SAFETY AGENT TEST")
    print("=" * 60)

    # 1. Load the trained YOLO model
    print("\n[1] Loading trained YOLO model...")
    model = load_model()
    print("Model loaded successfully.")

    # 2. Detect objects in the real image
    print(f"\n[2] Detecting objects in:\n{IMAGE_PATH}")
    detections = detect_objects(IMAGE_PATH, model)
    print("Detection results:")
    pprint(detections)

    # 3. Assess safety based on the detections
    print("\n[3] Assessing safety...")
    assessment = assess_safety(detections)
    print("Safety assessment:")
    pprint(assessment)

    # 4. Decide whether an alert should be recommended
    print("\n[4] Deciding alert...")
    alert = decide_alert(assessment)
    print("Alert decision:")
    pprint(alert)

    print("\n" + "=" * 60)
    print("REAL-IMAGE TEST COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    main()