# Bộ lọc ảnh trước dự đoán bệnh

## Cổng kiểm tra ảnh bằng CLIP zero-shot

`services/image_gate.py` so embedding ảnh với mô tả văn bản tổng quát về ảnh da heo và ảnh ngoài phạm vi. Cổng này dùng checkpoint CLIP pretrained, không dùng `pig_skin_gate.pt` và không train thêm đầu phân loại. Ảnh chỉ qua cổng khi similarity da heo đạt ngưỡng và cao hơn nhóm ảnh khác một khoảng tối thiểu.

### Cài đặt

Trong môi trường Python mà `services/project_data.py` chọn cho PyTorch, cài:

```powershell
python -m pip install -r PigSkinTech/requirements-clip.txt
```

Lần đầu chạy, OpenCLIP tải weights `ViT-B-32 / laion2b_s34b_b79k` từ internet vào cache model của tài khoản Windows. Các lần sau dùng cache; suy luận có thể chạy trên CUDA hoặc CPU. Không cần API key.

### Luồng

`services.inference.predict()` gọi gate trước model bệnh. Nếu ảnh không qua gate, dự đoán dừng và app yêu cầu chọn ảnh da heo khác. Nếu qua, ảnh được chuyển tới checkpoint MobileNetV2/EfficientNet đã chọn. Nếu OpenCLIP chưa cài, không tải được weights hoặc xảy ra lỗi, gate trả lỗi và không chạy model bệnh.

### Giới hạn

CLIP là mô hình tổng quát; điểm cosine không phải xác suất hay xác nhận bệnh. Bộ prompt và ngưỡng ban đầu (`MIN_PIG_SCORE`, `MIN_SCORE_MARGIN`) chỉ để thử, chưa được hiệu chuẩn trên bộ ảnh ngoài phạm vi đa dạng. Ảnh cận da có thể khó nhận ra là da heo; ảnh heo chụp xa có thể bị từ chối. Cần kiểm tra trên tập riêng gồm da heo cận cảnh, heo toàn thân, dép và nhiều ảnh ngoài phạm vi khác trước khi dùng thật. Không dùng gate để phân loại hoặc chẩn đoán bệnh.
