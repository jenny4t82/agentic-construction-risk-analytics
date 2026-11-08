#!/usr/bin/env python3
"""Reproducible, read-only Stage 1 PPE annotation audit.

Reads the existing matched image/label pairs and writes class summaries,
deterministic representative contact sheets, and a review index. Orphan label
files are excluded from annotation counts and samples.
"""
from __future__ import annotations

import csv
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = ROOT / "datasets/evaluation/construction-site-safety-v1"
SUPPLEMENTARY = ROOT / "datasets/external/ultralytics-construction-ppe"
OUT = ROOT / "reports/model-evaluation/outputs/ppe-audit"
ORIGINAL_CLASSES = {
    0: "Excavator", 1: "Gloves", 2: "Hardhat", 3: "Ladder", 4: "Mask",
    5: "NO-Hardhat", 6: "NO-Mask", 7: "NO-Safety Vest", 8: "Person",
    9: "SUV", 10: "Safety Cone", 11: "Safety Vest", 12: "bus",
    13: "dump truck", 14: "fire hydrant", 15: "machinery", 16: "mini-van",
    17: "sedan", 18: "semi", 19: "trailer", 20: "truck",
    21: "truck and trailer", 22: "van", 23: "vehicle", 24: "wheel loader",
}
SUPP_CLASSES = {
    0: "helmet", 1: "gloves", 2: "vest", 3: "boots", 4: "goggles",
    5: "none", 6: "Person", 7: "no_helmet", 8: "no_goggle",
    9: "no_gloves", 10: "no_boots",
}
CLASS_AUDIT_NOTES = {
    ("original", "Gloves"): "Small hand-region boxes; sampled construction hands include partly occluded/distant examples. Human review needed; this is not a confirmed label error.",
    ("original", "Hardhat"): "Sample includes cropped/small head regions; verify worn-hardhat box convention and person association.",
    ("original", "Mask"): "Positive mask boxes exist, but sampled image contexts are mixed; confirm construction/task domain and face box convention.",
    ("original", "NO-Hardhat"): "Explicit violation labels need visible heads and task/site requirement; sampled contexts include ambiguous/out-of-scope cases.",
    ("original", "NO-Mask"): "Small face-region boxes and task-specific respiratory applicability require review; sampled contexts include out-of-scope cases.",
    ("original", "NO-Safety Vest"): "Distant workers and torso visibility are difficult in sampled images; policy applicability must be explicit.",
    ("original", "Safety Vest"): "Some sampled boxes are cropped/unclear; verify qualifying garment and box extent.",
    ("original", "NO-Gloves (not in class map)"): "No class exists in original YAML/checkpoint; absence of Gloves boxes must not be converted to this violation.",
    ("supplementary", "helmet"): "Sample includes plausible worksite examples and a non-construction media example; confirm class scope and head/helmet box policy.",
    ("supplementary", "gloves"): "Sampled positive examples appear plausible, but confirm glove subtype and hand-box convention.",
    ("supplementary", "vest"): "Sampled worksite examples appear plausible; confirm vest definition and person/torso box conventions.",
    ("supplementary", "Person"): "Generic person class spans construction and non-construction imagery; only domain-eligible samples should be considered.",
    ("supplementary", "no_helmet"): "Sample includes non-construction contexts; visible bare head alone does not establish a site violation.",
    ("supplementary", "no_gloves"): "Sampled examples include non-construction/recreation contexts; bare hands do not establish required gloves. Earlier six reviewed examples remain concerns, not proof of dataset-wide invalidity.",
    ("supplementary", "NO-Mask (no direct equivalent)"): "No direct no_mask class in supplementary YAML; do not map none or another class.",
    ("supplementary", "NO-Safety Vest (no direct equivalent)"): "No direct no_vest class in supplementary YAML.",
}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
ORIGINAL_SPLITS = {"train": "train", "val": "valid", "test": "test"}
SUPP_SPLITS = {"train": "train", "val": "val", "test": "test"}
REVIEW_DECISIONS = {
    ("original", "IMG_5851_jpg.rf.b9a619e29a44480a0215306f1e8a68d8.jpg", "Gloves"): ("requires_human_review", "Multiple small hand boxes; glove and box extents need close review."),
    ("original", "youtube-308_jpg.rf.660669197399ff5d449f4bd99a7ee2db.jpg", "Gloves"): ("requires_human_review", "Construction scene; target hand regions are small or partly occluded."),
    ("original", "youtube-108_jpg.rf.4151b7657043acca8dc2cf6184a050d2.jpg", "Gloves"): ("requires_human_review", "Hand protection is too small to confirm at contact-sheet scale."),
    ("original", "youtube-628_jpg.rf.f6edfae049317bc122d330fff81bae5c.jpg", "Hardhat"): ("requires_human_review", "Head/helmet region is partly cropped and small."),
    ("original", "youtube-836_jpg.rf.5300f0409ac95be1ca9a6ba6e34fffef.jpg", "Hardhat"): ("plausible", "Visible worker wearing a hardhat in a construction-related scene."),
    ("original", "class1_150_jpg.rf.84bac47b79dbf4b1442b396826028fc1.jpg", "Hardhat"): ("requires_human_review", "Helmet/head evidence is small and task-site policy is undocumented."),
    ("original", "IMG_3100_mp4-23_jpg.rf.461f024ade0fdffd3bd82eac1b7d7baa.jpg", "Mask"): ("requires_human_review", "Face covering is visible; construction-domain relevance is unclear."),
    ("original", "IMG_3093_mp4-22_jpg.rf.2f07d23aa5f6279766cba3320c7da046.jpg", "Mask"): ("requires_human_review", "Face covering is visible; task/site relevance is unclear."),
    ("original", "NX_img_177_jpg.rf.97f18825a2ab066335fca1fa006ab670.jpg", "Mask"): ("out_of_scope", "Retail/interior context; construction PPE context is not evidenced."),
    ("original", "youtube-209_jpg.rf.6dec5d1a2fccd186e2568a195bf9c493.jpg", "Safety Vest"): ("requires_human_review", "Worksite is plausible; vest is small and partly obscured."),
    ("original", "youtube-416_jpg.rf.b8c38c8164fb29a2d9455e4ebaad39e7.jpg", "Safety Vest"): ("requires_human_review", "Lower-body crop; target vest box needs source-level review."),
    ("original", "ppe_1073_jpg.rf.103c2f8dc63b94e48b6a56823a20077a.jpg", "Safety Vest"): ("plausible", "Workers visibly wear reflective vests at a construction scene."),
    ("original", "class2_187_jpg.rf.36b43014b79a530927238148fd02bd05.jpg", "NO-Hardhat"): ("requires_human_review", "Head status, work context, and applicable site policy need confirmation."),
    ("original", "IMG_3103_mp4-17_jpg.rf.e0bcb68f0f4ec00ebd8fa5f7c4e38244.jpg", "NO-Hardhat"): ("out_of_scope", "Domestic-looking setting; construction task/site policy is not evidenced."),
    ("original", "class1_150_jpg.rf.84bac47b79dbf4b1442b396826028fc1.jpg", "NO-Hardhat"): ("ambiguous", "Worker is on a ladder; head-protection requirement is site/task-specific."),
    ("original", "4c43875bc97cdaece84ac6ce555235f1_jpg.rf.1e03659e1c41a52bcb06208f2aa2c4c8.jpg", "NO-Mask"): ("out_of_scope", "Gardening context; no construction site or respiratory policy is established."),
    ("original", "2009_003991_jpg.rf.3a15b50c5c3770ad316c587603f7c3a4.jpg", "NO-Mask"): ("out_of_scope", "Leisure/domestic context; applicable respiratory requirement is not shown."),
    ("original", "youtube-152_jpg.rf.f2d39681b16374dd5d28f01fa98e132e.jpg", "NO-Mask"): ("requires_human_review", "Construction scene, but faces are distant and mask policy is unknown."),
    ("original", "2_jpg.rf.d891d4911d57a5b1f0d708deb8ae76d1.jpg", "NO-Safety Vest"): ("requires_human_review", "Construction context is visible; target worker is distant."),
    ("original", "airport_inside_0090_jpg.rf.874201ab4cdc29f919627bd19efba9af.jpg", "NO-Safety Vest"): ("out_of_scope", "Airport concourse; distant people are outside the construction task context."),
    ("original", "youtube-152_jpg.rf.f2d39681b16374dd5d28f01fa98e132e.jpg", "NO-Safety Vest"): ("requires_human_review", "Active construction scene, but target people/vest visibility is limited."),
    ("supplementary", "image233.jpg", "helmet"): ("out_of_scope", "Media/event setting; no construction task is visible."),
    ("supplementary", "image330.jpg", "helmet"): ("plausible", "Construction worker with visible white hardhat; box appears aligned."),
    ("supplementary", "image517.jpg", "helmet"): ("plausible", "Rooftop construction context and visible hardhat."),
    ("supplementary", "image1224.jpg", "no_helmet"): ("out_of_scope", "Portrait/media context; no construction task is visible."),
    ("supplementary", "image1203.jpg", "no_helmet"): ("out_of_scope", "Indoor event interaction; no construction context."),
    ("supplementary", "image1256.jpg", "no_helmet"): ("out_of_scope", "Costume/event scene; no construction PPE context."),
    ("supplementary", "image382.jpg", "gloves"): ("plausible", "Construction-related task with visible protective gloves."),
    ("supplementary", "image532.jpeg", "gloves"): ("plausible", "Work task with visible gloves; construction context should be confirmed."),
    ("supplementary", "image470.jpeg", "gloves"): ("plausible", "Construction-related tool use with visible gloves."),
    ("supplementary", "image1278.jpg", "no_gloves"): ("out_of_scope", "Ski/recreation scene; bare hands do not establish a construction glove duty."),
    ("supplementary", "image1130.jpg", "no_gloves"): ("out_of_scope", "Leisure/event context; construction task and glove policy are absent."),
    ("supplementary", "image1139.jpg", "no_gloves"): ("out_of_scope", "Food preparation/home context; no construction glove requirement is evidenced."),
    ("supplementary", "image1097.jpg", "vest"): ("plausible", "Rooftop work context and visible high-visibility vest."),
    ("supplementary", "image576.jpg", "vest"): ("plausible", "Worker in high-visibility clothing at a rooftop worksite."),
    ("supplementary", "image927.jpg", "vest"): ("plausible", "Reflective vest visible in a rooftop construction scene."),
    ("supplementary", "image1401.jpg", "Person"): ("out_of_scope", "Gym scene; person box is plausible but outside construction domain."),
    ("supplementary", "image705.jpg", "Person"): ("plausible", "Person box aligns to a visible worker in a worksite-like scene."),
    ("supplementary", "image1074.jpg", "Person"): ("plausible", "Person box aligns to a visible rooftop worker."),
}


