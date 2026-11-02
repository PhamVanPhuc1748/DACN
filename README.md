# PigSkin AI Studio

Ứng dụng desktop phục vụ nghiên cứu và rà soát ảnh tổn thương da heo. Nhánh `devP` đưa giao diện Flet vào dự án, kết nối suy luận với checkpoint huấn luyện thật và đọc kết quả train từ các artifact của training workspace. Đây là công cụ nghiên cứu hỗ trợ người dùng; điểm số mô hình không thay thế kết luận của bác sĩ thú y.

## Phạm vi được đưa lên `devP`

- **Giao diện desktop:** các màn hình Tổng quan, Phân tích ảnh, Lịch sử, Dữ liệu, Huấn luyện và Mô hình; có giao diện sáng/tối, xem trước ảnh, thông tin hồ sơ và điểm nhấn minh họa vùng da.
- **Suy luận bằng checkpoint thật:** app tìm run hoàn chỉnh gần nhất, đọc cấu hình/lớp/chuẩn hóa từ run và gọi worker bằng Python có PyTorch. Hỗ trợ `mobilenet_v2`, `mobilenet_v3_large` và `efficientnet_b0`; hiện chỉ nhận checkpoint phân loại đơn nhãn.
- **Thông tin dữ liệu và đánh giá:** số lượng ảnh được đếm từ manifest; cấu hình và metric được đọc từ `config.json` và `final_metrics.json`. App đối chiếu SHA-256 manifest nếu run có lưu hash.
- **Hồ sơ cục bộ:** lịch sử ca và ảnh được lưu trên máy bằng SQLite và thư mục `PigSkinTech/case_images/`.
- **Tách môi trường huấn luyện:** mã train cũ trong `ml_workspace/src` đã được gỡ khỏi repo. Việc huấn luyện chạy trong training workspace riêng; app này đọc artifact để đánh giá và suy luận.

Không đưa dataset, trọng số, database cá nhân, ảnh ca bệnh hay tài liệu báo cáo/nghiên cứu đã tạo vào commit này. Backend API là luồng riêng và hiện chưa được nối với suy luận checkpoint thật của ứng dụng desktop; các thay đổi backend đang có trong working tree không thuộc commit này.

## Chạy ứng dụng trên Windows

Cài Python, tạo môi trường và cài các thư viện giao diện:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r PigSkinTech/requirements.txt
.\run_app.bat
```

`PigSkinTech/requirements.txt` chỉ cài Flet và Pillow. PyTorch/TorchVision cần được cài trong môi trường của training workspace theo đúng cấu hình CPU/CUDA của máy; app không tự cài các thư viện này.

## Kết nối training workspace

App cần một run hoàn chỉnh có cấu trúc tương tự:

```text
PigSkinResearchStudio/
├── .venv/Scripts/python.exe
└── ml_workspace/runs/<run-name>/
    ├── best_model.pt
    ├── config.json
    └── final_metrics.json
```

Trong PowerShell, đặt đường dẫn workspace trước khi mở app:

```powershell
$env:PIGSKIN_RESEARCH_ROOT = 'E:\code\PigSkinResearchStudio'
.\run_app.bat
```

`config.json` cần chứa danh sách lớp, tên kiến trúc và thông tin tiền xử lý tương ứng với checkpoint. Nếu đường dẫn không được đặt, app thử các vị trí mặc định trong thư mục `E:\code` và repo hiện tại. Khi không có run hợp lệ, app sẽ báo thiếu dữ liệu/checkpoint thay vì tạo số liệu thay thế.

## Đọc kết quả dự đoán

App hiển thị tối đa 5 lớp có điểm cao nhất. Điểm softmax là điểm số thô của mô hình, **chưa được hiệu chuẩn thành xác suất chẩn đoán**. Hãy dùng kết quả để rà soát nghiên cứu và nhờ người có chuyên môn xác minh.

## Các file chính

| File | Vai trò |
|---|---|
| `PigSkinTech/main.py` | Giao diện Flet và điều hướng các màn hình |
| `PigSkinTech/services/inference.py` | Kiểm tra ảnh, tìm run và gọi suy luận |
| `PigSkinTech/services/inference_worker.py` | Nạp checkpoint bằng PyTorch/TorchVision và trả điểm dự đoán |
| `PigSkinTech/services/project_data.py` | Đọc cấu hình, metric, manifest và thống kê run |
| `PigSkinTech/services/store.py` | Lưu hồ sơ và trạng thái rà soát cục bộ |
| `.gitignore` | Loại dataset, checkpoint, database và artifact cục bộ khỏi Git |
