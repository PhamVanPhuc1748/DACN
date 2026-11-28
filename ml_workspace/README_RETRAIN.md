# Huấn luyện AI từ ứng dụng DACN

Quản trị viên vào **Mô hình AI & Danh mục Bệnh lý** rồi chọn **Mở phòng huấn luyện AI**. Một cửa sổ Flet riêng sẽ mở. Cửa sổ dùng trainer `ml_workspace/train_model.py` từ PigSkin Research Studio; mỗi lần train tạo một thư mục mới trong `ml_workspace/runs/`. Run mới không tự kích hoạt.

## Dữ liệu

Manifest mẫu và class map nằm trong `ml_workspace/manifests/pig_skin_single_label_v4/`. Ảnh gốc vẫn được đọc từ `data/raw/Pig Skin Disease Single Label v4.v1-class-test.folder`. Cửa sổ tự chọn manifest mới nhất trong các nguồn đã biết; nút **Dùng manifest mới nhất** cập nhật lại lựa chọn này. Ba nút **Chọn CSV**, **Chọn thư mục** và **Chọn JSON** cho phép chọn dữ liệu thủ công. Khi chọn manifest có báo cáo đi kèm, thư mục gốc ảnh được điền theo báo cáo. Luôn bấm **Kiểm tra dữ liệu** trước khi train.

Chuyên gia có thể thẩm định ca và chọn **Đưa vào Dataset** trong màn hình của họ. Nút **Tạo manifest từ ca chuyên gia đã duyệt** tạo một manifest mới, thêm các ca này vào split train, bỏ qua SHA-256 trùng với ảnh đã có và giữ nguyên validation/test. Manifest mới và báo cáo nằm dưới `ml_workspace/runs/datasets/`, không sửa dữ liệu gốc. Group của ca mới dựa trên case ID vì hệ thống chưa lưu trang trại, con heo và phiên chụp. Vì vậy cần xem ảnh gần trùng và nguồn ảnh trước khi dùng kết quả cho báo cáo.

## Đọc kết quả

- **Train F1 cao, validation F1 thấp:** dấu hiệu model nhớ ảnh train nhưng khái quát kém.
- **Loss train giảm, loss validation tăng:** dấu hiệu quá khớp; checkpoint được chọn ở epoch có validation macro-F1 tốt nhất.
- **Test macro-F1 và recall từng lớp:** xem sau khi train; không chỉ nhìn accuracy tổng.
- **So với model đang dùng:** chỉ kết luận hơn/kém nếu tập đánh giá, class map và tiền xử lý tương thích. Khi không đủ bằng chứng, cửa sổ sẽ ghi rõ chưa so sánh được.

Đánh giá này mô tả hiệu năng phân loại trên tập ảnh hiện có; không chứng minh độ chính xác chẩn đoán thú y ngoài thực địa. Muốn dùng run mới cho toàn ứng dụng, admin quay lại tab model, chọn checkpoint và bấm **Lưu & dùng model**.

Trainer cần Python có PyTorch, torchvision, NumPy, scikit-learn và Pillow. Cửa sổ Flet dùng môi trường Python của ứng dụng; nếu môi trường đó không có Torch, ứng dụng tìm môi trường train đã cấu hình. Mỗi máy Windows chỉ chạy một job train đồng thời. Log được ghi trong `ml_workspace/runs/logs/` và tiến trình train có thể tiếp tục khi cửa sổ Flet đóng.
