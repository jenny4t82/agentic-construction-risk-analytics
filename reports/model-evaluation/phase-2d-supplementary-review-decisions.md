# Phase 2D — Supplementary Dataset Review Decisions

**Status: planning decision register only.** No source files were moved, removed, edited, merged, or added to a training set. “Quarantine” below means exclude from a future candidate manifest pending human decision; it does not mean physically moving the source.

## Decision summary

| Item | Recommended status | Decision |
|---|---|---|
| P01–P10 | quarantine | All are confirmed same-scene-family matches to the existing frozen test image `test/images/image_55_jpg.rf.bd0780b14a93c28b7d6af0558d1fdcaa.jpg`; supplementary split is train. Keep out of any training/validation candidate until the split-leakage risk and scene provenance are resolved. Do not alter the test set. |
| P11–P13 | quarantine | Confirmed same construction-site gate/background scene family with existing original train images; not test crossings, but likely sequence/group overlap remains. Keep out of first candidate pending source-group review. |
| 10 orphan labels / 93 rows | exclude from matched-image statistics and unresolved | Same-stem possible images exist, but no label-to-image association is verified. Do not pair by filename. Request original archive manifest or source export provenance. |
| `no_gloves` (556 boxes / 236 matched images) | eligible for review, not approved | The dataset-wide annotations are not invalidated by the small sample. The earlier six sampled examples and Stage 1 sample raise construction/task-context concerns. Require a representative, split-stratified human review against the project policy before any annotation is eligible. |
| `none` (797 boxes / 651 matched images) | exclude from violation mapping; unresolved semantics | Publisher YAML gives no usable definition. Do not map to any PPE violation, including `NO-Gloves`, `NO-Mask`, or `NO-Safety Vest`. Obtain a codebook or exclude this class from any future curated task. |

The full 13-pair evidence is in [`duplicate_review_index.csv`](./outputs/dataset-review/duplicate-review/duplicate_review_index.csv) and the contact sheet is [`duplicate_contact_sheet.jpg`](./outputs/dataset-review/duplicate-review/duplicate_contact_sheet.jpg). Pairwise dHash distances are 1–5. Visual review confirms a common gate/background and scene family with worker/pose variation. This establishes a near-duplicate scene risk, not identical pixels or a proven video source.

## Pair register

All pairs have supplementary labels `helmet`, `gloves`, `vest`, `boots`, and `Person`, except P12 which has `vest`, `boots`, and `Person`. The matched original labels contain `Gloves`, `Safety Vest`, `Hardhat`, `Mask`, and `Person`. These labels describe each image separately; a nearby image’s label is not transferred to its scene-family match.

| Pair | Supplementary path (split) | Existing path (split) | dHash | Existing evidence | Status / additional information |
|---|---|---|---:|---|---|
| P01 | `images/train/image685.jpg` (train) | `test/images/image_55_jpg.rf.bd0780b14a93c28b7d6af0558d1fdcaa.jpg` (test) | 1 | Confirmed same gate/background scene family; likely photo/session sequence. | **Quarantine.** High leakage risk. Need source sequence/provenance and human disposition. |
| P02 | `images/train/image702.jpg` (train) | same test image as P01 | 1 | Same as P01; worker/pose varies. | **Quarantine.** Same evidence and approval gate. |
| P03 | `images/train/image730.jpg` (train) | same test image as P01 | 1 | Same as P01; worker/pose varies. | **Quarantine.** Same evidence and approval gate. |
| P04 | `images/train/image699.jpg` (train) | same test image as P01 | 2 | Same as P01; worker/pose varies. | **Quarantine.** Same evidence and approval gate. |
| P05 | `images/train/image712.jpg` (train) | same test image as P01 | 2 | Same as P01; worker/pose varies. | **Quarantine.** Same evidence and approval gate. |
| P06 | `images/val/image709.jpg` (val) | `train/images/image_170_jpg.rf.747403dbb5b1c349197c96146345786c.jpg` (train) | 2 | Confirmed scene-family match; original side is train, not test. | **Quarantine.** Need source group/provenance and human review before split eligibility. |
| P07 | `images/train/image684.jpg` (train) | same test image as P01 | 3 | Same as P01; worker/pose varies. | **Quarantine.** High leakage risk. |
| P08 | `images/train/image725.jpg` (train) | same test image as P01 | 3 | Same as P01; worker/pose varies. | **Quarantine.** High leakage risk. |
| P09 | `images/train/image673.jpg` (train) | same test image as P01 | 4 | Same as P01; worker/pose varies. | **Quarantine.** High leakage risk. |
| P10 | `images/train/image724.jpg` (train) | same test image as P01 | 4 | Same as P01; worker/pose varies. | **Quarantine.** High leakage risk. |
| P11 | `images/val/image674.jpg` (val) | `train/images/image_153_jpg.rf.cdd9f88957c5b5b2844d12ae26f6917c.jpg` (train) | 4 | Confirmed scene-family match; original side is train, not test. | **Quarantine.** Need source group/provenance and human review. |
| P12 | `images/val/image705.jpg` (val) | `train/images/image_46_jpg.rf.76033125e51ba32ce27ce3301753535d.jpg` (train) | 4 | Confirmed scene-family match; original side is train, not test. | **Quarantine.** Need source group/provenance and human review. |
| P13 | `images/train/image693.jpg` (train) | `train/images/image_153_jpg.rf.cdd9f88957c5b5b2844d12ae26f6917c.jpg` (train) | 5 | Confirmed scene-family match; original side is train, not test. | **Quarantine.** Need source group/provenance and human review. |

