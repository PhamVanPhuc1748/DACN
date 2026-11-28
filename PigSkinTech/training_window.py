"""Separate Flet window for a local administrator-initiated training run."""
from __future__ import annotations

import csv
import hashlib
import inspect
import json
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import flet as ft

from services.project_data import active_run, torch_python
from services.auth_service import create_file_picker


ROOT = Path(__file__).resolve().parents[1]
TRAINER = ROOT / "ml_workspace" / "train_model.py"
MANIFEST_BUILDER = ROOT / "ml_workspace" / "build_retrain_manifest.py"
DATASET = ROOT / "data" / "raw" / "Pig Skin Disease Single Label v4.v1-class-test.folder"
SPLIT = ROOT / "ml_workspace" / "manifests" / "pig_skin_single_label_v4"
RUNS = ROOT / "ml_workspace" / "runs"
INK = "#17342A"
MUTED = "#405B50"
ACCENT = "#24634B"
LINE = "#A9BDB2"
PAPER = "#FFFFFF"

FIELDS = [
    ("epochs", "Số epoch tối đa", "25", "Số vòng học tối đa; early stopping có thể dừng sớm.", int),
    ("head-epochs", "Epoch chỉ học lớp cuối", "5", "Đóng băng backbone trước khi tinh chỉnh toàn mạng.", int),
    ("batch-size", "Batch size", "16", "Số ảnh mỗi bước; tăng có thể cần thêm VRAM.", int),
    ("num-workers", "Data loader workers", "0", "Số tiến trình đọc ảnh; 0 ổn định hơn trên Windows.", int),
    ("head-lr", "Learning rate lớp cuối", "0.001", "Tốc độ học ở giai đoạn đầu.", float),
    ("finetune-lr", "Learning rate tinh chỉnh", "0.0001", "Tốc độ học khi mở backbone.", float),
    ("weight-decay", "Weight decay", "0.0001", "Giảm nguy cơ weights quá khớp dữ liệu.", float),
    ("early-stopping-patience", "Kiên nhẫn dừng sớm", "4", "Số epoch không tăng validation macro-F1 trước khi dừng.", int),
    ("image-size", "Kích thước ảnh", "224", "Ảnh được resize thành hình vuông theo số pixel này.", int),
    ("seed", "Random seed", "42", "Giúp tái lập kết quả trong cùng môi trường.", int),
    ("rotation-degrees", "Xoay tối đa (độ)", "10", "Biến đổi ảnh train trong khoảng ± giá trị này.", float),
    ("horizontal-flip-probability", "Xác suất lật ngang", "0.5", "Chỉ áp dụng cho ảnh train; từ 0 đến 1.", float),
    ("brightness-jitter", "Thay đổi độ sáng", "0.10", "Mức dao động sáng của augmentation.", float),
    ("contrast-jitter", "Thay đổi tương phản", "0.10", "Mức dao động tương phản của augmentation.", float),
    ("saturation-jitter", "Thay đổi độ bão hòa", "0.05", "Mức dao động màu của augmentation.", float),
    ("multilabel-threshold", "Ngưỡng đa nhãn", "0.5", "Chỉ dùng khi chọn chế độ đa nhãn.", float),
]


