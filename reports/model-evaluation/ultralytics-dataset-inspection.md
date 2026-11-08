# Ultralytics Construction-PPE Dataset Inspection

Inspection date: **2026-11-02**
Dataset: **Ultralytics Construction-PPE**
Scope: acquire and inspect only. No merge, training, model changes, or label edits were performed.

## 1. Download verification

- **Official documentation:** [Construction-PPE dataset](https://docs.ultralytics.com/datasets/detect/construction-ppe/)
- **Official YAML:** [ultralytics/cfg/datasets/construction-ppe.yaml](https://github.com/ultralytics/ultralytics/blob/main/ultralytics/cfg/datasets/construction-ppe.yaml)
- **Official archive URL from that YAML:** [construction-ppe.zip](https://github.com/ultralytics/assets/releases/download/v0.0.0/construction-ppe.zip)
- **Download method:** downloaded the exact archive URL published in the official YAML (the docs say Ultralytics downloads and unpacks it when the dataset is first used). No training command was run.
- **Download location:** `datasets/external/ultralytics-construction-ppe/`
- **Original archive retained:** `datasets/external/ultralytics-construction-ppe/construction-ppe.zip`
- **Archive size:** 178,415,813 bytes
- **SHA256:** `BEF8DCB599AA4E9D9F5E602CB6FA7143D3C84D7F6A0FF40463D7F2A4C2632CCC`
- **Integrity:** ZIP CRC test passed; 2,852 entries; 179,301,803 uncompressed bytes.
- **Dataset version:** official documentation's citation metadata says **1.0.0**. The downloaded YAML has no dataset version field. The archive URL's GitHub release tag is `v0.0.0`; this is an asset release tag, not a dataset version field.
- **Published splits:** train 1,132, val 143, test 141 (1,416 total), matching the downloaded image inventory.
- The dataset and archive are ignored by the existing repository `.gitignore` rule for `datasets/` and ZIP files.

## 2. Dataset inventory and annotation checks

The inspected YAML is at [`datasets/external/ultralytics-construction-ppe/data.yaml`](../../datasets/external/ultralytics-construction-ppe/data.yaml). Its paths are `images/train`, `images/val`, and `images/test`, with matching `labels/` directories. It uses standard Ultralytics YOLO detection rows: `class_id x_center y_center width height` with normalized coordinates.

| Split | Images | Matched label files | Labeled instances | Empty matched labels | Missing label files | Orphan label files |
|---|---:|---:|---:|---:|---:|---:|
| Train | 1,132 | 1,132 | 9,098 | 0 | 0 | 10 |
| Validation (`val`) | 143 | 143 | 1,172 | 0 | 0 | 0 |
| Test | 141 | 141 | 1,251 | 0 | 0 | 0 |
| **Total** | **1,416** | **1,416** | **11,521** | **0** | **0** | **10** |

Class counts below are from annotations paired to image files. Training has 10 extra label files not paired to an image; those contain another 93 annotation rows (20 Person, 16 helmet, 16 gloves, 16 boots, 14 vest, 8 goggles, 3 none). These rows are excluded from the matched-image counts and should be resolved with the dataset publisher before any merge. They were not changed or deleted.

| ID | Class | Train | Val | Test | Total |
|---:|---|---:|---:|---:|---:|
| 0 | helmet | 1,341 | 201 | 192 | 1,734 |
| 1 | gloves | 1,146 | 136 | 163 | 1,445 |
| 2 | vest | 1,269 | 171 | 178 | 1,618 |
| 3 | boots | 1,235 | 151 | 211 | 1,597 |
| 4 | goggles | 419 | 47 | 52 | 518 |
| 5 | none | 651 | 81 | 65 | 797 |
| 6 | Person | 1,770 | 239 | 236 | 2,245 |
| 7 | no_helmet | 400 | 45 | 40 | 485 |
| 8 | no_goggle | 337 | 41 | 33 | 411 |
| 9 | no_gloves | 442 | 56 | 58 | 556 |
| 10 | no_boots | 88 | 4 | 23 | 115 |
|  | **Total** | **9,098** | **1,172** | **1,251** | **11,521** |

### Image dimensions

There are 93 distinct width/height combinations. **1,116/1,416** images are 640×640; the remaining 300 have varied dimensions, from 408×263 to 1024×1024. The downloaded YAML does not prescribe a resize operation. Preserve original dimensions and let a documented preprocessing pipeline handle resizing if the data is later integrated.

### Automated label checks

- Matched image files with missing label files: **0**.
- Empty matched label files: **0**.
- Invalid class IDs: **0**.
- Malformed/non-numeric rows in matched labels: **0**.
- Non-finite values, non-positive box width/height, normalized coordinates outside [0,1], or boxes extending outside image bounds: **0** among matched files.
- Orphan training label files: **10**, totaling 93 otherwise parseable rows. No other split has orphans.
- Duplicate image basenames within the supplementary dataset across splits: **0**.

The `none` class is in the YAML and has 797 matched boxes, but the inspected docs do not define its annotation semantics. Do not map it to any missing-PPE class. The docs explicitly state that `vest` has no dedicated missing-vest class.

## 3. `no_gloves` review

The class is present and has **556 matched boxes** across **236 images**: train 442 boxes / 190 images, validation 56 / 23 images, and test 58 / 23 images. This confirms that the dataset includes both positive `gloves` (1,445 boxes) and explicit `no_gloves` (556 boxes) annotations.

Three example images and their `no_gloves` labels were visually inspected: `images/train/image1117.jpg`, `images/val/image1129.jpg`, and `images/train/image1398.jpg`. The boxes are placed around hand regions, but these examples depict restaurant/eating, event or trade-show, and gym/exercise contexts rather than an obvious construction task. Some bare-hand detections may therefore encode “hands without gloves” without establishing that gloves are required by a construction-site rule; the gym example also warrants checking whether wrist/hand coverings affect the label. This is a **semantic/domain review concern**, not a confirmed incorrect label. The archive contains no separate annotation guide explaining when a `no_gloves` box should be assigned.

The smallest measured `no_gloves` box in matched labels is about 10.5×15.4 pixels when scaled to a 640×640 frame; small hand regions may be difficult to recognize. The `no_gloves` class has meaningful representation, but label context and policy need review before it is used as a violation class in SafeSite.

## 4. Existing-to-supplementary class mapping

The current 25-class mapping was read from [`datasets/evaluation/construction-site-safety-v1/data.yaml`](../../datasets/evaluation/construction-site-safety-v1/data.yaml). A “candidate direct” mapping means the names appear to describe the same gear category; it still requires a label-policy/codebook check. No configuration was changed.

| Existing ID | Existing class | Supplementary class | Supplementary ID | Status | Notes |
|---:|---|---|---:|---|---|
| 0 | Excavator | — | — | No equivalent | No construction-equipment equivalents in this PPE schema. |
| 1 | Gloves | gloves | 1 | Candidate direct | Confirm glove/PPE subtype and box extent. |
| 2 | Hardhat | helmet | 0 | Candidate direct | Confirm whether helmet subtype and head-vs-helmet box policy match. |
| 3 | Ladder | — | — | No equivalent | — |
| 4 | Mask | — | — | No equivalent | The supplementary dataset has no mask class. |
| 5 | NO-Hardhat | no_helmet | 7 | Candidate direct violation | Similar semantics; verify class definition and which region is boxed. |
| 6 | NO-Mask | — | — | No equivalent | No missing-mask class. |
| 7 | NO-Safety Vest | — | — | No equivalent | Docs explicitly state no missing-vest class. |
| 8 | Person | Person | 6 | Candidate direct | Confirm person box conventions. |
| 9 | SUV | — | — | No equivalent | — |
| 10 | Safety Cone | — | — | No equivalent | — |
| 11 | Safety Vest | vest | 2 | Candidate direct | `vest` is the publisher's PPE class; verify visible-area/extent policy. |
| 12 | bus | — | — | No equivalent | — |
| 13 | dump truck | — | — | No equivalent | — |
| 14 | fire hydrant | — | — | No equivalent | — |
| 15 | machinery | — | — | No equivalent | — |
| 16 | mini-van | — | — | No equivalent | — |
| 17 | sedan | — | — | No equivalent | — |
| 18 | semi | — | — | No equivalent | — |
| 19 | trailer | — | — | No equivalent | — |
| 20 | truck | — | — | No equivalent | — |
| 21 | truck and trailer | — | — | No equivalent | — |
| 22 | van | — | — | No equivalent | — |
| 23 | vehicle | — | — | No equivalent | — |
| 24 | wheel loader | — | — | No equivalent | — |

Supplementary-only classes:

| Supplementary class | ID | Existing equivalent | Mapping decision |
|---|---:|---|---|
| boots | 3 | — | No existing class; do not add implicitly. |
| goggles | 4 | — | No existing class; do not map to Mask. |
| none | 5 | — | Meaning not defined in the inspected docs; leave unmapped. |
| no_goggle | 8 | — | New violation class if desired later; no existing class. |
| no_gloves | 9 | — | Planned feature; requires new class and application support in a later approved phase. |
| no_boots | 10 | — | New violation class; no existing class. |

In particular, positive `gloves` must not be mapped to `NO-Gloves`, and the explicit `no_gloves` class must not be collapsed into the current 25 classes. No mask or vest violation can be inferred from missing positive boxes.

## 5. Duplicate investigation

All **717 existing dataset images** (train, validation, test) were compared with all **1,416 supplementary images**.

- **Exact duplicates by file SHA256:** 0 image pairs; 0 supplementary images shared byte-for-byte with an existing image.
- **Shared image basenames:** 0.
- `ImageHash` is not installed in `.venv-yolo`, and no package was installed. A 64-bit difference hash (dHash) was computed using the already-installed Pillow library. With the documented review threshold **Hamming distance ≤5/64**, the scan found **13 candidate pairs** involving 13 supplementary images. These are potential near-duplicates, not automatically confirmed duplicate files.
- Of those pairs, **9** pair a supplementary **train** image with an existing **test** image; **4** pair a supplementary image with an existing **train** image. No candidate pairs touch the existing validation split. There are no supplementary test images among these matches.
- A visual spot-check confirmed a same-location/same-scene sequence among several candidates around existing test image `image_55_jpg.rf.bd0780b14a93c28b7d6af0558d1fdcaa.jpg` and supplementary images including `image685.jpg`; people/poses differ, so these are sequence-level near-duplicate/leakage candidates rather than exact duplicates. Another candidate joins supplementary `val/image709.jpg` to existing `train/image_170_jpg.rf.747403dbb5b1c349197c96146345786c.jpg` from the same site/background.

**Integration consequence:** do not place the nine supplementary train candidates that match the frozen existing test scenes into training until a source/scene audit resolves them. Preserve the existing 82-image test set and group related frames by source/site/video in any future split. dHash can produce false positives for similar scenes and false negatives after substantial crops/edits, so the candidate list requires review; no images were moved or removed.

## 6. Licensing, attribution, and provenance

### Dataset license and source

The official dataset documentation identifies the dataset as AGPL-3.0, says to provide proper attribution, and includes a BibTeX citation for authors Mrunmayee Dalvi, Niyati Singh, Sahil Bhingarde, and Ketaki Chalke, publisher Ultralytics, version 1.0.0. The downloaded archive includes a `LICENSE` file containing the GNU AGPL v3 license text. The archive has no README, per-image source manifest, separate attribution table, or image-specific rights information. Consequently, the published dataset license and attribution information are recorded, but **the archive alone does not verify that each underlying photograph has separately documented redistribution rights**. Do not redistribute the archive or its images on the assumption that the AGPL notice resolves every source-image right.

### Keep these licenses separate

| Asset | What was verified | Limitation / action |
|---|---|---|
| Construction-PPE dataset | Official docs and archive state AGPL-3.0; attribution/citation requested. | Legal review needed for use, modification, redistribution, and source-image rights; missing per-image provenance in archive. |
| Ultralytics software | The dataset YAML/repository identifies the software with AGPL-3.0; Ultralytics publishes an Enterprise licensing option. | Software license is separate from the dataset license. Check the exact package/version and deployment model used by the project. |
| Application source | No root `LICENSE` file was found in this workspace during inspection; `requirements.txt` has no Ultralytics entry. | The application source license is not established by this inspection. Do not infer it from the dataset or environment. |
| Existing `weights/best.pt` | No checkpoint-specific license or source-data manifest was located as part of this dataset inspection. | Dataset rights do not automatically state the checkpoint's license. Review original training-data rights and weight distribution separately. |
| Any future derived checkpoint | No new checkpoint was created. | Whether training/weight distribution triggers obligations under these terms is a legal question; obtain counsel before training for or distributing a commercial/hosted product. |

The official dataset page says the dataset is released under AGPL-3.0 and describes commercial applications with attribution. Separately, Ultralytics' current [software licensing page](https://www.ultralytics.com/license) says its free AGPL option is for projects that are comfortable open-sourcing the entire project under AGPL-3.0, and lists an Enterprise license for commercial products/services, SaaS, proprietary deployment, and commercial use of custom-trained models. These statements concern different assets and should not be conflated: confirm the dataset's image rights and dataset-license scope with the publisher, and assess the Ultralytics software license independently for the intended platform. How either license applies to model parameters or a combined project depends on the facts and is not determined here. An open-source portfolio designation alone does not resolve the issue.

## 7. Compatibility assessment and recommendation

**Technical:** the archive is readable and uses a compatible YOLO detection annotation structure. It includes positive Gloves/helmet and explicit `no_gloves`/`no_helmet` boxes. Existing Hardhat, NO-Hardhat, Gloves, Safety Vest, and Person have plausible semantic counterparts, but box policy and semantic definitions still require a source review. There is no direct supplementary equivalent for Mask, NO-Mask, or NO-Safety Vest. Supplementary-only classes (`boots`, `goggles`, `none`, `no_goggle`, `no_boots`, `no_gloves`) must remain unmapped until a schema change is approved.

The archive YAML sets `path: construction-ppe`, matching the publisher's default extraction directory name, while this copy is stored at the requested `datasets/external/ultralytics-construction-ppe/` location. Preserve the original YAML; a future training/evaluation command may need a separate derived YAML that points to the actual external directory. Do not silently rewrite the archived configuration.

**Data quality:** the matched annotations pass basic syntax, ID, normalization, and bounds checks. Ten orphan train labels and ambiguous `none` semantics require publisher clarification. The no_gloves class is real and nontrivial in count, but visual review found out-of-domain contexts and no annotation codebook; do not yet treat every `no_gloves` box as a construction-site rule violation. dHash found scene-level candidates crossing the existing held-out test boundary, so source-aware split protection is required.

**Readiness:** **not ready to merge or train from yet.** It is acquired and structurally inspectable, but integration should wait for (1) legal review of dataset/image/software/model rights, (2) clarification of orphan files and `none`/`no_gloves` semantics, and (3) review/quarantine of near-duplicate scenes against existing test data. The current 25-class YAML and application remain unchanged.

## 8. Recommended next steps

1. Request publisher clarification on image-source rights, meaning of `none`, exact `no_gloves` policy, and the 10 orphan label files.
2. Have counsel review the archive AGPL terms against the project's source license, Ultralytics software use, hosted deployment, and any future checkpoint distribution.
3. Review the 13 dHash candidates and source/site/video groupings; keep any scene related to the existing held-out test out of future training.
4. Define the new `NO-Gloves` annotation semantics and required application support before changing a dataset schema. Do not infer it from absent Gloves detections.
5. In a separately approved future phase, create a provenance-preserving copy and a new schema/mapping manifest; leave the existing dataset, model, and frozen test set unchanged.

## Sources

- [Official Construction-PPE documentation](https://docs.ultralytics.com/datasets/detect/construction-ppe/)
- [Official dataset YAML](https://github.com/ultralytics/ultralytics/blob/main/ultralytics/cfg/datasets/construction-ppe.yaml)
- [Official Ultralytics assets release archive](https://github.com/ultralytics/assets/releases/download/v0.0.0/construction-ppe.zip)
- [Ultralytics licensing page](https://www.ultralytics.com/license)
- [Ultralytics software LICENSE](https://github.com/ultralytics/ultralytics/blob/main/LICENSE)
- [GNU AGPL v3.0 license text](https://www.gnu.org/licenses/agpl-3.0.html)
- [Existing project dataset config](../../datasets/evaluation/construction-site-safety-v1/data.yaml)
- [Dataset provenance record](./ultralytics-dataset-provenance.json)
