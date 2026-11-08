# PPE Remediation Gap Analysis — Stage 1

**Audit date:** 2026-11-02. This is a class/annotation audit only. No labels, YAMLs, model files, application mappings, thresholds, or dataset splits were changed.

## Current class coverage and application behavior

The original YAML and checkpoint class mapping contains 25 IDs. The PPE subset is: Gloves 1, Hardhat 2, Mask 4, NO-Hardhat 5, NO-Mask 6, NO-Safety Vest 7, Person 8, Safety Vest 11. There is no NO-Gloves output class. Full original and supplementary class audits are in [original_dataset_audit.csv](./outputs/ppe-audit/original_dataset_audit.csv) and [supplementary_dataset_audit.csv](./outputs/ppe-audit/supplementary_dataset_audit.csv).

The complete checkpoint/YAML class map verified against the existing evaluation metadata is: **0 Excavator, 1 Gloves, 2 Hardhat, 3 Ladder, 4 Mask, 5 NO-Hardhat, 6 NO-Mask, 7 NO-Safety Vest, 8 Person, 9 SUV, 10 Safety Cone, 11 Safety Vest, 12 bus, 13 dump truck, 14 fire hydrant, 15 machinery, 16 mini-van, 17 sedan, 18 semi, 19 trailer, 20 truck, 21 truck and trailer, 22 van, 23 vehicle, 24 wheel loader.** IDs and capitalization are preserved from the source YAML.

`detector.py` maps only the checkpoint violation names `NO-Hardhat`→`no_helmet`, `NO-Safety Vest`→`no_vest`, and `NO-Mask`→`no_mask`; positive PPE labels are not hazards. Its fallback accepts already-normalized `no_gloves`, `no_boots`, and `no_goggle`. `risk_agent.py` has corresponding normalized hazard names, and `safety_agent.py` turns a detection into a finding only after normalization. Thus the application taxonomy can consume a normalized no-gloves signal, but the current checkpoint cannot emit the class; the detector's named model-class map has no `NO-Gloves` alias. This is a schema/capability gap, not evidence that the model is predicting it.

One forward-compatibility inconsistency is visible: raw `NO-Gloves` is not one of the three named detector aliases and the direct fallback accepts `no_gloves` (underscore) rather than that raw class spelling. Therefore an eventual model emitting exactly `NO-Gloves` would not currently normalize through `detector.py`; this audit records the inconsistency but does not change code. `no_boots`/`no_goggle` are risk-taxonomy entries and detector fallbacks but have no class IDs in this 25-class checkpoint. Model outputs such as vehicles/equipment are valid model classes but are not hazard classes in the current PPE map.

`safety_graph.py` routes completed Safety Agent findings and does not add PPE classes or infer a violation from absent positive detections. No application files were modified.

## Measured annotation support

Original dataset: 717 matched images (521 train, 114 validation, 82 test), 5,570 matched instances, 52 empty-label images (34/10/8 by split), and zero malformed/out-of-range rows in the class-focused audit. Per-class images and boxes:

| ID | Class | Train images / boxes | Val images / boxes | Test images / boxes | Total images / boxes |
|---:|---|---:|---:|---:|---:|
| 1 | Gloves | 75 / 231 | 11 / 25 | 10 / 40 | 96 / 296 |
| 2 | Hardhat | 159 / 385 | 42 / 79 | 30 / 110 | 231 / 574 |
| 4 | Mask | 88 / 153 | 19 / 21 | 16 / 28 | 123 / 202 |
| 5 | NO-Hardhat | 171 / 292 | 37 / 69 | 25 / 41 | 233 / 402 |
| 6 | NO-Mask | 176 / 338 | 44 / 74 | 30 / 79 | 250 / 491 |
| 7 | NO-Safety Vest | 214 / 386 | 56 / 106 | 36 / 90 | 306 / 582 |
| 11 | Safety Vest | 138 / 322 | 28 / 41 | 22 / 61 | 188 / 424 |
| — | NO-Gloves | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |

The positive and violation supports are not directly balanced: Gloves and Mask have fewer instances than the explicit vest/helmet violations. This is a measured distribution, not proof of causation. Gloves also has small median normalized boxes in the source audit (0.0266 width × 0.0414 height); NO-Mask median is 0.0297 × 0.0313. These median normalized sizes support a small-object review hypothesis but do not alone establish annotation error.

Supplement: 1,416 matched images (1,132/143/141) and 11,521 matched rows. The 10 orphan train labels and 93 rows were excluded. `helmet`: 1,734 boxes; `no_helmet`: 485; `gloves`: 1,445; `no_gloves`: 556 across 236 images; `vest`: 1,618; `Person`: 2,245. No direct `no_mask` or `no_vest` class exists. `none` is undefined in the supplied codebook and must not be mapped to any violation.

