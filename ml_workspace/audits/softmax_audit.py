"""Reproduce the single-image, calibration, or shared-test audit without training."""
import argparse
import csv
import hashlib
import json
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import torch
import torchvision
from PIL import Image

root = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(root / "PigSkinTech"), str(root / "ml_workspace")]
from services import inference, project_data
from train_model import validate_manifest

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("mode", choices=("single", "validation", "common"))
parser.add_argument("--output", type=Path, required=True, help="Directory for audit artifacts")
parser.add_argument("--image", type=Path, help="Image for the single-image audit or optional dataset lookup")
parser.add_argument("--database", type=Path, help="Optional SQLite history for read-only verification of the latest pair")
parser.add_argument("--legacy-root", type=Path, help="Image root for the legacy 2017 manifest")
parser.add_argument("--curated-root", type=Path, help="Image root for the curated 2016 manifest")
parser.add_argument("--curated-manifest", type=Path, help="Override the manifest.csv under --curated-root")
parser.add_argument("--rf-root", type=Path, help="Image root for the RF conservative manifest")
args = parser.parse_args()
if args.mode != "single" and not all((args.legacy_root, args.curated_root, args.rf_root)):
    parser.error("validation and common require --legacy-root, --curated-root and --rf-root")
if args.mode == "single" and not (args.image or args.database):
    parser.error("single requires --image or --database")
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=True)
run_list = project_data.available_model_runs()
assert len(run_list) == 8
torch.set_num_threads(4)
classes = run_list[0]["config"]["classes"]
lookup = {label: i for i, label in enumerate(classes)}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write_json(name, data):
    (out / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def write_csv(name, records):
    with (out / name).open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)

