# Construction-PPE dataset integration readiness

Review date: 2026-11-02

## Recommendation

**Not ready; further investigation is required before integration.** Do not merge the dataset yet. This recommendation is based on (1) visually confirmed scene-family overlap across the frozen test boundary, (2) sampled `no_gloves` labels whose images are not construction-site contexts, (3) unresolved orphan-label association, and (4) unverified image/photo rights. Dataset/model/application files and existing splits were not changed.

## Duplicate and test-set leakage review

The original dHash scan found 13 candidate pairs at Hamming distances 1-5/64. All 13 pairs were visually reviewed in [the contact sheet](./outputs/dataset-review/duplicate-review/duplicate_contact_sheet.jpg) and logged in [the review index](./outputs/dataset-review/duplicate-review/duplicate_review_index.csv).

Visual comparison confirms that each candidate is from the same construction-site gate/background and same scene family; workers, clothing, and poses vary across frames. This is stronger evidence of a shared photo/session sequence than the hash alone, but does not prove identical source files or exact capture provenance. Nine pairs cross from supplementary **train** to the existing frozen **test** split (all near the same existing test image); four connect supplementary train/validation images to existing train. No candidate connects to existing validation. Exact SHA-256 duplicates were zero in the initial scan.

**Risk:** allowing the nine supplementary training frames into a combined training set could leak scene/background/worker appearance into the old test evaluation even when image pixels differ. Keep the existing test split frozen. Resolve source sequence grouping and then either exclude the overlapping sequence from training or redesign evaluation around group-level separation, preserving the original test artifacts for historical comparison. Do not treat a low dHash distance as an automatic deletion rule.

## `no_gloves` semantic review

The source dataset has 556 `no_gloves` boxes across 236 images (train 442/190 images, validation 56/23 images, test 58/23 images). The six-image review sample includes two train images, two validation images, and two test images. The [contact sheet](./outputs/dataset-review/no-gloves-review/no_gloves_contact_sheet.jpg) shows each source image beside its class-9 box overlay; the [CSV review index](./outputs/dataset-review/no-gloves-review/no_gloves_review_index.csv) records observations.

All six sampled scenes appear outside construction contexts: restaurant/eating, boxing/gym, electronics demonstration/event, social event, child soccer, and an outdoor group in a desert/street setting. Boxes do target hand or wrist regions, but their presence does not establish that a construction task/site policy requires gloves. Some target regions also include substantial arm or adjacent content, and the boxing sample includes athletic wraps. The sample cannot establish the quality of all 556 labels, but it is direct evidence that this class is not consistently scoped to the stated SafeSite definition in the inspected examples.

Treat `no_gloves` as **not suitable for automatic inclusion** under the SafeSite class policy. Request the publisher's annotation codebook and image provenance, then perform a broader task/context audit. Only images with verified construction-work context and a clear applicable glove requirement should be eligible for a future curated class. Do not relabel or discard these originals as part of this review.

## Orphan training labels

Ten labels contain 93 rows: `image940(1).txt` (23), `image941(1).txt` (7), `image944(1).txt` (8), `image945(1).txt` (8), `image946(1).txt` (7), `image947(1).txt` (7), `image948(1).txt` (7), `image949(1).txt` (7), `image95(1).txt` (8), and `image950(1).txt` (11). Their class totals are Person 20, helmet 16, gloves 16, boots 16, vest 14, goggles 8, and none 3. The detailed inventory is in [orphan_label_report.md](./outputs/dataset-review/orphan-label-review/orphan_label_report.md) and [orphan_labels.csv](./outputs/dataset-review/orphan-label-review/orphan_labels.csv).

Removing the literal `(1)` suffix yields a same-stem image candidate for each orphan label under `images/train/` (nine `.jpg` and one `.jpeg`). This may indicate an export naming collision, but filename similarity alone does not prove association. No labels were attached, and the candidates must remain excluded from any future merge until the source package or publisher verifies their pairing.

