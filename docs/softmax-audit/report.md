# Báo cáo kiểm tra chênh lệch Softmax và cảnh báo dịch tễ

**Kết luận.** Trên đúng ảnh được khám hai lần, MobileNetV2 `20261103_125653` cho Swinepox **67,5268%**. E07-A cho **46,5326%**, bằng trung bình của E03 (**32,2473%**) và E06 (**60,8179%**). Chênh lệch **20,9942 điểm phần trăm** tái hiện được với checkpoint hiện có. Cả tám model xếp Swinepox top-1. Hai lượt khám chưa có nhãn chuyên gia, nên dữ liệu này chỉ xác minh điểm số và thứ hạng của mô hình.

## 1. Ảnh và hai lượt khám

Đọc SQLite ở chế độ chỉ đọc, lấy hai dòng mới nhất theo `id DESC` và tính SHA-256 trực tiếp trên các bản sao ảnh đầu vào. Hai bản sao có SHA-256 giống nhau. Báo cáo dùng mã lượt A và B, đồng thời lược bỏ tên tệp, mã hồ sơ, thời điểm và SHA-256 của ảnh khám.

| Lượt khám | Model | Softmax lưu | Latency lưu |
|---|---|---:|---:|
| A | MobileNetV2 `20261103_125653` | 67,5268% | 38,76 ms |
| B | Ensemble E07-A | 46,5326% | 59,80 ms |

Dùng bản sao của lượt B làm đầu vào chung. CLIP gate chấp nhận ảnh, với pig similarity 0,30911 và margin 0,11596.

## 2. Suy luận cùng ảnh trên tám model

| Model | Top 1 | Top 2 | Top 3 | Median / p95 app (ms) | Median toàn classifier (ms) |
|---|---|---|---|---:|---:|
| MobileNetV2 20261029_161050 | Swinepox 76.9794% | Erysipelas 11.0554% | Dermatitis 6.9763% | 16.35 / 18.45 | 24.32 |
| MobileNetV2 20261103_125653 | Swinepox 67.5268% | Erysipelas 20.8925% | Dermatitis 8.0560% | 18.72 / 25.61 | 27.39 |
| EfficientNet-B0 20261103_125004 | Swinepox 72.9125% | Erysipelas 24.5878% | Dermatitis 2.1003% | 28.45 / 36.60 | 37.43 |
| MobileNetV2 RF baseline | Swinepox 58.2124% | Dermatitis 22.4652% | FMD 13.7030% | 19.31 / 22.38 | 27.37 |
| EfficientNet-B0 RF E01 | Swinepox 59.3134% | Dermatitis 34.4481% | Erysipelas 6.1129% | 29.96 / 63.74 | 38.49 |
| EfficientNet-B0 RF E03 | Swinepox 32.2473% | Erysipelas 23.4852% | Dermatitis 15.0332% | 24.34 / 25.92 | 32.25 |
| EfficientNet-B0 RF E06 | Swinepox 60.8179% | Dermatitis 15.6381% | Erysipelas 10.4029% | 25.03 / 29.21 | 33.23 |
| Ensemble RF E07-A | Swinepox 46.5326% | Erysipelas 16.9440% | Dermatitis 15.3357% | 51.14 / 65.17 | 59.48 |

[CSV xác suất đủ 10 lớp](single-image-probabilities.csv) dùng mã lớp của ứng dụng và thang 0–1. [JSON bằng chứng](single-image-evidence.json) có top-3, SHA-256 checkpoint, tổng xác suất, đối chiếu với logits và các số đo latency.

Đo trên CPU với PyTorch 2.14.1 và TorchVision 0.29.2, bốn luồng Torch, 21 lần/model sau warm-up. Cột **app** dùng đồng hồ mà ứng dụng báo, gồm forward, Softmax và lấy xác suất về CPU. Cột **toàn classifier** đo qua hàm suy luận, gồm đọc ảnh, tiền xử lý và xử lý kết quả với checkpoint đã cache. [Latency end-to-end](end-to-end-latency.csv) ghi một lần gọi `predict()` cho từng lựa chọn, gồm tiến trình CLIP gate và lần nạp đầu của từng lựa chọn. Kết quả từ 5,34 đến 6,24 giây và cả tám lần gọi trả lại đúng 10 xác suất đã đo ở classifier.

