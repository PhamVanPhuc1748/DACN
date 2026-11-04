# Báo cáo tích hợp model AI thật

Ngày kiểm tra: 03/11/2026 (Asia/Saigon)

## Nguồn và tính toàn vẹn

Nguồn được đọc trực tiếp từ gói `BanGiao_PigSkinResearchStudio` của Phúc.
Gói có 12 thư mục run lịch sử; sáu run dưới đây là bộ so sánh hoàn chỉnh dùng
cùng dataset v4, cùng hash, hai kiến trúc và ba seed. Các run cũ dùng manifest
khác nên không được trộn vào quyết định.

- Manifest thực tế SHA-256:
  `dba25e5585884d3bcb7039e1e6bd921ab73e123cf53334792e973742efe9ea99`.
- Số ảnh: train 1.575, validation 240, test 201.
- `classes.json`: 10 lớp, đúng thứ tự trong checkpoint; SHA-256
  `4a069a6fb036ffb8e23bf0aea0f39e8dafcdd680515d4e3f059abbbc59cf169e`.
- Checkpoint được load bằng `torch.load(..., weights_only=True)`, có đầy đủ
  metadata và 314 tensor. Strict state-dict load thành công; classifier có kích
  thước `(10, 1280)` và forward trả `(1, 10)` giá trị hữu hạn.

## So sánh sáu run

Tất cả số validation dưới đây được lấy từ `best_validation.json`; checkpoint
đã được trainer chọn theo validation macro-F1. Test chỉ được ghi tham khảo.

| Run | Model | Seed | Epoch tốt | Val acc | Val precision | Val recall | Val macro-F1 | Test acc | Test macro-F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 20261103_124605 | MobileNetV2 | 42 | 12 | 70,42% | 70,72% | 69,30% | 69,13% | 60,70% | 59,78% |
| 20261103_125004 | EfficientNet-B0 | 42 | 12 | 71,67% | 71,57% | 71,65% | 71,16% | 62,69% | 62,24% |
| **20261103_125653** | **MobileNetV2** | **123** | **12** | **73,75%** | **73,26%** | **73,13%** | **72,35%** | 64,18% | 63,55% |
| 20261103_130213 | EfficientNet-B0 | 123 | 29 | 71,25% | 71,05% | 71,08% | 70,78% | 60,20% | 59,89% |
| 20261103_130855 | MobileNetV2 | 2026 | 20 | 72,50% | 72,08% | 71,95% | 71,52% | 64,18% | 63,31% |
| 20261103_131518 | EfficientNet-B0 | 2026 | 11 | 71,67% | 71,71% | 70,90% | 70,89% | 65,17% | 64,62% |

Chọn run `20261103_125653` vì validation macro-F1 cao nhất (72,35%). Run
EfficientNet-B0 `131518` có test cao hơn nhưng không được chọn vì yêu cầu không
chọn model theo test set. Bảng số thập phân đầy đủ nằm tại
`reports/ai_integration/run_comparison.csv`.

## Model đã tích hợp

- Kiến trúc: torchvision MobileNetV2.
- Seed: 123; best epoch: 12.
- Checkpoint SHA-256:
  `d4f17fa44daff09f30cb885684d40da2f522e702f2b39fd700dab444b8f139d0`.
- Input: ảnh RGB, resize trực tiếp thành 224×224.
- Normalize mean `(0.485, 0.456, 0.406)`, std
  `(0.229, 0.224, 0.225)`.
- Không dùng `Resize(256) → CenterCrop(224)` vì không khớp pipeline train.
- Checkpoint, class map, metadata chọn model và metrics gốc được lưu riêng
  trong `models/`.

Môi trường Studio `.venv` Python 3.10.5 không bị cài thêm torch. Inference dùng
runtime Python 3.10.5 tách biệt qua `models/runtime.json`; runtime hiện có torch
2.12 nightly/torchvision 0.27 nightly và strict-load được checkpoint train bằng
torch 2.5.1/torchvision 0.20.1. Gói bàn giao không chứa `.venv` Python 3.11 nên
chưa thể tái tạo đúng môi trường train gốc, nhưng checkpoint đã được load và
đánh giá lại độc lập thành công.

