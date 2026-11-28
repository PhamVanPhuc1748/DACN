# Bàn giao kỹ thuật PigSkinTech cho Phúc và Lâm

## Chạy ứng dụng và chọn model

Dùng `git clone -b devN https://github.com/PhamVanPhuc1748/DACN.git`. Với clone sạch đang ở `devN`, dùng `git pull --ff-only origin devN`.

Dùng PowerShell tại thư mục gốc. Môi trường ứng dụng và PyTorch tách riêng.

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r PigSkinTech/requirements.txt
py -3.10 -m venv .venv_train
.\.venv_train\Scripts\python.exe -m pip install torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cpu
$env:PIGSKIN_AI_PYTHON = (Resolve-Path .\.venv_train\Scripts\python.exe).Path
Push-Location PigSkinTech
..\.venv\Scripts\python.exe main.py
Pop-Location
```

Ứng dụng `devN` cần SQL Server LocalDB và ODBC Driver 17 hoặc 18 cho luồng tài khoản và hồ sơ. Dùng database đã cấu hình theo README của PigSkinTech. Việc tích hợp giữ nguyên xác thực, phân quyền và duyệt chéo. Sau khi đăng nhập, mở màn hình phân tích, chọn **MobileNetV2 — Roboflow Baseline 2026-11-28** tại **Checkpoint cho phiên phân tích** rồi chạy ảnh. Chọn **MobileNetV2 — 20261103_125653 (mặc định)** để chuyển lại. Điều khiển này chỉ áp dụng cho phiên hiện tại. Màn hình Model Operations cung cấp chỉ số tham khảo.

Run đóng gói tại [PigSkinTech/models/runs/rf_v1_conservative_baseline_01](../../PigSkinTech/models/runs/rf_v1_conservative_baseline_01). `best_model.pt` SHA-256 `1885e1f0b36e0a5ffbbf6c54d7a2749e18f43fd949afdbaf33a729f2b656db15`. Nạp theo đúng class mapping kèm checkpoint. Chỉ số `test_metrics` ghi một lượt đánh giá cuối. Confusion matrix có hàng nhãn thật và cột nhãn dự đoán. `history.csv` lưu dữ liệu từng epoch. Báo cáo tuần giải thích kết quả và phạm vi sử dụng.

## Tái lập audit và huấn luyện

Dùng Python 3.10 x64 và venv riêng cho train. Ví dụ dưới đây dành cho RTX 5060 và driver tương thích CUDA 13. Có thể chọn ổ có dung lượng trống cho venv, cache và output.

```powershell
py -3.10-64 -m venv .venv_train
$py = '.\.venv_train\Scripts\python.exe'
& $py -m pip install torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cu130
& $py -m pip install -r ml_workspace/requirements-roboflow.txt
& $py -m pip check
```

Dataset nằm ngoài Git, có cấu trúc `train/<class>/<image>`, `valid/<class>/<image>` và `test/<class>/<image>`. Lần chạy sau nên đặt tên output mới. Root lịch sử có `dedupe_images.py` và `preview_pairs_v3.py` để đọc được báo cáo cũ. Quy trình tái lập ưu tiên công cụ audit chỉ đọc trong `ml_workspace`. Với lệnh legacy, bỏ cờ `--apply` để chỉ xuất báo cáo.

```powershell
$images = Read-Host 'Đường dẫn dataset Roboflow'
$work = 'ml_workspace/runs/roboflow_review'
$audit = "$work/audit"
& $py ml_workspace/audit_roboflow.py --image-root $images --threshold 12 --output $audit
& $py ml_workspace/review_roboflow.py --image-root $images --audit $audit --decisions "$work/decisions.csv"
```

Audit tạo CSV nhóm, thành viên, cặp và contact sheet. Ưu tiên nhóm xuyên split và khác nhãn. Xem `indirect_pairs` để phát hiện nối chuỗi. Điền cùng `confirmed_group` cho ảnh đã xác nhận liên quan. Trạng thái Exclude cần lý do và chỉ có hiệu lực trong manifest. Có thể dùng `--include-quality` với một CSV quyết định mới để mở thêm cờ chất lượng. Công cụ review giữ được `review_pending.csv` của run cũ và dùng `similarity_review.csv` khi audit mới. Khi phát hiện ảnh cùng nguồn bằng phương pháp khác, bổ sung quyết định theo đường dẫn tương đối.

```powershell
& $py ml_workspace/build_roboflow_manifest.py --image-root $images --audit $audit --review "$work/decisions.csv" --output "$work/draft"
$manifest = "$work/draft/manifest_draft.csv"
$classes = "$work/draft/classes.json"
& $py ml_workspace/train_model.py --image-root $images --manifest $manifest --classes-file $classes --dry-run
```

Kiểm tra `split_changes.csv` và `excluded_from_manifest.csv` trước khi khóa split. Trainer kiểm tra SHA-256 và group ID xuyên split. Audit dHash là bước riêng. Để tái tạo đúng run đã công bố cần cùng bản xuất, ảnh giữ nguyên byte và cùng quyết định review. Manifest baseline SHA-256 `d07aa8d72568457ae5ab97c1b9b1634111442cf6ab1af021edee77b9c2434300`. Báo cáo đóng gói có dấu vân tay của từng split.

```powershell
$output = Join-Path (Read-Host 'Thư mục run trên ổ còn trống') (Get-Date -Format 'yyyyMMdd_HHmmss')
& $py ml_workspace/train_model.py --image-root $images --manifest $manifest --classes-file $classes `
  --model mobilenet_v2 --pretrained --device cuda --batch-size 16 --image-size 224 --seed 123 `
  --epochs 30 --head-epochs 5 --head-lr 0.001 --finetune-lr 0.0001 --weight-decay 0.0001 `
  --early-stopping-patience 12 --num-workers 0 --output-dir $output
```

