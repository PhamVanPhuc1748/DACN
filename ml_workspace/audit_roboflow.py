"""Read-only Roboflow audit. Reports and previews go to a new output directory."""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import textwrap
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def write_csv(path, fields, rows):
    with path.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def inspect_image(path, root):
    relative = path.relative_to(root)
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("L")
        pixels = np.asarray(image, dtype=np.float32)
        small = np.asarray(image.resize((17, 16), Image.Resampling.LANCZOS))
    flags = []
    mean, contrast = float(pixels.mean()), float(pixels.std())
    edge = (np.abs(np.diff(pixels, axis=0)).mean() + np.abs(np.diff(pixels, axis=1)).mean()) / 2
    dark, bright = float((pixels <= 5).mean()), float((pixels >= 250).mean())
    size = path.stat().st_size
    name = path.name.casefold()
    for condition, flag in (
        (contrast < 15, "low_contrast"), (edge < 2.5, "low_edge"),
        (size < 5000, "small_file"), (mean < 35 or mean > 220, "extreme_mean"),
        (dark > .25, "dark_clipping"), (bright > .25, "bright_clipping"),
        (any(word in name for word in ("istock", "getty", "shutterstock", "alamy", "adobe", "licensed-image")), "stock_or_watermark_name"),
        (any(word in name for word in ("screenshot", "figure", "diagram", "illustration")), "screenshot_or_figure_name"),
        (any(word in name for word in ("dermnet", "visualdx", "human")), "possible_human_source_name"),
    ):
        if condition:
            flags.append(flag)
    row = dict(path=relative.as_posix(), split=relative.parts[0], label=relative.parts[1],
               width=image.width, height=image.height, bytes=size, mean=round(mean, 3),
               contrast=round(contrast, 3), edge=round(float(edge), 3),
               dark_fraction=round(dark, 4), bright_fraction=round(bright, 4), flags=";".join(flags))
    return row, (small[:, 1:] > small[:, :-1]).ravel()


def find_groups(bits, threshold):
    matrix = bits.astype(np.float32)
    complement = 1 - matrix
    adjacency = defaultdict(set)
    for start in range(0, len(matrix), 512):
        block = matrix[start:start + 512]
        distances = block @ complement.T + (1 - block) @ matrix.T
        left, right = np.where(distances <= threshold)
        for i, j in zip(left + start, right):
            if i < j:
                adjacency[int(i)].add(int(j))
                adjacency[int(j)].add(int(i))
    unseen = set(adjacency)
    groups = []
    for first in sorted(adjacency):
        if first not in unseen:
            continue
        pending, component = [first], []
        unseen.remove(first)
        while pending:
            member = pending.pop()
            component.append(member)
            neighbors = adjacency[member] & unseen
            unseen.difference_update(neighbors)
            pending.extend(neighbors)
        groups.append(sorted(component))
    return groups