## Kết quả tái đánh giá và inference

Đánh giá lại toàn bộ 201 ảnh test cho kết quả khớp `final_metrics.json`:

- Accuracy 64,18%; macro-precision 63,76%; macro-recall 63,61%; macro-F1
  63,55%.
- 129 ảnh đúng, 72 ảnh sai.
- Một ảnh test có nhãn `Healthy`
  (`test/Healthy/18_jpeg...jpg`) được Studio suy luận `Healthy`, softmax 99,81%.
  Đây chỉ là kiểm tra kỹ thuật với nhãn sẵn có, không phải xác nhận lâm sàng.

## Tối ưu worker suy luận

Nguyên nhân chậm là Studio từng tạo một Python subprocess mới và import
torch/torchvision, load checkpoint cho từng ảnh. Đo trên cùng ảnh Healthy:

| Chế độ | Cold start | Các lượt sau |
|---|---:|---:|
| Process mới cho mỗi ảnh | 11.835,7 ms | trung bình 5.870,8 ms |
| Worker sống lâu | 4.978,8 ms | trung bình 41,1 ms |

Worker mới nhanh hơn khoảng 2,38 lần ở cold start và 143 lần ở các dự đoán sau.
Chi tiết một lần khởi động: import runtime 4.612,5 ms, load/build/strict-load
checkpoint 141,5 ms. Khi đã warm: preprocessing trung bình 1,43 ms, forward
softmax trung bình 17,97 ms, tổng xử lý trong worker 22,07 ms.

Ứng dụng prewarm worker trên background thread sau đăng nhập, nên trong luồng
trình diễn bình thường người dùng không phải chờ cold start lúc bấm phân tích.
Các request được tuần tự hóa và gắn ID. Timeout sẽ dừng worker; worker chết hoặc
broken pipe được khởi động lại một lần. Đóng cửa sổ gửi lệnh shutdown, sau đó
terminate/kill có thời hạn nếu worker không hợp tác. Kết quả one-shot và worker
sống lâu đã được đối chiếu toàn bộ score với sai số tối đa `1e-7`, không thay
đổi confidence hay preprocessing. Số đo thô nằm trong
`reports/ai_integration/worker_benchmark.json`.

## Nhầm lẫn cần rà nhãn

| Lớp thật | Precision | Recall | F1 | Sai / tổng | Nhầm nổi bật |
|---|---:|---:|---:|---:|---|
| Mange | 39,13% | 45,00% | 41,86% | 11/20 | 5 sang Greasy Pig Disease |
| Erysipelas | 46,15% | 42,86% | 44,44% | 8/14 | 2 sang FMD, 2 Greasy, 2 Swinepox |
| Greasy Pig Disease | 50,00% | 51,61% | 50,79% | 15/31 | 11 sang Mange |
| Dermatitis | 72,22% | 61,90% | 66,67% | 8/21 | 3 sang Pityriasis, 3 Erysipelas |

Cặp Greasy Pig Disease → Mange là lỗi lớn nhất (11 ảnh); chiều ngược lại có 5
ảnh. Danh sách đầy đủ 72 ảnh sai nằm ở `misclassified.csv`; danh sách 59 lỗi có
liên quan bốn lớp ưu tiên nằm ở `focus_review.csv`. Các file chỉ tham chiếu ảnh,
không sửa dataset hoặc manifest.

## Giới hạn

- Softmax chưa được hiệu chuẩn và không phải xác suất chẩn đoán.
- Nhãn bệnh chưa được chuyên gia xác minh từng ảnh; split chưa có ID cá thể heo
  hoặc phiên chụp thật.
- Test set đã được xem qua nhiều lần, nên metric chỉ mang tính tham khảo.
- Chưa có môi trường Python 3.11 đúng bản train trong gói bàn giao.
- Cold start runtime vẫn khoảng 5 giây do import PyTorch; ứng dụng che độ trễ
  này bằng prewarm sau đăng nhập. Dự đoán warm đo được khoảng 41 ms end-to-end.

Model chỉ hỗ trợ chuyên gia. Kết quả không thay thế đánh giá của bác sĩ thú y.