Giữ `TORCH_HOME` ở ổ có đủ chỗ. Pilot dùng `--epochs 1 --head-epochs 0 --head-lr 0.0001 --skip-test`. `--skip-test` vẫn kiểm tra tính hợp lệ của manifest test. Công cụ ca chuyên gia của devP phụ thuộc kho hồ sơ devP và nằm ngoài phần tích hợp này. OpenCLIP là công cụ audit tùy chọn, tách khỏi luồng inference devN. Cài `PigSkinTech/requirements-clip.txt` và chuẩn bị cache trọng số trước khi chạy audit ngoại tuyến.

## Kiểm thử

Bản tích hợp devN đã chạy 88 unit test ứng dụng, 2 test công cụ ML, smoke inference CPU và render Flet cho user, expert, admin. Kiểm thử chuyển cũ → Roboflow → cũ chạy trong cùng worker và kiểm tra 10 điểm softmax. Test đăng nhập, hồ sơ và duyệt chéo dùng kết nối giả lập trong bộ test devN. Kiểm thử không kết nối LocalDB thật.

Phần tích hợp là commit chọn lọc trên lịch sử devN. Giữ luồng xác thực, OTP, phân quyền, lịch sử, duyệt chéo và runtime worker của devN. Checkpoint cũ được đóng gói từ artifact trùng SHA-256 đã ghi trong model manifest của devN. Tệp cấu hình runtime tìm Python theo đường dẫn tương đối hoặc biến môi trường.

```powershell
Push-Location PigSkinTech
..\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
..\.venv\Scripts\python.exe -B -m tests.flet_runtime_smoke --layout
Pop-Location
.\.venv_train\Scripts\python.exe -B -m unittest discover -s ml_workspace -p 'test_*.py' -v
```

Xem [báo cáo tuần](BAO_CAO_TUAN_NHOM_5_2026-11-28.md) về giới hạn dữ liệu. Không dùng chỉ số của hai run trên hai tập khác nhau để xếp hạng model. Dataset, cache, venv, DB runtime và ảnh ca khám giữ ngoài nội dung bàn giao.

### Kết quả smoke trên nền desktop devP

Phần dưới ghi lại QA của bản bàn giao nguồn. devN tiếp tục dùng runtime, workflow và LocalDB riêng. Test devN chạy trên dữ liệu giả lập độc lập với database thật, truy xuất đúng model qua cùng worker khi đổi phiên bản.

| Kiểm tra | Kết quả |
|---|---|
| Unit test ứng dụng | Tải checkpoint và inference JPEG/PNG, ảnh hỏng, thiếu checkpoint, config lỗi, giao diện sáng/tối. Ba tài khoản demo, chuyển bản cũ/mới, lưu lịch sử và thẩm định chạy với SQLite tạm. |
| Unit test ML | Kiểm tra nối chuỗi dHash, quyết định Pending, gom nhóm xuyên split, đường dẫn Unicode và round-trip CSV. |
| Suy luận thực | Checkpoint cũ và mới đều tải được. Bản mới sinh 10 xác suất hữu hạn, tổng xấp xỉ 1. Median 7 lượt forward đã làm nóng trên cùng ảnh mẫu là 24,44 ms CPU và 9,74 ms CUDA. Phép đo loại thời gian mở ứng dụng, chạy CLIP và nạp đầu tiên. |
| CLIP ngoại tuyến | Chấp nhận 5 ảnh heo mẫu, từ chối giày và cốc, từ chối đọc file lỗi và báo rõ khi giả lập thiếu OpenCLIP. Một ảnh da người bị chấp nhận (pig similarity 0,26299, margin 0,09061). Giữ nguyên ngưỡng. |
| Flet | Trang đăng nhập khởi tạo trong cửa sổ thử nghiệm, với SQLite tạm. Các luồng sau đăng nhập được kiểm tra ở tầng dịch vụ. Cần chạy lại thao tác GUI tương tác, tài khoản cấu hình OAuth/SQL Server thật và kiểm thử trên nhánh tích hợp. |

QA trong worktree thử cho thấy bản devP trước sửa mở DB ngay khi import `services.store`. Đã bỏ lần khởi tạo cấp module. Flet khởi tạo DB ở entry point và các hàm lưu trữ vẫn tự kiểm tra schema khi được gọi. Test mới kiểm tra import không đọc cấu hình DB.

Kiểm thử CLIP dùng ảnh công khai [giày trên Unsplash](https://images.unsplash.com/photo-1542291026-7eec264c27ff) và [cốc từ Pexels](https://www.pexels.com/photo/white-ceramic-mug-filled-with-coffee-beside-coffee-beans-678654/). Ca ảnh giày đại diện cho nhóm giày dép trong smoke. Trường hợp dép riêng chưa được đo vì nguồn ảnh trả HTTP 429. Bộ ca nhỏ này hỗ trợ phát hiện lỗi cụ thể. Với ảnh nghi ngoài phạm vi, cần kiểm tra nguồn và thẩm định thủ công trước khi sử dụng kết quả phân loại.