cases = []
image_path = args.image
if args.database:
    from contextlib import closing

    with closing(sqlite3.connect(args.database.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        cases = [dict(row) for row in db.execute("SELECT * FROM inspections ORDER BY id DESC LIMIT 2")]
    if len(cases) != 2:
        parser.error("the SQLite history must have at least two records")
    paths = [Path(row["image_path"]) for row in cases if row["image_path"]]
    if len(paths) != 2 or not all(path.is_file() for path in paths):
        parser.error("the latest two inspections must reference existing local images")
    image_path = image_path or paths[0]
    if any(sha(path) != sha(image_path) for path in paths):
        parser.error("the selected image and the two latest inspections must have the same SHA-256")
digest = sha(image_path) if image_path else None
suffix = {r["name"]: r["config"]["manifest_sha256"] for r in run_list}

def entry(run, sample_path):
    inference._predict_inprocess(sample_path, run)
    ckpt = run["checkpoint"].resolve()
    paths = [ckpt]
    if ckpt.name == "ensemble.json":
        paths = [(ckpt.parent / p).resolve() for p in json.loads(ckpt.read_text())["members"]]
    key = repr([(str(path), path.stat().st_mtime_ns) for path in [ckpt, *paths]])
    return inference._MODEL_RUNTIME_CACHE[key], paths

if args.mode == "single":
    rows = []
    audit = {"versions": [torch.__version__, torchvision.__version__], "models": {}}
    if cases:
        from services.outbreak_service import summarize_surveillance

        audit["verified_identical_inspection_images"] = True
        audit["surveillance_summary"] = [
            {"inspections": f.inspections, "animals": f.animals, "repeated_images": f.repeated_images,
             "suspected": len(f.suspected), "expert_confirmed": len(f.expert_confirmed)}
            for f in summarize_surveillance(cases)
        ]
    for run in run_list:
        name = run["name"]
        runtime, checkpoints = entry(run, image_path)
        config = run["config"]
        assert config["classes"] == classes
        assert config.get("class_to_index", lookup) == lookup
        meta = []
        transforms = torchvision.transforms
        eval_transform = transforms.Compose([
            transforms.Resize((config["image_size"], config["image_size"])), transforms.ToTensor(),
            transforms.Normalize(**config["normalization"]),
        ])
        with Image.open(image_path) as source:
            rgb = source.convert("RGB")
            tensor = runtime["transform"](rgb)
            assert torch.equal(tensor, eval_transform(rgb))
        with torch.inference_mode():
            logits = [model(tensor[None].to(runtime["device"]))[0].cpu() for model in runtime["members"]]
            reference = torch.stack([l.softmax(0) for l in logits]).mean(0)
        for checkpoint_path in checkpoints:
            checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
            assert checkpoint["classes"] == classes
            assert checkpoint.get("class_to_index", lookup) == lookup
            meta.append({"file": checkpoint_path.parent.name + "/" + checkpoint_path.name,
                         "sha256": sha(checkpoint_path), "has_class_to_index": "class_to_index" in checkpoint})
        result = inference._predict_inprocess(image_path, run)
        timings, elapsed = [], []
        for _ in range(21):
            begin = time.perf_counter()
            result = inference._predict_inprocess(image_path, run)
            elapsed.append((time.perf_counter() - begin) * 1000)
            timings.append(result["inference_ms"])
        scores = {x["label"]: x["confidence"] for x in result["all_scores"]}
        actual = torch.tensor([scores[k] for k in classes])
        maximum_error = (actual - reference).abs().max().item()
        assert maximum_error < 1e-6 and abs(actual.sum().item() - 1) < 1e-6
        rows.append(dict(model=name, **scores))
        audit["models"][name] = {"label": run["model_label"], "top3": result["top3"],
            "median_app_ms": float(np.median(timings)), "p95_app_ms": float(np.percentile(timings, 95)),
            "median_classifier_wall_ms": float(np.median(elapsed)), "p95_classifier_wall_ms": float(np.percentile(elapsed, 95)),
            "max_abs_reference_difference": maximum_error, "sum": sum(scores.values()),
            "swinepox_if_second_softmax": float(actual.softmax(0)[-1]), "checkpoints": meta,
            "training": {k: config.get(k) for k in ("optimizer", "label_smoothing", "image_size", "best_epoch", "augmentation")}}
    by_name = {r["model"]: r for r in rows}
    a = by_name["rf_v1_efficientnet_b0_E03_ls01"]
    b = by_name["rf_v1_efficientnet_b0_E06_ls01_adamw"]
    ensemble = by_name["rf_v1_E07-A"]
    audit["ensemble_max_abs_50_50_error"] = max(abs(ensemble[k] - (a[k] + b[k]) / 2) for k in classes)
    write_json("single-image-evidence.json", audit)
    write_csv("single-image-probabilities.csv", [{"model": r["model"], **{k: r[k] for k in classes}} for r in rows])
    sys.exit(0)

rf_manifest = root / "ml_workspace/manifests/rf_v1_conservative/manifest_draft.csv"
dataset_specs = [
    ("legacy_2017", root / "ml_workspace/manifests/pig_skin_single_label_v4/manifest.csv", args.legacy_root),
    ("curated_2016", args.curated_manifest or args.curated_root / "manifest.csv", args.curated_root),
    ("rf_v1", rf_manifest, args.rf_root),
]
datasets = {}
provenance = {}
for tag, manifest, base in dataset_specs:
    manifest_hash = sha(manifest)
    assert manifest_hash in suffix.values()
    rows, summary = validate_manifest(manifest, base, classes, "single")
    datasets[manifest_hash] = rows
    expected = next((run["config"]["split_sha256"] for run in run_list
                     if suffix[run["name"]] == manifest_hash and "split_sha256" in run["config"]), None)
    if expected is not None:
        assert expected == summary["split_sha256"]
    provenance[tag] = {"manifest_sha256": manifest_hash, "summary": summary,
        "all_split_fingerprints_match_training_config": expected is not None}
    if digest is not None:
        provenance[tag]["exact_query_matches"] = dict(Counter(r["split"] for r in rows if r["sha256"] == digest))
    print(tag, summary["split_counts"], flush=True)

def batch_scores(runtime, rows):
    values = []
    with torch.inference_mode():
        for start in range(0, len(rows), 32):
            tensors = []
            for r in rows[start:start + 32]:
                with Image.open(r["path"]) as source:
                    tensors.append(runtime["transform"](source.convert("RGB")))
            batch = torch.stack(tensors).to(runtime["device"])
            probs = torch.stack([model(batch).softmax(dim=1) for model in runtime["members"]]).mean(0)
            values.append(probs.cpu().numpy())
    return np.concatenate(values)

def metrics(probabilities, rows, model, split):
    y = np.array([lookup[r["labels"][0]] for r in rows])
    p = probabilities.astype(np.float64)
    actual = p.argmax(1) == y
    confidence = p.max(1)
    one_hot = np.eye(len(classes))[y]
    bins = []
    for index in range(15):
        mask = np.minimum((confidence * 15).astype(int), 14) == index
        bins.append(dict(model=model, split=split, bin=index + 1, lower=index / 15,
                         upper=(index + 1) / 15, n=int(mask.sum()),
                         mean_confidence=float(confidence[mask].mean()) if mask.any() else None,
                         accuracy=float(actual[mask].mean()) if mask.any() else None))
    ece = sum(b["n"] * abs(b["accuracy"] - b["mean_confidence"]) for b in bins if b["n"]) / len(y)
    pred = p.argmax(1)
    f1 = [2 * np.count_nonzero((y == j) & (pred == j)) /
          max(1, np.count_nonzero(y == j) + np.count_nonzero(pred == j))
          for j in sorted(set(y))]
    result = dict(model=model, split=split, n=len(y), accuracy=float(actual.mean()), macro_f1_present_classes=float(np.mean(f1)),
                  mean_confidence=float(confidence.mean()), ece=float(ece), brier=float(((p - one_hot) ** 2).sum(1).mean()),
                  nll=float(-np.log(np.maximum(p[np.arange(len(y)), y], 1e-15)).mean()))
    return result, bins

def evaluate_all(split, cohort=None):
    scores, bins = [], []
    for run in run_list:
        name = run["name"]
        rows = cohort if cohort is not None else [r for r in datasets[suffix[name]] if r["split"] == "val"]
        runtime, _ = entry(run, rows[0]["path"])
        p = batch_scores(runtime, rows)
        result, model_bins = metrics(p, rows, name, split)
        print(result, flush=True)
        scores.append(result)
        bins.extend(model_bins)
    write_csv(split + "-metrics.csv", scores)
    write_csv(split + "-reliability-bins.csv", bins)

if args.mode == "validation":
    write_json("dataset-provenance.json", provenance)
    evaluate_all("validation")
    sys.exit(0)

# Match the same original export identifier across manifests, and require
# conservative visual corroboration and unanimous test labels.
basis = np.cos(np.pi * np.outer(np.arange(8), (np.arange(32) + .5) / 32))
def visual_hash(path):
    with Image.open(path) as im:
        reduced = np.asarray(im.convert("L").resize((32, 32), Image.Resampling.LANCZOS), dtype=float)
    versions = (reduced, reduced[:, ::-1])
    bits = [(basis @ version @ basis.T).ravel()[1:] for version in versions]
    return [np.packbits(row > np.median(row)) for row in bits]

def key(row):
    return row["path"].name.lower().split(".rf.")[0]

all_rows = sum(datasets.values(), [])
hashes = {}
for row in all_rows:
    if row["sha256"] not in hashes:
        hashes[row["sha256"]] = visual_hash(row["path"])
popcount = np.unpackbits(np.arange(256, dtype=np.uint8)[:, None], axis=1).sum(axis=1)
def distances(pair, others):
    return popcount[np.bitwise_xor(pair, others)].sum(axis=-1).min(axis=-1)

if image_path is not None:
    query = visual_hash(image_path)[0]
    for report in provenance.values():
        rows = datasets[report["manifest_sha256"]]
        report["query_visual_candidates"] = dict(Counter(
            row["split"] for row in rows if distances(query, hashes[row["sha256"]]) <= 6))
write_json("dataset-provenance.json", provenance)

non_test = [r for r in all_rows if r["split"] != "test"]
non_test_hashes = {r["sha256"] for r in non_test}
non_test_keys = {key(r) for r in non_test}
non_test_visual = np.array([hashes[h] for h in non_test_hashes])
by_dataset = []
for rows in datasets.values():
    by_key = {}
    for row in rows:
        if row["split"] == "test":
            by_key.setdefault(key(row), []).append(row)
    by_dataset.append(by_key)
shared = sorted(set.intersection(*(set(d) for d in by_dataset)))
drop = Counter()
cohort = []
cohort_info = []
for uid in shared:
    groups = [d[uid] for d in by_dataset]
    versions = sum(groups, [])
    if len({tuple(r["labels"]) for r in versions}) != 1:
        drop["conflicting_test_labels"] += 1
        continue
    if uid in non_test_keys or any(r["sha256"] in non_test_hashes for r in versions):
        drop["train_or_val_source_key_or_exact_hash"] += 1
        continue
    item = groups[-1][0]
    reference = hashes[item["sha256"]][0]
    if any(distances(reference, hashes[r["sha256"]]) > 6 for r in versions):
        drop["test_versions_not_visually_corroborated"] += 1
        continue
    if any(np.any(distances(hashes[r["sha256"]][0], non_test_visual) <= 6) for r in versions):
        drop["near_duplicate_in_train_or_val"] += 1
        continue
    if any(distances(reference, hashes[r["sha256"]]) <= 6 for r in cohort):
        drop["near_duplicate_in_cohort"] += 1
        continue
    cohort.append(item)
    cohort_info.append(dict(item=len(cohort), label=item["labels"][0]))
write_json("common-test-provenance.json", {"shared_test_source_ids": len(shared), "excluded": dict(drop),
    "n": len(cohort), "class_counts": dict(Counter(r["label"] for r in cohort_info))})
print("COMMON", len(shared), drop, len(cohort), flush=True)
if cohort:
    write_csv("common-test-cohort.csv", cohort_info)
    evaluate_all("common-test", cohort)
