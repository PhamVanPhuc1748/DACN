"""Desktop reviewer for the Roboflow audit and its separate decisions CSV."""
from __future__ import annotations

import argparse
import csv
import os
import re
import tkinter as tk
from collections import defaultdict
from pathlib import Path
from tempfile import NamedTemporaryFile
from tkinter import messagebox, ttk

from PIL import Image, ImageOps, ImageTk


FIELDS = ("path", "candidate_group", "disposition", "confirmed_group", "notes")


def read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def load_review(audit, decisions, include_quality=False):
    template_path = audit / "review_pending.csv"
    template = read_rows(template_path if template_path.is_file() else audit / "similarity_review.csv")
    rows = {row["path"]: {key: row[key] for key in FIELDS} for row in template}
    if len(rows) != len(template):
        raise ValueError("Trùng đường dẫn trong danh sách audit")
    if include_quality:
        for candidate in read_rows(audit / "quality_candidates.csv"):
            path = candidate["path"]
            rows.setdefault(path, dict(path=path, candidate_group="", disposition="", confirmed_group="", notes=""))
    if not rows:
        raise ValueError("Danh sách audit không có ảnh cần duyệt")
    if decisions.exists():
        saved_rows = read_rows(decisions)
        if len(saved_rows) != len(rows) or set(rows) != {row["path"] for row in saved_rows}:
            raise ValueError("CSV quyết định không khớp danh sách audit")
        for saved in saved_rows:
            row = rows[saved["path"]]
            for key in FIELDS[2:]:
                row[key] = saved[key]
    return rows


