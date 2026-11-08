# Phase 2D — Dataset Remediation Plan

## Decision status

This is a source-selection and curation plan, not a dataset build. **Stage 2 remains in planning/research.** No source is approved for integration until source suitability, annotation semantics, and licensing/provenance are reviewed. The original dataset, supplementary dataset, YAMLs, checkpoint, application, and frozen test split remain unchanged.

The approved direction is to evaluate NO-Gloves as a proposed 26th class only. It is not part of the production class map. Its training eligibility remains conditional on obtaining appropriate construction/task examples and human annotation approval.

## Evidence-led priorities

The held-out test baseline and validation-only investigation show weak recall for Gloves (9.52%), NO-Mask (13.92%), NO-Hardhat (36.59%), and NO-Safety Vest (37.78%). These are reasons to improve representative data and annotation consistency, not proof of a single cause.

Current support and split counts are in the [26-class coverage matrix](./phase-2d-class-coverage-matrix.csv). Current original-set support is 5,570 instances over 717 matched images; the supplementary set has 11,521 matched instances over 1,416 images. The supplementary dataset contributes 556 no_gloves boxes but only a small reviewed sample has been checked for construction/task suitability. Do not extrapolate the sample’s out-of-domain findings to all 556 boxes.

### Priority order

1. **NO-Gloves (proposed class):** retain as conditional research target. The existing Ultralytics labels are not automatically eligible. Seek CPPED author access/codebook and rights, and ask the TechScience authors about a dataset release/provenance. Build a human-reviewed candidate pool requiring visible hands and documented task/site glove requirement. If the evidence and rights are not obtained, defer this class from the experimental taxonomy rather than training on ambiguous labels.
2. **NO-Mask:** there is no direct supplementary equivalent in the inspected Ultralytics set. Source explicit, task-specific construction examples or annotate rights-cleared original/new imagery under the policy. Do not infer from absent Mask detections.
3. **NO-Safety Vest:** investigate the Mendeley Dataset of PPE NoVest class. Require image-level rights/provenance, construction/task context, visibility, annotation convention, and duplicate review. Do not infer from absent Safety Vest boxes.
4. **NO-Hardhat:** investigate the Mendeley Dataset of PPE NoHelmet labels, and request codebooks for candidate person-without-helmet sources. Confirm visible worker/head, requirement context, and image rights. Do not map head, normal head, or missing helmet detections into violations.
5. **Positive Gloves, Hardhat, Mask, Safety Vest, and Person:** retain the original labels while auditing box convention and source rights. Use supplemental positives only after the same provenance/domain review; industrial positives do not automatically represent construction tasks.

## Source dispositions

### Useful leads, not approvals

- **Dataset of PPE (Mendeley v6):** best concrete lead for explicit NoHelmet and NoVest; lacks gloves and mask. Its CC BY 4.0 dataset declaration is not enough to clear every embedded source photo.
- **CPPED:** strongest explicit no gloves research lead; authors report 2,017 such annotations and require a justified data request. CC BY-NC 4.0 means no assumed commercial/portfolio use. Request source manifest, codebook, and written rights clarification.
- **TechScience 2025 paper dataset:** reports explicit no_gloves, no_helmet, and no_safety_vest, but no separate licensed download was verified. Contact authors; do not rely on the reported paper classes as available assets.
- **SH17, SHEL5K, SHWD, SFCHD:** potentially useful for positive PPE or helmet research under limitations described in [source research](./phase-2d-dataset-source-research.md); none directly solves all target violation classes.
- **Mendeley construction-safety five-class dataset and Springer paper lead:** unresolved metadata/access. Do not select until primary-source class map, file access, licensing, and provenance are verified.
- **Current Ultralytics Construction-PPE:** retain as an inspected, separate candidate. Its no_gloves requires broad review; its none class remains undefined and excluded from violation mapping.

### Exclusions and quarantine

