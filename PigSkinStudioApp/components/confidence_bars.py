"""components/confidence_bars.py — 10 thanh ProgressBar thể hiện prediction_scores.

Hiệu ứng: mỗi ProgressBar luôn đầy (value=1) nhưng có width = 0 lúc đầu và animate_size;
sau lần render đầu, width được đặt = track_width * score → thanh "trượt" mượt từ 0 lên điểm số thật.
"""
from __future__ import annotations

import time

import flet as ft

import config
from components import safe_update

AMBER = "#E0A030"


class ConfidenceBars(ft.Column):
    def __init__(self, track_width: int = 300, close_margin: float = config.CLOSE_SCORE_MARGIN):
        super().__init__(spacing=10)
        self.track_width = track_width
        self.close_margin = close_margin
        self._warning = ft.Container(visible=False)
        self._rows = ft.Column(spacing=8)
        self._empty = ft.Text("Chưa có kết quả. Chọn run, nạp ảnh rồi bấm “Chạy dự đoán”.",
                              size=12, color=ft.Colors.ON_SURFACE_VARIANT, italic=True)
        self.controls = [self._warning, self._rows, self._empty]

    # ------------------------------------------------------------------
    def clear(self) -> None:
        self._rows.controls.clear()
        self._warning.visible = False
        self._empty.visible = True
        safe_update(self)

    def set_scores(self, scores: list[dict], animate: bool = True) -> None:
        """scores: [{class_id, code, name_vi, score}] — không cần sắp xếp trước. Gọi được từ thread nền."""
        ordered = sorted(scores, key=lambda s: s["score"], reverse=True)
        self._empty.visible = not ordered
        self._rows.controls.clear()
        if not ordered:
            self._warning.visible = False
            safe_update(self)
            return

        top = ordered[0]["score"]
        second = ordered[1]["score"] if len(ordered) > 1 else 0.0
        is_close = (top - second) < self.close_margin
        close_ids = {s["class_id"] for s in ordered if top - s["score"] < self.close_margin}

        bars: list[tuple[ft.ProgressBar, float]] = []
        for rank, s in enumerate(ordered):
            is_top = rank == 0
            in_close = is_close and s["class_id"] in close_ids
            color = AMBER if in_close else (ft.Colors.PRIMARY if is_top else ft.Colors.with_opacity(0.55, ft.Colors.PRIMARY))
            bar = ft.ProgressBar(
                value=1.0, width=0, bar_height=12 if is_top else 9, color=color,
                bgcolor=ft.Colors.TRANSPARENT, border_radius=6,
                animate_size=ft.Animation(700 + rank * 60, ft.AnimationCurve.EASE_OUT_CUBIC),
            )
            bars.append((bar, s["score"]))
            label = s.get("name_vi") or s["code"]
            self._rows.controls.append(
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=10, vertical=6),
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.10, AMBER if in_close else ft.Colors.PRIMARY) if is_top else None,
                    border=ft.border.all(1, ft.Colors.with_opacity(0.4, color)) if is_top else None,
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Row([
                                        ft.Icon(ft.Icons.EMOJI_EVENTS if is_top else ft.Icons.CIRCLE, size=16 if is_top else 8,
                                                color=color),
                                        ft.Text(label, size=13 if is_top else 12,
                                                weight=ft.FontWeight.W_700 if is_top else ft.FontWeight.W_400),
                                        ft.Text(s["code"], size=11, color=ft.Colors.ON_SURFACE_VARIANT,
                                                font_family=config.MONO_FONT),
                                    ], spacing=6, tight=True),
                                    ft.Text(f"{s['score'] * 100:5.1f}%", size=13 if is_top else 12,
                                            weight=ft.FontWeight.W_700 if is_top else ft.FontWeight.W_500,
                                            font_family=config.MONO_FONT),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Container(  # track
                                width=self.track_width, height=12 if is_top else 9, border_radius=6,
                                bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE),
                                alignment=ft.alignment.center_left,
                                content=bar,
                            ),
                        ],
                        spacing=4,
                    ),
                )
            )

        if is_close:
            names = ", ".join((s.get("name_vi") or s["code"]) for s in ordered if s["class_id"] in close_ids)
            self._warning.content = ft.Row(
                [ft.Icon(ft.Icons.WARNING_AMBER, color=AMBER, size=18),
                 ft.Text(f"Model phân vân: chênh lệch top-1/top-2 chỉ {(top - second) * 100:.1f} điểm % "
                         f"(< {self.close_margin * 100:.0f}). Các lớp sát nhau: {names}. Cần chuyên gia xem kỹ.",
                         size=12, color=AMBER, expand=True)],
                spacing=8,
            )
            self._warning.padding = 10
            self._warning.border_radius = 8
            self._warning.bgcolor = ft.Colors.with_opacity(0.12, AMBER)
            self._warning.border = ft.border.all(1, ft.Colors.with_opacity(0.45, AMBER))
            self._warning.visible = True
        else:
            self._warning.visible = False

        safe_update(self)
        if animate:
            time.sleep(0.06)  # để frame width=0 kịp render rồi mới tăng width → có hiệu ứng trượt
        for bar, score in bars:
            bar.width = max(2.0, self.track_width * float(score))
        safe_update(self)