def parse_label(path: Path, class_names: dict[int, str]):
    rows = []
    malformed = 0
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split()
        try:
            cid = int(parts[0])
            coords = [float(v) for v in parts[1:]]
            valid = cid in class_names and len(coords) == 4 and all(0 <= v <= 1 for v in coords)
            if not valid:
                malformed += 1
                continue
            rows.append({"class_id": cid, "class_name": class_names[cid], "xywh": coords,
                         "line": line_number})
        except (ValueError, IndexError):
            malformed += 1
    return rows, malformed


def collect_dataset(name: str, base: Path, split_dirs: dict[str, str], classes: dict[int, str]):
    records = []
    split_counts = {}
    for split, directory in split_dirs.items():
        if (base / "images" / directory).is_dir():
            images_dir = base / "images" / directory
            labels_dir = base / "labels" / directory
        else:
            images_dir = base / directory / "images"
            labels_dir = base / directory / "labels"
        images = sorted(p for p in images_dir.glob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS)
        by_stem = {p.stem: p for p in images}
        labels = sorted(labels_dir.glob("*.txt"))
        matched = 0
        orphan = 0
        for label in labels:
            image = by_stem.get(label.stem)
            if image is None:
                orphan += 1
                continue
            matched += 1
            rows, malformed = parse_label(label, classes)
            try:
                with Image.open(image) as im:
                    width, height = im.size
            except Exception:
                width = height = None
            records.append({"dataset": name, "split": split, "image": image, "label": label,
                            "rows": rows, "malformed": malformed, "width": width, "height": height})
        split_counts[split] = {"images": len(images), "matched_label_files": matched,
                               "orphan_labels_excluded": orphan,
                               "empty_labels": sum(not r["rows"] for r in records if r["split"] == split)}
    return records, split_counts