- Quarantine all 13 near-duplicate scene-family candidates from any first combined-data manifest. Nine supplementary train images share a scene family with the original frozen test image; four other pairs connect supplementary and original training/validation scene families. This is a manifest status only: do not delete or move data.
- Exclude all ten orphan label files (93 rows) from matched-image statistics and future use unless the source publisher verifies exact image associations. Same-stem names are not sufficient evidence.
- Exclude supplementary none from the proposed PPE classes until the publisher defines it; never map it to a violation.
- Do not map no_goggle or no_boots to any existing class.
- Do not include non-construction/recreation no_gloves examples as construction violations. Keep them in a human-review queue until reviewed under the policy; do not treat the six reviewed examples as representative of all labels.

## Future curation workflow (not executed)

1. **Source intake:** preserve a read-only source archive and record publisher, immutable version/URL, retrieval date/method, SHA256, declared dataset license, attribution, image-level rights evidence, and any author permissions. Keep dataset, software, application, and trained-model licensing records separate.
2. **Codebook review:** compare actual class definitions, box semantics, visibility thresholds, and split construction. Obtain explicit answers for no_gloves and none, and any NoHelmet or NoVest class.
3. **Human image review:** review each candidate violation with the [PPE annotation policy](./ppe-annotation-policy.md). Label states must separate explicit violation, compliant/positive PPE, not visible, not applicable, and uncertain. A missing positive annotation does not imply violation.
4. **Deduplication and source grouping:** calculate exact hashes, then image perceptual similarity; review candidate scene/video groups. Exclude or group images at the scene/source sequence level before splitting. Record reviewed decisions and avoid placing related frames across train/validation/test.
5. **Candidate manifest:** create a separate, versioned, non-mutating manifest with source path/hash, original split, source scene group, proposed split, class mapping, review status, license/provenance record, and exclusion rationale. No merged labels or images are created by this plan.
6. **Class mapping approval:** retain the original 25 IDs and meanings. Any experimental 26-class proposal must be approved separately. Do not map unrelated, generic, or ambiguous classes to a violation.
7. **Split design:** keep the original 82-image held-out test split frozen and untouched. Never move, augment, or train on it. Remove the nine train-to-test scene overlaps from candidate training and review any other cross-source scene families. New evaluation data must be independently sourced and grouped at scene/site/camera/time level before a future independent evaluation.
8. **Balance and sampling:** plan additions based on class support, image diversity, and per-source counts, not arbitrary box targets. Avoid overrepresenting one source, location, camera, worker, or video burst. Keep positive PPE, explicit violation, and person examples sufficiently represented. Retain empty/negative images only with defined and reviewed annotation semantics.
9. **Approval gates:** require data-owner/source-rights review, annotation-policy review, duplicate/split review, and a human decision on whether NO-Gloves has enough valid examples. Only after those gates may Stage 3 experimental model work be proposed.

## Risks and limits

- Dataset license declarations do not resolve underlying photo copyrights, source terms, attribution, redistribution, or commercial use.
- Similar class strings can hide different concepts or box conventions. In particular NoHelmet/no_helmet does not automatically prove the SafeSite violation definition.
- The existing validation/test weakness cannot be attributed to imbalance, annotation quality, or confidence filtering alone from current evidence. The current supplement is a possible data source, not demonstrated corrective evidence.
- Mixing datasets can teach source-specific backgrounds, label conventions, and different PPE policies.
- The proposed class count is not evidence of effective sample size: correlated frames, ambiguous context, or duplicate scenes reduce independent coverage.
- No production threshold, class map, model, application path, or dataset is changed by this plan.

## Recommendation

Proceed with **source clarification and human review**, not merge or training. The Mendeley PPE dataset is the most promising verified source lead for NO-Hardhat and NO-Safety Vest; CPPED is the strongest NO-Gloves lead but is noncommercial and access-controlled; the TechScience multi-violation dataset is promising only after the authors supply licensed files and provenance. No verified new source currently resolves NO-Mask. If suitable, rights-cleared NO-Gloves examples cannot be established, defer it from the experimental model.

**Stage 2 is not complete:** primary-source access, source image rights, annotation definitions, duplicate group disposition, and human approval remain open.
