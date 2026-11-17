# Research and baseline decision (provisional)

## Decision

Use MobileNetV2 as the first transfer-learning baseline and EfficientNet-B0 as the second candidate. Evaluate both on exactly the same frozen, leakage-safe dataset split. Treat these as starting points, not final model selection. The local dataset has not yet been reconciled with its multiple existing exports and labels.

## Rationale

- MobileNetV2 offers a relatively small inference footprint appropriate for a single-machine MVP; P1 includes it in a livestock skin-image comparison, although P1 is not a pig study and is only partially verified.
- EfficientNet-B0 gives a second, distinct architecture for comparison. It is materially smaller than the EfficientNet-B7 reported by P1. P3 provides human dermatoscopy precedent but contains a B0/B1 naming inconsistency and cannot establish pig-image performance.
- P2 suggests an ROI-first pattern for a localized pig feature. It evaluated slaughter carcass tail images, so this project still needs a controlled ROI/demo or a validated pig detector before whole-pen claims.
- P5 supports designing an uncertain/review route; it does not establish that a raw Softmax score is calibrated confidence.

## Not yet concluded

- Actual canonical class set, single-label versus multi-label target, and trusted label source.
- Which copy/export is authoritative, whether offline augmentations or duplicate stems remain, and whether the existing audit CSV corresponds to current files.
- Performance, latency, and false-negative rate on this project’s data.
- Whether the dataset's close-up photos can support real pen video or multi-pig ROI inference.
- Exact baseline transforms, weights, optimizer, and training schedule; settle these after dataset review and resource plan.

## Evidence boundary

P1 is partially verified; P2, P3, and P5 full text were accessible; P4 was abstract-only. See [`literature_matrix.md`](literature_matrix.md) and the per-paper records. No external benchmark is treated as a local result.