def class_audit(records, class_names, targets, dataset_name, split_counts, output_csv):
    fields = ["class_id", "class_name", "images_containing_class", "instances",
              "train_images", "train_instances", "val_images", "val_instances",
              "test_images", "test_instances", "empty_label_images_total",
              "malformed_rows", "box_width_median_normalized", "box_height_median_normalized",
              "audit_note"]
    rows_out = []
    for target in targets:
        cid, target_name = target if isinstance(target, tuple) else (target, class_names[target])
        counts = {s: [set(), 0] for s in ("train", "val", "test")}
        widths, heights = [], []
        malformed = 0
        for rec in records:
            malformed += rec["malformed"]
            for item in rec["rows"]:
                if cid is not None and item["class_id"] == cid:
                    counts[rec["split"]][0].add(rec["image"].name)
                    counts[rec["split"]][1] += 1
                    widths.append(item["xywh"][2])
                    heights.append(item["xywh"][3])
        total_images = sum(len(counts[s][0]) for s in counts)
        total_instances = sum(counts[s][1] for s in counts)
        notes = []
        notes.append(CLASS_AUDIT_NOTES.get((dataset_name, target_name), ""))
        notes = [note for note in notes if note]
        if total_instances == 0:
            notes.append("No matched instances in this dataset")
        if cid == 5 and dataset_name == "supplementary":
            notes.append("Class 'none' is undefined; excluded from PPE semantic interpretation")
        rows_out.append({
            "class_id": "" if cid is None else cid, "class_name": target_name,
            "images_containing_class": total_images, "instances": total_instances,
            "train_images": len(counts["train"][0]), "train_instances": counts["train"][1],
            "val_images": len(counts["val"][0]), "val_instances": counts["val"][1],
            "test_images": len(counts["test"][0]), "test_instances": counts["test"][1],
            "empty_label_images_total": sum(split_counts[s]["empty_labels"] for s in split_counts),
            "malformed_rows": malformed,
            "box_width_median_normalized": round(statistics.median(widths), 6) if widths else "",
            "box_height_median_normalized": round(statistics.median(heights), 6) if heights else "",
            "audit_note": "; ".join(notes),
        })
    with output_csv.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows_out)
    return rows_out


