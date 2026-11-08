"""Evaluate the existing YOLO checkpoint on the archived held-out test split.

Run from the repository root with the project's YOLO environment:

    .\\.venv-yolo\\Scripts\\python.exe reports/model-evaluation/evaluate_yolo.py

The script does not train or save model weights. It uses Ultralytics' standard
validation confidence handling (no custom ``conf`` is passed), evaluates only
the dataset's ``test`` split, and creates a unique output directory per run.
The source archive is never modified. Dataset extraction and evaluation
artifacts live under Git-ignored directories.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

import torch
import ultralytics
import yaml
from PIL import Image
from ultralytics import YOLO


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CHECKPOINT = PROJECT_ROOT / "weights" / "best.pt"
DEFAULT_ARCHIVE = PROJECT_ROOT / "datasets" / "raw" / "Construction Site Safety.v1i.yolov8.zip"
DEFAULT_DATASET_ROOT = PROJECT_ROOT / "datasets" / "evaluation" / "construction-site-safety-v1"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "reports" / "model-evaluation" / "outputs"
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
PREVIOUS_VALIDATION = {
    "precision": 0.463,
    "recall": 0.458,
    "mAP50": 0.435,
    "mAP50-95": 0.288,
    "images": 114,
    "instances": 733,
    "source": "Saved validation output in notebooks/Construction_Risk_YOLO_Training.ipynb",
}


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


def safe_extract_archive(archive_path: Path, destination: Path) -> None:
    """Extract a ZIP only after rejecting paths that escape the destination."""

    destination.mkdir(parents=True, exist_ok=True)
    destination_resolved = destination.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            member_path = PurePosixPath(member.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise ValueError(f"Unsafe archive path rejected: {member.filename}")
            target = (destination / Path(*member_path.parts)).resolve()
            if target != destination_resolved and destination_resolved not in target.parents:
                raise ValueError(f"Archive member escapes extraction directory: {member.filename}")
        archive.extractall(destination)


def ensure_dataset_extracted(archive_path: Path, dataset_root: Path) -> None:
    required = [
        dataset_root / "data.yaml",
        dataset_root / "train" / "images",
        dataset_root / "valid" / "images",
        dataset_root / "test" / "images",
        dataset_root / "test" / "labels",
    ]
    if all(path.exists() for path in required):
        return
    if dataset_root.exists() and any(dataset_root.iterdir()):
        raise FileExistsError(
            f"Dataset directory exists but is incomplete; refusing to overwrite it: {dataset_root}"
        )
    safe_extract_archive(archive_path, dataset_root)
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Archive extraction did not produce required paths: " + ", ".join(missing))


def image_files(directory: Path) -> list[Path]:
    return sorted(path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES)


def count_test_instances(images_dir: Path, labels_dir: Path, class_count: int) -> tuple[int, list[int], list[str]]:
    counts = [0] * class_count
    warnings: list[str] = []
    images = image_files(images_dir)
    for image_path in images:
        label_path = labels_dir / f"{image_path.stem}.txt"
        if not label_path.exists():
            warnings.append(f"Missing label file for {image_path.name}")
            continue
        for line_number, line in enumerate(label_path.read_text(encoding="utf-8").splitlines(), start=1):
            parts = line.split()
            if not parts:
                continue
            try:
                class_id = int(parts[0])
            except ValueError:
                warnings.append(f"Invalid class ID in {label_path.name}:{line_number}")
                continue
            if not 0 <= class_id < class_count:
                warnings.append(f"Out-of-range class ID {class_id} in {label_path.name}:{line_number}")
                continue
            counts[class_id] += 1
    return len(images), counts, warnings


def checkpoint_metadata(model: YOLO) -> dict[str, Any]:
    inner = getattr(model, "model", None)
    model_yaml = getattr(inner, "yaml", None)
    if not isinstance(model_yaml, dict):
        model_yaml = {}
    checkpoint = getattr(model, "ckpt", None)
    if not isinstance(checkpoint, dict):
        checkpoint = {}
    stride = getattr(inner, "stride", None)
    if stride is not None:
        try:
            stride_value: Any = stride.detach().cpu().tolist()
        except AttributeError:
            stride_value = stride
    else:
        stride_value = None
    parameter_count = None
    if inner is not None and callable(getattr(inner, "parameters", None)):
        parameter_count = sum(parameter.numel() for parameter in inner.parameters())
    return {
        "architecture": type(inner).__name__ if inner is not None else None,
        "parameter_count": parameter_count,
        "task": getattr(model, "task", None),
        "yaml_file": model_yaml.get("yaml_file"),
        "scale": model_yaml.get("scale"),
        "configured_class_count": model_yaml.get("nc"),
        "stride": stride_value,
        "checkpoint_epoch": checkpoint.get("epoch"),
        "checkpoint_date": checkpoint.get("date"),
        "checkpoint_ultralytics_version": checkpoint.get("version"),
    }


def make_run_directory(output_root: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_root.mkdir(parents=True, exist_ok=True)
    run_dir = output_root / f"test-evaluation-{timestamp}"
    if run_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing evaluation output: {run_dir}")
    run_dir.mkdir()
    return run_dir


def build_per_class_metrics(metrics: Any, names: dict[int, str], dataset_counts: list[int]) -> list[dict[str, Any]]:
    box_metrics = metrics.box
    class_positions = {int(class_id): position for position, class_id in enumerate(metrics.ap_class_index)}
    nt_per_class = getattr(metrics, "nt_per_class", None)
    nt_per_image = getattr(metrics, "nt_per_image", None)
    rows: list[dict[str, Any]] = []
    for class_id in range(len(names)):
        position = class_positions.get(class_id)
        instances = int(nt_per_class[class_id]) if nt_per_class is not None else dataset_counts[class_id]
        images = int(nt_per_image[class_id]) if nt_per_image is not None else None
        if position is None:
            precision = recall = map50 = map5095 = None
        else:
            precision, recall, map50, map5095 = (float(value) for value in metrics.class_result(position))
        rows.append(
            {
                "class_id": class_id,
                "class_name": names[class_id],
                "images": images,
                "instances": instances,
                "precision": precision,
                "recall": recall,
                "mAP50": map50,
                "mAP50-95": map5095,
            }
        )
    return rows


def find_visuals(run_dir: Path) -> list[str]:
    candidates = {
        "confusion_matrix.png",
        "confusion_matrix_normalized.png",
        "PR_curve.png",
        "BoxPR_curve.png",
        "P_curve.png",
        "BoxP_curve.png",
        "R_curve.png",
        "BoxR_curve.png",
        "F1_curve.png",
        "BoxF1_curve.png",
    }
    return sorted(
        str(path.relative_to(run_dir))
        for path in run_dir.rglob("*")
        if path.is_file() and (path.name in candidates or path.name.startswith("val_batch") and path.suffix.lower() in {".jpg", ".jpeg", ".png"})
    )


def write_markdown_report(report: dict[str, Any], destination: Path) -> None:
    overall = report["metrics"]
    lines = [
        "# YOLOv8 PPE Test-Split Evaluation",
        "",
        f"- Run ID: `{report['run_id']}`",
        f"- Generated (UTC): `{report['generated_at_utc']}`",
        f"- Checkpoint: `{report['checkpoint']['path']}`",
        f"- Dataset archive: `{report['dataset']['archive_path']}`",
        f"- Test split: `{report['dataset']['test_images']} images`, `{report['dataset']['test_instances']} labeled instances`",
        f"- Ultralytics: `{report['environment']['ultralytics_version']}`; PyTorch: `{report['environment']['torch_version']}`; device: `{report['environment']['device']}`",
        "- Evaluation protocol: Ultralytics validation on `split=test`, `imgsz=640`, `batch=16`, `plots=True`; no custom confidence threshold was supplied.",
        "- No training or weight saving was performed. Precision/recall follow Ultralytics' built-in confidence sweep; its summary operating point is reported for evaluation only. No production threshold was selected or changed from test results.",
        "",
        "## Overall metrics",
        "",
        "| Metric | Test split | Previous notebook validation |",
        "|---|---:|---:|",
        f"| Precision | {overall['precision']:.4f} | {PREVIOUS_VALIDATION['precision']:.3f} |",
        f"| Recall | {overall['recall']:.4f} | {PREVIOUS_VALIDATION['recall']:.3f} |",
        f"| mAP50 | {overall['mAP50']:.4f} | {PREVIOUS_VALIDATION['mAP50']:.3f} |",
        f"| mAP50-95 | {overall['mAP50-95']:.4f} | {PREVIOUS_VALIDATION['mAP50-95']:.3f} |",
        "",
        "The prior values are saved validation output from the training notebook on 114 validation images / 733 instances. This test split is a different 82-image / labeled-instance sample, so differences are descriptive and do not isolate a model change.",
        "",
        "## PPE-focused classes",
        "",
        "| ID | Class | Images | Instances | Precision | Recall | mAP50 | mAP50-95 |",
        "|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["per_class_metrics"]:
        if row["class_name"] not in PPE_CLASSES:
            continue
        values = [row[key] for key in ("precision", "recall", "mAP50", "mAP50-95")]
        formatted = ["n/a" if value is None else f"{value:.4f}" for value in values]
        lines.append(
            f"| {row['class_id']} | {row['class_name']} | {row['images'] or 0} | {row['instances']} | "
            + " | ".join(formatted)
            + " |"
        )
    lines.extend(["", "`n/a` means the class had no evaluable ground-truth instances in the test split, so per-class metrics are undefined.", "", "## Generated visual evidence", ""])
    if report["visuals"]:
        lines.extend(f"- `{item}`" for item in report["visuals"])
    else:
        lines.append("No supported plot files were found in the Ultralytics output directory.")
    lines.extend(["", "## Dataset and checkpoint integrity", "", f"- Checkpoint SHA256: `{report['checkpoint']['sha256']}`", f"- Dataset archive SHA256: `{report['dataset']['archive_sha256']}`", f"- Class map match: `{report['class_map_match']}`", f"- Checkpoint metadata: `{json.dumps(report['checkpoint']['metadata'], sort_keys=True)}`", ""])
    if report["warnings"]:
        lines.extend(["## Warnings", "", *[f"- {warning}" for warning in report["warnings"]], ""])
    destination.write_text("\n".join(lines), encoding="utf-8")


def run_evaluation(checkpoint: Path, archive: Path, dataset_root: Path, output_root: Path) -> Path:
    for required_path in (checkpoint, archive):
        if not required_path.is_file():
            raise FileNotFoundError(f"Required input not found: {required_path}")

    checkpoint = checkpoint.resolve()
    archive = archive.resolve()
    dataset_root = dataset_root.resolve()
    output_root = output_root.resolve()
    ensure_dataset_extracted(archive, dataset_root)

    with (dataset_root / "data.yaml").open("r", encoding="utf-8") as stream:
        original_data = yaml.safe_load(stream)
    if not isinstance(original_data, dict):
        raise ValueError("Dataset data.yaml must contain a YAML mapping")
    dataset_names = normalize_names(original_data.get("names"))
    declared_count = int(original_data.get("nc", len(dataset_names)))
    if declared_count != len(dataset_names):
        raise ValueError(f"Dataset declares nc={declared_count}, but has {len(dataset_names)} class names")

    model = YOLO(str(checkpoint))
    checkpoint_names = normalize_names(model.names)
    if checkpoint_names != dataset_names:
        mismatches = [
            f"ID {class_id}: dataset={dataset_names.get(class_id)!r}, checkpoint={checkpoint_names.get(class_id)!r}"
            for class_id in sorted(set(dataset_names) | set(checkpoint_names))
            if dataset_names.get(class_id) != checkpoint_names.get(class_id)
        ]
        raise ValueError("Checkpoint class IDs/names do not match dataset data.yaml: " + "; ".join(mismatches))

    test_images_dir = dataset_root / "test" / "images"
    test_labels_dir = dataset_root / "test" / "labels"
    image_count, dataset_instance_counts, warnings = count_test_instances(
        test_images_dir, test_labels_dir, declared_count
    )
    if image_count == 0:
        raise ValueError(f"No test images found in {test_images_dir}")
    if warnings:
        # Dataset integrity warnings should be visible before costly inference.
        print("Dataset warnings:", file=sys.stderr)
        for warning in warnings:
            print(f"- {warning}", file=sys.stderr)

    run_dir = make_run_directory(output_root)
    eval_yaml = run_dir / "evaluation-data.yaml"
    evaluation_data = dict(original_data)
    evaluation_data.update(
        {
            "path": str(dataset_root),
            "train": "train/images",
            "val": "valid/images",
            "test": "test/images",
            "nc": declared_count,
            "names": [dataset_names[class_id] for class_id in range(declared_count)],
        }
    )
    with eval_yaml.open("w", encoding="utf-8") as stream:
        yaml.safe_dump(evaluation_data, stream, sort_keys=False, allow_unicode=True)

    cuda_available = torch.cuda.is_available()
    device = "0" if cuda_available else "cpu"
    # Deliberately omit `conf`: Ultralytics validation uses its standard metric
    # protocol to construct PR curves and aggregate precision/recall/mAP.
    metrics = model.val(
        data=str(eval_yaml),
        split="test",
        imgsz=640,
        batch=16,
        device=device,
        workers=0,
        plots=True,
        project=str(run_dir / "ultralytics"),
        name="test",
        exist_ok=False,
        verbose=True,
    )

    mean_precision, mean_recall, mean_map50, mean_map5095 = (float(value) for value in metrics.mean_results())
    per_class = build_per_class_metrics(metrics, dataset_names, dataset_instance_counts)
    result_dirs = sorted((run_dir / "ultralytics").glob("test*"), key=lambda path: path.stat().st_mtime)
    visuals = find_visuals(result_dirs[-1]) if result_dirs else []
    actual_instance_count = int(sum(int(value) for value in metrics.nt_per_class))
    report = {
        "run_id": run_dir.name,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "checkpoint": {
            "path": str(checkpoint),
            "size_bytes": checkpoint.stat().st_size,
            "sha256": sha256_file(checkpoint),
            "class_names": {str(class_id): name for class_id, name in checkpoint_names.items()},
            "metadata": checkpoint_metadata(model),
        },
        "dataset": {
            "archive_path": str(archive),
            "archive_sha256": sha256_file(archive),
            "extracted_path": str(dataset_root),
            "source_data_yaml": str(dataset_root / "data.yaml"),
            "evaluation_data_yaml": str(eval_yaml),
            "class_count": declared_count,
            "test_images": image_count,
            "test_instances": actual_instance_count,
            "test_instances_from_labels": int(sum(dataset_instance_counts)),
            "test_instances_by_class": {str(class_id): count for class_id, count in enumerate(dataset_instance_counts)},
        },
        "class_map_match": True,
        "environment": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "ultralytics_version": ultralytics.__version__,
            "torch_version": torch.__version__,
            "cuda_available": cuda_available,
            "device": device,
        },
        "evaluation": {
            "split": "test",
            "imgsz": 640,
            "batch": 16,
            "workers": 0,
            "plots": True,
            "custom_confidence_threshold": None,
            "test_images_evaluated": int(getattr(metrics, "seen", image_count) or image_count),
            "instances_evaluated": actual_instance_count,
            "ultralytics_output_directory": str(result_dirs[-1]) if result_dirs else None,
        },
        "metrics": {
            "precision": mean_precision,
            "recall": mean_recall,
            "mAP50": mean_map50,
            "mAP50-95": mean_map5095,
        },
        "previous_validation": PREVIOUS_VALIDATION,
        "per_class_metrics": per_class,
        "visuals": visuals,
        "warnings": warnings,
    }

    with (run_dir / "evaluation_report.json").open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    with (run_dir / "per_class_metrics.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(per_class[0]))
        writer.writeheader()
        writer.writerows(per_class)
    write_markdown_report(report, run_dir / "evaluation_report.md")
    return run_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_dir = run_evaluation(args.checkpoint, args.archive, args.dataset_root, args.output_root)
    except Exception as error:
        print(f"Evaluation failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(f"Evaluation completed: {run_dir}")
    print(f"Markdown report: {run_dir / 'evaluation_report.md'}")
    print(f"JSON report: {run_dir / 'evaluation_report.json'}")
    print(f"Per-class CSV: {run_dir / 'per_class_metrics.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
