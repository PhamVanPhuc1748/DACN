"""
Loc anh trung / gan giong nhau trong mot thu muc dataset.

Cach dung (trong venv cua project, da co Pillow + numpy):
    python dedupe_images.py <thu_muc_dataset>                # chi bao cao, KHONG di chuyen gi
    python dedupe_images.py <thu_muc_dataset> --apply        # chuyen anh trung sang <thu_muc>_duplicates
    python dedupe_images.py <thu_muc_dataset> --threshold 8  # chat hon (so nho = chi bat anh rat giong)

Quy tac:
- So sanh bang perceptual hash (dHash 16x16 = 256 bit); khoang cach Hamming <= threshold la "giong nhau".
- Trong moi nhom giong nhau, giu 1 anh: uu tien anh o thu muc train, roi anh co do phan giai lon nhat.
- Nhom co anh nam o cac lop (thu muc cha) khac nhau duoc danh dau "conflict": khong tu di chuyen, can xem tay.
- Khong bao gio xoa anh. --apply chi di chuyen anh trung sang thu muc _duplicates.
- Ket qua ghi vao dedupe_report.csv.
"""
import argparse
import csv
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
HASH_SIZE = 16  # 16x16 -> 256 bit


def dhash_bits(path: Path):
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)
        w, h = im.size
        g = im.convert("L").resize((HASH_SIZE + 1, HASH_SIZE), Image.LANCZOS)
    a = np.asarray(g, dtype=np.int16)
    bits = (a[:, 1:] > a[:, :-1]).flatten().astype(np.float32)
    return bits, w, h


class UnionFind:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--threshold", type=int, default=12, help="Hamming toi da tren 256 bit (mac dinh 12)")
    ap.add_argument("--apply", action="store_true", help="chuyen anh trung sang thu muc _duplicates")
    ap.add_argument("--report", type=Path, default=Path("dedupe_report.csv"))
    args = ap.parse_args()

    root = args.root.resolve()
    if not root.is_dir():
        sys.exit(f"Khong thay thu muc: {root}")

    files = [p for p in sorted(root.rglob("*")) if p.is_file() and p.suffix.lower() in EXTS]
    print(f"Tim thay {len(files)} anh trong {root}")

    paths, bits, sizes, bad = [], [], [], []
    for i, p in enumerate(files, 1):
        try:
            b, w, h = dhash_bits(p)
        except Exception as e:  # anh hong
            bad.append((p, str(e)))
            continue
        paths.append(p)
        bits.append(b)
        sizes.append((w, h))
        if i % 500 == 0:
            print(f"  da bam {i}/{len(files)}")
    if bad:
        print(f"Bo qua {len(bad)} anh doc loi (xem cuoi bao cao)")
    n = len(paths)
    if n == 0:
        sys.exit("Khong co anh hop le.")

    B = np.stack(bits).astype(np.float32)
    notB = 1.0 - B
    uf = UnionFind(n)
    chunk = 1024
    for s in range(0, n, chunk):
        blk = B[s:s + chunk]
        d = blk @ notB.T + (1.0 - blk) @ B.T  # khoang cach Hamming, kich thuoc (chunk, n)
        ii, jj = np.where(d <= args.threshold)
        ii = ii + s
        keep = ii < jj
        for i, j in zip(ii[keep], jj[keep]):
            uf.union(int(i), int(j))

    groups = {}
    for i in range(n):
        groups.setdefault(uf.find(i), []).append(i)
    dup_groups = [g for g in groups.values() if len(g) > 1]

    def rel(i):
        return paths[i].relative_to(root)

    def split_of(i):
        parts = rel(i).parts
        return parts[0].lower() if len(parts) > 1 else ""

    def cls_of(i):
        return paths[i].parent.name

    def rank(i):
        w, h = sizes[i]
        return (0 if split_of(i) == "train" else 1, -(w * h), -paths[i].stat().st_size, str(rel(i)))

    rows, to_move = [], []
    n_conflict = 0
    for gid, g in enumerate(sorted(dup_groups, key=lambda x: str(rel(min(x)))), 1):
        g = sorted(g, key=rank)
        kept = g[0]
        conflict = len({cls_of(i) for i in g}) > 1
        n_conflict += conflict
        for i in g:
            if i == kept:
                action = "keep" if not conflict else "conflict-keep"
            else:
                action = "duplicate" if not conflict else "conflict"
                if not conflict:
                    to_move.append(i)
            dist = int(np.sum(B[i] != B[kept]))
            rows.append([gid, action, str(rel(i)), cls_of(i), split_of(i), sizes[i][0], sizes[i][1], dist])

    if args.report.exists():
        ap.error("Bao cao da ton tai. Hay chon --report moi de giu bao cao cu.")
    with open(args.report, "x", newline="", encoding="utf-8-sig") as f:
        wr = csv.writer(f)
        wr.writerow(["group", "action", "path", "class", "split", "width", "height", "dist_to_kept"])
        wr.writerows(rows)
        for p, e in bad:
            wr.writerow(["", "unreadable", str(p.relative_to(root)), "", "", "", "", e])

    print()
    print(f"Anh hop le       : {n}")
    print(f"Nhom giong nhau  : {len(dup_groups)}")
    print(f"Anh se chuyen di : {len(to_move)}  (giu lai {n - len(to_move)})")
    print(f"Nhom conflict    : {n_conflict}  (khac lop, can xem tay, khong tu di chuyen)")
    print(f"Bao cao          : {args.report.resolve()}")

    if args.apply and to_move:
        dest_root = root.parent / (root.name + "_duplicates")
        if any((dest_root / rel(i)).exists() for i in to_move):
            sys.exit("Thu muc cach ly co file cung ten. Khong di chuyen anh.")
        for i in to_move:
            dst = dest_root / rel(i)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(paths[i]), str(dst))
        print(f"Da chuyen {len(to_move)} anh sang {dest_root}")
    elif to_move:
        print("Dang o che do xem thu. Xem dedupe_report.csv roi chay lai voi --apply neu on.")


if __name__ == "__main__":
    main()