def draw_overlay(image_path: Path, label_path: Path, class_names: dict[int, str]):
    im = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(im)
    rows, _ = parse_label(label_path, class_names)
    width, height = im.size
    colors = [(240, 60, 60), (40, 180, 80), (40, 120, 240), (255, 180, 20), (180, 60, 220)]
    for item in rows:
        cid, (cx, cy, bw, bh) = item["class_id"], item["xywh"]
        x1, y1 = (cx - bw / 2) * width, (cy - bh / 2) * height
        x2, y2 = (cx + bw / 2) * width, (cy + bh / 2) * height
        color = colors[cid % len(colors)]
        draw.rectangle((x1, y1, x2, y2), outline=color, width=max(2, min(width, height) // 250))
        text = f'{cid}: {class_names[cid]}'
        draw.text((x1, max(0, y1 - 16)), text, fill=color, stroke_width=2, stroke_fill="black")
    return im, rows


def deterministic_samples(records, class_ids, class_names, limit_per_class_split=1):
    result = []
    for cid in class_ids:
        for split in ("train", "val", "test"):
            candidates = [r for r in records if r["split"] == split and any(x["class_id"] == cid for x in r["rows"])]
            candidates.sort(key=lambda r: hashlib.sha256(f"safesite-ppe-audit-v1|{split}|{cid}|{r['image'].name}".encode()).hexdigest())
            result.extend((cid, r) for r in candidates[:limit_per_class_split])
    return result


def contact_sheet(records, classes, class_names, title, filename, index_rows):
    samples = deterministic_samples(records, classes, class_names)
    if not samples:
        return
    cell_w, image_h, header_h = 760, 450, 78
    thumb_w, thumb_h = 370, 370
    cols = 2
    rows_n = (len(samples) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell_w, rows_n * (image_h + header_h)), "#f3f4f6")
    d = ImageDraw.Draw(sheet)
    d.text((20, 10), title, fill="#111827", font=ImageFont.load_default())
    for i, (target_id, rec) in enumerate(samples):
        x = (i % cols) * cell_w
        y = (i // cols) * (image_h + header_h) + 38
        overlay, rows = draw_overlay(rec["image"], rec["label"], class_names)
        source = Image.open(rec["image"]).convert("RGB")
        source.thumbnail((thumb_w, thumb_h))
        overlay.thumbnail((thumb_w, thumb_h))
        decision, decision_note = REVIEW_DECISIONS.get((rec["dataset"], rec["image"].name, class_names[target_id]), ("requires_human_review", "No completed manual decision for this sample."))
        d.text((x + 8, y), f"{rec['split'].upper()} | {rec['image'].name} | target: {class_names[target_id]} ({target_id})", fill="#111827")
        d.text((x + 8, y + 18), f"Review: {decision} — {decision_note[:92]}", fill="#7c2d12")
        d.text((x + 10, y + 38), "Original", fill="#374151")
        d.text((x + thumb_w + 20, y + 38), "Ground-truth overlay", fill="#374151")
        source_x = x + 8 + (thumb_w - source.width) // 2
        overlay_x = x + thumb_w + 16 + (thumb_w - overlay.width) // 2
        sheet.paste(source, (source_x, y + 58))
        sheet.paste(overlay, (overlay_x, y + 58))
        all_labels = sorted({f"{r['class_name']} ({r['class_id']})" for r in rows})
        note = "Box/class alignment only; policy/context review pending"
        index_rows.append({
            "dataset": rec["dataset"], "split": rec["split"], "filename": rec["image"].name,
            "image_path": rec["image"].relative_to(ROOT).as_posix(),
            "label_path": rec["label"].relative_to(ROOT).as_posix(),
            "target_class_id": target_id, "target_class_name": class_names[target_id],
            "boxes_in_image": len(rows), "image_class_labels": " | ".join(all_labels),
            "review_status": decision, "review_note": decision_note,
        })
    OUT.mkdir(parents=True, exist_ok=True)
    sheet.save(OUT / filename, quality=90)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    orig, orig_splits = collect_dataset("original", ORIGINAL, ORIGINAL_SPLITS, ORIGINAL_CLASSES)
    supp, supp_splits = collect_dataset("supplementary", SUPPLEMENTARY, SUPP_SPLITS, SUPP_CLASSES)
    o_classes = [1, 2, 4, 5, 6, 7, 11, (None, "NO-Gloves (not in class map)")]
    s_classes = [0, 1, 2, 6, 7, 9, (None, "NO-Mask (no direct equivalent)"), (None, "NO-Safety Vest (no direct equivalent)")]
    o_rows = class_audit(orig, ORIGINAL_CLASSES, o_classes, "original", orig_splits, OUT / "original_dataset_audit.csv")
    s_rows = class_audit(supp, SUPP_CLASSES, s_classes, "supplementary", supp_splits, OUT / "supplementary_dataset_audit.csv")
    reviews = []
    contact_sheet(orig, [1, 2, 4, 11], ORIGINAL_CLASSES, "Original dataset — positive PPE sample", "original_positive_ppe.jpg", reviews)
    contact_sheet(orig, [5, 6, 7], ORIGINAL_CLASSES, "Original dataset — explicit missing-PPE sample", "original_missing_ppe.jpg", reviews)
    contact_sheet(supp, [0, 7], SUPP_CLASSES, "Supplementary — helmet / no_helmet", "supplementary_helmet_no_helmet.jpg", reviews)
    contact_sheet(supp, [1, 9], SUPP_CLASSES, "Supplementary — gloves / no_gloves", "supplementary_gloves_no_gloves.jpg", reviews)
    contact_sheet(supp, [2, 6], SUPP_CLASSES, "Supplementary — vest / Person", "supplementary_vest_person.jpg", reviews)
    with (OUT / "visual_review_index.csv").open("w", newline="", encoding="utf-8-sig") as f:
        fields = ["dataset", "split", "filename", "image_path", "label_path", "target_class_id", "target_class_name", "boxes_in_image", "image_class_labels", "review_status", "review_note"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(reviews)
    metadata = {
        "sampling": "Deterministic SHA256 rank of seed|split|class_id|filename; one image per target class per split.",
        "source_images_are_not_modified": True,
        "labels_are_not_modified": True,
        "orphan_labels_included_in_counts_or_samples": False,
        "split_counts": {"original": orig_splits, "supplementary": supp_splits},
        "matched_image_counts": {"original": len(orig), "supplementary": len(supp)},
        "class_audit_rows": {"original": o_rows, "supplementary": s_rows},
        "review_index_rows": len(reviews),
        "review_status_counts": {
            name: dict(Counter(r["review_status"] for r in reviews if r["dataset"] == name))
            for name in ("original", "supplementary")
        },
        "status_policy": "Review status is a conservative visual scope/ambiguity classification; it is not an annotation correction or safety determination.",
    }
    (OUT / "audit_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(OUT), "matched_images": metadata["matched_image_counts"],
                      "review_samples": len(reviews), "original_splits": orig_splits,
                      "supplementary_splits": supp_splits}, indent=2))


if __name__ == "__main__":
    main()