def latest_training_inputs(active: dict | None = None) -> tuple[Path, Path, Path, str]:
    """Choose the newest known manifest together with its matching image root."""
    generated = RUNS / "datasets"
    candidates: list[tuple[Path, Path, str]] = []
    for manifest in generated.glob("retrain_*/manifest.csv"):
        report = manifest.with_suffix(".json")
        try:
            details = json.loads(report.read_text(encoding="utf-8"))
            image_root = Path(details["image_root"])
            if image_root.is_dir():
                candidates.append((manifest, image_root, "Manifest từ ca chuyên gia đã duyệt"))
        except (OSError, KeyError, ValueError, json.JSONDecodeError):
            continue
    if active and (active.get("data") or {}).get("matches_run"):
        current = Path(active["config"].get("manifest") or "")
        if current.is_file():
            candidates.append((current, DATASET, "Manifest của model đang dùng"))
    candidates.append((SPLIT / "manifest.csv", DATASET, "Manifest mẫu đi kèm dự án"))
    for manifest, image_root, source in sorted(candidates, key=lambda item: item[0].stat().st_mtime if item[0].is_file() else 0, reverse=True):
        if not manifest.is_file() or not image_root.is_dir():
            continue
        try:
            with manifest.open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                fields = set(reader.fieldnames or [])
                first = next(reader, None)
            if ({"relative_path", "split", "labels", "group_id"} <= fields and first
                    and (image_root / first["relative_path"]).is_file()):
                return manifest, image_root, SPLIT / "classes.json", source
        except (OSError, csv.Error):
            continue
    return SPLIT / "manifest.csv", DATASET, SPLIT / "classes.json", "Manifest mẫu đi kèm dự án"


def comparison_basis(baseline: dict | None, candidate: dict) -> str | None:
    """Return the evidence for comparing two saved evaluations."""
    if not baseline or any(baseline.get(key) != candidate.get(key) for key in
                           ("classes", "label_mode", "image_size", "normalization")):
        return None
    old_splits = baseline.get("split_sha256") or {}
    new_splits = candidate.get("split_sha256") or {}
    if all(old_splits.get(split) and old_splits[split] == new_splits.get(split)
           for split in ("val", "test")):
        return "fingerprint"
    if (baseline.get("manifest_sha256") and
            baseline["manifest_sha256"] == candidate.get("manifest_sha256")):
        return "manifest"

    def reviewed_rows(config: dict) -> dict[str, set[tuple[str, str]]] | None:
        path = Path(config.get("manifest") or "")
        if not path.is_file() or not config.get("manifest_sha256"):
            return None
        if hashlib.sha256(path.read_bytes()).hexdigest() != config["manifest_sha256"]:
            return None
        splits = {"val": set(), "test": set()}
        with path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                split = (row.get("split") or "").lower()
                if split in ("valid", "validation"):
                    split = "val"
                if split in splits:
                    splits[split].add((row.get("relative_path") or "", row.get("labels") or ""))
        return splits if all(splits.values()) else None

    old_rows, new_rows = reviewed_rows(baseline), reviewed_rows(candidate)
    if old_rows and old_rows == new_rows:
        return "same-rows"
    return None


def assessment(history: list[dict], baseline: dict | None, config: dict) -> tuple[str, str]:
    """Explain observed generalization without claiming clinical improvement."""
    if not history:
        return "Chưa có kết quả", "Chạy train để xem train và validation sau từng epoch."
    last = history[-1]
    train_f1 = float(last.get("train_macro_f1", 0))
    val_f1 = float(last.get("val_macro_f1", 0))
    train_loss = float(last.get("train_eval_loss", last.get("train_loss", 0)))
    val_loss = float(last.get("val_loss", 0))
    gap = train_f1 - val_f1
    message = (
        f"Epoch {last['epoch']}: train macro-F1 {train_f1:.1%}, validation macro-F1 {val_f1:.1%}; "
        f"chênh lệch {gap:+.1%}. Loss train {train_loss:.3f}, validation {val_loss:.3f}. "
    )
    recent = history[-min(4, len(history)):]
    if gap >= 0.15 and val_loss > train_loss:
        verdict = "Có dấu hiệu học vẹt"
        message += "Model học tốt trên ảnh train nhưng kém hơn rõ trên ảnh chưa dùng để học."
    elif len(recent) >= 3 and float(recent[-1]["val_loss"]) > float(recent[0]["val_loss"]) and train_loss < float(recent[0].get("train_eval_loss", recent[0].get("train_loss", 0))):
        verdict = "Cần theo dõi quá khớp"
        message += "Loss validation tăng trong khi loss train giảm."
    else:
        verdict = "Chưa thấy dấu hiệu học vẹt rõ"
        message += "Vẫn cần xem kết quả theo từng bệnh và ảnh thực tế."
    if baseline:
        if not comparison_basis(baseline, config):
            message += " Chưa thể so sánh công bằng với model đang dùng: tập val/test, lớp hoặc tiền xử lý khác hay thiếu dấu vân tay split."
    return verdict, message


