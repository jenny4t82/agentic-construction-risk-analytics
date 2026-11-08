# Construction PPE Dataset Expansion Plan

Research and planning snapshot: **2026-11-02**. No datasets were downloaded, extracted, merged, or relabeled for this plan.

## Executive summary

The existing dataset has 717 images (521 train, 114 validation, 82 test), all resized to 640×640. It contains explicit `NO-Hardhat`, `NO-Mask`, and `NO-Safety Vest` boxes, but has no `NO-Gloves` class. Training counts for Gloves (231), NO-Hardhat (292), NO-Mask (338), and NO-Safety Vest (386) are much lower than Person (808) and Safety Cone (464), though NO-Mask and NO-Safety Vest are not absent or vanishingly rare. The validation analysis found weak recall even where confidence was reduced, and flagged small/occluded objects, distant workers, dense scenes, and out-of-domain imagery for human review. Those findings support targeted data and annotation review, but do not establish that class count alone caused the misses.

The most practical public supplement identified for investigation is the **Ultralytics Construction-PPE** dataset: its publisher lists 1,416 YOLO images and explicit `no_gloves` and `no_helmet` labels. It has no `no_mask` or `no_vest`, and its AGPL-3.0 terms require a licensing review before any use in a commercial product. **CPPED** is a relevant lead with 2,612 images and a `no gloves` class, but access is by justified request and it is marked CC BY-NC 4.0, excluding commercial use. For NO-Mask and NO-Safety Vest, the inspected public sources did not yield a clearly licensed, construction-focused dataset with directly compatible violation labels. Curating verified project imagery may be necessary.

## 1. Existing dataset summary

Local source: [`datasets/evaluation/construction-site-safety-v1/`](../../datasets/evaluation/construction-site-safety-v1/). The split inventory below was calculated from the current images and YOLO label files. Image and instance counts are local measurements, not upstream estimates.

| Split | Images | Labeled instances | Image dimensions |
|---|---:|---:|---|
| Train | 521 | 4,031 | 521 at 640×640 |
| Validation | 114 | 733 | 114 at 640×640 |
| Test | 82 | 806 | 82 at 640×640 |
| **Total** | **717** | **5,570** | **All 640×640** |

All image files had a corresponding label file in this inventory. The dataset README says images were resized to 640×640 using stretch resizing; this may alter object aspect ratios relative to source imagery. It records a CC BY 4.0 license and identifies the Roboflow project/version; verify the applicable upstream terms and attribution on any new export.

### Class counts by split

| Class ID | Class | Train | Validation | Test | Total |
|---:|---|---:|---:|---:|---:|
| 0 | Excavator | 145 | 12 | 9 | 166 |
| 1 | Gloves | 231 | 25 | 40 | 296 |
| 2 | Hardhat | 385 | 79 | 110 | 574 |
| 3 | Ladder | 43 | 10 | 5 | 58 |
| 4 | Mask | 153 | 21 | 28 | 202 |
| 5 | NO-Hardhat | 292 | 69 | 41 | 402 |
| 6 | NO-Mask | 338 | 74 | 79 | 491 |
| 7 | NO-Safety Vest | 386 | 106 | 90 | 582 |
| 8 | Person | 808 | 166 | 174 | 1,148 |
| 9 | SUV | 16 | 0 | 0 | 16 |
| 10 | Safety Cone | 464 | 44 | 92 | 600 |
| 11 | Safety Vest | 322 | 41 | 61 | 424 |
| 12 | bus | 1 | 0 | 0 | 1 |
| 13 | dump truck | 127 | 13 | 17 | 157 |
| 14 | fire hydrant | 6 | 0 | 0 | 6 |
| 15 | machinery | 31 | 8 | 6 | 45 |
| 16 | mini-van | 6 | 1 | 0 | 7 |
| 17 | sedan | 39 | 13 | 2 | 54 |
| 18 | semi | 7 | 0 | 0 | 7 |
| 19 | trailer | 13 | 1 | 1 | 15 |
| 20 | truck | 29 | 4 | 2 | 35 |
| 21 | truck and trailer | 4 | 3 | 0 | 7 |
| 22 | van | 18 | 3 | 7 | 28 |
| 23 | vehicle | 74 | 18 | 30 | 122 |
| 24 | wheel loader | 93 | 22 | 12 | 127 |

