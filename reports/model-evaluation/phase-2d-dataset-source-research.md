# Phase 2D — Dataset Source Research

**Scope:** research and selection only. No dataset was downloaded in this phase. Candidate counts, class descriptions, formats, and licenses below are attributed to the named publisher/repository or paper. “Unknown” means not verified from the accessible primary source. Dataset license declarations do not, by themselves, establish rights in underlying photos or permission to redistribute trained weights.

## Selection summary

| Candidate | Most relevant potential use | Current decision |
|---|---|---|
| Dataset of PPE (Mendeley Data, v6) | Explicit `NoHelmet` and `NoVest` | Best concrete follow-up for `NO-Hardhat`/`NO-Safety Vest`, conditional on source-rights and label-policy review. It has no gloves or mask classes. |
| CPPED (authors’ project) | Explicit `no gloves` with construction-worker violation framing | Strongest direct `NO-Gloves` research lead. Access requires a justified request; CC BY-NC 4.0 limits commercial use. Must inspect source images and codebook before any use. |
| TechScience generic PPE inspection dataset (paper) | Reports `no_gloves`, `no_helmet`, and `no_safety_vest` | Promising lead, not yet an acquirable/rights-cleared dataset. Need author-provided release, image provenance, license, and annotation definitions. |
| SH17 | Positive gloves, helmet, face-mask, vest, person | Could supplement positive PPE only for noncommercial research if licensing and domain suitability are approved. No explicit missing-PPE classes. |
| SHEL5K | Helmet / head and person-without-helmet labels | Possible hardhat research source, but license is noncommercial and split/source lineage needs review. Not useful for gloves, masks, or vests. |
| SHWD | Helmet and normal-head detection | Research-only lead; “normal head” is not automatically a safety violation. Image rights remain unresolved. |
| SFCHD | Chemical-plant helmet/clothing/person imagery | Domain-adjacent positive examples only; no absence classes and no dataset license verified. Defer pending permission and source review. |
| Mendeley 5-class construction monitoring dataset | Potential construction context | Public record does not expose enough class, count, format, or split detail to establish suitability. Do not select until publisher metadata/files are inspectable. |
| Springer 2025 construction PPE dataset paper | Reports several explicit violation classes | Unverified lead only; no publisher-authorized data location, license, or reproducible class codebook verified. |

## Candidate details

### 1. Dataset of PPE — Mendeley Data, version 6

