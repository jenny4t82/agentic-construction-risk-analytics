# Phase 2C - Clean dataset integration plan

Project: SafeSite Risk Intelligence - Agentic Construction Risk Analytics Platform
Milestone: Safety Intelligence & Worker Protection
Prepared: 2026-11-02

## Executive summary

The official Ultralytics Construction-PPE download has been inspected, and its data-quality questions have been reviewed. This phase prepares a traceable integration proposal only. **The dataset is NOT READY FOR INTEGRATION. No files have been merged, no labels or YAMLs have been changed, and no training has started.**

The principal gates are unresolved photo rights and licensing scope, nine supplementary training images from the scene family of the frozen existing test set, unverified pairings for ten orphan labels, and sampled `no_gloves` labels whose images do not show a construction task/site policy. The current 25-class model does not contain a `NO-Gloves` class.

## Decisions made

- Keep the original 25-class configuration, model checkpoint, and original train/validation/test splits unchanged.
- Treat class-name similarity as a provisional mapping hypothesis, not approval.
- Do not map `no_gloves` to `Gloves`, and never infer glove absence from lack of a positive `gloves` detection.
- Do not map `none` to a violation. Do not invent mappings for missing vest/mask violation classes.
- Exclude orphan label rows until the source association is verified.
- Quarantine all 13 visually confirmed scene-family overlaps. The nine supplementary-train/existing-test pairs are high-priority future-training exclusions while the original test benchmark is retained. Keep the other four in review; do not automatically exclude them.
- Do not use the old held-out test set to choose thresholds or make training decisions.

## Proposed mappings

Candidate provisional source mappings are `helmet` (0) to existing `Hardhat` (2), `no_helmet` (7) to `NO-Hardhat` (5), `gloves` (1) to `Gloves` (1), `vest` (2) to `Safety Vest` (11), and `Person` (6) to `Person` (8). All require annotation-policy and bounding-box review. `no_gloves` (9) is only a new-class proposal and is not suitable for automatic inclusion under the current SafeSite definition. `none` (5) is undefined; boots, goggles, and their absence classes have no current target. The source has no mask or missing-vest class.

See [proposed class mapping](./proposed-class-mapping.md) for per-class confidence and approval requirements.

## Quarantine findings

The reviewed duplicate index contains 13 scene-family matches at dHash distance 1-5/64, with zero exact SHA-256 pairs found in the original scan. Nine pairs connect supplementary train to the frozen existing test; four connect supplementary train/validation to existing train. Distinct poses do not establish different source sessions. The quarantine manifest also records the ten orphan label files and same-stem candidate image paths. Those possible candidates are not asserted to be the correct pairings.

The proposed manifest contains all 1,416 matched image/label pairs and ten additional orphan-label candidate records. Each row carries original split, source labels, proposed mapping, eligibility, quarantine status, archive hash, and a no-approval note. All records remain blocked, quarantined, or excluded; the manifest does not approve data use.

- [Quarantine manifest](./outputs/dataset-review/integration-plan/quarantine_manifest.csv)
- [Proposed dataset manifest](./outputs/dataset-review/integration-plan/proposed_dataset_manifest.csv)
- [Visual duplicate review](./dataset-integration-readiness.md#duplicate-and-test-set-leakage-review)
- [NO-Gloves sample review](./dataset-integration-readiness.md#no_gloves-semantic-review)
- [Orphan-label report](./outputs/dataset-review/orphan-label-review/orphan_label_report.md)

## Proposed dataset structure

No materialized combined dataset is proposed in this phase. If approval gates pass, create a new derived dataset directory with a generated configuration that references original sources read-only and an explicit, versioned file-level inclusion/remap manifest. Preserve each source's original archive, image, label, split, source ID, class ID/name, hash, license/attribution metadata, and human review decision. Do not edit either source dataset in place.

The first possible mapped target set is limited to Hardhat, NO-Hardhat, Gloves, Safety Vest, and Person. This is conditional on review and rights clearance, not a final inclusion set. Exclude source classes without a current equivalent and unresolved `none` semantics. Do not create `NO-Gloves` examples from absent positive labels.

## Future split strategy

1. Keep the original 82-image held-out test set, its annotations, and its evaluation outputs untouched as the historical benchmark. Never include those images or their unresolved scene-family neighbors in training while comparing against that benchmark.
2. Determine site, scene, source-photo, capture-session, and video identifiers before assigning any approved new data. Keep a group and all known frames from it entirely within one split.
3. Do not trust publisher train/val/test assignments as proof of independence across sources. Audit the full combined candidate set for exact and perceptual matches, then manually inspect scene-family candidates before split assignment.
4. Build a new source-grouped validation set for iteration and threshold selection. Use available independent groups and class/condition coverage to determine its size; do not choose a split percentage without reviewing group counts and expected per-class support.
5. Consider a separate, newly curated external test set from distinct sites/capture sources. Lock it before model comparison and do not use it for tuning.
6. Report metrics separately by dataset/source and annotation policy. A metric difference across datasets with different populations, class definitions, box conventions, or image difficulty is not by itself evidence of model improvement or regression.

## Unresolved questions

- What are the photo sources and rights for every image? Are training, derived labels, and redistribution of photos/derivatives allowed? What attribution is required?
- What is the publisher's precise `no_gloves` rule, including task-specific glove requirements, uncertain/occluded hands, and non-construction images?
- How did the non-construction contexts observed in the review sample enter this dataset, and are they intended examples for the published class?
- Are the ten orphan labels duplicates/alternate annotations of the same-stem images, and what source export produced the `(1)` names?
- Do the 13 visual scene-family matches share a site/session/video source? What group-level exclusion boundary should govern the new split?
- Does the project intend to add a `NO-Gloves` model/output schema and application support in a later separately approved phase?
- What is the intended distribution/deployment model for Ultralytics software and the existing/custom-trained checkpoint, and what license review applies?

## Approval gates

All gates must be documented before any merge or training:

1. Dataset license and attribution reviewed.
2. Underlying image/photo rights clarified.
3. Orphan image-label pairings verified or excluded.
4. Near-duplicate scene overlap resolved.
5. Class semantics and mapping approved.
6. Construction-specific `no_gloves` annotation policy established.
7. New class requirements approved.
8. Dataset configuration validated.
9. Split integrity verified.
10. Human approval obtained before training.

## Exact next action

Request one written clarification package from Ultralytics covering per-image photo provenance/rights and redistribution, the `no_gloves` annotation codebook and domain scope, the ten orphan label/image pairings, and provenance for the shared scene family. Then obtain project legal review and human sign-off before preparing any merge. No external message has been sent as part of this planning task.

## Detailed evidence

- [Dataset integration readiness](./dataset-integration-readiness.md)
- [Licensing review](./licensing-review.md)
- [Dataset inspection](./ultralytics-dataset-inspection.md)
- [Dataset provenance JSON](./ultralytics-dataset-provenance.json)
- [Dataset expansion research](./dataset-expansion-plan.md)
- [Milestone 2 progress log](../../docs/milestone-2-progress-log.md)