def sheet(root, entries, output, title, columns=3):
    font = ImageFont.load_default(size=14)
    tile_w, tile_h = 400, 350
    canvas = Image.new("RGB", (columns * tile_w, 40 + tile_h * ((len(entries) + columns - 1) // columns)), "#f6f7f9")
    draw = ImageDraw.Draw(canvas)
    draw.text((10, 10), title, fill="black", font=font)
    for index, (row, caption) in enumerate(entries):
        x, y = (index % columns) * tile_w + 8, (index // columns) * tile_h + 40
        with Image.open(root / row["path"]) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail((215, 215))
            canvas.paste(image, (x, y))
        lines = [caption, row["label"]]
        lines.extend(textwrap.wrap(row["path"], width=47))
        draw.multiline_text((x, y + 220), "\n".join(lines), fill="black", font=font, spacing=3)
    canvas.save(output, quality=90)


def clip_sample(root, rows, size, output):
    # Offline mode uses the installed app weights from the local Hugging Face cache.
    os.environ["HF_HUB_OFFLINE"] = "1"
    sys.path.insert(0, str(ROOT / "PigSkinTech"))
    import torch
    from services.image_gate import load_model, MODEL_NAME, PRETRAINED

    torch.set_num_threads(min(4, os.cpu_count() or 1))
    model, preprocess, (positive, negative), device = load_model()
    import open_clip

    prompts = {
        "pig_closeup": "a close-up veterinary photograph of pig skin",
        "pig_fullbody": "a photograph of one or more pigs in a farm or pen",
        "human_skin": "a clinical dermatology photograph of a rash on human skin",
        "illustration": "a drawing, printed illustration, or diagram of a pig",
        "other_subject": "a photograph unrelated to pigs or veterinary medicine",
    }
    tokenizer = open_clip.get_tokenizer(MODEL_NAME)
    labelled = defaultdict(list)
    for row in rows:
        labelled[row["label"]].append(row)
    samples = []
    for label, candidates in sorted(labelled.items()):
        # Spread the exploratory sample across each class's sorted inventory.
        indices = np.linspace(0, len(candidates) - 1, min(size, len(candidates)), dtype=int)
        samples.extend(candidates[i] for i in indices)
    scores = []
    with torch.inference_mode():
        text = torch.nn.functional.normalize(model.encode_text(tokenizer(list(prompts.values())).to(device)).float())
        for start in range(0, len(samples), 8):
            batch = samples[start:start + 8]
            tensors = []
            for row in batch:
                with Image.open(root / row["path"]) as image:
                    tensors.append(preprocess(ImageOps.exif_transpose(image).convert("RGB")))
            features = torch.nn.functional.normalize(model.encode_image(torch.stack(tensors).to(device)).float())
            similarities = (features @ text.T).tolist()
            gate_scores = (features @ torch.stack((positive, negative)).T).tolist()
            for row, values, (pig, other) in zip(batch, similarities, gate_scores):
                top = max(zip(prompts, values), key=lambda item: item[1])[0]
                scores.append(dict(path=row["path"], label=row["label"], top_prompt=top,
                                   gate_pig=round(pig, 5), gate_other=round(other, 5),
                                   gate_margin=round(pig - other, 5),
                                   **{key: round(value, 5) for key, value in zip(prompts, values)}))
    write_csv(output / "clip_sample.csv", list(scores[0]), scores)
    suspects = sorted((s for s in scores if s["top_prompt"] in {"human_skin", "illustration", "other_subject"}),
                      key=lambda s: (s["top_prompt"], -s[s["top_prompt"]]))
    index = {row["path"]: row for row in rows}
    if suspects:
        sheet(root, [(index[s["path"]], s["top_prompt"]) for s in suspects[:24]],
              output / "clip_candidates.jpg", "CLIP candidates for human review")
    return dict(model=f"{MODEL_NAME}:{PRETRAINED}", device=str(device), sample=len(scores), suspect=len(suspects))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threshold", type=int, default=12, choices=range(257), metavar="0..256")
    parser.add_argument("--clip-per-class", type=int, default=0, help="Offline CLIP sample size per class")
    parser.add_argument("--clip-only", action="store_true", help="Write an independent CLIP sample report")
    args = parser.parse_args()
    root, output = args.image_root.resolve(), args.output.resolve()
    if not root.is_dir() or output.is_relative_to(root):
        parser.error("Use an existing dataset root and an output directory outside it")
    if args.clip_per_class < 0 or (args.clip_only and not args.clip_per_class):
        parser.error("Provide a positive --clip-per-class for --clip-only")
    rows, hashes, errors = [], [], []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
            continue
        try:
            if len(path.relative_to(root).parts) != 3:
                raise ValueError("Expected split/class/image")
            row, bits = inspect_image(path, root)
            rows.append(row)
            hashes.append(bits)
        except (OSError, ValueError, IndexError) as error:
            errors.append(dict(path=path.relative_to(root).as_posix(), error=str(error)))
    if not rows:
        parser.error("No readable images found")
    output.mkdir(parents=True, exist_ok=False)
    if args.clip_only:
        print(json.dumps(clip_sample(root, rows, args.clip_per_class, output)))
        return
    write_csv(output / "unreadable.csv", ["path", "error"], errors)
    bits = np.stack(hashes)
    groups = find_groups(bits, args.threshold)
    summaries, members, pairs = [], [], []
    review = {}
    sheets = output / "groups"
    sheets.mkdir()
    for number, group in enumerate(groups, 1):
        group_id = f"G{number:03}"
        cross_split = len({rows[i]["split"] for i in group}) > 1
        cross_label = len({rows[i]["label"] for i in group}) > 1
        reference = min(group, key=lambda i: (rows[i]["split"] != "train",
                        -rows[i]["width"] * rows[i]["height"], -rows[i]["bytes"], rows[i]["path"]))
        distances = []
        for i, j in combinations(group, 2):
            distance = int(np.count_nonzero(bits[i] != bits[j]))
            distances.append(distance)
            pairs.append(dict(group=group_id, path_a=rows[i]["path"], path_b=rows[j]["path"],
                              hamming=distance, direct_edge=int(distance <= args.threshold)))
        indirect = sum(d > args.threshold for d in distances)
        priority = "cross_split_and_label" if cross_split and cross_label else (
            "cross_split" if cross_split else "cross_label" if cross_label else "within_split")
        summaries.append(dict(group=group_id, priority=priority, count=len(group), cross_split=int(cross_split),
                              cross_label=int(cross_label), indirect_pairs=indirect, diameter=max(distances),
                              reference=rows[reference]["path"]))
        entries = []
        for i in sorted(group, key=lambda i: (i != reference, rows[i]["path"])):
            row = rows[i]
            distance = int(np.count_nonzero(bits[i] != bits[reference]))
            members.append(dict(group=group_id, path=row["path"], split=row["split"], label=row["label"],
                                hamming_to_reference=distance, reference=int(i == reference)))
            entries.append((row, f"{group_id} | {row['split']} | Hamming to ref: {distance}"))
            review[row["path"]] = dict(path=row["path"], candidate_group=group_id, disposition="",
                                       confirmed_group="", notes="")
        for start in range(0, len(entries), 12):
            sheet(root, entries[start:start + 12], sheets / f"{group_id}_{start // 12 + 1:02}.jpg",
                  f"{group_id} | {priority} | diameter {max(distances)} | chained pairs {indirect}")
    for error in errors:
        path = error["path"]
        if len(Path(path).parts) == 3:
            review[path] = dict(path=path, candidate_group="", disposition="", confirmed_group="",
                                notes="")
    summaries.sort(key=lambda row: (-row["cross_split"], -row["cross_label"], row["group"]))
    for name, data, fields in (
        ("group_summary", summaries, "group priority count cross_split cross_label indirect_pairs diameter reference"),
        ("group_members", members, "group path split label hamming_to_reference reference"),
        ("group_pairs", pairs, "group path_a path_b hamming direct_edge"),
        ("similarity_review", list(review.values()), "path candidate_group disposition confirmed_group notes"),
    ):
        write_csv(output / f"{name}.csv", fields.split(), data)
    quality = [row for row in rows if row["flags"]]
    write_csv(output / "quality_candidates.csv", list(rows[0]), quality)
    quality_dir = output / "quality"
    quality_dir.mkdir()
    sort_keys = {
        "low_contrast": lambda row: row["contrast"],
        "low_edge": lambda row: row["edge"],
        "small_file": lambda row: row["bytes"],
        "extreme_mean": lambda row: -abs(row["mean"] - 127.5),
        "dark_clipping": lambda row: -row["dark_fraction"],
        "bright_clipping": lambda row: -row["bright_fraction"],
    }
    for flag in sorted({flag for row in quality for flag in row["flags"].split(";")}):
        candidates = [row for row in quality if flag in row["flags"].split(";")]
        sort_key = sort_keys.get(flag)
        if sort_key:
            candidates.sort(key=sort_key)
        sheet(root, [(row, flag) for row in candidates[:12]], quality_dir / f"{flag}.jpg",
              f"{flag} | Showing {min(12, len(candidates))} of {len(candidates)} | Review only")
    summary = dict(images=len(rows), unreadable=len(errors), threshold=args.threshold, groups=len(groups),
                   cross_split=sum(row["cross_split"] for row in summaries),
                   cross_label=sum(row["cross_label"] for row in summaries),
                   chained_groups=sum(row["indirect_pairs"] > 0 for row in summaries),
                   chained_pairs=sum(row["indirect_pairs"] for row in summaries),
                   quality_candidates=len(quality))
    if args.clip_per_class:
        summary["clip"] = clip_sample(root, rows, args.clip_per_class, output)
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