def save_review(path, rows):
    # Write beside the destination so replacing the previous CSV stays on one volume.
    with NamedTemporaryFile(mode="w", encoding="utf-8-sig", newline="", dir=path.parent,
                            prefix=".review-", suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows.values())
            stream.flush()
            os.fsync(stream.fileno())
        except Exception:
            stream.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class Reviewer:
    def __init__(self, window, images, audit, decisions, include_quality=False):
        self.window, self.images, self.decisions = window, images, decisions
        self.rows = load_review(audit, decisions, include_quality)
        self.meta = {row["group"]: row for row in read_rows(audit / "group_summary.csv")}
        self.members = {row["path"]: row for row in read_rows(audit / "group_members.csv")}
        self.observations = {}
        for filename, field in (("quality_candidates.csv", "flags"), ("visual_candidates.csv", "observation")):
            report = audit / filename
            if report.is_file():
                self.observations.update({row["path"]: row[field] for row in read_rows(report)})
        self.pairs = defaultdict(dict)
        for pair in read_rows(audit / "group_pairs.csv"):
            self.pairs[pair["group"]][frozenset((pair["path_a"], pair["path_b"]))] = pair["hamming"]
        grouped = defaultdict(list)
        for row in self.rows.values():
            grouped[row["candidate_group"] or row["path"]].append(row)
        priority = {"cross_split_and_label": 0, "cross_split": 2, "cross_label": 3, "within_split": 4}
        self.groups = sorted(grouped.items(), key=lambda item: (
            1 if item[0] == "V001" else priority.get(self.meta.get(item[0], {}).get("priority"), 5), item[0]))
        self.index = None
        self.editors = []
        self.photos = []
        window.title("PigSkinTech · Duyệt dataset Roboflow")
        window.geometry("1340x790")
        window.minsize(840, 580)
        window.protocol("WM_DELETE_WINDOW", self.close)
        window.bind("<Control-s>", lambda _: self.save())

        header = ttk.Frame(window, padding=10)
        header.pack(fill="x")
        ttk.Button(header, text="← Nhóm trước", command=lambda: self.go(-1)).pack(side="left")
        ttk.Button(header, text="Nhóm tiếp →", command=lambda: self.go(1)).pack(side="left", padx=5)
        ttk.Button(header, text="Lưu quyết định (Ctrl+S)", command=self.save).pack(side="left", padx=10)
        self.progress = ttk.Label(header)
        self.progress.pack(side="right")
        ttk.Label(window, padding=(10, 0), wraplength=1050,
                  text="Chọn trạng thái từng ảnh. Điền chung confirmed_group cho các ảnh Include đã xác nhận liên quan. "
                       "Exclude cần lý do và chỉ loại ảnh khỏi manifest.").pack(anchor="w")

        body = ttk.Frame(window, padding=10)
        body.pack(fill="both", expand=True)
        sidebar = ttk.Frame(body)
        sidebar.pack(side="left", fill="y", padx=(0, 10))
        self.navigation = tk.Listbox(sidebar, width=30, exportselection=False)
        nav_scroll = ttk.Scrollbar(sidebar, command=self.navigation.yview)
        self.navigation.configure(yscrollcommand=nav_scroll.set)
        nav_scroll.pack(side="right", fill="y")
        self.navigation.pack(side="left", fill="both", expand=True)
        self.navigation.bind("<<ListboxSelect>>", self.select)
        detail = ttk.Frame(body)
        detail.pack(side="left", fill="both", expand=True)
        self.title = ttk.Label(detail, wraplength=650)
        self.title.pack(anchor="w", pady=(0, 6))
        scroll = ttk.Scrollbar(detail, orient="vertical")
        horizontal = ttk.Scrollbar(detail, orient="horizontal")
        self.canvas = tk.Canvas(detail, highlightthickness=0, yscrollcommand=scroll.set,
                                xscrollcommand=horizontal.set)
        scroll.configure(command=self.canvas.yview)
        horizontal.configure(command=self.canvas.xview)
        horizontal.pack(side="bottom", fill="x")
        scroll.pack(side="right", fill="y")
        self.canvas.pack(fill="both", expand=True)
        self.cards = ttk.Frame(self.canvas)
        self.canvas.create_window(0, 0, window=self.cards, anchor="nw")
        self.cards.bind("<Configure>", lambda _: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.refresh_navigation()
        self.show(0)

    def refresh_navigation(self):
        self.navigation.delete(0, "end")
        priority = {"cross_split_and_label": "Split + nhãn", "cross_split": "Xuyên split",
                    "cross_label": "Nghi khác nhãn", "within_split": "Cùng split"}
        for i, (group, rows) in enumerate(self.groups):
            name = group if rows[0]["candidate_group"] else f"Ảnh riêng {i + 1}"
            kind = priority.get(self.meta.get(group, {}).get("priority"), "Trực quan")
            done = sum(bool(row["disposition"]) for row in rows)
            self.navigation.insert("end", f"{name} · {kind} · {done}/{len(rows)}")
        self.progress.configure(text=f"Đã lưu {sum(bool(row['disposition']) for row in self.rows.values())}/{len(self.rows)} ảnh")
        if self.index is not None:
            self.navigation.selection_set(self.index)
            self.navigation.see(self.index)

    def show(self, index):
        self.index = index
        self.navigation.selection_clear(0, "end")
        self.navigation.selection_set(index)
        self.navigation.see(index)
        for card in self.cards.winfo_children():
            card.destroy()
        self.editors.clear()
        self.photos.clear()
        group, rows = self.groups[index]
        meta = self.meta.get(group)
        heading = group if rows[0]["candidate_group"] else "Kiểm tra ảnh riêng"
        if meta:
            heading += f"   |   Hamming tối đa {meta['diameter']}   |   {meta['indirect_pairs']} cặp > ngưỡng"
        self.title.configure(text=heading)
        for i, row in enumerate(rows):
            self.add_card(group, rows, i, row)
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)

    def add_card(self, group, rows, index, row):
        relative = row["path"]
        parts = Path(relative).parts
        card = ttk.LabelFrame(self.cards, padding=8, text=f"Ảnh {index + 1} · {parts[0]}")
        card.grid(row=index // 4, column=index % 4, padx=4, pady=4, sticky="n")
        image_path = (self.images / relative).resolve()
        try:
            if not image_path.is_relative_to(self.images):
                raise ValueError("Đường dẫn nằm ngoài dataset")
            with Image.open(image_path) as source:
                preview = ImageOps.exif_transpose(source).convert("RGB")
                preview.thumbnail((216, 216))
            photo = ImageTk.PhotoImage(preview)
            self.photos.append(photo)
            ttk.Label(card, image=photo).pack()
        except (OSError, ValueError) as error:
            ttk.Label(card, text=str(error), wraplength=225).pack()
        for value in (parts[1], relative):
            ttk.Label(card, text=value, wraplength=225).pack(anchor="w", pady=(2, 0))
        if relative in self.members:
            hamming = ", ".join(
                f"#{j+1} = {self.pairs[group].get(frozenset((relative, peer['path'])), '?')}"
                for j, peer in enumerate(rows) if peer is not row)
            ttk.Label(card, text=f"Hamming  {hamming}", wraplength=225).pack(anchor="w")
        if relative in self.observations:
            ttk.Label(card, text=self.observations[relative], wraplength=225).pack(anchor="w")
        status = tk.StringVar(value=row["disposition"].capitalize() or "Pending")
        confirmed = tk.StringVar(value=row["confirmed_group"])
        notes = tk.StringVar(value=row["notes"])
        ttk.Combobox(card, textvariable=status, values=("Pending", "Include", "Exclude"),
                     state="readonly", width=27).pack(anchor="w", pady=(8, 3))
        for label, variable in (("confirmed_group", confirmed), ("Lý do / ghi chú", notes)):
            ttk.Label(card, text=label).pack(anchor="w")
            ttk.Entry(card, textvariable=variable, width=30).pack(anchor="w", pady=(0, 4))
        self.editors.append((row, status, confirmed, notes))

    def save(self):
        updated = dict(self.rows)
        for row, status, confirmed, notes in self.editors:
            action = status.get().lower().replace("pending", "")
            group, reason = confirmed.get().strip(), notes.get().strip()
            if group and (action != "include" or not re.fullmatch(r"[a-zA-Z0-9_.-]+", group)):
                messagebox.showerror("confirmed_group", f"Chỉ dùng chữ ASCII, số, dấu chấm, gạch dưới hoặc gạch ngang cho ảnh Include.\n{row['path']}")
                return False
            if action == "exclude" and not reason:
                messagebox.showerror("Thiếu lý do", row["path"])
                return False
            updated[row["path"]] = dict(row, disposition=action, confirmed_group=group, notes=reason)
        if updated != self.rows:
            try:
                save_review(self.decisions, updated)
            except OSError as error:
                messagebox.showerror("Không lưu được", str(error))
                return False
            for path, values in updated.items():
                self.rows[path].update(values)
        self.refresh_navigation()
        return True

    def select(self, _event):
        selected = self.navigation.curselection()
        if selected and selected[0] != self.index:
            index = selected[0]
            if self.save():
                self.show(index)
            else:
                self.refresh_navigation()

    def go(self, offset):
        index = self.index + offset
        if 0 <= index < len(self.groups) and self.save():
            self.show(index)

    def close(self):
        if self.save():
            self.window.destroy()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-root", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--include-quality", action="store_true", help="Thêm ứng viên chất lượng vào danh sách duyệt")
    args = parser.parse_args()
    images, audit, decisions = args.image_root.resolve(), args.audit.resolve(), args.decisions.resolve()
    if (not images.is_dir() or decisions.is_relative_to(images) or decisions.is_relative_to(audit)
            or not decisions.parent.is_dir()):
        parser.error("Chọn dataset hợp lệ và một CSV quyết định riêng bên ngoài dataset và thư mục audit")
    window = tk.Tk()
    try:
        reviewer = Reviewer(window, images, audit, decisions, args.include_quality)
        if not decisions.exists():
            save_review(decisions, reviewer.rows)
    except (OSError, KeyError, ValueError) as error:
        messagebox.showerror("Không mở được danh sách duyệt", str(error))
        window.destroy()
        raise SystemExit(1) from error
    window.mainloop()


if __name__ == "__main__":
    main()
