# Kế hoạch huấn luyện AI cho đề tài PIG CV

Ngày lập: 2026-10-25. Đây là **kế hoạch đề xuất**, chưa phải cấu hình đã chạy. Các thông số trong mục “paper báo cáo” là từ nghiên cứu gốc; các cấu hình trong mục “đề xuất cho repo” cần được kiểm chứng trên dữ liệu đã duyệt. Kế hoạch dừng trước khi cài PyTorch, giải nén/copy dữ liệu hoặc chạy train.

## 1. Mục tiêu và nguyên tắc

Mục tiêu gần: xây classifier ảnh tái lập được, đo được sai sót theo từng lớp và tạo đầu ra `needs_review` khi ảnh hoặc dự đoán chưa đủ tin cậy. Sau đó mới kiểm chứng ROI/video.

- Paper khác nhau về loài vật, ảnh và nhãn. Không lấy accuracy của paper làm benchmark cho heo.
- Không dùng mọi thư mục trong `data/processed` như một dataset duy nhất: repo có ảnh classification 10 lớp, folder nhãn ghép, ảnh review và export YOLO 4 lớp.
- Không bắt đầu train cho tới khi chốt nguồn ảnh, label mapping, quyền sử dụng, cách xử lý 203 ảnh review và split theo nhóm.
- Không thay nhãn ảnh thành diagnosis thú y; phần mềm chỉ phân loại ảnh trong phạm vi dữ liệu được xác nhận.

## 2. Cách dùng kết quả từng paper

| Paper | Thành phần hữu ích | Đưa vào kế hoạch | Không sao chép trực tiếp |
|---|---|---|---|
| P1 — Girmaw | Transfer learning; thử MobileNetV2 cùng một backbone EfficientNet | Dùng MobileNetV2 làm baseline nhẹ; thêm EfficientNet-B0 làm đối chứng thứ hai | P1 thử EfficientNetB7 trên bò/cừu/dê; không lấy 99,01% accuracy hay suy ra thông số toàn văn paywall |
| P2 — Tailception | Định vị ROI rồi classification; kiểm soát chất lượng ảnh; cân bằng dữ liệu train | Tạo một cổng feasibility ROI riêng trước khi tuyên bố video; theo dõi chất lượng ROI | Không dùng Inception-ResNet-v2/ResNet-50 detector cho chuồng nếu chưa có kiểm chứng; dữ liệu là đuôi xác heo ở lò mổ |
| P3 — Tajerian | Transfer learning hai giai đoạn, augmentation train, metric theo lớp, xem lỗi ảnh | Tham khảo quy trình freeze head rồi fine-tune; dùng macro-F1 và class recall | Không lấy thông số/84,3% từ ảnh dermoscopy người làm cấu hình tối ưu cho heo; paper có mâu thuẫn B0/B1 |
| P4 — Yao | Nhắc tới regularization/imbalance: Dropout, DropBlock, Modified RandAugment, MWNL, CLS | Chỉ cân nhắc một cách xử lý imbalance sau baseline và error analysis | Không tái lập loss/CLS từ abstract; toàn văn và thông số chưa có |
| P5 — SkiNet | Phân đoạn, uncertainty, saliency và chuyển ca khó cho người đánh giá | Thiết kế `needs_review`; giai đoạn sau cân nhắc MC Dropout/TTA và hiệu chuẩn ngưỡng | Không bê nguyên Bayesian MultiResUNet/DenseNet169; ngưỡng 0,25/0,35 chỉ của paper trên ảnh da người |

