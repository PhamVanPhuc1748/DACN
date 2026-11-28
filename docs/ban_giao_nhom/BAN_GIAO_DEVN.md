# Bàn giao PigSkinTech trên devN

## Nguồn và phạm vi

- Nguồn `origin/devP` tại `d9d8c3181b9a816bf4b8033d6dec8b0db54e78ec`.
- Đích `origin/devN` có commit gốc `628668855241386129b119e9e500af77a3b68140`. Commit thay thế được tạo trên `handoff/devn-full-project` với commit gốc này làm cha.
- Nhánh sao lưu cục bộ `backup/devN-before-devP-replacement` trỏ đến commit gốc. Lịch sử devN được bảo toàn bằng cập nhật fast-forward.
- Kiểm kê devP gồm giao diện Flet, đăng nhập local và Google OAuth, Farmer, Admin, Expert, profile, chatbot, SQLite và SQL Server, cửa sổ training, clinical widgets, quản lý model, theme, backend FastAPI, CLIP gate, mô hình đóng gói và tài liệu. Năm ảnh demo và ảnh nền đăng nhập giữ nguyên bytes và được đặt trong `PigSkinTech/assets/demo/`.
- Loại frontend React, `src/api`, `src/ui`, trainer cũ `ml_workspace/src`, các lớp dịch vụ, OTP, worker, công cụ đóng gói và giao diện chỉ thuộc devN cũ. Backend FastAPI của Phúc và worker suy luận của Phúc thuộc cây devP.
- Cây bàn giao loại DB runtime, ca khám, ảnh curate phát sinh khi sử dụng, cache, venv và raw dataset. Các tài khoản demo dùng mật khẩu bootstrap trong cấu hình local. SQL schema và cấu hình mẫu được giữ trong Git.

## Kết quả đối chiếu artifact

Các cột tính theo phần trăm. E01–E06 dùng `best_validation.json`, E01–E02 dùng `final_metrics.json` cho test. E03 và E06 dùng đánh giá cùng E09. E07–E09 dùng CSV so sánh đã lưu. Xem [artifact E01–E09](roboflow_experiments/) và [danh mục run cùng checkpoint SHA-256](roboflow_experiments/index.json).

| ID | Thí nghiệm | Val Accuracy | Val Macro-F1 | Test Accuracy | Test Macro-F1 |
| --- | --- | ---: | ---: | ---: | ---: |
| E01 | MobileNetV2 | 75.18 | 74.96 | 71.87 | 72.08 |
| E02 | EfficientNet-B0 baseline | 76.97 | 76.94 | 75.41 | 75.21 |
| E03 | EfficientNet-B0, Adam, label smoothing 0.1, epoch 28 | 78.1623 | 78.3718 | 76.1229 | 76.0570 |
| E04 | Fine-tune LR 5e-5 | 77.21 | 77.09 | Bỏ qua | Bỏ qua |
| E05 | Cosine annealing | 77.45 | 77.34 | Bỏ qua | Bỏ qua |
| E06 | EfficientNet-B0, AdamW, label smoothing 0.1, epoch 18 | 78.2816 | 78.1556 | 76.1229 | 76.1079 |
| E07 | Ensemble E07-A, 665/838 | 79.36 | 79.47 | Đánh giá ở E09 | Đánh giá ở E09 |
| E08 | TTA flip, cấu hình E08-C tốt nhất | 78.76 | 78.79 | Bỏ qua | Bỏ qua |
| E09 | Test của E07-A đã chốt theo validation | 79.36 | 79.47 | 76.5957 | 76.4107 |

E09 phân loại đúng 324/423, sai 99/423, gồm 6 ảnh heo bệnh được dự đoán Healthy. Chốt trọng số E07-A từ validation, 0.5 cho softmax E03 và 0.5 cho softmax E06. TTA tắt. Điểm softmax dùng để xếp hạng, chưa được hiệu chuẩn cho chẩn đoán.

## Model registry và tái lập

| Model | Thư mục dưới `PigSkinTech/models/runs` | Artifact tải |
| --- | --- | --- |
| Ba model có sẵn từ devP | `20261029_161050`, `20261103_125004`, `20261103_125653` | `best_model.pt` trong từng run |
| E01 | `rf_v1_conservative_baseline_01` | `best_model.pt` |
| E02 | `rf_v1_efficientnet_b0_baseline_01` | `best_model.pt` |
| E03 | `rf_v1_efficientnet_b0_E03_ls01` | `best_model.pt` |
| E06 | `rf_v1_efficientnet_b0_E06_ls01_adamw` | `best_model.pt` |
| E07-A | `rf_v1_E07-A` | `ensemble.json`, chỉ tới hai checkpoint E03/E06 |

Checkpoint dùng RGB, resize 224×224, ImageNet normalization, thứ tự 10 lớp theo config, `torch.load(weights_only=True)` và `strict=True`. Registry đọc dataset, phiên bản và metric của run. E03 là lựa chọn nhẹ. E07-A là ứng viên nghiên cứu có validation Macro-F1 tốt nhất. Bản bàn giao tiếp tục dùng `20261103_125653` làm mặc định của Phúc. Admin có thể kích hoạt E03 hoặc E07-A sau khi chọn và xem metric của model.