### Imbalance and support

Across training labels, class counts range from **1 bus** and **4 truck-and-trailer** boxes to **808 Person** boxes, an extreme long tail. This aggregate imbalance includes vehicle classes that are not the main PPE objective. Within the requested PPE set, training support is Gloves 231, NO-Hardhat 292, NO-Mask 338, NO-Safety Vest 386, Mask 153, Safety Vest 322, and Hardhat 385; Person has 808. Validation has only 25 Gloves and 74 NO-Mask examples, so per-class validation estimates are noisy. The test split remains reserved for final evaluation and is not to be merged into training or used to choose thresholds.

The class layout is mixed: it includes PPE/wearer boxes, explicit violation boxes, construction objects, traffic-control items, and general vehicles. It also has many classes with tiny counts and some classes absent in one or more splits. Stratification and grouped splitting by source video/site are important if this dataset is revised.

### Annotation and metadata review notes

The Phase 1B validation analysis reported zero malformed, missing, or out-of-range label rows. Its deterministic 14-image visual review did not confirm semantic label errors, but flagged these for human review:

- `airport_inside_0090...jpg`: distant people and PPE boxes only a few pixels wide at model input scale; class and box edges are difficult to verify.
- `youtube-308...jpg`: two Gloves boxes cover small hand regions on a kneeling worker and were missed at the analysis reference threshold.
- `autox4_mp4-63...jpg`: racing-track imagery with distant people and a NO-Safety Vest label; confirm whether this non-construction domain is intentional and consistently annotated.
- `YouTube_FreeStockFootage_People-wearing-face-mask...jpg`: crowded urban pedestrians with small, overlapping PPE and Person boxes; review visibility and person-to-PPE association.

These are review candidates, not findings of incorrect labels. The dataset README metadata is also inconsistent: `README.dataset.txt` says “Human-Worker are annotated,” while `data.yaml` declares 25 classes and the label inventory contains those class IDs. Treat `data.yaml` plus observed labels as the working schema, but verify source/version provenance before adding data.

## 2. Current model weaknesses

The prior held-out test summary supplied for this phase reported recalls of Gloves 9.52%, NO-Mask 13.92%, NO-Hardhat 36.59%, and NO-Safety Vest 37.78%. The Phase 1B validation-only fixed-IoU analysis at confidence 0.25 measured:

| Class | Validation GT | TP | FP | FN | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| Gloves | 25 | 7 | 4 | 18 | 63.64% | 28.00% |
| NO-Mask | 74 | 13 | 13 | 61 | 50.00% | 17.57% |
| NO-Safety Vest | 106 | 44 | 18 | 62 | 70.97% | 41.51% |
| NO-Hardhat | 69 | 31 | 19 | 38 | 62.00% | 44.93% |

Those validation figures use class-aware greedy matching at IoU ≥ 0.50 and are not directly comparable to the held-out evaluator's AP protocol. Lowering the validation analysis score cutoff from 0.25 to 0.05 raised overall recall from 48.57% to 61.66%, but lowered precision from 69.40% to 30.44% and increased false positives from 157 to 1,033. At 0.25, only 4 of 18 missed Gloves and 18 of 61 missed NO-Mask objects had a same-class, IoU≥0.50 prediction below 0.25. Therefore threshold filtering contributes to some misses but is not the sole observed mechanism.

**Interpretation:** Gloves has low validation support and visible small/occluded hand examples, so a data-volume and object-scale contribution is plausible. NO-Mask has 74 validation boxes—more than Gloves—yet many are missed, so its results do not support “too few examples” as a sufficient explanation. Class confusion, labeling policy, domain mismatch, visual scale, and model capacity remain hypotheses to investigate through audited examples and source-separated evaluation.

## 3. Supplementary dataset comparison

Image totals and classes below are those published by the dataset host/authors. A dataset listing is not proof that every image has clear downstream redistribution or commercial rights; inspect the actual archive notices and source-image rights before acquisition or use.