## 3. Công thức ensemble, preprocessing và mapping

- **Ensemble.** [ensemble.json](../../PigSkinTech/models/runs/rf_v1_E07-A/ensemble.json) trỏ tới checkpoint E03 và E06. [Ứng dụng](../../PigSkinTech/services/inference.py) tính Softmax trên logits riêng của từng checkpoint rồi lấy trung bình từng lớp. [Evaluator E07](../../ml_workspace/evaluate_ensemble.py) khai báo trọng số 0,5 và 0,5. Đối chiếu vector 10 lớp nhận được sai số tuyệt đối lớn nhất **1,49 × 10⁻⁸** so với trung bình tính từ hai lượt chạy độc lập, phù hợp sai số float32.
- **Số lần Softmax.** Tự tính lại xác suất từ logits của từng checkpoint rồi so sánh với kết quả trả về. Tất cả vector trùng trong phép đo và có tổng xấp xỉ 1. Nếu áp dụng Softmax lần nữa trên vector đã trả về, điểm Swinepox sẽ thành **17,3605%** và **14,2686%** ở hai model được hỏi. Giao diện chỉ chuyển xác suất sang phần trăm để hiển thị. [Worker fallback](../../PigSkinTech/services/inference_worker.py) dùng một Softmax cho checkpoint đơn và chuyển ensemble về cùng hàm suy luận.
- **Mapping.** Đối chiếu danh sách lớp có thứ tự trong config và checkpoint, cùng `class_to_index` ở nơi có trường này. Tám lựa chọn dùng cùng thứ tự 10 lớp. `Healthy` ở index 0 và `Infected_Viral_Swinepox` ở index 9. E07-A kế thừa thứ tự này qua config và cả hai checkpoint.
- **Preprocessing khi đánh giá.** Ứng dụng, worker, [trainer hiện tại](../../ml_workspace/train_model.py), evaluator E07 và trainer trong bộ bàn giao của Phúc cùng dùng PIL `convert("RGB")`, resize trực tiếp 224 × 224, `ToTensor()` và chuẩn hóa ImageNet với mean `[0.485, 0.456, 0.406]`, std `[0.229, 0.224, 0.225]`. Tensor từ pipeline ứng dụng bằng từng phần tử với pipeline validation dựng lại trên chính ảnh này. Kiểm tra riêng trên TorchVision 0.29.2 đại diện app và 0.26.0 đại diện RF cho cùng SHA-256 trên byte tensor float32, `9d11f6ddcefcc74f136694c41b72fd25eec1708aa77d08e405b8a37ef13ec1f7`. Với TorchVision 0.20.1 của các run cũ, phạm vi xác minh là mã nguồn và cấu hình. Train có thêm augmentation ngẫu nhiên, gồm lật, xoay và thay đổi màu. CLIP gate là bước quyết định có gửi ảnh tới classifier hay không.
- **Nguồn chênh lệch.** Các checkpoint cho phân bố khác nhau trên cùng tensor, và E07-A tổng hợp đúng hai phân bố đó. E03 và E06 có label smoothing 0,1 khi train và dùng Adam/AdamW tương ứng. MobileNetV2 của Phúc dùng kiến trúc và bộ dữ liệu khác. Các khác biệt này có thể ảnh hưởng độ sắc của phân bố. Thí nghiệm suy luận hiện tại không cô lập riêng tác động của từng yếu tố.

## 4. Kiểm tra ảnh trong train, validation và test

Kiểm tra toàn bộ danh sách ảnh thuộc ba manifest đã khớp SHA-256 với cấu hình tương ứng.

| Manifest | Lựa chọn model | Train | Val | Test | Khớp SHA-256 ảnh hoặc pHash ≤ 6 |
|---|---|---:|---:|---:|---:|
| Legacy 2017, bộ bàn giao | MobileNetV2 20261029 | 1.576 | 240 | 201 | 0 |
| Curated 2016, bộ bàn giao | MobileNetV2 và EfficientNet-B0 20261103 | 1.575 | 240 | 201 | 0 |
| RF v1 conservative | 5 lựa chọn RF, gồm ensemble | 3.152 | 838 | 423 | 0 |