- **Publisher/source:** Mendeley Data record and its associated paper: [dataset record](https://data.mendeley.com/datasets/zkzghjvpn2/6), [open article](https://pmc.ncbi.nlm.nih.gov/articles/PMC12398887/).
- **Verified facts:** The record reports 2,286 images, YOLO format, four classes (`Helmet`, `NoHelmet`, `NoVest`, `Vest`), and 1,829 train / 457 validation images, with no separate test split. Its dataset record declares CC BY 4.0. The paper reports input images standardized to 640×640 and class image frequencies of Helmet 1,390, NoHelmet 622, NoVest 661, Vest 809; its train/validation annotation-row counts are Helmet 1,970/451, NoHelmet 960/214, NoVest 836/222, Vest 1,096/289.
- **Construction relevance:** Relevant PPE categories and described PPE inspection use; source images are aggregated from GDUT-HWD, Roboflow HelmetVest, Kaggle Safety Helmet and Reflective Jacket, and 200 author-taken images. Not every image is proven to depict construction work or a task requiring each item.
- **Violation semantics:** `NoHelmet` and `NoVest` are explicit names, but task/site requirement, visibility/occlusion policy, and whether boxes denote people, body regions, or missing item locations must be verified against original annotations and project policy.
- **Rights/access:** Mendeley says CC BY 4.0 for the dataset record. The article also identifies source datasets with different licenses (reported as Apache-2.0 for two sources and CC BY 4.0 for one) and includes author-taken photos; the paper text also has an article-level CC BY-NC notice. Do not assume the top-level declaration clears every source image or that the article license is the dataset license. Verify source licenses/permissions and redistribution terms with the dataset authors before use, especially commercial deployment.
- **Limitations/overlap:** The authors state duplicates/low-quality images were removed, but a source-level manifest and split-group procedure were not verified. Compare against both local datasets before acquisition; no guarantee against overlap.
- **Assessment:** Most useful verified candidate for `NO-Hardhat` and `NO-Safety Vest`, conditional on license/provenance and annotation-policy review. Not a source for gloves or mask.

### 2. CPPED — Construction Personal Protective Equipment Dataset

- **Publisher/source:** Authors’ project [QHCV/CPPED](https://github.com/QHCV/CPPED); associated ASCE article DOI [10.1061/JCEMD4.COENG-15310](https://ascelibrary.com/doi/10.1061/JCEMD4.COENG-15310).
- **Verified facts:** Repository README reports 2,612 images and 13 categories, YOLO normalized box annotations, and a dataset based on construction-worker PPE violation detection. Its per-class annotation totals include `no gloves` 2,017, `gloves` 985, `person` 5,936, `head` 957, `vest` 2,587, and `mask` 529; remaining categories are clothing colors and shoes/glasses categories. It does not list explicit `no helmet`, `no mask`, or `no vest` classes. Authors ask users to request the data via Google Drive with a justified purpose. The repository declares CC BY-NC 4.0.
- **Construction relevance:** High by stated project purpose; still inspect images for task context and visible-hand evidence under SafeSite policy.
- **Violation semantics:** `no gloves` is explicitly annotated. The repository’s class labels do not provide enough policy detail to establish all examples meet the SafeSite rule. Do not infer `NO-Mask` from `mask` or `NO-Hardhat` from `head`.
- **Rights/access:** Request-only access; declared CC BY-NC 4.0 is noncommercial and share-alike. The associated paper describes images from prior research and internet sources. Obtain the authors’ source-level rights/provenance and written permission for intended portfolio/commercial use; access approval is not itself a rights grant.
- **Limitations/overlap:** Split/group details and source manifest should be requested. Potential overlap with web-sourced imagery and other public PPE collections requires exact and perceptual duplicate checking.
- **Assessment:** Best direct `NO-Gloves` lead, but not currently cleared for commercial use and not ready for integration.

### 3. Generic PPE inspection dataset described by TechScience (2025)

- **Publisher/source:** Primary paper PDF: [TechScience paper](https://file.techscience.com/files/cmc/2025/online/CMC0905/TSP_CMC_67547/TSP_CMC_67547.pdf); author-affiliation record: [university publication record](https://iau.sa.elsevierpure.com/en/publications/deep-learning-based-automated-inspection-of-generic-personal-prot/).
- **Verified facts from paper:** Reports 20,001 pre-augmentation images assembled from phone captures, CCTV frames, and referenced external sources; nine classes include `person`, positive gloves/helmet/safety vest/safety shoes and `no_gloves`, `no_helmet`, `no_safety_vest`, `no_safety_shoes`. Reported pre-augmentation splits: 14,001 train / 4,000 test / 2,000 validation; augmentation expands the reported corpus to 50,096. The paper references a Roboflow source `tml_safety_v3` among its data sources.
- **Construction relevance:** PPE inspection and CCTV may be industrial/warehouse context; the accessible paper evidence does not establish that every image is a construction site or that the task requires each PPE item.
- **Violation semantics:** Explicit violation class names are reported. Exact annotation definitions, class-to-image provenance, source-level splits, and mapping details require access to the actual labels/codebook.
- **Rights/access:** No separately downloadable author dataset release or dataset-specific license/redistribution permission was verified. Do not rely on the paper or the referenced Roboflow source as a blanket license.
- **Limitations/overlap:** Composite-source leakage and source overlap risk are material. Need source manifest, group-level split method, class counts, and permission for each source. The paper’s reported total and augmented total should be kept distinct.
- **Assessment:** High-priority research contact for multiple violation classes; not selectable for training until files, provenance, license, and annotation policy are supplied.

### 4. SH17 industrial PPE dataset

- **Publisher/source:** Authors’ [SH17 repository](https://github.com/ahmadmughees/SH17dataset) and paper [arXiv:2407.04590](https://arxiv.org/abs/2407.04590) (DOI 10.1016/j.jnlssr.2024.09.002).
- **Verified facts:** Paper reports 8,099 annotated images, 75,994 object instances, and 17 classes: `person`, `ear`, `ear-mufs`, `face`, `face-guard`, `face-mask`, `foot`, `tool`, `glasses`, `gloves`, `helmet`, `hands`, `head`, `medical-suit`, `shoes`, `safety-suit`, `safety-vest`. Repository provides YOLO-style configuration; source described as Pexels. Repository declares CC BY-NC-SA 4.0. The checked YAML is not a full split manifest for the complete stated corpus; obtain exact split inventory before use.
- **Construction relevance:** Industrial/manufacturing safety, not exclusively construction.
- **Violation semantics:** Only positive PPE/item and body-part detections; no explicit absent-PPE classes. `head` or lack of a positive PPE box must not become a violation.
- **Rights/access:** CC BY-NC-SA 4.0 is noncommercial and share-alike. Verify the rights and terms for the underlying Pexels images and compliance with Pexels’ terms; not a default commercial source.
- **Assessment:** Conditional candidate for positive PPE pretraining/review in noncommercial research; not a violation dataset.

### 5. SHEL5K — Safety Helmet Wearing Dataset

- **Publisher/source:** Authors’ [SHEL5K repository](https://github.com/MoyoG/SHEL5K) and [Mendeley record](https://data.mendeley.com/datasets/9rcv8mm682/1).
- **Verified facts:** Repository describes 5,000 images (4,000 train and 1,000 test) with helmet/head/person-related labels, including person-with-helmet and person-without-helmet. The Mendeley record declares CC BY-NC 3.0. Confirm exact annotation class IDs/format and corresponding image/label pairs from publisher files before considering any use.
- **Construction relevance:** Helmet detection with construction/manufacturing backgrounds, but not a broad construction PPE dataset.
- **Violation semantics:** `person without helmet` is a candidate explicit class, but its box definition and policy assumptions need checking; head-only labels are not violations.
- **Rights/access:** Noncommercial license declaration; verify underlying-source rights and share/redistribution scope. No commercial suitability assumed.
- **Overlap/assessment:** Source ancestry includes an existing public Kaggle safety-helmet collection, increasing duplicate risk with public datasets. Candidate only for `NO-Hardhat`/helmet research after provenance and overlap review.

### 6. Safety Helmet Wearing Dataset (SHWD)

- **Publisher/source:** Authors’ [njvisionpower repository](https://github.com/njvisionpower/Safety-Helmet-Wearing-Dataset).
- **Verified facts:** Repository reports 7,581 images, 9,044 helmet-wearing objects and 111,514 “normal head” objects, in Pascal VOC format, with download links hosted on Google/Baidu. Repository contains an MIT license for the code/repository; a dataset-image license was not established.
- **Construction relevance:** Helmet detection images, but source imagery/context and task requirements need review.
- **Violation semantics:** “Normal head” or no helmet annotation is not by itself an explicit construction PPE violation. Do not turn absence/normal-head into `NO-Hardhat` without worker, visibility, and applicable requirement evidence.
- **Rights/access/assessment:** Image rights, redistribution, and commercial permissions unresolved. Defer; not a usable violation source without written rights and contextual review.

### 7. SFCHD — Safety Facilities in Chemical Plants

- **Publisher/source:** Authors’ [SFCHD-SCALE repository](https://github.com/lijfrank/SFCHD-SCALE) and paper [arXiv:2306.02098](https://arxiv.org/abs/2306.02098).
- **Verified facts:** Repository reports 12,373 images and 50,558 annotations (its category totals appear to sum to one more); classes include Person, Safety Helmet, Safety Clothing, Other Clothing, Head, Blurred Clothing, and Blurred Head. Chemical-plant imagery is the stated context. Download links are external; the dataset’s exact annotation format and a dataset license were not verified.
- **Construction relevance:** Industrial process setting, not construction.
- **Violation semantics:** No explicit absence classes. `Head` and `Other Clothing` are not violations; only possible positive PPE or image-difficulty examples after label review.
- **Rights/access/assessment:** Dataset-photo rights and commercial use unknown. Defer until license and format are confirmed; low priority for SafeSite construction-specific violations.

### 8. Construction Safety Monitoring dataset — Mendeley Data

- **Publisher/source:** [Mendeley Data record](https://data.mendeley.com/datasets/8vf7z6v5sb/1).
- **Verified facts:** Record identifies a five-class construction safety monitoring dataset and declares CC BY 4.0. Public record reviewed here does not expose verified class names, image count, split structure, or annotation format.
- **Construction relevance:** Claimed by title/description, not verified at image level.
- **Violation semantics/access/assessment:** Unknown. It cannot be mapped to any class until the files/codebook and license provenance are inspected. Hold as unresolved, not selected.

### 9. Construction PPE violations dataset in a 2025 Springer proceedings paper

- **Publisher/source:** DOI [10.1007/978-3-032-00267-9_18](https://doi.org/10.1007/978-3-032-00267-9_18).
- **Unverified lead:** A secondary catalog claims 4,000+ images and labels including `no hardhat`, `no vest`, `no gloves`, and `no boots`. The original publisher/author page did not provide a verified download, exact class counts, format, or dataset license in the material reviewed for this plan.
- **Assessment:** Do not rely on the secondary statistics. Contact the authors/publisher for authoritative dataset access, codebook, source manifest, and rights. Until then this is a lead only.

## Sources not selected

- **Current original Roboflow/Bartu dataset:** It is the project’s existing 717-image v1 set (25 classes, declared CC BY 4.0), not new independent data. It remains the source of current `NO-Mask` and `NO-Safety Vest` labels; it cannot resolve weak recall by itself. [Project page](https://universe.roboflow.com/bartu/construction-site-safety-qrecb).
- **Ultralytics Construction-PPE:** Already acquired and inspected locally (1,416 images; AGPL-3.0 declared by Ultralytics; classes include `no_gloves` and `no_helmet`, but no `no_mask` or `no_vest`). It is not an additional source in this phase. Image rights, `none` semantics, duplicate groups, and `no_gloves` context remain unresolved. [Official documentation](https://docs.ultralytics.com/datasets/detect/construction-ppe/).
- **CPPE-5:** Medical PPE rather than construction; its authors report 1,029 images, 4,698 boxes, and positive-only classes for coveralls, face shields, gloves, masks, and goggles. It is not suitable for construction violation labels. [Primary paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC10018606/).
- **Roboflow Universe user uploads without source provenance:** Search results may expose relevant class names, but an aggregator/export alone does not verify original image rights, construction context, annotation semantics, or split lineage. Do not select without source publisher and license verification.

## Missing-source needs by class

| Target | What remains needed |
|---|---|
| `NO-Gloves` | Construction-specific, task-relevant examples with visible hands and a documented glove requirement; CPPED/TechScience access and rights review; human image-by-image policy approval. |
| `NO-Mask` | New construction/task-specific explicit labels or verified source with explicit `no_mask`; no current supplementary direct equivalent. Do not derive from missing `Mask`. |
| `NO-Safety Vest` | Mendeley Dataset of PPE is the strongest explicit lead; confirm construction context, box policy, source rights, and leakage. Do not derive from missing `Safety Vest`. |
| `NO-Hardhat` | Mendeley Dataset of PPE, CPPED/SHEL5K candidate labels after codebook review, with applicable site requirement and visible head evidence. Do not infer from `head`/`normal head`. |
| Positive `Gloves` / `Hardhat` / `Safety Vest` | Review rights-cleared source candidates and retain original data; avoid mixing incompatible box conventions. |
| Positive `Mask` | No verified construction-specific positive-mask source selected; distinguish face masks from respirators only if project policy and labels support it. |
| `Person` | Prefer in-domain worker imagery and a consistent person-box convention; generic industrial people are only conditional positives. |

## Rights and provenance gate

Before acquisition or integration, obtain for each source: immutable version/URL and download method; dataset and image-level license evidence; attribution text; source image/provider lineage; commercial and redistribution permissions; author permission if terms are unclear; codebook and annotation examples; original split/group manifest; hash manifest. The Ultralytics dataset’s AGPL declaration is separate from Ultralytics software licensing, application licensing, and underlying photographs. CPPED and SH17/SHEL5K have noncommercial declarations, so they are not assumed usable in a commercial portfolio. Mendeley CC BY declarations require attribution and do not remove the need to verify contributors’ rights in embedded images.

## Research confidence

The counts and classes above are verified only to the degree stated by the cited publisher/repository/paper. Dataset-level license pages are not legal advice and do not establish that every embedded photograph can be redistributed or used in model weights. No source is currently approved for integration. The next selection decision requires human review of data semantics and license/provenance evidence, with legal clarification where image rights are not explicit.
