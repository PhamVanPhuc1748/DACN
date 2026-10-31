# PigSkin Research Studio — Desktop (Flet + SQLite)

## Cài đặt & chạy

```bash
cd PigSkinStudioApp
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python main.py
```

Lần đầu chạy, app tạo `pig_skin.db` tại `E:\code\PigSkinResearchStudio\` (nếu thư mục tồn tại, nếu không thì cạnh `main.py`)
và nạp **dữ liệu mẫu** 2.017 ảnh (1.576 / 240 / 201) cùng run `20261028_190505`.
Tên lớp và chỉ số từng lớp trong dữ liệu mẫu là giả lập; chỉ số tổng của run lấy từ run thật.

Đổi đường dẫn bằng biến môi trường: `PIGSKIN_ROOT`, `PIGSKIN_DB`.

## Nạp dữ liệu thật

Màn hình **Dataset** → khối *Importer 6 bước*:
1. Kiểm tra 4 đường dẫn (manifest.csv, classes.json, thư mục ảnh gốc, thư mục run).
2. Tick “Xóa toàn bộ dữ liệu hiện có” ở lần nạp đầu để thay dữ liệu mẫu.
3. Bấm **Chạy nạp dữ liệu**. Lỗi giữa chừng → rollback, CSDL không đổi.

Nhãn từ manifest luôn vào `pending`; nhãn đã duyệt được giữ khi nạp lại.

## Cấu trúc

```
config.py                    đường dẫn, số liệu chuẩn, ngưỡng, bảng màu
database/schema.py           10 bảng + 3 index (đúng tài liệu thiết kế)
database/db_manager.py       truy vấn an toàn, checklist, mock seeder
database/seed_importer.py    importer 6 bước
components/                  metric_card, status_badge, confidence_bars (+ tiện ích trong __init__)
services/predictor.py        suy luận MobileNetV2 (torch) hoặc chế độ demo; cắt khung hình video
views/                       5 màn hình
main.py                      NavigationRail + điều hướng
```

## Dự đoán

- Có `torch` + `torchvision` và checkpoint tồn tại → chạy model thật; thứ tự lớp lấy từ `config_json["classes"]`.
- Không có → **chế độ demo** (điểm giả lập, mặc định không lưu vào CSDL).
- Video cần `opencv-python`.
- Khung xác nhận chuyên gia không bao giờ điền sẵn `actual_class_id`. CSDL từ chối `confirmed` khi nhãn thật khác lớp dự đoán,
  và từ chối `incorrect` khi nhãn thật trùng lớp dự đoán.