Kiểm hash tệp và sàng ảnh gần trùng bằng pHash DCT 63 bit, khoảng cách Hamming ≤ 6, có xét ảnh lật ngang. RF v1 khớp thêm cả ba dấu vân tay split của lần train. Config ba model cũ có hash manifest nhưng thiếu dấu vân tay nội dung split để đối chiếu, nên kết quả gắn với bản dữ liệu bàn giao đọc được. Phép sàng có thể bỏ qua bản crop mạnh hoặc ảnh khác của cùng con vật. Chi tiết nguồn, số lượng và hash ở [dataset-provenance.json](dataset-provenance.json).

## 5. Calibration trên validation

Chạy lại checkpoint trên validation gốc tương ứng, cùng pipeline classifier trên RTX 5060 Laptop GPU, PyTorch 2.11.0 / TorchVision 0.26.0. Cả ba chỉ số càng thấp càng tốt.

- **ECE top-label** tính `Σ_b (n_b / N) × |accuracy_b − confidence_b|`. Chia điểm Softmax top-1 thành 15 bin bằng nhau trên [0, 1], bỏ bin rỗng. Bin cuối chứa 1.
- **Brier đa lớp** tính `(1/N) × Σ_i Σ_{k=1..10} (p_ik − 1[y_i=k])²`. Tổng theo 10 lớp và không chia thêm cho 10.
- **NLL** tính `−(1/N) × Σ_i ln(max(p_i,y_i, 10⁻¹⁵))` bằng log tự nhiên.

| Model | n | Accuracy | Softmax TB | ECE | Brier | NLL |
|---|---:|---:|---:|---:|---:|---:|
| MobileNetV2 20261029_161050 | 240 | 72.92% | 75.24% | 7.09% | 0.4079 | 0.9971 |
| MobileNetV2 20261103_125653 | 240 | 73.75% | 75.36% | 7.59% | 0.3945 | 0.9354 |
| EfficientNet-B0 20261103_125004 | 240 | 71.67% | 78.91% | 8.62% | 0.4146 | 0.9802 |
| MobileNetV2 RF baseline | 838 | 75.18% | 81.60% | 6.54% | 0.3642 | 0.8330 |
| EfficientNet-B0 RF E01 | 838 | 76.97% | 87.50% | 10.82% | 0.3552 | 0.8922 |
| EfficientNet-B0 RF E03 | 838 | 78.16% | 74.20% | 5.71% | 0.3286 | 0.7685 |
| EfficientNet-B0 RF E06 | 838 | 78.28% | 72.35% | 7.07% | 0.3414 | 0.7913 |
| Ensemble RF E07-A | 838 | 79.36% | 72.57% | 7.81% | 0.3256 | 0.7558 |

Trên cùng 838 ảnh RF, E07-A có accuracy cao nhất và Brier/NLL thấp nhất trong năm lựa chọn RF. E03 có ECE thấp nhất. E07-A có accuracy 79,36% và Softmax top-1 trung bình 72,57%, tương ứng mức tự tin trung bình thấp hơn tỷ lệ đúng **6,79 điểm phần trăm** trên split này. Ba dòng model của Phúc dùng validation khác với nhóm RF. Các con số giữa hai nhóm không đủ để xếp hạng calibration chung. E07-A đã được chọn dựa trên validation RF, nên kết quả validation mang tính mô tả.

[Reliability diagram cho tám model](reliability-diagram.svg) · [CSV chỉ số](validation-metrics.csv) · [CSV từng bin](validation-reliability-bins.csv)

## 6. So sánh trên cùng tập có nhãn

Đối chiếu test của ba manifest bằng phần tên ảnh trước hậu tố `.rf.`. Trong 49 mã xuất hiện ở cả ba test split, loại 39 mã vì nhãn test giữa các nguồn không thống nhất và loại 2 mã vì trùng tên nguồn hoặc SHA-256 với train/validation. Với các ảnh giữ lại, kiểm nhãn thống nhất và pHash giữa các bản test, đồng thời sàng gần trùng với train/validation của cả ba manifest và giữa các ảnh trong tập chung. Tám checkpoint/lựa chọn nhận **cùng tám tệp RF** sau khi lọc và cùng nhãn. Trình kiểm tra manifest cũng xác nhận group ID và hash không cắt ngang các split trong từng manifest. Dữ liệu thiếu ID động vật để kiểm tra trùng cá thể giữa các bộ.

