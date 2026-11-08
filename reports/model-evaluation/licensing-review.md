# Ultralytics Construction-PPE licensing review

Review date: 2026-11-02. This is a provenance and issue-spotting review, not legal advice or a determination that any particular use is permitted.

## Dataset license declaration

The official [Construction-PPE dataset documentation](https://docs.ultralytics.com/datasets/detect/construction-ppe/) declares **AGPL-3.0** and requests attribution to the dataset authors. The downloaded archive includes a GNU AGPL v3 license text. The documentation identifies the dataset as authored by Mrunmayee Dalvi, Niyati Singh, Sahil Bhingarde, and Ketaki Chalke, published by Ultralytics, version 1.0.0. The archive has no per-image source manifest.

This records the publisher's dataset-level declaration. It does not establish the copyright owner or license for every underlying photograph, establish that the publisher had authority to license every image for every downstream use, or resolve whether redistribution of images, labels, derivatives, or model weights is allowed. Those rights remain **unverified** and require written publisher/source clarification and legal review before integration or distribution.

## Attribution and redistribution

The documentation asks users to cite the dataset and its authors. Retaining the archive's license and attribution notices is prudent provenance practice. No per-image attribution schedule, photo credits, releases, or source URLs were found in the extracted archive/provenance files. The available materials do not let this review verify photo-level attribution obligations or permission to redistribute the images. Do not assume that the AGPL notice alone resolves those questions.

## Separate licensing layers

| Layer | Evidence reviewed | Status / open question |
|---|---|---|
| Dataset declaration | Official dataset documentation and archive license text | Dataset declared AGPL-3.0; attribution requested. Scope against underlying photos is unresolved. |
| Underlying photos | Archive contents and provenance record | No per-image source/rights manifest found. Copyright, releases, and redistribution permission are unresolved. |
| Ultralytics software | [Ultralytics license page](https://www.ultralytics.com/license) and [software repository license](https://github.com/ultralytics/ultralytics/blob/main/LICENSE) | Separate from dataset licensing. Ultralytics describes AGPL-3.0 as appropriate when the entire project is open-sourced under AGPL, and lists Enterprise licensing for commercial, proprietary, and SaaS cases. Applicability to this project's intended deployment needs counsel/vendor confirmation. |
| Existing checkpoint | `weights/best.pt` and prior evaluation artifacts | Checkpoint-specific training-data provenance and license were not reviewed in this phase. Do not infer its licensing from this supplementary dataset. |
| Application source | Workspace root | No root `LICENSE` file was found in the workspace root during this review. Confirm the intended application license separately. |

The AGPL-3.0 text is available from the [GNU project](https://www.gnu.org/licenses/agpl-3.0.html). A software license notice, dataset declaration, and any permission for underlying photographs are distinct questions. This report does not conclude that AGPL obligations do or do not attach to a trained checkpoint or a combined application.

## Decision needed before integration

1. Ask Ultralytics for the source/provenance and rights basis for the photos, including whether the image files and derived labels may be used for training and whether the photos or derivatives may be redistributed.
2. Have counsel review the dataset declaration, intended training/use/distribution, the project's own source license, and the Ultralytics software license requirements for any planned commercial, hosted, or proprietary use.
3. Record written answers, attribution text, and any conditions in a provenance manifest before approving a merge.

## Sources

- [Ultralytics Construction-PPE documentation](https://docs.ultralytics.com/datasets/detect/construction-ppe/)
- [Official dataset YAML and download reference](https://github.com/ultralytics/ultralytics/blob/main/ultralytics/cfg/datasets/construction-ppe.yaml)
- [Ultralytics software licensing page](https://www.ultralytics.com/license)
- [Ultralytics software repository license](https://github.com/ultralytics/ultralytics/blob/main/LICENSE)
- [GNU AGPL v3 text](https://www.gnu.org/licenses/agpl-3.0.html)
- Local provenance: [ultralytics-dataset-provenance.json](./ultralytics-dataset-provenance.json)
