"""Render the reliability diagram from the audit's validation CSV files."""
import argparse
import csv
import html
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("results", type=Path, help="Directory holding the validation audit CSV files")
out = parser.parse_args().results
def read(name):
    with (out / (name + ".csv")).open(encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))

validation = read("validation-metrics")
bins = read("validation-reliability-bins")
names = {
    "20261029_161050": "MobileNetV2 20261029_161050",
    "20261103_125653": "MobileNetV2 20261103_125653",
    "20261103_125004": "EfficientNet-B0 20261103_125004",
    "rf_v1_conservative_baseline_01": "MobileNetV2 RF baseline",
    "rf_v1_efficientnet_b0_baseline_01": "EfficientNet-B0 RF E01",
    "rf_v1_efficientnet_b0_E03_ls01": "EfficientNet-B0 RF E03",
    "rf_v1_efficientnet_b0_E06_ls01_adamw": "EfficientNet-B0 RF E06",
    "rf_v1_E07-A": "Ensemble RF E07-A",
}
model_order = list(names)
valid = {row["model"]: row for row in validation}
parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="680" viewBox="0 0 1120 680" role="img" aria-labelledby="title desc">',
         '<title id="title">Reliability diagram trên validation</title>',
         '<desc id="desc">Tám biểu đồ. Đường chéo là hiệu chỉnh lý tưởng. Kích thước điểm tăng theo số ảnh trong bin.</desc>',
         '<rect width="1120" height="680" fill="#fff"/>',
         '<g font-family="Segoe UI, Arial, sans-serif" fill="#0f172a">',
         '<text x="30" y="38" font-size="25" font-weight="bold">Reliability diagram trên validation</text>',
         '<text x="30" y="63" font-size="14">15 bin cùng độ rộng · Bỏ bin rỗng · Điểm lớn hơn khi bin có nhiều ảnh · Đường chéo là hiệu chỉnh lý tưởng</text>']
def line(x1, y1, x2, y2, color, extra=""):
    parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" {extra}/>')

for index, model in enumerate(model_order):
    x = 55 + index % 4 * 274
    y = 315 + index // 4 * 295
    width, height = 185, 175
    color = "#2563eb" if index < 3 else "#047857"
    parts.append(f'<text x="{x-19}" y="{y-206}" font-weight="bold" font-size="13">{html.escape(names[model])}</text>')
    count, ece = valid[model]["n"], float(valid[model]["ece"])
    parts.append(f'<text x="{x-19}" y="{y-188}" font-size="11" fill="#475569">n = {count} · ECE = {ece:.2%}</text>')
    for val in (0, .25, .5, .75, 1):
        xx, yy = x + width * val, y - height * val
        line(xx, y, xx, y - height, "#e2e8f0")
        line(x, yy, x + width, yy, "#e2e8f0")
        if val in (0, .5, 1):
            parts.append(f'<text x="{xx}" y="{y+15}" text-anchor="middle" font-size="10">{val:g}</text>')
            parts.append(f'<text x="{x-7}" y="{yy+4}" text-anchor="end" font-size="10">{val:g}</text>')
    line(x, y, x + width, y - height, "#64748b", 'stroke-dasharray="5 5"')
    line(x, y, x + width, y, "#64748b")
    line(x, y, x, y - height, "#64748b")
    for row in bins:
        if row["model"] != model or not int(row["n"]):
            continue
        n = int(row["n"])
        acc, conf = float(row["accuracy"]), float(row["mean_confidence"])
        parts.append(f'<circle cx="{x+width*conf:.2f}" cy="{y-height*acc:.2f}" r="{2+8*(n/int(count))**.5:.2f}" fill="{color}" fill-opacity="0.8" stroke="#fff"><title>n={n}, Softmax={conf:.2%}, accuracy={acc:.2%}</title></circle>')
    parts.append(f'<text x="{x+width/2}" y="{y+34}" font-size="12" text-anchor="middle">Softmax top-1 trung bình</text>')
    parts.append(f'<text x="{x-30}" y="{y-height/2}" font-size="11" text-anchor="middle" transform="rotate(-90 {x-30} {y-height/2})">Tỷ lệ đúng</text>')
parts.append("</g></svg>")
(out / "reliability-diagram.svg").write_text("\n".join(parts) + "\n", encoding="utf-8")
