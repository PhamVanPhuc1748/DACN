# Literature matrix

| ID | Evidence status | Domain / input | What the paper supports | Relevance class | Limit for this project |
|---|---|---|---|---|---|
| P1 Girmaw 2025 | Partially verified; publisher abstract/selected snippets | Cattle, sheep, goats; still images | Transfer-learning comparison including MobileNetV2, EfficientNetB7, DenseNet201 | `related_work`, `architecture_baseline` | Not pigs; PDF paywalled; detailed training and split fields unavailable |
| P2 Brünger et al. 2019 | Verified; open full text | Slaughter pig carcass tails; still images | Explicit part detection/crop before classification; image quality matters | `related_work`, `architecture_baseline`, `deployment_inspiration` | Tail on carcasses is not skin disease on live pigs or pen video |
| P3 Tajerian et al. 2023 | Verified; open full text | Human dermatoscopy; HAM10000 | EfficientNet-style transfer learning and class-wise evaluation | `related_work`, `architecture_baseline` | Article has B0/B1 naming inconsistency; wrong species and imaging modality |
| P4 Yao et al. 2022 | Abstract only | Human dermatoscopy; small/imbalanced datasets | Possible future regularization/imbalance ideas if local error analysis warrants | `related_work`; optional `method_reimplementation` | Full text unavailable; do not infer settings from abstract |
| P5 Singh et al. 2022 | Verified; open full text | Human skin-lesion images; ISIC 2018 | Uncertainty/review and explanation as design considerations | `related_work`, `deployment_inspiration` | Full Bayesian segmentation/classification system exceeds current MVP and does not validate pig predictions |

## Cross-paper decision

Start local experiments with **MobileNetV2** and **EfficientNet-B0**, using the same reviewed labels, leakage-safe split, seed, and evaluation protocol. MobileNetV2 is the resource-conscious first baseline and appears in P1's non-pig transfer-learning study; EfficientNet-B0 is a practical second comparison but is **not** P1's EfficientNetB7 and P3 itself has B0/B1 wording inconsistency. These are project engineering choices, not a claim that either performs better on pig data.

No paper score is used to rank the local models. Do not begin training until labels, splits, and representative image framing have been audited.