def main(page: ft.Page) -> None:
    page.title = "PigSkinTech · Huấn luyện AI"
    page.window.width = 1280
    page.window.height = 860
    page.window.min_width = 950
    page.window.min_height = 680
    page.padding = 20
    page.bgcolor = "#F0F5F1"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(color_scheme_seed=ACCENT)
    page.scroll = ft.ScrollMode.AUTO

    active = active_run()
    baseline = active["config"] if active else None
    running: dict = {"process": None, "run": None}
    controls: dict[str, ft.TextField] = {}
    initial_manifest, initial_root, initial_classes, initial_source = latest_training_inputs(active)

    def field(label, value, help_text, width=340):
        return ft.TextField(
            value=str(value),
            tooltip=help_text, width=width, dense=True, text_size=15, color=INK,
            bgcolor=PAPER, filled=True, fill_color=PAPER, border_color=LINE,
            focused_border_color=ACCENT,
        )

    manifest = field("Manifest CSV", initial_manifest, "CSV chỉ rõ ảnh, nhãn và tập train/validation/test.", 720)
    image_root = field("Thư mục gốc ảnh", initial_root, "Nơi chứa ảnh mà manifest đang tham chiếu.", 720)
    classes_file = field("Class map JSON", initial_classes, "Tên và thứ tự các lớp bệnh của model.", 720)
    model = ft.Dropdown(label="Kiến trúc", value="mobilenet_v2", width=260, options=[
        ft.dropdown.Option("mobilenet_v2", "MobileNetV2"),
        ft.dropdown.Option("mobilenet_v3_large", "MobileNetV3-Large"),
        ft.dropdown.Option("efficientnet_b0", "EfficientNet-B0"),
    ])
    label_mode = ft.Dropdown(label="Kiểu nhãn", value="single", width=260, options=[
        ft.dropdown.Option("single", "Một bệnh/ảnh"),
        ft.dropdown.Option("multilabel", "Nhiều bệnh/ảnh"),
    ])
    device = ft.Dropdown(label="Thiết bị", value="auto", width=230, options=[
        ft.dropdown.Option("auto", "Tự chọn GPU/CPU"),
        ft.dropdown.Option("cuda", "Chỉ GPU CUDA"),
        ft.dropdown.Option("cpu", "Chỉ CPU"),
    ])
    pretrained = ft.Switch(label="Khởi tạo từ weights ImageNet", value=True)
    augmentation = ft.Switch(label="Biến đổi ảnh train", value=True)
    for key, label, value, help_text, _ in FIELDS:
        controls[key] = field(label, value, help_text, 265)

    status = ft.Text("Sẵn sàng kiểm tra dữ liệu", size=16, weight=ft.FontWeight.BOLD, color=INK)
    verdict = ft.Text("Chưa có kết quả", size=18, weight=ft.FontWeight.BOLD, color=INK)
    explanation = ft.Text("Theo dõi train và validation để nhận biết dấu hiệu học vẹt; xem test theo từng lớp trước khi kích hoạt.", color=MUTED, size=14, selectable=True)
    summary = ft.Text(f"Đã chọn: {initial_source}.", color=MUTED, size=14, selectable=True)
    epoch_table = ft.DataTable(columns=[ft.DataColumn(ft.Text(s)) for s in
        ("Epoch", "Train loss", "Val loss", "Train F1", "Val F1", "Chênh F1")], rows=[])
    metrics = ft.Text("", color=INK, size=14, selectable=True)
    log = ft.TextField(label="Nhật ký", value="", multiline=True, read_only=True, min_lines=8, max_lines=12,
                       expand=True, text_size=13, color=INK, bgcolor="#F6F9F7", border_color=LINE,
                       label_style=ft.TextStyle(color=INK))
    check_button = ft.FilledButton("Kiểm tra dữ liệu", icon=ft.Icons.FACT_CHECK_OUTLINED)
    train_button = ft.FilledButton("Bắt đầu train", icon=ft.Icons.PLAY_ARROW_ROUNDED)
    stop_button = ft.OutlinedButton("Dừng train", icon=ft.Icons.STOP_ROUNDED, disabled=True)
    build_button = ft.OutlinedButton("Tạo manifest từ ca chuyên gia đã duyệt", icon=ft.Icons.DATASET_LINKED_ROUNDED)
    newest_button = ft.OutlinedButton("Dùng manifest mới nhất", icon=ft.Icons.UPDATE_ROUNDED)
    manifest_picker = create_file_picker(page)
    classes_picker = create_file_picker(page)
    image_picker = create_file_picker(page)

    def set_manifest(path: str) -> None:
        selected = Path(path)
        manifest.value = str(selected)
        if selected.resolve() == (SPLIT / "manifest.csv").resolve():
            image_root.value = str(DATASET)
        else:
            report = selected.with_suffix(".json")
            try:
                details = json.loads(report.read_text(encoding="utf-8"))
                image_root.value = str(Path(details["image_root"]))
            except (OSError, KeyError, ValueError, json.JSONDecodeError):
                status.value = "Đã chọn manifest. Hãy kiểm tra thư mục gốc ảnh trước khi train."
        summary.value = f"Manifest đang chọn: {selected.name}. Bấm Kiểm tra dữ liệu để xác nhận ảnh và nhãn."
        page.update()

    def set_classes(path: str) -> None:
        classes_file.value = path
        status.value = "Đã chọn class map. Hãy kiểm tra thứ tự lớp trước khi train."
        page.update()

    def set_image_root(path: str) -> None:
        image_root.value = path
        status.value = "Đã chọn thư mục ảnh. Hãy bấm Kiểm tra dữ liệu."
        page.update()

    async def choose_file(picker, extensions: list[str], callback) -> None:
        if inspect.iscoroutinefunction(picker.pick_files):
            files = await picker.pick_files(allow_multiple=False,
                                            file_type=ft.FilePickerFileType.CUSTOM,
                                            allowed_extensions=extensions)
            if files and getattr(files[0], "path", None):
                callback(files[0].path)
        else:
            def on_result(event):
                files = getattr(event, "files", None) or []
                if files and getattr(files[0], "path", None):
                    callback(files[0].path)
            picker.on_result = on_result
            picker.pick_files(allow_multiple=False, file_type=ft.FilePickerFileType.CUSTOM,
                              allowed_extensions=extensions)

    async def choose_image_root(_) -> None:
        if inspect.iscoroutinefunction(image_picker.get_directory_path):
            path = await image_picker.get_directory_path()
            if path:
                set_image_root(path)
        else:
            image_picker.on_result = lambda event: set_image_root(event.path) if getattr(event, "path", None) else None
            image_picker.get_directory_path()

    def use_newest(_) -> None:
        newest_manifest, newest_root, newest_classes, source = latest_training_inputs(active)
        manifest.value, image_root.value, classes_file.value = map(str, (newest_manifest, newest_root, newest_classes))
        summary.value = f"Đã chọn: {source}. Manifest: {newest_manifest.name}."
        status.value = "Đã cập nhật đường dẫn. Hãy bấm Kiểm tra dữ liệu."
        page.update()

    newest_button.on_click = use_newest
    async def browse_manifest_click(_):
        await choose_file(manifest_picker, ["csv"], set_manifest)

    async def browse_classes_click(_):
        await choose_file(classes_picker, ["json"], set_classes)

    browse_manifest = ft.OutlinedButton("Chọn CSV", icon=ft.Icons.FOLDER_OPEN_ROUNDED,
                                        on_click=browse_manifest_click)
    browse_classes = ft.OutlinedButton("Chọn JSON", icon=ft.Icons.FOLDER_OPEN_ROUNDED,
                                       on_click=browse_classes_click)
    browse_images = ft.OutlinedButton("Chọn thư mục", icon=ft.Icons.FOLDER_OPEN_ROUNDED,
                                      on_click=choose_image_root)

    def build_manifest(_):
        if build_button.disabled or train_button.disabled:
            return
        build_button.disabled = True
        status.value = "Đang kiểm tra ảnh chuyên gia đã duyệt và đối chiếu ảnh trùng…"
        page.update()

        def worker():
            try:
                output = RUNS / "datasets" / ("retrain_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")) / "manifest.csv"
                process = subprocess.run([sys.executable, str(MANIFEST_BUILDER), "--output", str(output)],
                                         cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
                if process.returncode:
                    raise RuntimeError((process.stderr or process.stdout).strip().splitlines()[-1])
                report = json.loads(process.stdout)
                manifest.value = str(output)
                image_root.value = str(ROOT)
                summary.value = (
                    f"Manifest mới: {report['base_images']} ảnh gốc + "
                    f"{report['expert_images_added_to_train']} ca chuyên gia vào train; "
                    f"bỏ qua {report['duplicates_skipped']} ảnh trùng, {report['invalid_cases_skipped']} ca thiếu ảnh/nhãn. "
                    "Group ca mới dựa trên case ID; cần rà soát ảnh gần trùng và nguồn trước khi diễn giải kết quả."
                )
                status.value = "Đã tạo manifest mới. Hãy bấm Kiểm tra dữ liệu trước khi train."
            except (OSError, ValueError, KeyError, RuntimeError) as exc:
                status.value = f"Không tạo được manifest: {exc}"
            finally:
                build_button.disabled = False
                page.update()

        threading.Thread(target=worker, daemon=True).start()

    build_button.on_click = build_manifest

    def arguments() -> list[str]:
        for key, label, _, _, caster in FIELDS:
            raw = (controls[key].value or "").strip()
            try:
                caster(raw)
            except ValueError as exc:
                raise ValueError(f"Thông số '{label}' phải là số hợp lệ.") from exc
        for control, label in ((manifest, "Manifest CSV"), (image_root, "Thư mục gốc ảnh"),
                               (classes_file, "Class map JSON")):
            if not (control.value or "").strip():
                raise ValueError(f"Cần điền {label}.")
        args = [
            "--manifest", manifest.value.strip(), "--image-root", image_root.value.strip(),
            "--classes-file", classes_file.value.strip(), "--model", model.value,
            "--label-mode", label_mode.value, "--device", device.value,
            "--pretrained" if pretrained.value else "--no-pretrained",
            "--augmentation" if augmentation.value else "--no-augmentation",
        ]
        for key in controls:
            args.extend([f"--{key}", controls[key].value.strip()])
        return args

    def refresh() -> None:
        run = running["run"]
        if not run:
            return
        history_path = run / "history.csv"
        if history_path.is_file():
            try:
                with history_path.open(encoding="utf-8", newline="") as stream:
                    rows = list(csv.DictReader(stream))
                epoch_table.rows = []
                for row in rows:
                    train_f1 = float(row.get("train_macro_f1", 0))
                    val_f1 = float(row.get("val_macro_f1", 0))
                    values = [row["epoch"], f"{float(row['train_loss']):.3f}",
                              f"{float(row['val_loss']):.3f}", f"{train_f1:.1%}",
                              f"{val_f1:.1%}", f"{train_f1-val_f1:+.1%}"]
                    epoch_table.rows.append(ft.DataRow(cells=[ft.DataCell(ft.Text(value)) for value in values]))
                config_path = run / "config.json"
                config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
                verdict.value, explanation.value = assessment(rows, baseline, config)
                verdict.color = "#B45309" if "học vẹt" in verdict.value and "Chưa" not in verdict.value else "#315B49"
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                pass
        final_path = run / "final_metrics.json"
        if final_path.is_file():
            try:
                final = json.loads(final_path.read_text(encoding="utf-8"))
                test = final["test_metrics"]
                lines = [f"Checkpoint tốt nhất: epoch {final['best_epoch']}; validation macro-F1 {final['best_val_macro_f1']:.1%}",
                         f"Test accuracy: {test.get('accuracy', test.get('subset_accuracy', 0)):.1%}; test macro-F1: {test['macro_f1']:.1%}",
                         "Từng lớp (precision / recall / F1):"]
                for name, values in test.get("per_class", {}).items():
                    lines.append(f"• {name}: {values['precision']:.1%} / {values['recall']:.1%} / {values['f1']:.1%}")
                metrics.value = "\n".join(lines)
                if baseline:
                    config = json.loads((run / "config.json").read_text(encoding="utf-8"))
                    previous = active.get("metrics", {}).get("test_metrics", {})
                    basis = comparison_basis(baseline, config)
                    if basis and previous.get("macro_f1") is not None:
                        delta = test["macro_f1"] - previous["macro_f1"]
                        evidence = ("cùng ảnh và nhãn val/test theo fingerprint" if basis == "fingerprint"
                                    else "cùng manifest" if basis == "manifest"
                                    else "cùng danh sách đường dẫn và nhãn val/test")
                        metrics.value += f"\nSo với model đang dùng ({evidence}): test macro-F1 {delta:+.1%}."
                        if basis == "same-rows":
                            metrics.value += " Chưa có hash ảnh val/test của run cũ để xác nhận nội dung ảnh không đổi."
                        declines = []
                        for name, values in test.get("per_class", {}).items():
                            old = previous.get("per_class", {}).get(name, {})
                            if isinstance(old, dict) and old.get("recall") is not None:
                                change = values["recall"] - old["recall"]
                                if change <= -0.05:
                                    declines.append(f"{name} {change:+.1%}")
                        if declines:
                            metrics.value += "\nRecall giảm từ 5 điểm % ở: " + ", ".join(declines) + "."
                    else:
                        metrics.value += "\nChưa đủ điều kiện so sánh trực tiếp với model đang dùng."
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                pass
        page.update()

    def work(dry_run: bool) -> None:
        try:
            args = arguments()
            python = torch_python() if not dry_run else Path(sys.executable)
            if not python:
                raise RuntimeError("Chưa tìm thấy Python có PyTorch và torchvision để train.")
            if not TRAINER.is_file():
                raise RuntimeError("Thiếu ml_workspace/train_model.py.")
            run = None
            if not dry_run:
                RUNS.mkdir(parents=True, exist_ok=True)
                run = RUNS / ("dacn_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
                args.extend(["--output-dir", str(run)])
            logs_dir = RUNS / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            log_path = logs_dir / ("check_" if dry_run else "train_")
            log_path = log_path.with_name(log_path.name + datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".log")
            command = [str(python), "-u", str(TRAINER), *args]
            if dry_run:
                command.append("--dry-run")
            running["run"] = run
            status.value = ("Đang kiểm tra dữ liệu…" if dry_run else "Đang huấn luyện; model đang dùng chưa thay đổi.") + f" Log: {log_path}"
            page.update()
            with log_path.open("w", encoding="utf-8") as log_stream:
                process = subprocess.Popen(command, cwd=ROOT, stdout=log_stream,
                                           stderr=subprocess.STDOUT)
            running["process"] = process
            while process.poll() is None:
                log.value = log_path.read_text(encoding="utf-8", errors="replace")[-22000:]
                refresh()
                time.sleep(0.6)
            result = process.wait()
            log.value = log_path.read_text(encoding="utf-8", errors="replace")[-22000:]
            refresh()
            if dry_run and result == 0:
                checks = "\n".join(line for line in log.value.splitlines()
                                   if line.startswith(("Manifest valid:", "Split counts:", "Leakage checks:")))
                summary.value = (summary.value + "\n" + checks).strip()
            status.value = ("Kiểm tra dữ liệu đạt." if dry_run else "Train hoàn tất; hãy xem metric trước khi kích hoạt model.") if result == 0 else f"Tiến trình dừng với mã {result}. Xem nhật ký."
        except Exception as exc:
            status.value = f"Lỗi: {exc}"
        finally:
            running["process"] = None
            check_button.disabled = False
            train_button.disabled = False
            stop_button.disabled = True
            page.update()

    def launch(dry_run: bool) -> None:
        if running["process"] is not None or train_button.disabled:
            return
        try:
            arguments()
        except ValueError as exc:
            status.value = str(exc)
            page.update()
            return
        check_button.disabled = True
        train_button.disabled = True
        stop_button.disabled = False
        log.value = ""
        metrics.value = ""
        epoch_table.rows = []
        page.update()
        threading.Thread(target=work, args=(dry_run,), daemon=True).start()

    def stop(_):
        process = running["process"]
        if process and process.poll() is None:
            process.terminate()
            status.value = "Đã yêu cầu dừng. Run chưa hoàn tất sẽ không xuất hiện trong danh sách model."
            page.update()

    check_button.on_click = lambda _: launch(True)
    train_button.on_click = lambda _: launch(False)
    stop_button.on_click = stop

    for dropdown in (model, label_mode, device):
        dropdown.color = INK
        dropdown.label_style = ft.TextStyle(color=INK, size=14)
        dropdown.filled = True
        dropdown.fill_color = PAPER
        dropdown.border_color = LINE
        dropdown.focused_border_color = ACCENT

    def note(value):
        return ft.Text(value, size=14, color=MUTED, selectable=True)

    def section(title, subtitle, content):
        return ft.Container(
            bgcolor=PAPER, border_radius=14, padding=22,
            border=ft.border.all(1, "#D5E2D9"),
            content=ft.Column([
                ft.Text(title, size=19, weight=ft.FontWeight.BOLD, color=INK),
                note(subtitle), *content,
            ], spacing=14),
        )

    def label(value):
        return ft.Text(value, size=14, weight=ft.FontWeight.BOLD, color=INK)

    def description(value):
        return ft.Text(value, size=13, color=MUTED, selectable=True)

    def path_row(control, button, title, meaning):
        return ft.Column([
            label(title),
            ft.Row([control, button], wrap=True, spacing=10,
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
            description(meaning),
        ], spacing=6)

    def parameter(key):
        spec = next(item for item in FIELDS if item[0] == key)
        return ft.Container(
            width=280,
            content=ft.Column([
                label(spec[1]),
                controls[key],
                description(spec[3]),
            ], spacing=6),
        )

    def parameter_row(keys):
        return ft.Row([parameter(key) for key in keys], wrap=True,
                      spacing=16, run_spacing=28,
                      vertical_alignment=ft.CrossAxisAlignment.START)

    def choice(control, title, meaning):
        control.label = None
        return ft.Container(width=280, content=ft.Column([
            label(title), control, description(meaning),
        ], spacing=6))

    def switch_choice(control, meaning):
        return ft.Container(width=330, content=ft.Column([
            control, description(meaning),
        ], spacing=5))

    basic_keys = ("epochs", "head-epochs", "batch-size", "image-size", "early-stopping-patience")
    advanced_keys = ("num-workers", "head-lr", "finetune-lr", "weight-decay", "seed", "multilabel-threshold")
    augment_keys = ("rotation-degrees", "horizontal-flip-probability", "brightness-jitter",
                    "contrast-jitter", "saturation-jitter")
    advanced = ft.ExpansionTile(
        title=ft.Text("Thông số nâng cao", size=16, weight=ft.FontWeight.BOLD, color=INK),
        subtitle=note("Learning rate, seed, ngưỡng đa nhãn và tăng cường ảnh"),
        initially_expanded=False,
        controls=[ft.Container(
            padding=ft.padding.symmetric(horizontal=12, vertical=18),
            content=ft.Column([
                label("Tối ưu và ngưỡng dự đoán"),
                parameter_row(advanced_keys),
                label("Biến đổi ảnh train"),
                parameter_row(augment_keys),
                ft.Container(
                    bgcolor="#EFF6F1", border_radius=8, padding=14,
                    content=description(
                        "Thông số cố định: Adam; CrossEntropyLoss cho một nhãn hoặc BCEWithLogitsLoss "
                        "cho đa nhãn. Ảnh được chuẩn hóa theo ImageNet; checkpoint được chọn bằng validation macro-F1."
                    ),
                ),
            ], spacing=24),
        )],
    )

    page.add(
        ft.Container(
            bgcolor=INK, border_radius=14, padding=24,
            content=ft.Column([
                ft.Text("HUẤN LUYỆN AI", size=26, weight=ft.FontWeight.BOLD, color=PAPER),
                ft.Text("Chọn dữ liệu → kiểm tra → train → đọc kết quả. Run mới chỉ được dùng khi admin kích hoạt.",
                        size=15, color="#E8F5EC"),
            ], spacing=6),
        ),
        section("Model đang dùng", "Mốc tham khảo trước khi tạo run mới", [
            note(
                (f"{active['name']} · validation macro-F1 "
                 f"{float(active['metrics'].get('best_val_macro_f1') or 0):.1%} · test macro-F1 "
                 f"{float(active['metrics'].get('test_metrics', {}).get('macro_f1') or 0):.1%}. "
                 "Chỉ kết luận hơn/kém khi tập đánh giá tương thích.")
                if active else "Chưa có model đang dùng để đối chiếu."
            ),
        ]),
        section("1. Chọn dữ liệu", "Có thể chọn file thủ công hoặc lấy manifest mới nhất do ứng dụng tạo", [
            path_row(manifest, browse_manifest, "Manifest CSV",
                     "Quy định ảnh nào thuộc train, validation và test; chứa nhãn và group_id để kiểm tra rò rỉ dữ liệu."),
            path_row(image_root, browse_images, "Thư mục gốc ảnh",
                     "Nơi chứa các ảnh mà cột relative_path trong manifest tham chiếu tới. Chọn sai thư mục sẽ không đọc được ảnh."),
            path_row(classes_file, browse_classes, "Class map JSON",
                     "Danh sách tên lớp theo đúng thứ tự đầu ra của model; nhãn trong manifest phải thuộc danh sách này."),
            ft.Row([newest_button, build_button], wrap=True, spacing=10),
            summary,
        ]),
        section("2. Cấu hình train", "Các thông số thường dùng ở đây; mở phần nâng cao khi cần điều chỉnh thêm", [
            ft.Row([
                choice(model, "Kiến trúc model", "Chọn backbone để train một model mới trong mỗi run."),
                choice(label_mode, "Kiểu nhãn", "Một bệnh/ảnh dùng softmax; đa nhãn dùng sigmoid cho từng bệnh."),
                choice(device, "Thiết bị train", "Tự chọn GPU nếu có CUDA, hoặc ép chạy CPU/GPU."),
            ], wrap=True, spacing=16, run_spacing=24, vertical_alignment=ft.CrossAxisAlignment.START),
            ft.Row([
                switch_choice(pretrained, "Dùng weights ImageNet làm điểm khởi đầu; có thể cần tải về lần đầu."),
                switch_choice(augmentation, "Chỉ biến đổi ảnh train để model gặp nhiều cách chụp hơn."),
            ], wrap=True, spacing=20, run_spacing=20, vertical_alignment=ft.CrossAxisAlignment.START),
            parameter_row(basic_keys),
            advanced,
        ]),
        section("3. Kết quả và quyết định", "Train tốt hơn chưa đủ; hãy xem validation và từng lớp trên test", [
            ft.Row([check_button, train_button, stop_button], wrap=True, spacing=10),
            status,
            ft.Container(bgcolor="#EAF4ED", border_radius=10, padding=16,
                         content=ft.Column([verdict, explanation], spacing=5)),
            ft.Row([epoch_table], scroll=ft.ScrollMode.AUTO),
            metrics,
            ft.ExpansionTile(title=ft.Text("Nhật ký kỹ thuật", color=INK, weight=ft.FontWeight.BOLD),
                             subtitle=note("Mở khi cần xem lỗi hoặc đường dẫn output"), initially_expanded=False,
                             controls=[log]),
        ]),
    )


if __name__ == "__main__":
    ft.app(target=main)
