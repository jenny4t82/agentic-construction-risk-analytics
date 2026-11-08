# Proposed Construction-PPE class mapping

**Status: proposal only. No dataset merge, label edit, model update, or schema update is approved by this document.** Every source image remains blocked by unresolved photo-rights review, and mapped labels require a policy/box-convention review before use.

## Candidate mapping

| Supplement ID | Supplement class | Proposed target | Confidence in semantic equivalence | Evidence and assumptions | Approval needed |
|---:|---|---|---|---|---|
| 0 | `helmet` | Existing `Hardhat` (ID 2) | Medium; provisional | Both describe head protection. Verify the source boxes cover the same object extent and that “helmet” means an accepted construction hardhat under SafeSite policy. | Human label sample review and annotation-policy approval. |
| 1 | `gloves` | Existing `Gloves` (ID 1) | Medium; provisional | Positive glove labels are available. Verify glove type and item-box conventions; do not infer missing gloves from absence of this detection. | Human label sample review and annotation-policy approval. |
| 2 | `vest` | Existing `Safety Vest` (ID 11) | Medium; provisional | Similar high-visibility vest concept. Verify source meaning and box extent. It does not provide a missing-vest label. | Human label sample review and annotation-policy approval. |
| 3 | `boots` | None in current schema | High confidence: no equivalent class | Existing 25-class schema has no boots class. | Exclude unless a later schema change is approved. |
| 4 | `goggles` | None in current schema | High confidence: no equivalent class | Existing 25-class schema has no goggles class. | Exclude unless a later schema change is approved. |
| 5 | `none` | No mapping | Undefined | Publisher documentation/YAML reviewed here does not define this label. Never interpret it as missing PPE. | Obtain a codebook; exclude until semantics are verified. |
| 6 | `Person` | Existing `Person` (ID 8) | Medium; provisional | Similar person category, but verify full-body/visible-person box conventions and capitalization does not imply a distinct class. | Human label sample review. |
| 7 | `no_helmet` | Existing `NO-Hardhat` (ID 5) | Medium; provisional | Explicit missing-helmet label appears to represent the same broad violation. Verify construction context, visibility rules, and whether the absence region is boxed consistently. | Human label sample and violation-policy approval. |
| 8 | `no_goggle` | None in current schema | High confidence: no equivalent class | Existing schema has no explicit missing-goggles class. | Exclude unless a later schema change is approved. |
| 9 | `no_gloves` | **Proposed new class `NO-Gloves`; not an existing class** | Low pending context/policy review | Source class exists, but the six reviewed samples are outside construction contexts. Bare hands do not establish that task/site policy required gloves. | Establish construction-specific annotation policy, manually curate examples, obtain human approval, and separately approve model/application schema changes. |
| 10 | `no_boots` | None in current schema | High confidence: no equivalent class | Existing schema has no explicit missing-boots class. | Exclude unless a later schema change is approved. |

## Unsupported classes in the existing model

The supplementary dataset has no `Mask`, `NO-Mask`, or `NO-Safety Vest` class. It also has no explicit missing-vest category; the official dataset documentation states that `vest` has no dedicated missing-vest class. Do not map `none` to any violation, use missing positive detections to infer a violation, or derive a missing-PPE class from an unpaired person/object annotation.

## Existing-schema mapping reference

| Existing ID | Existing class | Supplement source class | Proposal |
|---:|---|---|---|
| 1 | `Gloves` | `gloves` (1) | Provisional candidate only. |
| 2 | `Hardhat` | `helmet` (0) | Provisional candidate only. |
| 5 | `NO-Hardhat` | `no_helmet` (7) | Provisional candidate only. |
| 8 | `Person` | `Person` (6) | Provisional candidate only. |
| 11 | `Safety Vest` | `vest` (2) | Provisional candidate only. |
| — | `NO-Gloves` | `no_gloves` (9) | New-class proposal, requires separate approval. |
| 4, 6, 7 | `Mask`, `NO-Mask`, `NO-Safety Vest` | No equivalent | No mapping. |

All other existing project classes have no equivalent in this supplementary dataset. All other supplementary classes are out of scope or undefined as listed above.

## Use conditions

1. Resolve dataset/photo rights and attribution before any use.
2. Obtain the publisher annotation guide and confirm class and box semantics.
3. Resolve duplicate scene groups and orphan labels using the proposed quarantine manifest.
4. Approve a construction-specific `NO-Gloves` definition before curating that class.
5. Obtain human approval of the final class map and split manifest before any merge or training.

See [dataset integration readiness](./dataset-integration-readiness.md), [licensing review](./licensing-review.md), and [Phase 2C plan](./phase-2c-integration-plan.md).