| Model | Đúng / 8 | Macro-F1 trên 5 lớp có nhãn |
|---|---:|---:|
| MobileNetV2 20261029_161050 | 6/8 | 69.33% |
| MobileNetV2 20261103_125653 | 6/8 | 69.33% |
| EfficientNet-B0 20261103_125004 | 5/8 | 60.00% |
| MobileNetV2 RF baseline | 5/8 | 63.33% |
| EfficientNet-B0 RF E01 | 6/8 | 73.33% |
| EfficientNet-B0 RF E03 | 6/8 | 73.33% |
| EfficientNet-B0 RF E06 | 6/8 | 73.33% |
| Ensemble RF E07-A | 6/8 | 73.33% |

Tám ảnh thuộc năm lớp và không có Swinepox. Một ảnh tương ứng 12,5 điểm phần trăm accuracy. Tập này chỉ dùng làm đối chiếu thăm dò và không đủ để kết luận model nào vượt trội. [Nhãn theo mẫu đã ẩn danh](common-test-cohort.csv) · [Tóm tắt tiêu chí lọc](common-test-provenance.json) · [CSV chỉ số](common-test-metrics.csv)

## 7. Cảnh báo dịch tễ “2/10” khi chỉ có hai lượt khám

Trước bản sửa, hàm banner hiện khi nhận cả hai dòng. Hai dòng thuộc cùng lịch sử người dùng, cùng giá trị trường trại, cùng mã vật nuôi và cùng SHA-256 ảnh. Cả hai dùng dự đoán Swinepox ở mức `Cao` và chưa có nhãn chuyên gia.

Nguyên nhân là banner đếm từng dòng, gộp nhãn AI và nhãn chuyên gia, rồi luôn in mẫu số 10. [Bản sửa](../../PigSkinTech/services/outbreak_service.py) giữ cửa sổ tối đa 10 lượt gần nhất và ngưỡng hiện có là hai cá thể nguy cơ cao. Mỗi trang trại được xét riêng. Trong một trại, mã cá thể đã chuẩn hóa là đơn vị đếm. Thời gian khám xác định thứ tự trong cửa sổ. SHA-256 chỉ xác minh ảnh dùng lại trong lịch sử của cùng cá thể. Mẫu số là số cá thể có định danh trong phạm vi đã xét. Lượt thiếu trại hoặc mã cá thể vẫn có trong lịch sử. Bản ghi đã thẩm định có nhãn được ưu tiên trong cửa sổ. Banner nêu riêng cá thể nghi mắc từ AI và cá thể đã được chuyên gia xác nhận.

Tái chạy với hai dòng gốc ở chế độ chỉ đọc cho kết quả **không hiện banner**. Trường trại của hai dòng dùng giá trị mặc định cũ nên không đủ điều kiện giám sát theo trại. Regression test với trại và mã hợp lệ xác nhận cùng cá thể qua hai thời điểm chỉ được đếm một lần, kể cả khi hai bản sao ảnh có cùng SHA-256.

## Chạy lại audit

Chạy từ thư mục repo bằng môi trường Python có PyTorch, TorchVision, NumPy và Pillow. Đặt đầu ra vào thư mục riêng cho lần chạy. Chế độ `single` xác minh 10 xác suất và công thức ensemble. `--database` là tùy chọn để đối chiếu hai lượt khám mới nhất trong SQLite chỉ đọc. Chế độ `validation` và `common` nhận thư mục dữ liệu đã đối chiếu với các manifest trong báo cáo.

```text
python ml_workspace/audits/softmax_audit.py single --image IMAGE --output AUDIT_RUN
python ml_workspace/audits/softmax_audit.py validation --legacy-root LEGACY --curated-root CURATED --rf-root RF --output VALIDATION_RUN
python ml_workspace/audits/softmax_audit.py common --legacy-root LEGACY --curated-root CURATED --rf-root RF --output COMMON_RUN
python ml_workspace/audits/render_softmax_report.py VALIDATION_RUN
```

Có thể truyền `--curated-manifest` nếu manifest curated nằm ngoài thư mục ảnh, và `--image` ở chế độ `common` để sàng ảnh đầu vào trong cả ba dataset. Kiểm tra dùng checkpoint có sẵn và giữ nguyên Ensemble, ngưỡng Softmax, model mặc định và kết quả E01–E09.