## Suggested class mapping

Mapping is semantic only; no class configuration was changed. Confirm annotation policy before using even the direct-looking classes.

| Existing class | Supplement class (ID) | Recommendation |
|---|---|---|
| Hardhat | `helmet` (0) | Candidate map; confirm head/helmet box conventions and class definition. |
| NO-Hardhat | `no_helmet` (7) | Candidate map; confirm violation policy and scene scope. |
| Gloves | `gloves` (1) | Candidate map; verify what counts as protective gloves and the box policy. |
| NO-Gloves | `no_gloves` (9) | New planned class only; exclude pending construction/task-policy validation and application/model schema approval. |
| Safety Vest | `vest` (2) | Candidate map; confirm vest definition and box extent. |
| Person | `Person` (6) | Candidate map; verify person-box convention. |
| Mask / NO-Mask | None | No equivalent class; do not map `none` to either. |
| NO-Safety Vest | None | No missing-vest class in this dataset. |
| Other classes | `boots` (3), `goggles` (4), `none` (5), `no_goggle` (8), `no_boots` (10) | Exclude from the current 25-class model unless a separately approved schema expansion is made. `none` semantics are undocumented. |

The 25-class existing configuration remains unchanged. `NO-Gloves` is not present in it; including class 9 would require a separate, explicit model/application design decision after this readiness review.

## Licensing and provenance status

The official dataset documentation declares AGPL-3.0 and requests attribution. The archive includes AGPL text but has no per-image source/rights manifest. Underlying photo rights, any redistribution permission, and the interaction of dataset terms with derivative labels/checkpoints remain unverified. Ultralytics software licensing is separate from the dataset license; the project's application license and checkpoint-specific provenance are also unresolved. See [licensing-review.md](./licensing-review.md) for evidence, links, and questions to resolve. Obtain publisher clarification and legal review before integration or distribution.

## Include/exclude recommendation

No integration is approved now. If blockers are resolved, a future curated proposal may consider only verified, policy-compatible examples for `helmet`→Hardhat, `no_helmet`→NO-Hardhat, `gloves`→Gloves, `vest`→Safety Vest, and `Person`→Person, subject to annotation audit. Exclude:

- the nine supplementary training candidates that overlap the existing held-out test scene family, unless a documented group-level policy proves they cannot contaminate the evaluation;
- all ten orphan label files and their possible image candidates until association is verified;
- `no_gloves` examples outside verified construction/task-policy contexts, including the reviewed sample, from any SafeSite missing-gloves target class;
- `none`, `boots`, `goggles`, `no_goggle`, and `no_boots` under the current schema;
- all photos until image rights and permitted downstream use are clarified.

## Next steps

1. Obtain the `no_gloves` annotation guide/codebook and ask how non-construction images entered a dataset described as construction PPE.
2. Request per-image photo source, rights, attribution, and redistribution information from Ultralytics; have counsel review the dataset, software, checkpoint, and project-license layers.
3. Request confirmation of the ten orphan label/image pairs and provenance for the shared scene sequence.
4. If cleared, prepare a separate curation manifest that preserves the old test set, keeps scene/session groups together across splits, records all remaps, and excludes unresolved samples. Review and approve that manifest before any data merge.

## Review artifacts

- [Duplicate contact sheet](./outputs/dataset-review/duplicate-review/duplicate_contact_sheet.jpg)
- [Duplicate review CSV](./outputs/dataset-review/duplicate-review/duplicate_review_index.csv)
- [NO-Gloves contact sheet](./outputs/dataset-review/no-gloves-review/no_gloves_contact_sheet.jpg)
- [NO-Gloves review CSV](./outputs/dataset-review/no-gloves-review/no_gloves_review_index.csv)
- [Orphan-label report](./outputs/dataset-review/orphan-label-review/orphan_label_report.md)
- [Orphan-label CSV](./outputs/dataset-review/orphan-label-review/orphan_labels.csv)
