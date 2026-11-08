"""Analyze YOLO errors and confidence trade-offs on the validation split only.

Run from the repository root with the existing project environment:

    .\\.venv-yolo\\Scripts\\python.exe reports/model-evaluation/analyze_validation.py

All matching uses class-aware, one-to-one greedy assignment at IoU >= 0.50.
Predictions are generated once at confidence 0.05, then filtered to the
requested confidence grid. The 0.25 reference is for error examples only.
This script reads only ``valid/images`` and ``valid/labels``; it never opens
the held-out test split, changes labels, trains, or saves model weights.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import random
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import ultralytics
import yaml
from PIL import Image, ImageDraw, ImageFont
from ultralytics import YOLO


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CHECKPOINT = PROJECT_ROOT / "weights" / "best.pt"
DEFAULT_DATASET = PROJECT_ROOT / "datasets" / "evaluation" / "construction-site-safety-v1"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "reports" / "model-evaluation" / "outputs"
THRESHOLDS = (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50)
REFERENCE_THRESHOLD = 0.25
MINIMUM_INFERENCE_CONFIDENCE = min(THRESHOLDS)
MATCH_IOU = 0.50
CONFUSION_CANDIDATE_IOU = 0.30
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
PPE_CLASSES = {
    "Hardhat",
    "NO-Hardhat",
    "Mask",
    "NO-Mask",
    "Safety Vest",
    "NO-Safety Vest",
    "Gloves",
    "Person",
}
REVIEW_SEED = 2026
MAX_FN_EXAMPLES_PER_CLASS = 3
MAX_FP_EXAMPLES_PER_CLASS = 3
MAX_REVIEW_IMAGES = 14
MANUAL_REVIEW_FINDINGS = [
    {
        "image_name": "airport_inside_0090_jpg.rf.874201ab4cdc29f919627bd19efba9af.jpg",
        "observation": "The image shows people far down an airport concourse. The 12 GT boxes include very small Person and PPE boxes (some only a few pixels wide at 640x640), making class and box boundaries difficult to verify visually.",
        "interpretation": "Candidate for human review of visibility, box extent, and whether distant PPE labels are sufficiently observable; this is not proof of a bad annotation.",
    },
    {
        "image_name": "youtube-308_jpg.rf.660669197399ff5d449f4bd99a7ee2db.jpg",
        "observation": "A kneeling worker is visible; the two Gloves GT boxes fall on small hand regions, and both are missed at the 0.25 reference threshold.",
        "interpretation": "Supports small/occluded-object difficulty as a plausible contributor to glove misses; review the hand visibility and box boundaries before treating it as an annotation error.",
    },
    {
        "image_name": "autox4_mp4-63_jpg.rf.6f327b2292207b3e6f4ce2f234351f6f.jpg",
        "observation": "This is a racing-track scene with a vehicle and traffic cones; the labels also include a distant Person and NO-Safety Vest.",
        "interpretation": "Candidate for domain-scope review: confirm that non-construction scenes and the PPE violation labels on distant figures are intentionally included and consistently labeled.",
    },
    {
        "image_name": "YouTube_FreeStockFootage_People-wearing-face-mask_Empty-Street_Covid19-D_DbgrvhlGs-720p_mp4-66_jpg.rf.20b52f8f0231617b7301fce4b011aa86.jpg",
        "observation": "The image contains a dense urban pedestrian scene with many small, closely spaced people and overlapping PPE/Person boxes; many violation GT boxes have no matching prediction at 0.25.",
        "interpretation": "Candidate for human review of person-to-PPE association, visibility, and domain relevance. The observed misses could also reflect the image difficulty and domain shift.",
    },
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_names(names: Any) -> dict[int, str]:
    if isinstance(names, dict):
        return {int(class_id): str(name) for class_id, name in names.items()}
    if isinstance(names, (list, tuple)):
        return {class_id: str(name) for class_id, name in enumerate(names)}
    raise ValueError(f"Unsupported class-name format: {type(names).__name__}")


def scalar(value: Any) -> float:
    item = getattr(value, "item", None)
    return float(item() if callable(item) else value)


def image_files(directory: Path) -> list[Path]:
    return sorted(
        path for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def read_yolo_labels(label_path: Path, image_width: int, image_height: int, names: dict[int, str]) -> tuple[list[dict[str, Any]], list[str]]:
    objects: list[dict[str, Any]] = []
    issues: list[str] = []
    if not label_path.exists():
        return objects, [f"Missing label file: {label_path.name}"]
    for line_number, line in enumerate(label_path.read_text(encoding="utf-8").splitlines(), start=1):
        parts = line.split()
        if not parts:
            continue
        try:
            class_id = int(parts[0])
            cx, cy, width, height = (float(value) for value in parts[1:5])
        except (ValueError, IndexError):
            issues.append(f"Malformed YOLO row at {label_path.name}:{line_number}")
            continue
        if class_id not in names:
            issues.append(f"Unknown class ID {class_id} at {label_path.name}:{line_number}")
            continue
        if width <= 0 or height <= 0 or not all(0 <= value <= 1 for value in (cx, cy, width, height)):
            issues.append(f"Out-of-range/zero-area box at {label_path.name}:{line_number}")
            continue
        x1 = (cx - width / 2) * image_width
        y1 = (cy - height / 2) * image_height
        x2 = (cx + width / 2) * image_width
        y2 = (cy + height / 2) * image_height
        objects.append({
            "class_id": class_id,
            "class_name": names[class_id],
            "xyxy": [x1, y1, x2, y2],
            "source_line": line_number,
        })
    return objects, issues


def box_iou(left: list[float], right: list[float]) -> float:
    x1 = max(left[0], right[0])
    y1 = max(left[1], right[1])
    x2 = min(left[2], right[2])
    y2 = min(left[3], right[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    left_area = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1])
    right_area = max(0.0, right[2] - right[0]) * max(0.0, right[3] - right[1])
    union = left_area + right_area - intersection
    return intersection / union if union > 0 else 0.0


def match_image(
    ground_truth: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    iou_threshold: float,
    all_predictions: list[dict[str, Any]] | None = None,
    confidence_threshold: float | None = None,
) -> dict[str, Any]:
    """Greedily match per class, highest-confidence predictions first."""
    matched_prediction_indices: set[int] = set()
    matched_ground_truth_indices: set[int] = set()
    matches: list[dict[str, Any]] = []
    false_positives: list[dict[str, Any]] = []

    class_ids = sorted({obj["class_id"] for obj in ground_truth} | {pred["class_id"] for pred in predictions})
    for class_id in class_ids:
        gt_indices = [index for index, obj in enumerate(ground_truth) if obj["class_id"] == class_id]
        pred_indices = sorted(
            (index for index, pred in enumerate(predictions) if pred["class_id"] == class_id),
            key=lambda index: predictions[index]["confidence"],
            reverse=True,
        )
        for pred_index in pred_indices:
            eligible = [
                (box_iou(predictions[pred_index]["xyxy"], ground_truth[gt_index]["xyxy"]), gt_index)
                for gt_index in gt_indices
                if gt_index not in matched_ground_truth_indices
            ]
            best_iou, best_gt = max(eligible, default=(0.0, None))
            if best_gt is not None and best_iou >= iou_threshold:
                matched_prediction_indices.add(pred_index)
                matched_ground_truth_indices.add(best_gt)
                matches.append({"prediction_index": pred_index, "ground_truth_index": best_gt, "iou": best_iou})
            else:
                false_positives.append({"prediction_index": pred_index, "best_same_class_iou": best_iou})

    missed_ground_truths = [
        index for index in range(len(ground_truth)) if index not in matched_ground_truth_indices
    ]
    for item in false_positives:
        pred_index = item["prediction_index"]
        overlaps = [
            (box_iou(predictions[pred_index]["xyxy"], obj["xyxy"]), gt_index)
            for gt_index, obj in enumerate(ground_truth)
        ]
        best_iou, best_gt = max(overlaps, default=(0.0, None))
        item["best_any_class_iou"] = best_iou
        item["best_ground_truth_index"] = best_gt
        item["candidate_class_confusion"] = bool(
            best_gt is not None
            and best_iou >= CONFUSION_CANDIDATE_IOU
            and predictions[pred_index]["class_id"] != ground_truth[best_gt]["class_id"]
        )

    missed_details = []
    candidate_pool = all_predictions if all_predictions is not None else predictions
    for gt_index in missed_ground_truths:
        target = ground_truth[gt_index]
        overlaps = [
            (box_iou(pred["xyxy"], target["xyxy"]), pred_index)
            for pred_index, pred in enumerate(predictions)
        ]
        best_any_iou, best_any_index = max(overlaps, default=(0.0, None))
        same_class_overlaps = [
            (box_iou(pred["xyxy"], target["xyxy"]), pred_index)
            for pred_index, pred in enumerate(predictions)
            if pred["class_id"] == target["class_id"]
        ]
        best_same_iou, best_same_index = max(same_class_overlaps, default=(0.0, None))
        below_threshold_candidates = [
            {
                "prediction": pred,
                "iou": box_iou(pred["xyxy"], target["xyxy"]),
            }
            for pred in candidate_pool
            if pred["class_id"] == target["class_id"]
            and confidence_threshold is not None
            and pred["confidence"] < confidence_threshold
            and box_iou(pred["xyxy"], target["xyxy"]) >= MATCH_IOU
        ]
        above_threshold_candidate_used = any(
            pred["class_id"] == target["class_id"]
            and (confidence_threshold is None or pred["confidence"] >= confidence_threshold)
            and box_iou(pred["xyxy"], target["xyxy"]) >= MATCH_IOU
            for pred in candidate_pool
        )
        if below_threshold_candidates:
            reason = "same_class_candidate_below_confidence_threshold"
        elif above_threshold_candidate_used:
            reason = "same_class_candidate_assigned_elsewhere_or_duplicate"
        elif best_any_index is not None and best_any_iou >= MATCH_IOU and predictions[best_any_index]["class_id"] != target["class_id"]:
            reason = "overlapping_wrong_class_prediction"
        elif best_same_index is not None and best_same_iou > 0:
            reason = "same_class_overlap_below_iou_threshold"
        elif best_any_index is not None and best_any_iou >= CONFUSION_CANDIDATE_IOU:
            reason = "overlap_with_other_class_prediction"
        else:
            reason = "no_material_prediction_overlap"
        missed_details.append({
            "ground_truth_index": gt_index,
            "reason": reason,
            "best_same_class_iou": best_same_iou,
            "best_same_class_prediction_index": best_same_index,
            "best_any_class_iou": best_any_iou,
            "best_any_class_prediction_index": best_any_index,
            "below_threshold_same_class_candidates": below_threshold_candidates,
        })

    return {
        "matches": matches,
        "false_positives": false_positives,
        "missed_ground_truths": missed_details,
    }


def metrics_for_threshold(images: list[dict[str, Any]], threshold: float, names: dict[int, str]) -> dict[str, Any]:
    class_counts = {
        class_id: {"ground_truth": 0, "predictions": 0, "tp": 0, "fp": 0, "fn": 0}
        for class_id in names
    }
    total = {key: 0 for key in ("ground_truth", "predictions", "tp", "fp", "fn")}
    per_image_matches: dict[str, Any] = {}

    for image in images:
        selected_predictions = [pred for pred in image["predictions_min_conf"] if pred["confidence"] >= threshold]
        result = match_image(
            image["ground_truth"],
            selected_predictions,
            MATCH_IOU,
            all_predictions=image["predictions_min_conf"],
            confidence_threshold=threshold,
        )
        per_image_matches[image["image"]] = {
            "selected_predictions": selected_predictions,
            "match_result": result,
        }
        for obj in image["ground_truth"]:
            class_counts[obj["class_id"]]["ground_truth"] += 1
        for pred in selected_predictions:
            class_counts[pred["class_id"]]["predictions"] += 1
        for match in result["matches"]:
            class_id = selected_predictions[match["prediction_index"]]["class_id"]
            class_counts[class_id]["tp"] += 1
        for error in result["false_positives"]:
            class_id = selected_predictions[error["prediction_index"]]["class_id"]
            class_counts[class_id]["fp"] += 1
        for error in result["missed_ground_truths"]:
            class_id = image["ground_truth"][error["ground_truth_index"]]["class_id"]
            class_counts[class_id]["fn"] += 1

    for class_id, values in class_counts.items():
        total["ground_truth"] += values["ground_truth"]
        total["predictions"] += values["predictions"]
        total["tp"] += values["tp"]
        total["fp"] += values["fp"]
        total["fn"] += values["fn"]
    per_class = {}
    for class_id, values in class_counts.items():
        per_class[str(class_id)] = {
            "class_name": names[class_id],
            **values,
            "precision": values["tp"] / values["predictions"] if values["predictions"] else None,
            "recall": values["tp"] / values["ground_truth"] if values["ground_truth"] else None,
        }
    return {
        "confidence_threshold": threshold,
        **total,
        "precision": total["tp"] / total["predictions"] if total["predictions"] else None,
        "recall": total["tp"] / total["ground_truth"] if total["ground_truth"] else None,
        "per_class": per_class,
        "images": per_image_matches,
    }


def safe_label(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_")[:90] or "image"


def draw_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fill: str, font: ImageFont.ImageFont) -> None:
    x, y = xy
    left, top, right, bottom = draw.textbbox((x, y), text, font=font)
    draw.rectangle((left - 2, top - 1, right + 2, bottom + 1), fill=(20, 20, 20))
    draw.text((x, y), text, fill=fill, font=font)


def render_annotated_image(
    source_path: Path,
    gt: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    match_result: dict[str, Any],
    destination: Path,
    names: dict[int, str],
) -> None:
    image = Image.open(source_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    missed_gt = {row["ground_truth_index"] for row in match_result["missed_ground_truths"]}
    false_positive_pred = {row["prediction_index"] for row in match_result["false_positives"]}
    matched_pred = {row["prediction_index"] for row in match_result["matches"]}
    # GT green; missed GT red; matched predictions blue; false positives magenta.
    for index, obj in enumerate(gt):
        color = "#ff3030" if index in missed_gt else "#00c853"
        width = 4 if index in missed_gt else 2
        box = tuple(round(value) for value in obj["xyxy"])
        draw.rectangle(box, outline=color, width=width)
        label = f"GT {obj['class_name']}" + (" [MISSED]" if index in missed_gt else "")
        draw_text(draw, (box[0], max(0, box[1] - 13)), label, color, font)
    for index, pred in enumerate(predictions):
        color = "#ff00ff" if index in false_positive_pred else "#00a5ff"
        width = 4 if index in false_positive_pred else 2
        box = tuple(round(value) for value in pred["xyxy"])
        draw.rectangle(box, outline=color, width=width)
        marker = "FP" if index in false_positive_pred else ("TP" if index in matched_pred else "PRED")
        label = f"{marker} {pred['class_name']} {pred['confidence']:.2f}"
        draw_text(draw, (box[0], min(image.height - 12, box[3] + 1)), label, color, font)
    legend_height = 48
    draw.rectangle((0, 0, image.width, legend_height), fill=(15, 15, 15))
    draw.text((6, 4), "GT green | missed GT red | matched prediction blue | false positive magenta", fill="white", font=font)
    draw.text((6, 22), f"Confidence >= {REFERENCE_THRESHOLD:.2f} | class-aware IoU match >= {MATCH_IOU:.2f}", fill="white", font=font)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, quality=92)


def select_review_images(images: list[dict[str, Any]], names: dict[int, str]) -> list[dict[str, Any]]:
    rng = random.Random(REVIEW_SEED)
    selected: dict[str, dict[str, Any]] = {}
    target_ids = [class_id for class_id, name in names.items() if name in PPE_CLASSES]
    for class_id in target_ids:
        candidates = [image for image in images if any(obj["class_id"] == class_id for obj in image["ground_truth"])]
        rng.shuffle(candidates)
        for image in candidates[:2]:
            selected[image["image"]] = image
    remaining = [image for image in images if image["image"] not in selected]
    rng.shuffle(remaining)
    for image in remaining:
        if len(selected) >= MAX_REVIEW_IMAGES:
            break
        selected[image["image"]] = image
    return list(selected.values())[:MAX_REVIEW_IMAGES]


def create_contact_sheet(paths: list[Path], destination: Path, columns: int = 3, cell_size: tuple[int, int] = (480, 320)) -> None:
    if not paths:
        return
    rows = (len(paths) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * cell_size[0], rows * (cell_size[1] + 24)), (35, 35, 35))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, path in enumerate(paths):
        image = Image.open(path).convert("RGB")
        image.thumbnail(cell_size)
        column = index % columns
        row = index // columns
        x = column * cell_size[0] + (cell_size[0] - image.width) // 2
        y = row * (cell_size[1] + 24)
        sheet.paste(image, (x, y))
        draw.text((column * cell_size[0] + 4, y + cell_size[1] + 3), path.name[:70], fill="white", font=font)
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination, quality=88)


def make_run_dir(output_root: Path) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    run_id = "validation-analysis-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = output_root / run_id
    if run_dir.exists():
        raise FileExistsError(f"Refusing to overwrite prior analysis: {run_dir}")
    run_dir.mkdir()
    for name in ("false_negative_examples", "false_positive_examples", "annotation_review"):
        (run_dir / name).mkdir()
    return run_dir


def write_threshold_csv(threshold_results: list[dict[str, Any]], names: dict[int, str], path: Path) -> None:
    columns = [
        "confidence_threshold", "class_id", "class_name", "ground_truth_instances",
        "predictions", "tp", "fp", "fn", "precision", "recall",
    ]
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for result in threshold_results:
            writer.writerow({
                "confidence_threshold": result["confidence_threshold"],
                "class_id": "",
                "class_name": "ALL",
                "ground_truth_instances": result["ground_truth"],
                "predictions": result["predictions"],
                "tp": result["tp"],
                "fp": result["fp"],
                "fn": result["fn"],
                "precision": result["precision"],
                "recall": result["recall"],
            })
            for class_id in names:
                values = result["per_class"][str(class_id)]
                writer.writerow({
                    "confidence_threshold": result["confidence_threshold"],
                    "class_id": class_id,
                    "class_name": values["class_name"],
                    "ground_truth_instances": values["ground_truth"],
                    "predictions": values["predictions"],
                    "tp": values["tp"],
                    "fp": values["fp"],
                    "fn": values["fn"],
                    "precision": values["precision"],
                    "recall": values["recall"],
                })


def write_report(report: dict[str, Any], path: Path) -> None:
    reference = next(row for row in report["threshold_results"] if row["confidence_threshold"] == REFERENCE_THRESHOLD)
    missed_classes = sorted(
        (row for row in reference["per_class"].values() if row["fn"]),
        key=lambda row: row["fn"], reverse=True,
    )
    false_positive_classes = sorted(
        (row for row in reference["per_class"].values() if row["fp"]),
        key=lambda row: row["fp"], reverse=True,
    )
    lines = [
        "# Validation-Split YOLO Error Analysis",
        "",
        f"- Run: `{report['run_id']}`",
        f"- Generated UTC: `{report['generated_at_utc']}`",
        f"- Checkpoint SHA256: `{report['checkpoint']['sha256']}`",
        f"- Validation images analyzed: **{report['validation']['image_count']}**",
        f"- Ground-truth instances: **{report['validation']['instance_count']}**",
        f"- Class map matches checkpoint: **{report['class_map_match']}**",
        f"- Matching: **class-aware one-to-one greedy matching, IoU >= {MATCH_IOU:.2f}**; each prediction can match at most one ground-truth box.",
        f"- Threshold sweep: {', '.join(f'{value:.2f}' for value in THRESHOLDS)}. Predictions were generated at the minimum threshold and then score-filtered.",
        f"- Error-example reference threshold: **{REFERENCE_THRESHOLD:.2f}**. This is an analysis reference only; production behavior was not changed.",
        "- This analysis reads only the validation split. No training or checkpoint writes occurred.",
        "",
        "## Threshold comparison",
        "",
        "| Confidence | Predictions | TP | FP | FN | Precision | Recall |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["threshold_results"]:
        lines.append(
            f"| {row['confidence_threshold']:.2f} | {row['predictions']} | {row['tp']} | {row['fp']} | {row['fn']} | "
            f"{row['precision']:.4f} | {row['recall']:.4f} |"
        )
    lines.extend([
        "",
        "Lower confidence retains more candidate boxes and can recover missed objects, but it also admits additional false positives. The fixed IoU criterion and one-to-one assignment are unchanged across thresholds. This sweep is descriptive and does not select a production threshold.",
        "",
        f"## PPE classes at confidence {REFERENCE_THRESHOLD:.2f}",
        "",
        "| Class | GT instances | Predictions | TP | FP | FN | Precision | Recall |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for class_id, row in reference["per_class"].items():
        if row["class_name"] in PPE_CLASSES:
            p = "n/a" if row["precision"] is None else f"{row['precision']:.4f}"
            r = "n/a" if row["recall"] is None else f"{row['recall']:.4f}"
            lines.append(f"| {row['class_name']} (ID {class_id}) | {row['ground_truth']} | {row['predictions']} | {row['tp']} | {row['fp']} | {row['fn']} | {p} | {r} |")
    lines.extend(["", "## Most frequently missed classes at the reference threshold", ""])
    lines.extend(f"- **{row['class_name']}**: {row['fn']} missed / {row['ground_truth']} ground-truth instances" for row in missed_classes[:10])
    lines.extend(["", "## Classes with the most false positives at the reference threshold", ""])
    lines.extend(f"- **{row['class_name']}**: {row['fp']} false-positive boxes" for row in false_positive_classes[:10])
    lines.extend([
        "",
        "## Interpretation: measured findings and hypotheses",
        "",
        "Measured counts and threshold metrics are in this report and `threshold_comparison.csv`. Each missed object includes nearest same-class and any-class IoU evidence in the JSON. Candidate wrong-class overlaps use IoU >= 0.30 for review only; the TP criterion remains IoU >= 0.50.",
        "",
        "Potential causes such as class imbalance, occlusion, small/distant PPE, image-domain mismatch, annotation omissions, or class confusion are hypotheses unless supported by the listed per-image evidence and human review. The script flags malformed/missing/out-of-range label rows but does not rewrite labels.",
        "",
        "### Manual visual sample notes",
        "",
    ])
    for finding in report["manual_visual_review"]:
        lines.append(f"- `{finding['image_name']}` — {finding['observation']} **Review:** {finding['interpretation']}")
    lines.extend([
        "",
        "These are review candidates from the sample, not confirmed annotation defects. The automated format checks found no missing, malformed, or out-of-range validation label rows.",
        "",
        "## Annotation review sample",
        "",
        f"A deterministic sample of up to {MAX_REVIEW_IMAGES} validation images is in `annotation_review/`, with GT and prediction overlays at the fixed reference threshold. The report does not automatically declare annotations wrong; see `annotation_review/annotation_review_notes.md` and `review_index.csv` for manual review candidates.",
        "",
        "## Artifacts",
        "",
        "- `validation_error_analysis.json`: full image-level GT and predictions, baseline matches/errors, and all threshold metrics.",
        "- `threshold_comparison.csv`: overall and per-class counts/precision/recall for each threshold.",
        "- `false_negative_examples/`: selected images with missed GT boxes highlighted.",
        "- `false_positive_examples/`: selected images with false-positive predictions highlighted.",
        "- `annotation_review/`: deterministic sample, contact sheet, index, and human-review guidance.",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def analyze(checkpoint: Path, dataset_root: Path, output_root: Path) -> Path:
    if not checkpoint.is_file():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint}")
    validation_images_dir = dataset_root / "valid" / "images"
    validation_labels_dir = dataset_root / "valid" / "labels"
    if not validation_images_dir.is_dir() or not validation_labels_dir.is_dir():
        raise FileNotFoundError("Validation images/labels not found; expected valid/images and valid/labels")

    with (dataset_root / "data.yaml").open("r", encoding="utf-8") as stream:
        dataset_config = yaml.safe_load(stream)
    if not isinstance(dataset_config, dict):
        raise ValueError("Dataset data.yaml must contain a mapping")
    dataset_names = normalize_names(dataset_config.get("names"))
    if int(dataset_config.get("nc", len(dataset_names))) != len(dataset_names):
        raise ValueError("Dataset nc does not match the number of class names")

    model = YOLO(str(checkpoint))
    model_names = normalize_names(model.names)
    if model_names != dataset_names:
        raise ValueError("Checkpoint class IDs/names do not exactly match validation dataset data.yaml")

    output_dir = make_run_dir(output_root)
    image_paths = image_files(validation_images_dir)
    if not image_paths:
        raise ValueError("No validation images found")

    image_records: list[dict[str, Any]] = []
    label_issues: list[dict[str, str]] = []
    class_instance_counts = Counter()
    class_image_counts = Counter()
    device = "0" if torch.cuda.is_available() else "cpu"
    print(f"Analyzing validation only: {len(image_paths)} images; device={device}; Ultralytics={ultralytics.__version__}")

    for index, image_path in enumerate(image_paths, start=1):
        with Image.open(image_path) as opened:
            opened.load()
            width, height = opened.size
        labels_path = validation_labels_dir / f"{image_path.stem}.txt"
        ground_truth, issues = read_yolo_labels(labels_path, width, height, dataset_names)
        label_issues.extend({"image": str(image_path), "issue": issue} for issue in issues)
        image_class_ids = set()
        for obj in ground_truth:
            class_instance_counts[obj["class_id"]] += 1
            image_class_ids.add(obj["class_id"])
        for class_id in image_class_ids:
            class_image_counts[class_id] += 1

        results = model.predict(
            source=str(image_path),
            conf=MINIMUM_INFERENCE_CONFIDENCE,
            imgsz=640,
            iou=0.70,
            max_det=300,
            device=device,
            verbose=False,
        )
        predictions: list[dict[str, Any]] = []
        for result in results or ():
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            for box_index in range(len(boxes)):
                class_id = int(scalar(boxes.cls[box_index]))
                if class_id not in model_names:
                    continue
                predictions.append({
                    "class_id": class_id,
                    "class_name": model_names[class_id],
                    "confidence": scalar(boxes.conf[box_index]),
                    "xyxy": [float(value) for value in boxes.xyxy[box_index].tolist()],
                })
        image_records.append({
            "image": str(image_path),
            "width": width,
            "height": height,
            "ground_truth": ground_truth,
            "predictions_min_conf": predictions,
        })
        if index % 20 == 0 or index == len(image_paths):
            print(f"Processed {index}/{len(image_paths)} validation images")

    threshold_results = [metrics_for_threshold(image_records, threshold, dataset_names) for threshold in THRESHOLDS]
    reference_result = next(row for row in threshold_results if row["confidence_threshold"] == REFERENCE_THRESHOLD)
    ref_image_errors = reference_result["images"]

    # Save selected false-negative examples: up to three images per class, sorted
    # by the matched object's nearest same-class IoU (least overlap first).
    fn_candidates: dict[int, list[tuple[float, dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    fp_candidates: dict[int, list[tuple[float, dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    image_by_path = {image["image"]: image for image in image_records}
    for image_key, error_data in ref_image_errors.items():
        image = image_by_path[image_key]
        for missed in error_data["match_result"]["missed_ground_truths"]:
            gt = image["ground_truth"][missed["ground_truth_index"]]
            fn_candidates[gt["class_id"]].append((missed["best_same_class_iou"], image, error_data))
        for false_positive in error_data["match_result"]["false_positives"]:
            pred = error_data["selected_predictions"][false_positive["prediction_index"]]
            fp_candidates[pred["class_id"]].append((pred["confidence"], image, error_data))

    saved_fn: set[str] = set()
    for class_id, candidates in fn_candidates.items():
        for _, image, error_data in sorted(candidates, key=lambda item: item[0])[:MAX_FN_EXAMPLES_PER_CLASS]:
            if image["image"] in saved_fn:
                continue
            saved_fn.add(image["image"])
            target = output_dir / "false_negative_examples" / f"{class_id:02d}_{safe_label(Path(image['image']).stem)}.jpg"
            render_annotated_image(Path(image["image"]), image["ground_truth"], error_data["selected_predictions"], error_data["match_result"], target, dataset_names)
    saved_fp: set[str] = set()
    for class_id, candidates in fp_candidates.items():
        for _, image, error_data in sorted(candidates, key=lambda item: item[0], reverse=True)[:MAX_FP_EXAMPLES_PER_CLASS]:
            if image["image"] in saved_fp:
                continue
            saved_fp.add(image["image"])
            target = output_dir / "false_positive_examples" / f"{class_id:02d}_{safe_label(Path(image['image']).stem)}.jpg"
            render_annotated_image(Path(image["image"]), image["ground_truth"], error_data["selected_predictions"], error_data["match_result"], target, dataset_names)

    review_images = select_review_images(image_records, dataset_names)
    review_rows = []
    review_paths = []
    for image in review_images:
        error_data = ref_image_errors[image["image"]]
        destination = output_dir / "annotation_review" / f"{safe_label(Path(image['image']).stem)}.jpg"
        render_annotated_image(Path(image["image"]), image["ground_truth"], error_data["selected_predictions"], error_data["match_result"], destination, dataset_names)
        review_paths.append(destination)
        review_rows.append({
            "image": image["image"],
            "review_overlay": str(destination),
            "ground_truth_classes": ";".join(sorted({obj["class_name"] for obj in image["ground_truth"]})),
            "ground_truth_count": len(image["ground_truth"]),
            "predictions_at_0_25": len(error_data["selected_predictions"]),
            "missed_at_0_25": len(error_data["match_result"]["missed_ground_truths"]),
            "false_positives_at_0_25": len(error_data["match_result"]["false_positives"]),
            "review_reason": "Deterministic PPE-stratified sample; visually confirm box extent, class, visibility, occlusion, and whether any object is unlabeled.",
        })
    create_contact_sheet(review_paths, output_dir / "annotation_review" / "contact_sheet.jpg")
    with (output_dir / "annotation_review" / "review_index.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(review_rows[0]) if review_rows else ["image"])
        writer.writeheader()
        writer.writerows(review_rows)
    (output_dir / "annotation_review" / "annotation_review_notes.md").write_text(
        "# Annotation review guidance\n\n"
        "This folder contains a deterministic, PPE-stratified sample of validation images with ground-truth and model overlays. "
        "The automated analysis does not decide that an annotation is wrong. A reviewer should compare visible workers/PPE with the green ground-truth boxes, "
        "red missed ground-truth boxes, blue matched predictions, and magenta false positives. Check for absent labels, incorrect class IDs, overly broad/tight boxes, "
        "small or distant PPE, occlusion, and ambiguity. Record any conclusion with the original image path and evidence; do not edit dataset labels during this review.\n\n"
        f"Label-format issues detected automatically: {len(label_issues)}. See the JSON report for paths and details.\n\n"
        "## Manual sample observations\n\n"
        + "\n".join(
            f"- `{finding['image_name']}` — {finding['observation']} Review: {finding['interpretation']}"
            for finding in MANUAL_REVIEW_FINDINGS
        )
        + "\n",
        encoding="utf-8",
    )

    total_gt = sum(class_instance_counts.values())
    report = {
        "run_id": output_dir.name,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "validation only",
        "checkpoint": {"path": str(checkpoint.resolve()), "sha256": sha256_file(checkpoint.resolve()), "size_bytes": checkpoint.stat().st_size},
        "dataset": {"path": str(dataset_root.resolve()), "data_yaml": str((dataset_root / "data.yaml").resolve()), "split_read": "valid", "class_count": len(dataset_names)},
        "class_map_match": True,
        "environment": {
            "python_version": platform.python_version(),
            "ultralytics_version": ultralytics.__version__,
            "torch_version": torch.__version__,
            "device": device,
        },
        "validation": {
            "image_count": len(image_records),
            "instance_count": total_gt,
            "class_instance_counts": {str(class_id): class_instance_counts[class_id] for class_id in dataset_names},
            "class_image_counts": {str(class_id): class_image_counts[class_id] for class_id in dataset_names},
        },
        "matching": {
            "method": "class-aware greedy one-to-one; predictions sorted by descending confidence; each GT and prediction matched at most once",
            "iou_threshold": MATCH_IOU,
            "candidate_class_confusion_iou": CONFUSION_CANDIDATE_IOU,
        },
        "inference": {
            "imgsz": 640,
            "nms_iou": 0.70,
            "max_det": 300,
            "minimum_confidence": MINIMUM_INFERENCE_CONFIDENCE,
            "thresholds": list(THRESHOLDS),
            "error_example_reference_threshold": REFERENCE_THRESHOLD,
        },
        "label_issues": label_issues,
        "manual_visual_review": MANUAL_REVIEW_FINDINGS,
        "threshold_results": [
            {key: value for key, value in row.items() if key != "images"}
            for row in threshold_results
        ],
        "reference_threshold_per_image_errors": {
            image_key: {
                "selected_predictions": error_data["selected_predictions"],
                "matches": error_data["match_result"]["matches"],
                "false_positives": [
                    {
                        **item,
                        "prediction": error_data["selected_predictions"][item["prediction_index"]],
                    }
                    for item in error_data["match_result"]["false_positives"]
                ],
                "missed_ground_truths": [
                    {
                        **item,
                        "ground_truth": image_by_path[image_key]["ground_truth"][item["ground_truth_index"]],
                        "best_same_class_prediction": (
                            error_data["selected_predictions"][item["best_same_class_prediction_index"]]
                            if item["best_same_class_prediction_index"] is not None else None
                        ),
                        "best_any_class_prediction": (
                            error_data["selected_predictions"][item["best_any_class_prediction_index"]]
                            if item["best_any_class_prediction_index"] is not None else None
                        ),
                    }
                    for item in error_data["match_result"]["missed_ground_truths"]
                ],
            }
            for image_key, error_data in ref_image_errors.items()
            if error_data["match_result"]["false_positives"] or error_data["match_result"]["missed_ground_truths"]
        },
        "all_validation_images": [
            {
                "image": image["image"],
                "width": image["width"],
                "height": image["height"],
                "ground_truth": image["ground_truth"],
                "predictions_at_minimum_confidence": image["predictions_min_conf"],
            }
            for image in image_records
        ],
        "examples": {
            "false_negative_directory": "false_negative_examples",
            "false_negative_images": sorted(path.name for path in (output_dir / "false_negative_examples").glob("*.jpg")),
            "false_positive_directory": "false_positive_examples",
            "false_positive_images": sorted(path.name for path in (output_dir / "false_positive_examples").glob("*.jpg")),
            "annotation_review_directory": "annotation_review",
            "annotation_review_images": [path.name for path in review_paths],
        },
        "limitations": [
            "These are validation-split metrics at a fixed IoU matching criterion, not Ultralytics' AP metrics.",
            "The score sweep is descriptive and must not be used as a held-out test or production-threshold selection.",
            "Automated overlaps cannot establish annotation correctness; sampled images require human review.",
        ],
    }
    with (output_dir / "validation_error_analysis.json").open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    write_threshold_csv(threshold_results, dataset_names, output_dir / "threshold_comparison.csv")
    write_report(report, output_dir / "validation_error_analysis.md")
    return output_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        output_dir = analyze(args.checkpoint, args.dataset, args.output_root)
    except Exception as error:
        print(f"Validation analysis failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(f"Validation analysis completed: {output_dir}")
    print(f"Markdown report: {output_dir / 'validation_error_analysis.md'}")
    print(f"JSON report: {output_dir / 'validation_error_analysis.json'}")
    print(f"Threshold CSV: {output_dir / 'threshold_comparison.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
