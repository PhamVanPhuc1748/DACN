# Khảo sát hiện trạng repo

Ngày khảo sát: 2026-10-22. Đây là snapshot quan sát được; không khẳng định model đã train hay benchmark đã chạy.

## Repo và ứng dụng

- Backend: FastAPI trong `backend/app/main.py`; nhận ảnh đơn/lô, lưu hồ sơ, phản hồi và xuất file. SQLite đang có `diagnostic_records` và `doctor_feedbacks`; chưa thấy migration framework, bảng farms/pens/cameras/users, quyền theo farm hay outbox.
- Dự đoán hiện tại **mô phỏng**: `_demo_disease_code` suy mã lớp từ tên file và gán confidence hằng số. Response có ghi `Mô phỏng theo tên tệp · chưa nạp mô hình AI`.
- Endpoint `/models` báo `inference_ready: false`; `ml_workspace/weights` rỗng. Chưa có model loader trong backend.
- Frontend là React + Vite; có các màn hình phân tích, lịch sử, hướng dẫn bệnh và model. Chưa thấy video playback, SSE, hay camera worker.
- GUI train và các script train/audit/split đã được chuyển ra `E:\code\PigSkinResearchStudio`; thư mục đó có pipeline train độc lập. Repo DACN chỉ giữ vùng `ml_workspace/weights` mà backend tham chiếu.
- Repo đang có thay đổi cục bộ chưa commit tại thời điểm khảo sát, gồm sửa đổi backend/frontend, `backend/pigskin.db` và brief này. Các file đó được đọc như trạng thái hiện tại và không bị ghi đè bởi khảo sát.

## Môi trường đã quan sát

- Python hệ thống 3.11.9. Môi trường `.venv`/`venv` Python 3.11.9 có FastAPI, Pillow và OpenCV; chưa có `torch`, `torchvision` hoặc `ultralytics`.
- `nvidia-smi` thấy NVIDIA GeForce RTX 4050 Laptop GPU, VRAM 6 GiB; PyTorch/CUDA chưa cài nên chưa xác nhận được khả năng sử dụng từ Python.
- Requirements chưa khóa versions; các requirements gốc gồm thêm packages không dùng trực tiếp trong backend. Không có dependency lock Python.

## Dữ liệu

- `data/processed`: 7.599 ảnh, đều đọc được, RGB 224×224. Trong đó có các thư mục `pig-skin-v4-clean` (6.796), `pig-skin-v4-review` (203), nhiều thư mục nhãn/nhãn ghép và `Unlabeled`.
- Audit CSV có sẵn gồm 6.999 dòng; SHA-256 khớp với 6.796 ảnh clean và 203 ảnh review. Báo cáo này chưa coi CSV đó là split đã duyệt: nó bao gồm cả review, và các đường dẫn trong CSV cần gắn root `pig-skin-v4-clean` hoặc dò sang `pig-skin-v4-review` mới khớp.
- `data/raw` có 737 ảnh RGB 650×650 trong export YOLOv8, cùng `data.yaml` 4 lớp (Erysipelas, Greasy Pig, Healthy, Sarcoptic Mange). Hai archive hiện có: một export classification v4 gồm 2.037 ảnh và một archive YOLO. Nội dung archive chỉ được liệt kê/đếm; không giải nén hay thay đổi.
- Chưa thấy video (`VIDEO_DATA_UNAVAILABLE`), manifests trong `data/splits`, artifacts trong `ml_workspace/weights` hoặc `models`.
- Chi tiết kiểm toán, duplicate và giới hạn nằm trong [`dataset_report.md`](dataset_report.md). Các bản CSV/JSON audit nằm dưới `data/reports/` (đường dẫn data bị `.gitignore` bỏ qua).

## Rủi ro / thiếu hụt so với brief

1. Nhiều nguồn dữ liệu, taxonomy và task khác nhau (classification 10 lớp, multi-label folder names, YOLO 4 lớp); chưa có quyết định nguồn chuẩn.
2. Không có video nên chưa thể kiểm chứng ROI, độ trễ, false alerts/video-hour hay tính phù hợp với ảnh ngoài thực địa.
3. 203 ảnh trong thư mục review và near-duplicate candidates cần người xem duyệt; không tự động bỏ.
4. App hiện tại chưa đáp ứng MVP realtime, quyền dữ liệu theo farm hoặc event workflow; demo prediction không phải inference AI.
5. Chưa thể đánh giá baseline hoặc chất lượng mô hình vì chưa xác nhận nhãn/split và chưa có dependency/model artifacts.