## Model weaknesses: held-out evidence, not diagnosis

The existing test report measured recall: Gloves 9.52%, NO-Mask 13.92%, NO-Hardhat 36.59%, NO-Safety Vest 37.78%. Validation analysis at confidence 0.25 and class-aware IoU >= 0.50 recorded Gloves 7 TP / 4 FP / 18 FN from 25 GT (28.00% recall); NO-Mask 13 / 13 / 61 from 74 (17.57%); NO-Hardhat 31 / 19 / 38 from 69 (44.93%); NO-Safety Vest 44 / 18 / 62 from 106 (41.51%). These are distinct evaluation protocols/splits and should not be combined as one metric.

The prior validation review found small/occluded hands, distant PPE, dense scenes, and domain-diverse images. Its automated format checks found no malformed/missing/out-of-range validation rows. Neither fact rules out semantic annotation issues elsewhere. The threshold sweep improved recall while greatly increasing false positives; threshold changes are not a substitute for class/policy remediation and are outside this stage.

## Annotation and dataset risks

- The 39-image deterministic contact-sheet sample covers target classes in train, validation, and test. It contains plausible positive examples, multiple out-of-scope contexts, and cases needing human review. See [visual_review_index.csv](./outputs/ppe-audit/visual_review_index.csv) and the five sheets in [ppe-audit](./outputs/ppe-audit/).
- Original violation labels require task/site policy context beyond box-format correctness. Several sampled examples are distant, domestic, leisure, or otherwise difficult to associate with a construction task. Those samples are marked out of scope, ambiguous, or requiring human review; they are not automatic label corrections.
- The six supplementary `no_gloves` cases reviewed earlier remain documented concerns: restaurant/meal, gym/boxing, electronics/event booth, social event, child soccer, and an outdoor group. This is a sample, not proof all 556 matched boxes are invalid. The current deterministic sample also shows out-of-construction/recreation contexts. Bare hands and a hand-region box do not establish a construction glove requirement.
- Supplement `no_helmet` has 485 boxes, but the sample includes non-construction contexts. `helmet` examples can be visually clear but annotation scope and box convention still need publisher codebook confirmation.
- Supplement `vest` and `Person` coverage is substantial, but names do not establish identical meaning or box extent. The sample review is not a full audit of 11,521 rows.
- Ten supplementary orphan label files (93 rows) remain excluded from matched statistics and any future candidate manifest until their original image association is verified. Thirteen near-duplicate candidates, including nine supplementary-train/original-test scene-family links, and unresolved image/photo rights remain Stage 2 integration gates documented in [dataset-integration-readiness.md](./dataset-integration-readiness.md) and [licensing-review.md](./licensing-review.md).

## Priority order for remediation planning

| Priority | Class(es) | Evidence-based gap | Stage 2 need |
|---:|---|---|---|
| 1 | NO-Mask | Lowest violation recall (13.92% test; 17.57% validation); original support exists, supplement has no equivalent. | Audit policy and original boxes; collect or label construction/task-specific face examples only when respiratory requirement is documented. |
| 2 | Gloves / planned NO-Gloves | Gloves test recall 9.52%; original has 296 boxes and small hand boxes. Supplement has 1,445 positive glove boxes, but 556 `no_gloves` labels include known out-of-domain concerns. | Curate positive hand-scale examples; require task-policy evidence for every missing-glove label. Do not add `NO-Gloves` to schema in Stage 1. |
| 3 | NO-Safety Vest | Test recall 37.78%; original support 582 boxes; supplement lacks missing-vest class. | Review visibility, person association, torso box convention and domain; obtain additional construction-specific explicit violations if policy-cleared. |
| 4 | NO-Hardhat | Test recall 36.59%; original 402 boxes; supplement `no_helmet` has 485 candidate boxes, with scope issues. | Human-audit visible heads, task applicability and duplicate/split groups before selecting any examples. |
| 5 | Hardhat / Mask / Safety Vest | Positive class test recall is materially higher than violation classes, but support and semantics still require validation. | Preserve separate gear-presence definitions; audit source class/box conventions before any remap. |

## Decision and limitations

Proceed to Stage 2 as a **curation and annotation-review plan only**, after the human/legal/source gates. Hardhat, Gloves, Safety Vest, and NO-Hardhat have potentially useful candidate data but are not automatically approved for inclusion. NO-Mask and NO-Safety Vest need construction-specific, policy-grounded data review; the selected supplement does not fill those gaps. NO-Gloves is not currently trainable under the existing 25-class schema; a new class requires a separately approved schema/model/application design and valid task-specific examples. See [Stage 1 decisions](./ppe-stage-1-decisions.md).

This audit is deterministic and reproducible for counts/sampling, but the sample review is human visual triage rather than a full box-by-box policy adjudication. No training, merge, production changes, or test-set tuning occurred.