Một lượt thử forward + softmax trên ảnh demo đo được E03 20,87 ms CPU và 25,78 ms CUDA, E07-A 51,33 ms CPU và 38,01 ms CUDA. Các số này là phép đo từng lượt trong smoke test, loại thời gian tải checkpoint và CLIP. Một lượt qua `predict()` với CLIP trả về timing bộ phân loại 81,0 ms CPU.

Roboflow Pig Skin Disease Single Label v4 gồm 4.413 ảnh, train 3.152, validation 838, test 423. Manifest đã đóng băng và class mapping nằm tại `ml_workspace/manifests/rf_v1_conservative`.

- Manifest SHA-256 `d07aa8d72568457ae5ab97c1b9b1634111442cf6ab1af021edee77b9c2434300`.
- Class mapping SHA-256 `4a069a6fb036ffb8e23bf0aea0f39e8dafcdd680515d4e3f059abbbc59cf169e`.

Để tái lập offline dữ liệu, chỉ định thư mục ảnh Roboflow bằng `PIGSKIN_IMAGE_ROOT` cho ba script `evaluate_*.py`. Các script dùng checkpoint đóng gói hoặc đường dẫn `PIGSKIN_CHECKPOINT_RUNS`. Kết quả ghi vào `ml_workspace/runs` hoặc `PIGSKIN_EVAL_OUTPUT`. Dùng `ml_workspace/requirements.txt` cho nghiên cứu. Công cụ xử lý gồm dedupe, preview, audit, review và build manifest. Quá trình bàn giao giữ nguyên trọng số và số liệu gốc.

## Kiểm thử và giới hạn

| Kiểm tra | Trạng thái |
| --- | --- |
| Cú pháp Python, import entry point desktop, `pip check` môi trường desktop | PASS |
| Unit tests desktop 5 bài, công cụ Roboflow 2 bài | PASS |
| SQLite cô lập, đăng nhập ba role, đổi model, dự đoán lưu lịch sử, expert review | PASS, tầng dịch vụ |
| Load strict và inference cả tám lựa chọn trên CPU và CUDA, Top-3, softmax E07-A bằng trung bình E03/E06 | PASS |
| OpenCLIP với cache offline, ảnh heo mẫu được chấp nhận và ảnh trắng bị từ chối qua `predict()` | PASS |
| Ảnh nền đăng nhập và năm ảnh demo | PASS |
| Chatbot fallback khi thiếu API key | PASS, tầng dịch vụ |
| Entry point Flet, màn đăng nhập và dashboard Farmer, Expert, Admin với CSDL test | PASS, kết nối Flet giả lập |
| FastAPI startup, health, disease catalog and valid/invalid login | PASS, TestClient with two isolated SQLite databases |
| Ensemble worker subprocess | PASS, CPU |
| GUI desktop e2e, Google OAuth thật, nhà cung cấp chatbot từ xa, SQL Server thật | NOT RUN |

Kiểm thử CLIP ở lần bàn giao trước ghi nhận một ảnh da người qua gate. Giữ nguyên prompt và ngưỡng của Phúc. Dataset còn 1.260 quality flags, chưa xác minh nhãn toàn diện. Các kiểm tra exact/group không phát hiện cross-split leakage trong manifest đã dùng. Kết quả này có phạm vi giới hạn ở các kiểm tra đã chạy. Nghiên cứu dùng một seed. Test split đã được đánh giá ở E01/E02 và chưa có external validation. Final Test Accuracy chưa đạt 80%.

## Chạy fresh clone trên Windows

```powershell
git clone --branch devN https://github.com/PhamVanPhuc1748/DACN.git D:/DACN_devN
Set-Location D:/DACN_devN
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r PigSkinTech/requirements.txt -r PigSkinTech/requirements-clip.txt
Copy-Item PigSkinTech/.env.example PigSkinTech/.env
# Chon DATABASE_ENGINE=sqlite va dat PIGSKIN_DEMO_PASSWORD trong PigSkinTech/.env.
.\.venv\Scripts\python.exe run_app.py
```

OpenCLIP tải weights ở lần dùng đầu nếu cache trống. Các classifier nằm trong clone. Có thể chạy backend riêng trên loopback sau khi cài `backend/requirements.txt`. Cấu hình API và OAuth qua `PigSkinTech/.env` hoặc mẫu backend tương ứng.

Để smoke GUI, đăng nhập lần lượt Farmer, Expert và Admin bằng tài khoản trong README và mật khẩu demo đã cấu hình. Trong Admin chọn E03 rồi E07-A, thử ảnh demo trong Farmer, xem ba điểm cao nhất, lưu và mở lịch sử. Chuyển hồ sơ sang Expert để duyệt. Kiểm tra profile và chatbot trên giao diện theo cấu hình local.

## Kiểm tra Git

Trong clone devN sau push, `git rev-parse HEAD` cho biết commit chứa báo cáo này. Dùng `git ls-remote origin refs/heads/devN refs/heads/devP` để đối chiếu HEAD devN với clone và xác nhận HEAD devP. Commit cha của commit thay thế phải là `628668855241386129b119e9e500af77a3b68140`.