| Candidate | Published scale and classes | Format / access | License and use notes | Assessment |
|---|---|---|---|---|
| [Ultralytics Construction-PPE](https://docs.ultralytics.com/datasets/detect/construction-ppe/) | 1,416 images: 1,132 train / 143 val / 141 test. `helmet`, `gloves`, `vest`, `boots`, `goggles`, `none`, `Person`, `no_helmet`, `no_goggle`, `no_gloves`, `no_boots`. | YOLO; direct 178.4 MB GitHub assets release, no registration/API described by publisher. | Publisher lists AGPL-3.0 and states commercial/open-source use with attribution. Confirm how that license covers the image archive, derived labels, trained weights, and distribution in this product before use. | **Best directly relevant lead for Gloves and a supplemental helmet/Person signal.** Has no no-mask or no-vest class; generic `none` is ambiguous and must not be mapped to any violation. |
| [CPPED](https://github.com/QHCV/CPPED) | 2,612 images; 13 categories; reported object counts include person 5,936, `no gloves` 2,017, gloves 985, mask 529, vest 2,587, head 957, color-coded clothing classes, shoes/no shoes, and glasses. | YOLO-style normalized `class x_center y_center width height`; Google Drive access requires a justified-use request. | CC BY-NC 4.0 per repository. Attribution and non-commercial restriction; not suitable for commercial use absent separate permission. Repository notes source images were taken from prior research and the internet, so check underlying image rights too. | **Strong research lead for glove/no-glove variation, but access and non-commercial terms limit product use.** `head` is not a no-hardhat label; classes `yellow/white/blue/red` appear to be clothing/vest color categories and need a codebook check. |
| [Mendeley Dataset of PPE, v6](https://data.mendeley.com/datasets/zkzghjvpn2/6) | 2,286 images, 640×640; four classes reported in the related paper: Helmet, NoHelmet, NoVest, Vest. | YOLO `.jpg`/`.txt`; Mendeley “Download All” page, no API requirement indicated; account/login behavior may vary. | **License conflict to resolve:** Mendeley record says CC BY 4.0; its related 2025 article identifies CC BY-NC. Do not use until the actual archive terms and authors confirm applicable rights. CC BY 4.0 normally permits commercial reuse with attribution, while CC BY-NC does not. | **Potential fit for NO-Hardhat / NO-Safety Vest only if license is clarified.** Does not cover gloves or masks; likely image-source overlap risk because it aggregates public datasets. |
| [SH17](https://github.com/ahmadmughees/SH17dataset) | 8,099 images / 75,994 instances; 17 classes include Person, Head, Face, Glasses, Face-mask-medical, Hands, Gloves, Safety-vest, Helmet, Safety-suit, etc. | YOLO-oriented data/config; dataset is available through Kaggle, with a script to restore images from Pexels URLs. Kaggle access generally requires a user account; confirm current listing access/terms. | Repository declares CC BY-NC-SA 4.0, with Pexels restrictions and “research/analysis” intent. Not cleared for commercial product use. | **Secondary candidate for worn Gloves/Mask/Vest/Helmet and diverse industrial visuals**, but no explicit missing-PPE classes. `Head` or absent item boxes do not mean an explicit violation. Cross-domain scenes may not resemble the target sites. |
| [Construction Site Safety (Roboflow Universe, PPE-detection)](https://universe.roboflow.com/ppe-detection-gwtcs/construction-site-safety-1vvac) | Listed as 717 images and the same 25 names as the local dataset, including all three current violation labels and no NO-Gloves. | Roboflow Universe project; 717 images visible. Export/download authentication requirements were not verified. | Project page lists CC BY 4.0. Follow attribution and verify export/version details. | **Likely the existing dataset or a rehost/fork, not an expansion source.** Exact image-level duplication has not been tested; do not merge without hashes/perceptual deduplication. |
| [Kaggle PPE Detection tutorial/input](https://www.kaggle.com/code/daffamuhamadazhar/yolov8-ppe-detection/input) | Notebook describes a Roboflow-derived 10-class collection: Hardhat, Mask, NO-Hardhat, NO-Mask, NO-Safety Vest, Person, Safety Cone, Safety Vest, machinery, vehicle. No Gloves class. | Kaggle notebook links to the Roboflow collection; Kaggle account may be needed to access notebook input. Separate original archive/count not verified. | The notebook references the source Roboflow collection's CC BY 4.0; do not treat the Kaggle notebook as independent licensing or independent images. | **Not a new source based on verified evidence; likely overlaps current collection and lacks gloves.** |
| [SHWD: Safety Helmet Wearing Dataset](https://github.com/njvisionpower/Safety-Helmet-Wearing-Dataset) | 7,581 images; 9,044 positive helmet objects and 111,514 normal head objects, per repository. | Pascal VOC XML; Google Drive/Baidu Drive links; likely account/service access, not a YOLO-ready package. | GitHub repository has an MIT license file, but that alone may cover code rather than third-party image content. Image license/redistribution rights are not clear from the inspected README. | **Helmet/head pretraining lead only.** Positive `hat` and `person`/head annotations are not explicit NO-Hardhat boxes; exclude from commercial use pending image-rights clarification. |
| [CHVG dataset / paper](https://pubmed.ncbi.nlm.nih.gov/35875643/) | 1,699 images, eight classes: four helmet colors, vest, safety glass, person body, person head. | Paper points to Figshare; direct Figshare access was blocked during research. Annotation format and registration needs not verified. | Figshare record is listed as CC BY 4.0 in an NLM catalog, but direct record and exact file license should be checked before use. | **Optional for positive hardhat/vest robustness only.** No explicit violations, Gloves, or Mask. Older work reports small-object challenges for construction PPE generally; inspect actual examples before considering. |
| [CPPE-5 medical PPE](https://arxiv.org/abs/2112.09569) | Medical imagery with gloves, masks, coveralls, goggles, and face shields; not a construction dataset. | Bounding-box detection annotations; GitHub/Kaggle distribution. | Verify its specific repository/archive license; not established in this pass. | **Not recommended for construction PPE expansion.** Medical gloves/masks have different appearance and context; at most a separate domain robustness experiment after license review. |

### Source and licensing notes

- The existing export's `README.dataset.txt` and `data.yaml` point to the original Roboflow Construction Site Safety project and state CC BY 4.0. Preserve attribution and release/version metadata with any future use.
- The Ultralytics docs explicitly state the split counts, class names, automatic/direct download path, and AGPL-3.0 license. The page's statement about commercial applications is a publisher statement, not legal advice; review obligations for a commercial model and dataset distribution.
- CPPED's repository explicitly requires a justified access request and describes CC BY-NC 4.0. The Creative Commons deed says NC material cannot be used commercially.
- SH17's repository describes 8,099 images, classes, Kaggle availability, Pexels image sourcing, and CC BY-NC-SA 4.0. Do not assume the dataset's repository license removes all Pexels or person-image restrictions.
- The Mendeley record and its related article disagree on CC BY vs CC BY-NC. The archive's exact license and contributor permissions must be resolved before use.

## 4. Class compatibility table

Compatibility here means label semantics, not string similarity. `Direct*` means the published class appears semantically aligned but still requires sample-level codebook and box-policy review. Do not infer a missing-PPE violation from absent positive-PPE detections or generic head/person boxes.

| Existing class | Ultralytics Construction-PPE | CPPED | Mendeley PPE | SH17 | SHWD / CHVG |
|---|---|---|---|---|---|
| Hardhat | `helmet` → Direct*; may cover helmet/head differently | `head` is ambiguous; color-coded categories need codebook | `Helmet` → Direct* | `Helmet` → Direct* | SHWD `hat` positive; CHVG colored helmet classes → Direct* |
| NO-Hardhat | `no_helmet` → Direct* after box-policy check | No explicit class; `head` is not equivalent | `NoHelmet` → Direct* | No explicit violation class | SHWD has normal head objects but class is not named as a violation; CHVG has head and helmet boxes only |
| Mask | No mask class | `mask` positive, but verify if face mask type matches construction requirement | No class | `Face-mask-medical` positive; not necessarily same mask policy | No direct class in these candidates |
| NO-Mask | No explicit class | No explicit class | No class | No explicit class; absence of mask boxes is not negative label | No direct class |
| Safety Vest | `vest` → Direct* | `vest` plus color categories; meaning/box conventions require codebook | `Vest` → Direct* | `Safety-vest` → Direct* | CHVG `vest` → Direct* |
| NO-Safety Vest | No explicit class | No explicit class | `NoVest` → Direct* if semantics match | No explicit class | No explicit class |
| Gloves | `gloves` → Direct* | `gloves` → Direct* | No class | `Gloves` → Direct* | No gloves class |
| NO-Gloves | `no_gloves` → Direct* if class truly marks missing gloves | `no gloves` → Direct* after codebook review | No class | No explicit class | No direct class |
| Person | `Person` → Direct*; inspect `none` separately | `person` → Direct* | No person class listed in article's four-class schema | `Person` → Direct* | SHWD `person`; CHVG `person body` → possible meaning/extent difference |

Ultralytics `none` is not mapped to any missing-PPE class. In CPPED, color labels such as `yellow`, `white`, `blue`, and `red` are not equivalent to Safety Vest without inspecting the dataset's annotation guide and examples. SH17's positive PPE labels permit evaluation of item appearance, not training explicit absence classes unless a verified person-level labeling protocol is developed separately.

## 5. Recommended expansion strategy

### Acquisition priorities

1. **Investigate Ultralytics Construction-PPE first** for explicit `no_gloves`, gloves, `no_helmet`, helmet, and Person examples. Before acquisition, obtain a copy of the archive's license/attribution notices and assess AGPL-3.0 implications for the intended commercial platform. It does not address NO-Mask or NO-Safety Vest.
2. **Request CPPED only for a non-commercial research track** or seek a separate written commercial grant. It is unusually relevant to glove absence, but access requires a justified request and the published NC term excludes commercial use. Do not treat `head` as NO-Hardhat.
3. **Resolve the Mendeley PPE license conflict** before considering it for NO-Hardhat/NO-Safety Vest. If rights are confirmed, inspect source composition and deduplicate because it combines images from public platforms.
4. Consider **SH17 only for positive item/person diversity or research** after accepting NC-SA and Pexels constraints. Its missing-class annotations are not explicit, so it will not directly improve violation labels without a separately designed and reviewed annotation effort.
5. Do not acquire the Kaggle/Roboflow duplicate as a second dataset. For NO-Mask and NO-Safety Vest, investigate whether the original source has a later, separately licensed version with direct annotations; otherwise plan a small, provenance-controlled collection from the target operating environment.

### Class priorities and NO-Gloves decision

- Prioritize targeted, visually clear examples for **Gloves** and **NO-Mask**, then **NO-Safety Vest** and **NO-Hardhat**, based on measured validation misses and user-provided held-out class recalls. Sample across camera distance, worker pose, PPE color/style, lighting, occlusion, and crowding. Include both compliant and non-compliant examples from the same source domains to avoid a source/background shortcut.
- Do not set arbitrary image targets. Establish a baseline by auditing unique workers/scenes and labeled instances per split, then acquire examples until each target has enough independent scenes and coverage across the key conditions. Monitor per-class AP/recall and FP counts on a validation set curated from separate sites/videos.
- **NO-Gloves is justified only if the product requirement is to detect glove violations explicitly.** Current model classes and Safety Agent do not support it, so adding the class is a later schema/application change, not a Phase 2 data-only remap. A glove-free worker inferred from no Gloves box is unsafe without person association, visibility rules, and complete positive-glove annotation. Decide the desired semantics first: explicit glove-absence boxes, person-level compliance labels, or separate person/PPE association logic.
- For NO-Mask, define the mask policy (e.g., face covering type, when it is required, and visibility rules) before annotation. A general medical-mask dataset is not a substitute for construction-specific missing-mask examples.

### Balancing, deduplication, and split safety

- Balance by **image/scene and condition**, not only by box count. Avoid oversampling near-duplicate frames; keep both compliant and violation examples from varied sites, workers, camera viewpoints, and times.
- Preserve source IDs, licenses, original class names, split, image path, and attribution for every sample. Maintain a class-mapping manifest and a written annotation codebook.
- Detect exact duplicates with cryptographic hashes and near-duplicates with perceptual hashes plus manual checks. Compare candidate images to all three existing splits, including test, before assigning any new data. A match to a held-out test image or same source video should not enter training.
- Keep the existing 82-image test split and its labels frozen as the historical benchmark. Make a new source-aware validation split for iteration; do not tune on the old test split. For any final comparison, evaluate the unchanged model and a candidate model on the same frozen test set only after all data and training decisions are locked. Because some source media may contribute frames across splits, perform a video/site/source-group leakage audit before relying on the current split as an independent test.
- Keep all candidate source datasets and generated artifacts outside tracked Git paths, and record hashes, license text, URLs, retrieval date, and class/split manifests.

## 6. Risks and limitations

- Public dataset counts and labels are publisher-reported; class frequency by split for candidate datasets was not independently measured because no archives were downloaded.
- License labels can describe a code repository rather than image rights. Pexels, source-platform, privacy/publicity, attribution, NC/SA, and model-distribution terms may impose additional constraints. Have legal review before any commercial training or redistribution.
- Candidate labels may use different box conventions: boxes around a PPE item, a head/person, or an absent-PPE region are not interchangeable. Positive-only labels are not negative examples.
- Public web images can duplicate the existing Roboflow set or each other, include frames from the same source video, and vary in annotation completeness. Expansion without source grouping and deduplication could inflate apparent validation performance.
- Class counts alone do not prove why recall is weak. No-mask's validation support (74 instances) is higher than Gloves (25), yet recall is lower; visual difficulty, label policy, domain shift, semantic confusion, and model limitations remain possible contributors.
- No direct, verified, publicly available, commercially cleared dataset with explicit construction-site NO-Mask labels was identified in this research pass.

## 7. Proposed next steps

1. Confirm intended commercial/non-commercial use and have the Ultralytics AGPL and Mendeley license discrepancy reviewed before dataset acquisition.
2. Obtain and review the candidate annotation guide and representative images before approving any source; verify `no_gloves`, `no_helmet`, and `no_vest` semantics rather than relying on class names alone.
3. Complete human review of the Phase 1B annotation candidates and the class-level confusion/error examples. Resolve source-video/site grouping and audit split leakage.
4. Define a stable annotation codebook for visible PPE, explicit violations, person-to-PPE association, and “not observable / unknown.” Do not convert missing boxes into violation labels.
5. Create a new provenance manifest and deduplicated, source-grouped training/validation extension. Leave the existing test set untouched.
6. Only after dataset rights and labels are cleared, run a controlled next-phase experiment with the current checkpoint as the baseline, fixed training configuration, and separate validation evaluation; retraining is outside this plan.

## Sources

- Ultralytics, [Construction-PPE dataset documentation](https://docs.ultralytics.com/datasets/detect/construction-ppe/) and its [dataset YAML](https://github.com/ultralytics/ultralytics/blob/main/ultralytics/cfg/datasets/construction-ppe.yaml).
- QHCV, [CPPED repository and access/license notes](https://github.com/QHCV/CPPED); Creative Commons, [CC BY-NC 4.0 deed](https://creativecommons.org/licenses/by-nc/4.0/).
- Elsevier Mendeley Data, [Dataset of PPE, version 6](https://data.mendeley.com/datasets/zkzghjvpn2/6); related article, [Dataset of personal protective equipment](https://pmc.ncbi.nlm.nih.gov/articles/PMC12398887/).
- Ahmad and Rahimi, [SH17 repository](https://github.com/ahmadmughees/SH17dataset), [paper](https://arxiv.org/abs/2407.04590), and [published article](https://doi.org/10.1016/j.jnlssr.2024.09.002).
- Roboflow Universe, [Construction Site Safety project](https://universe.roboflow.com/ppe-detection-gwtcs/construction-site-safety-1vvac); Kaggle, [PPE notebook input description](https://www.kaggle.com/code/daffamuhamadazhar/yolov8-ppe-detection/input).
- njvisionpower, [Safety Helmet Wearing Dataset repository](https://github.com/njvisionpower/Safety-Helmet-Wearing-Dataset).
- Ferdous and Ahsan, [CHVG dataset paper record](https://pubmed.ncbi.nlm.nih.gov/35875643/); [NLM catalog entry for Figshare record and CC BY 4.0 metadata](https://datasetcatalog.nlm.nih.gov/dataset?q=0002780681).
- Researchers, [CPPE-5 medical PPE dataset paper](https://arxiv.org/abs/2112.09569).