Nguồn: [P1](https://doi.org/10.1016/j.bspc.2024.107334), [P2](https://doi.org/10.1017/S1751731118003038), [P3](https://doi.org/10.1371/journal.pone.0284437), [P4](https://doi.org/10.1109/TMI.2021.3136682), [P5](https://doi.org/10.1371/journal.pone.0276836). Xem hồ sơ riêng trong `docs/research/papers/` để biết trạng thái truy cập và thông số được báo cáo.

## 3. Cổng 0 — chốt dataset, nhãn và quyền trước khi train

### Việc phải hoàn tất

1. Chọn một nguồn classification chính thức. Hiện có 6.796 ảnh trong `pig-skin-v4-clean`, 203 ảnh trong `pig-skin-v4-review`, archive classification 2.037 ảnh và các thư mục export khác. Không gộp chúng trước khi đối chiếu nguồn và hash.
2. Chủ dữ liệu/giảng viên duyệt quyền sử dụng và attribution. Export YOLO ghi CC BY 4.0; license của các thư mục classification khác chưa xác minh.
3. Chốt taxonomy và mục tiêu:
   - **Single-label:** mỗi ảnh đúng một lớp, dùng CrossEntropyLoss + Softmax.
   - **Multi-label:** một ảnh có thể có nhiều nhãn độc lập, dùng BCEWithLogitsLoss + sigmoid cho từng nhãn.
   - Folder ghép chưa đủ bằng chứng để quyết định là multi-label thật; cần người có chuyên môn xác nhận.
4. Duyệt 203 ảnh review; không tự xóa hoặc coi chúng là nhãn chuẩn.
5. Xem các exact/near-duplicate candidates và dựng group/component id. Ưu tiên farm, cá thể, nguồn ảnh, recording session nếu có; nếu không có metadata, dùng stem/hash làm biện pháp tạm và ghi giới hạn.
6. Sinh manifest CSV có tối thiểu: `relative_path`, `sha256`, `group_id`, `label(s)`, `source`, `split`, `review_status`.

### Split và kiểm tra leakage

- Mục tiêu ban đầu có thể là 70/15/15 train/validation/test, nhưng tỷ lệ phải điều chỉnh theo số group và lớp hiếm.
- Chia theo group, không theo file đơn. Ảnh exact duplicate phải vào cùng split; các near-duplicate nối thành cùng component khi review xác nhận là cùng ảnh gốc.
- Nếu có farm/pig/session id, dùng chúng làm group thay vì chỉ stem. Stem không chứng minh ảnh thuộc hai cá thể khác nhau.
- Duyệt phân phối nhãn giữa các tập; val dùng chọn checkpoint/threshold, test chỉ đánh giá cuối sau khi pipeline khóa.
- Nếu lớp hiếm không thể xuất hiện đủ ở cả ba split, báo rõ giới hạn thay vì tạo điểm số có vẻ cân bằng bằng cách rò rỉ ảnh.

**Cổng chấp nhận:** nhãn được duyệt; split tái lập với seed cố định; không có group giao nhau; không có path lỗi; manifest không chứa ảnh chưa duyệt như ground truth.

## 4. Cổng 1 — baseline image classification

### Cấu hình đề xuất để bắt đầu

| Thành phần | Đề xuất v0 | Lý do / lưu ý |
|---|---|---|
| Model A | MobileNetV2 pretrained, thay classification head theo số nhãn đã duyệt | P1 có MobileNetV2 trong livestock study; chọn làm baseline vì gọn, không phải vì paper chứng minh tốt nhất trên heo |
| Model B | EfficientNet-B0 pretrained, head tương đương | Đối chứng thứ hai; B0 khác EfficientNetB7 của P1 |
| Kích thước | Khởi đầu 224×224; giữ cùng kích thước cho hai model nếu preprocessing cho phép | Ảnh `pig-skin-v4-clean` hiện 224×224; khi đổi nguồn phải kiểm tra lại |
| Khởi tạo | Weights chính thức từ framework, ghi rõ phiên bản/tên weights/license và preprocessing tương ứng | Không tự nhận là weights của các paper nếu họ không công bố nguồn |
| Loss | CE cho single-label; BCEWithLogits cho multi-label | Chốt theo taxonomy, không trộn hai mục tiêu |
| Optimizer | Adam làm lựa chọn đầu để đối chiếu với P2/P3/P5 | Đây là lựa chọn thử nghiệm, không phải thông số đã chứng minh tối ưu cho repo |
| Batch | Bắt đầu 16 trên RTX 4050 6 GiB; tăng lên 32 nếu còn VRAM ổn định | Cấu hình gợi ý theo tài nguyên quan sát được; xác nhận khi có Torch/CUDA |
| LR / epochs | Head: LR 1e-3 trong tối đa 5 epochs; fine-tune một phần backbone: LR 1e-4, tối đa 20 epochs; early stopping patience 4 | Mốc khởi đầu thực nghiệm; gần tinh thần freeze/fine-tune ở P3 nhưng giảm lịch để phù hợp vòng thử ngắn |
| Seed | 42 cho split và training | Ghi seed, library versions, deterministic settings và hardware vào config/log |

P3 dùng 15 epochs cho head rồi 4 epochs fine-tune, LR khởi đầu 0,001 và batch 32 trên HAM10000. Đề xuất trên rút ngắn vòng thử và batch 16 để giảm rủi ro VRAM; cần tune bằng validation, không gọi đây là tái lập P3.

### Augmentation chỉ trên train

- Bắt đầu nhẹ: horizontal flip nếu không làm đổi ý nghĩa, xoay nhỏ khoảng ±10°, crop/scale vừa phải và điều chỉnh sáng/nhiễu nhẹ.
- Không dùng hue shift mạnh vì màu đỏ/tím có thể là dấu hiệu lớp.
- P2 dùng xoay ±10°, noise/brightness/blur trong ảnh đuôi lò mổ; P3 dùng shift ±20% và flips trên dermoscopy. Đây là gợi ý biến đổi để thử, không phải bộ augmentation đã xác nhận cho ảnh heo.
- Không augmentation cho validation/test. Không nhân bản/copy ảnh trên đĩa; nếu cần sampler, lặp chỉ trong DataLoader train.

### Ghi nhận đầu ra mỗi run

- `config.yaml`/JSON, class mapping, seed, split manifest version/hash.
- Model name, weights source, transform/preprocessing, loss, optimizer, LR, batch, epochs, early stopping.
- Best checkpoint theo metric validation được chọn trước.
- Confusion matrix, accuracy, macro-F1, precision/recall/F1 từng lớp; đặc biệt recall lớp bất thường và false negatives.
- Model size, thời gian inference/frame hoặc ảnh, hardware/driver/framework version.

**Cổng chấp nhận:** chạy được lặp lại; cùng split/preprocessing cho hai backbone; có bảng lỗi theo lớp; không chọn model chỉ theo accuracy tổng.

## 5. Cổng 2 — xử lý class imbalance chỉ khi baseline chứng minh cần

Đầu tiên dùng confusion matrix và số lượng nhãn để phân biệt lỗi do imbalance với lỗi do nhãn nhiễu, ảnh không rõ, split hoặc domain gap.

Thử theo thứ tự, mỗi lần thay một yếu tố:

1. Baseline không cân bằng để làm mốc.
2. Class-weighted cross-entropy (single-label) **hoặc** weighted sampler; không bật cả hai cùng lúc ở vòng đầu.
3. Đo macro-F1, recall từng lớp, false-negative rate, và precision để thấy trade-off cảnh báo giả.
4. Chỉ khi vẫn có bằng chứng overfit/thiếu mẫu mới thử dropout/DropBlock hoặc augmentation mạnh hơn.
5. MWNL và CLS của P4 để ngoài scope hiện tại: cần full text/công thức và thí nghiệm tái lập.

P2 oversample mọi lớp lên 4.000 ảnh nhưng lớp nặng bị lặp rất nhiều lần và paper vẫn quan sát overfit. Do đó không sao chép tỷ lệ 4.000/lớp cho dataset này.

## 6. Cổng 3 — ROI và khả năng dùng với video

Classifier ảnh chỉ phân loại vùng ảnh đầu vào; nó không tự tìm đúng con heo hay vùng da trong khung hình toàn chuồng.

1. **Kiểm tra framing:** xem mẫu ảnh từng lớp và video thực tế được phép dùng. Repo hiện chưa có video (`VIDEO_DATA_UNAVAILABLE`).
2. **Thử crop có kiểm soát:** tạo các crop ROI được con người duyệt trên video/ảnh thực địa; kiểm tra classifier trên crop và ghi rõ đây là demo ROI-controlled.
3. **Đánh giá detector riêng:** `data/raw` có 737 ảnh YOLO với 4 nhãn, là một task/dataset khác. Trước khi dùng detector phải xác minh box đang bao pig hay lesion, cách lớp liên hệ với classifier, group split và chất lượng annotation.
4. Nếu detector phù hợp, đo recall phát hiện vùng, tỷ lệ ROI sai/không thấy, và ảnh crop sau detector. Chỉ sau cổng này mới ghép inference video.
5. P2 dùng part detector ResNet-50 và landmark lỗ hậu môn trong ảnh xác heo; chỉ mượn nguyên tắc định vị ROI, không bê landmark/model sang camera chuồng.

**Cổng chấp nhận:** video test có nguồn/nhãn kiểm chứng; ROI đo được; tách `normal`, `suspected`, `unobservable`, `monitoring_unavailable`; đo latency capture→decision→event. Nếu chưa có video/ROI thì giới hạn demo ở ảnh hoặc crop được chọn.

## 7. Cổng 4 — uncertainty và `needs_review`

### Phiên bản MVP

- Bắt đầu bằng quality gate: ảnh quá nhỏ, mờ, vùng da không thấy/ROI không hợp lệ → `needs_review` hoặc `unobservable`.
- Không xem raw Softmax là xác suất chẩn đoán đã hiệu chuẩn.
- Dùng validation để chọn threshold theo yêu cầu recall/false-alert; giữ test riêng.

### Thử nghiệm sau baseline

- Hiệu chuẩn score bằng temperature scaling hoặc phương pháp đơn giản khác trên validation; báo calibration metric nếu làm.
- Nếu cần ước lượng độ không ổn định, thử MC Dropout hoặc TTA trên một tập con. Đo thêm latency vì inference nhiều lượt.
- P5 dùng Bayesian MultiResUNet/DenseNet169, MC Dropout và TTA; ngưỡng 0,25/0,35 được chọn trên ISIC người. Không sao chép các threshold đó.
- Saliency như Grad-CAM/XRAI chỉ là hỗ trợ xem vùng model chú ý, không phải bằng chứng model đã định vị đúng bệnh.

**Cổng chấp nhận:** trên validation, nhóm được đưa ra kết luận “certain” có lỗi/recall được báo cáo; số lượng chuyển review và latency được đo; test chỉ chạy sau khi threshold khóa.

## 8. Thứ tự thí nghiệm và tiêu chí chọn model

| Run | Mục tiêu | Thay đổi duy nhất | Kết quả cần lưu |
|---|---|---|---|
| R0 | Kiểm tra data pipeline | Không train; đọc manifest, label, transforms | Số ảnh/lớp/split; lỗi path; group leakage; sample grid |
| R1 | Baseline | MobileNetV2 + cấu hình v0 | Metrics theo lớp, curves, checkpoint, latency |
| R2 | So sánh kiến trúc | EfficientNet-B0, giữ split/loss/augment gần tương đương | Cùng bảng metrics và latency với R1 |
| R3 | Phân tích lỗi | Không đổi model; rà false negatives/nhãn khó | Error categories, đề xuất thu thập/duyệt dữ liệu |
| R4 | Cân bằng lớp (nếu cần) | Class weights **hoặc** sampler | Trade-off macro-F1, recall, precision, false alerts |
| R5 | ROI feasibility | Model đã chọn trên crop/video có ROI | Chất lượng ROI, bỏ sót vùng, latency end-to-end |
| R6 | Review/uncertainty | Quality gate; MC Dropout/TTA chỉ nếu cần | Coverage, lỗi nhóm certain, review rate, latency |

Chọn model dựa trên recall lớp bất thường, macro-F1, false alert burden, latency, độ ổn định qua split/group và mức dễ vận hành. Nếu metric gần nhau, ưu tiên model nhẹ hơn cho demo một máy; không lấy accuracy paper khác để phá hòa.

## 9. Phân công và điều kiện bắt đầu

- **TV1 AI/Data:** chốt nguồn/taxonomy, review ảnh, group split, train R1–R4, báo cáo metric/lỗi.
- **TV2 Backend/Video:** kiểm tra detector/ROI, chuẩn hóa inference input/output, đo latency video và trạng thái nguồn.
- **TV3 Frontend/Test:** hiển thị class/score cùng trạng thái `needs_review`, thu phản hồi người dùng, lập ca kiểm thử false alert/ảnh không quan sát được.

Trước khi cài PyTorch/torchvision hoặc chạy bất kỳ train nào, nhóm cần duyệt dependency/version, mức dùng GPU/thời gian, nơi lưu checkpoint/log và nguồn weights. Kế hoạch này chưa cài dependency, chưa tạo split cuối, chưa thay schema và chưa chạy train.

## 10. Kết luận kế hoạch

Thứ tự khuyến nghị: **duyệt dữ liệu → group-safe split → MobileNetV2 → EfficientNet-B0 → phân tích lỗi → xử lý imbalance có bằng chứng → ROI/video → uncertainty/review**. Kết quả trực tiếp nhất từ các paper là kiến trúc ROI trước classification (P2), transfer learning làm baseline (P1/P3) và luồng review dựa trên uncertainty (P5). P4 chỉ nên là hướng đọc tiếp khi imbalance và overfit đã xuất hiện trong kết quả local.