P01–P05 and P07–P10 are the nine supplementary train-to-test relationships, with all nine reusing the same original test image. P06, P11, P12, and P13 are the remaining four relationships: supplementary validation to original train (P06, P11, P12) and supplementary train to original train (P13). Keep every listed supplementary candidate quarantined; do not infer that an image is invalid or delete it.

## Orphan labels

All ten files contain 93 annotation rows in total. The `possible_image_matches` column lists filename-family candidates only; all rows say `association_verified=no`.

| Orphan label | Rows | Class distribution | Possible same-stem image | Status |
|---|---:|---|---|---|
| `image940(1).txt` | 23 | Person 10; helmet 6; none 1; vest 6 | `images/train/image940.jpg` | unresolved; exclude unless original association evidence is obtained |
| `image941(1).txt` | 7 | Person 1; boots 2; gloves 2; helmet 1; vest 1 | `images/train/image941.jpg` | unresolved; exclude unless verified |
| `image944(1).txt` | 8 | Person 1; boots 2; gloves 2; goggles 1; helmet 1; vest 1 | `images/train/image944.jpg` | unresolved; exclude unless verified |
| `image945(1).txt` | 8 | Person 1; boots 2; gloves 2; goggles 1; helmet 1; vest 1 | `images/train/image945.jpg` | unresolved; exclude unless verified |
| `image946(1).txt` | 7 | Person 1; boots 2; gloves 1; goggles 1; helmet 1; vest 1 | `images/train/image946.jpg` | unresolved; exclude unless verified |
| `image947(1).txt` | 7 | Person 1; boots 2; gloves 1; goggles 1; helmet 1; vest 1 | `images/train/image947.jpg` | unresolved; exclude unless verified |
| `image948(1).txt` | 7 | Person 1; boots 2; gloves 1; goggles 1; helmet 1; vest 1 | `images/train/image948.jpg` | unresolved; exclude unless verified |
| `image949(1).txt` | 7 | Person 1; boots 2; gloves 1; goggles 1; helmet 1; vest 1 | `images/train/image949.jpg` | unresolved; exclude unless verified |
| `image95(1).txt` | 8 | Person 1; boots 2; gloves 2; goggles 1; helmet 1; vest 1 | `images/train/image95.jpg` | unresolved; exclude unless verified |
| `image950(1).txt` | 11 | Person 2; gloves 4; goggles 1; helmet 2; none 2 | `images/train/image950.jpeg` | unresolved; exclude unless verified |

Full source inventory: [`orphan_labels.csv`](./outputs/dataset-review/orphan-label-review/orphan_labels.csv). No orphan rows are included in matched-image counts or proposed class support.

## `no_gloves` sample evidence and decision

The review sample is small and stratified at two examples per split. All six previously documented examples are outside a clear construction context (restaurant, boxing gym, electronics event, social event, child playing soccer, outdoor group). Stage 1 also found out-of-scope contexts in its supplementary review sample. These observations justify manual review; they do **not** establish that all 556 boxes are out of scope. The class has 442 train, 56 validation, and 58 test boxes across 190, 23, and 23 images respectively. Before reuse, review a larger randomized/stratified sample, inspect every candidate in context, and verify visible hands plus a task/site glove requirement. Human reviewers must record uncertain/not-visible/not-applicable separately from an explicit violation.

## `none` class decision

The local YAML defines `none` as a class, and matched labels contain 797 boxes across all splits (651 train, 81 validation, 65 test). The publisher-provided material inspected to date does not define whether it means no PPE, no object, a negative image, or some other annotation state. Its box annotations and name do not establish a specific missing item or site requirement. Keep it out of the 26-class taxonomy until a publisher codebook is supplied; never remap it to a violation by implication.

## Gates before a future training manifest

1. Human reviewer signs off on any retained near-duplicate scene groups and split assignments; the existing test images stay frozen and cannot contribute to training or validation.
2. Publisher/source provenance resolves archive and image rights, attribution, and redistribution/training permissions.
3. Obtain annotation codebook, especially `no_gloves` and `none`; review candidate `no_gloves` images against the project policy.
4. Obtain verifiable source association for any orphan labels or exclude all ten.
5. Record per-image source, license, original split, scene group, and review decision. No class enters training solely because it appears in a YAML.
