# Tổng hợp và phân tích 5 bài báo cho đề tài PIG CV

> Tài liệu đọc nhanh nhưng có giải thích chi tiết: nêu câu hỏi nghiên cứu, dữ liệu, phương pháp, kết quả, giới hạn và phần có thể vận dụng cho đồ án **phân loại dấu hiệu bất thường ngoài da trên heo**. Đây là bản tổng hợp phân tích bằng tiếng Việt, không phải bản dịch nguyên văn toàn bộ bài báo.

## Cách đọc và ranh giới thông tin

- **Bài báo báo cáo:** số liệu và phương pháp được trích từ bài hoặc nguồn xuất bản.
- **Phân tích:** giải thích ý nghĩa và hạn chế của thiết kế nghiên cứu.
- **Gợi ý cho PIG CV:** đề xuất kỹ thuật cho đồ án, cần kiểm chứng trên dữ liệu heo của nhóm.
- Kết quả của các bài thuộc các loài, cách chụp, nhãn và tập test khác nhau. **Không so sánh trực tiếp accuracy giữa các bài và không coi kết quả bài báo là kết quả của đồ án.**
- P1 chỉ xác minh được abstract và một số phần trên trang xuất bản. P2, P3, P5 có toàn văn mở. P4 có bản preprint toàn văn trên arXiv, dù bản IEEE có thể bị giới hạn truy cập.

## Tóm tắt một trang

| Bài | Bài toán và dữ liệu | Công nghệ chính | Giá trị thiết thực nhất cho PIG CV |
|---|---|---|---|
| **P1 — Girmaw (2025)** | Phân loại bệnh da trên 1.405 ảnh bò, cừu, dê | EfficientNetB7, MobileNetV2, DenseNet201; transfer learning | Tham khảo transfer learning và so sánh model nhẹ/nặng; dữ liệu không phải heo |
| **P2 — Tailception (2019)** | Chấm tổn thương đuôi trên ảnh xác heo tại lò mổ | Tìm landmark/ROI bằng ResNet-50, phân loại crop bằng Inception-ResNet-v2 | Bài gần lĩnh vực nhất; học cách định vị ROI, kiểm tra chất lượng ảnh và độ tin cậy nhãn |
| **P3 — Tajerian et al. (2023)** | Phân loại 7 loại tổn thương da người trên HAM10000 | EfficientNet transfer learning, Global Average Pooling, Softmax | Tham khảo huấn luyện theo giai đoạn và đánh giá theo từng lớp |
| **P4 — Yao et al. (2022)** | Phân loại ảnh da người trên các bộ dữ liệu nhỏ/mất cân bằng | DCNN, Dropout, DropBlock, Modified RandAugment, MWNL, CLS | Chỉ cân nhắc kỹ thuật mất cân bằng sau khi baseline chứng minh vấn đề này có thật |
| **P5 — SkiNet (2022)** | Phân đoạn và phân loại tổn thương da người, có ước lượng bất định | Bayesian MultiResUNet, Bayesian DenseNet-169, MC Dropout, TTA, saliency | Tham khảo trạng thái `needs_review`, cổng chất lượng ảnh và cách xem lại kết quả khó |

## P1 — Phân loại bệnh da trên gia súc bằng deep learning

**Trích dẫn:** Dagne Walle Girmaw, “Livestock animal skin disease detection and classification using deep learning approaches,” *Biomedical Signal Processing and Control*, 102 (2025), 107334. [DOI](https://doi.org/10.1016/j.bspc.2024.107334) · [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S1746809424013922).

### Câu hỏi và dữ liệu

Bài khảo sát việc phân loại dấu hiệu bệnh da trên ảnh **bò, cừu và dê**. Nhóm tác giả thu thập **1.405 ảnh** tại College of Veterinary Medicine, Haramaya University; ảnh được mô tả ở độ phân giải **224 × 224 px** và có nhãn do bác sĩ thú y chuyên môn gán. Nguồn xuất bản nêu **4 lớp**, nhưng tên và số lượng ảnh trong từng lớp chưa được xác minh từ phần truy cập hiện có.

Dataset được nhóm nghiên cứu tự thu thập. Chưa tìm thấy link tải công khai hoặc license riêng đã xác minh; trang bài báo ghi code availability là “Not applicable”. Điều này có nghĩa chưa thể tái lập từ một kho dữ liệu mở đã biết, chứ không khẳng định tác giả sẽ không cung cấp dữ liệu theo yêu cầu.

### Mô hình và cách áp dụng

Bài dùng transfer learning: lấy backbone đã học đặc trưng ảnh, thay đầu phân loại để dự đoán 4 lớp, rồi so sánh:

- **MobileNetV2:** mạng gọn, thường được cân nhắc khi cần giảm chi phí suy luận.
- **DenseNet201:** tái sử dụng đặc trưng qua kết nối giữa nhiều tầng.
- **EfficientNetB7:** biến thể lớn hơn trong họ EfficientNet, thường cần nhiều tài nguyên hơn các backbone nhỏ.
- **Softmax:** chuyển các điểm đầu ra thành phân phối trên các lớp loại trừ nhau. Điểm lớn nhất không tự động là xác suất đã hiệu chuẩn hay chẩn đoán thú y.

Phần truy cập được nói có tiền xử lý và augmentation, nhưng không đủ bằng chứng để xác định chính xác optimizer, learning rate, epochs, batch size, weights pretrained hay tỷ lệ chia dữ liệu. Không nên tự bổ sung những thông số này.

### Kết quả và cách hiểu

Publisher báo cáo accuracy **99,01% với EfficientNetB7**, **97,08% với DenseNet201** và **95,31% với MobileNetV2** trên tập của chính nghiên cứu. Đây chỉ là kết quả trong bối cảnh ảnh và nhãn của bài. Khi không có phân bố lớp, class-wise recall và thông tin split chi tiết, accuracy chưa cho biết model bỏ sót bao nhiêu trường hợp hiếm hoặc liệu ảnh cùng nguồn có xuất hiện ở cả train và test hay không.

### Vận dụng cho PIG CV

- **Có thể mượn:** thiết kế transfer learning; so sánh một baseline nhẹ với một backbone thứ hai trên cùng split.
- **Không mượn nguyên:** accuracy, taxonomy, model B7 như mặc định, hay giả định rằng ảnh cận cảnh gia súc tương đương ảnh/video heo.
- **Đề xuất:** dùng MobileNetV2 làm baseline tài nguyên thấp và EfficientNet-B0 làm đối chứng ban đầu. Đây là quyết định kỹ thuật của đồ án, không phải kết luận của P1 về hiệu năng trên heo.

## P2 — “Tailception”: định vị đuôi rồi phân loại tổn thương

**Trích dẫn:** J. Brünger, S. Dippel, R. Koch, C. Veit, “‘Tailception’: using neural networks for assessing tail lesions on pictures of pig carcasses,” *Animal*, 13(5) (2019), 1030–1036. [DOI](https://doi.org/10.1017/S1751731118003038) · [Toàn văn Cambridge Core](https://www.cambridge.org/core/journals/animal/article/tailception-using-neural-networks-for-assessing-tail-lesions-on-pictures-of-pig-carcasses/57F1EE3D905C52E67EFB6A268FD5BAA6) · [PDF](https://literatur.thuenen.de/digbib_extern/dn065606.pdf).

### Câu hỏi và dữ liệu

Mục tiêu là tự động chấm mức tổn thương đuôi trên **xác heo sau giết mổ**, rồi so kết quả với người chấm được đào tạo. Trong khoảng **100.000 ảnh** thu tại một lò mổ trong sáu ngày, khoảng 90% là đuôi không tổn thương. Ba người chấm đã đánh giá **13.124 ảnh** dùng cho nghiên cứu mô hình. Gần như mọi heo đều đã cắt đuôi.

Nhãn tổn thương có bốn mức từ 0 đến 3; tình trạng mất đuôi là nhãn nhị phân riêng. Tập 13.124 ảnh được chia **10.499 train và 2.625 validation**. Lớp nặng hiếm: lớp 3 chỉ có **101 ảnh** trước bước oversampling. Data statement ghi ảnh có thể được cung cấp theo yêu cầu hợp lý từ tác giả; không thấy kho tải mở được nêu trong bài.

Ảnh được chụp tự động bằng hai camera RGB đồng bộ ở hai góc phía lưng sau công đoạn làm sạch; hai góc được ghép thành một ảnh. Ánh sáng, vị trí camera và dây chuyền tương đối ổn định. Đây là điều kiện khác đáng kể so với camera chuồng.

### Pipeline hai giai đoạn

1. **Định vị phần cần xem:** mạng dựa trên ResNet-50 tìm một mốc giải phẫu (vị trí lỗ hậu môn) để xác định vùng chứa đuôi.
2. **Chuẩn hóa ROI:** tạo crop từ hai góc, mỗi vùng khoảng **320 × 256 px**, rồi ghép thành đầu vào khoảng **320 × 512 px**.
3. **Phân loại severity:** dùng Inception-ResNet-v2 đã khởi tạo từ ImageNet; đầu ra Softmax 4 lớp. Lớp hiếm được oversample tới 4.000 ảnh train mỗi lớp, ảnh được xoay ±10° và biến đổi nhiễu/độ sáng/blur.
4. **Phân loại mất đuôi:** dùng cùng ảnh crop và kiến trúc, nhưng đầu ra sigmoid nhị phân.

Part detector dùng Adam, learning rate 0,0001, 30 epochs. Classifier tổn thương dùng Adam, learning rate 0,00001, tối đa 30 epochs; paper ghi có overfit và dùng early stopping. Batch size không được nêu trong phần phương pháp đã rà soát.

### Kết quả và ý nghĩa

Đồng thuận trung vị giữa người chấm là **80%** cho tổn thương đuôi (PABAK 0,75) và **94%** cho mất đuôi (PABAK 0,87). Mạng đồng thuận với người chấm **74%** ở tổn thương và **95%** ở mất đuôi. PABAK điều chỉnh tỷ lệ lớp và bias khi tính đồng thuận; không đồng nghĩa với accuracy hoặc F1.

Điểm quan trọng là con người cũng không đồng thuận hoàn toàn. Tác giả nêu chất lượng ảnh là một nguyên nhân lớn gây bất đồng; bóng, cấu trúc chồng lấp và vật thể đỏ ngoài vùng đuôi cũng có thể làm mạng phân loại sai. Vì vậy, chất lượng ROI và chất lượng nhãn cần được đo cùng với classifier.

### Vận dụng cho PIG CV

- **Có thể mượn:** ROI/crop trước classification; đánh giá detector và classifier riêng; quality gate cho ảnh mờ/che khuất; xem lại độ nhất quán của nhãn.
- **Không mượn nguyên:** landmark lỗ hậu môn, crop cố định, model/weights hay điểm số của ảnh xác heo làm mô hình cho da heo sống.
- **Đề xuất:** trước khi tuyên bố nhận dạng trong video toàn chuồng, tạo một tập video đại diện và kiểm tra ROI. Nếu crop không hợp lệ, trả `needs_review` hoặc `unobservable`, không ép classifier ra nhãn.

## P3 — Transfer learning EfficientNet trên HAM10000

**Trích dẫn:** A. Tajerian et al., “Design and validation of a new machine-learning-based diagnostic tool for the differentiation of dermatoscopic skin cancer images,” *PLOS ONE*, 18(4) (2023), e0284437. [DOI và toàn văn](https://doi.org/10.1371/journal.pone.0284437) · [Trang PLOS](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0284437).

### Câu hỏi và dữ liệu

Bài xây công cụ phân loại **7 loại tổn thương da người** trên HAM10000, gồm **10.015 ảnh dermoscopy** từ nhiều nguồn. Hơn một nửa ground truth được xác nhận bằng mô bệnh học; các trường hợp còn lại dựa trên theo dõi, đồng thuận chuyên gia hoặc confocal microscopy theo mô tả dataset. Dữ liệu lệch lớp rõ rệt, lớp melanocytic nevus chiếm đa số.

HAM10000 có thể tải qua ISIC Archive. Tuy vậy cần phân biệt HAM10000 với gói collection ISIC tổng hợp và kiểm tra license/citation áp dụng cho đúng ảnh hoặc collection; ISIC nêu license có thể khác nhau theo contributor. [ISIC datasets](https://challenge.isic-archive.com/data/) · [ISIC FAQ](https://www.isic-archive.com/blank-1).

### Mô hình và huấn luyện

Pipeline gồm resize ảnh thành **240 × 240 × 3**, augmentation hình học (dịch ngang/dọc tối đa ±20%, shear nhỏ, lật ngang/dọc), EfficientNet transfer learning, Global Average Pooling và Softmax 7 lớp.

Huấn luyện có hai giai đoạn: đóng băng backbone và học classifier head **15 epochs**, sau đó mở 50 lớp cuối để fine-tune **4 epochs**. Bài báo nêu Adam, categorical cross-entropy, batch size 32 và learning rate bắt đầu 0,001; có ReduceLROnPlateau. Chia dữ liệu được mô tả là **8.015 train / 2.000 test**, ngẫu nhiên. Không thấy xác nhận split theo người/lesion.

Tên kiến trúc có điểm không nhất quán: abstract gọi EfficientNet-B1, trong khi nội dung cũng nhắc EfficientNet-B0. Khi trích dẫn nên giữ rõ sự bất nhất thay vì tự chọn một tên rồi coi như chắc chắn.

### Kết quả và cách đọc

Accuracy trên test là **84,3%**. F1 theo lớp: NV 0,93; VASC 0,80; BCC 0,72; BKL 0,70; AKIEC 0,63; MEL 0,58; DF 0,54. Chênh lệch giữa F1 lớp lớn và lớp nhỏ cho thấy accuracy tổng không mô tả đầy đủ khả năng nhận diện từng loại. Bài cũng ghi nhận ảnh trùng trong các lỗi nổi bật, nhắc đến rủi ro duplicate và chất lượng dữ liệu.

### Vận dụng cho PIG CV

- **Có thể mượn:** transfer learning theo giai đoạn; augmentation chỉ trên train; chọn checkpoint bằng validation; báo precision/recall/F1 theo lớp và kiểm tra false negative.
- **Không mượn nguyên:** kích thước 240, batch 32, epochs, phép augmentation, backbone B0/B1 hoặc 84,3% như cấu hình tối ưu cho heo.
- **Đề xuất:** split theo group nguồn/con vật/video nếu metadata cho phép; tìm exact/near-duplicate trước khi train; giữ test không dùng để chọn checkpoint hoặc ngưỡng cảnh báo.

## P4 — Học trên dataset nhỏ và mất cân bằng

**Trích dẫn:** P. Yao et al., “Single Model Deep Learning on Imbalanced Small Datasets for Skin Lesion Classification,” *IEEE Transactions on Medical Imaging*, 41(5) (2022), 1242–1254. [DOI IEEE](https://doi.org/10.1109/TMI.2021.3136682) · [Bản preprint toàn văn arXiv](https://arxiv.org/pdf/2102.01284).

### Dữ liệu

Preprint báo cáo bốn dataset ảnh da người:

- **ISIC 2018 / HAM10000:** 10.015 ảnh train, 7 lớp; test challenge 1.512 ảnh không có nhãn công bố theo bài.
- **ISIC 2017:** 2.000 train, 150 validation, 600 test; ba lớp MEL, SK, NV.
- **ISIC 2019:** 25.331 ảnh train, 8 lớp; 8.238 test không có nhãn công bố theo bài.
- **7-PT / Derm7pt:** 1.011 ca, gồm ảnh dermoscopy và metadata; đa số còn có ảnh lâm sàng. Bài dùng 413/203/395 ca train/validation/test và chỉ dùng ảnh dermoscopy.

Các tập train ISIC có trang tải chính thức; một số nhãn test được giữ kín để chấm qua challenge. Derm7pt có trang dữ liệu nghiên cứu, nhưng cần đọc điều khoản tại nguồn trước khi tái phân phối hoặc dùng ngoài mục đích nghiên cứu. [ISIC datasets](https://challenge.isic-archive.com/data/) · [Derm7pt](https://derm.cs.sfu.ca/Welcome.html).

### Ý tưởng phương pháp

Bài so sánh nhiều họ DCNN, từ VGG, ResNet, DenseNet, EfficientNet đến RegNet. Kết luận thực nghiệm của tác giả là model vừa phải có thể phù hợp hơn model lớn trên dataset nhỏ; model tốt nhất thay đổi theo kích thước dataset.

Để giảm overfit và xử lý lệch lớp, bài kết hợp:

- **Dropout / DropBlock:** regularization; DropBlock loại vùng liên tiếp trên feature map.
- **Modified RandAugment:** chọn và áp dụng phép biến đổi ảnh với xác suất/độ mạnh thiết kế cho ảnh dermoscopy.
- **MWNL (Multi-Weighted New Loss):** điều chỉnh trọng số loss theo lớp và độ khó; bài còn có bước giới hạn loss rất lớn để giảm ảnh hưởng mẫu ngoại lệ.
- **CLS (Cumulative Learning Strategy):** đầu tiên học biểu diễn trên phân bố gốc, sau đó chuyển dần sang rebalancing và giảm learning rate.
- **BACC:** balanced accuracy, trung bình recall theo lớp; được dùng làm metric chính vì dữ liệu lệch.

### Vận dụng cho PIG CV

- **Có thể mượn:** dùng macro-F1/BACC hoặc recall theo lớp để phát hiện model chỉ học lớp đông; thử model gọn trước model lớn; chỉ xử lý imbalance sau khi xác nhận nó là nguồn lỗi.
- **Không nên làm ngay:** đưa đồng thời DropBlock, RandAugment biến thể, MWNL và CLS vào lần train đầu. Khi đổi nhiều thành phần, khó biết thành phần nào gây cải thiện; kỹ thuật còn cần cài đặt và đánh giá cẩn thận.
- **Đề xuất:** baseline trước, sau đó thử riêng class weights hoặc weighted sampler trên cùng split; so sánh recall lớp bất thường, precision và false alerts.

## P5 — SkiNet: phân đoạn, phân loại và báo bất định

**Trích dẫn:** R. K. Singh et al., “SkiNet: A deep learning framework for skin lesion diagnosis with uncertainty estimation and explainability,” *PLOS ONE*, 17(10) (2022), e0276836. [DOI và toàn văn](https://doi.org/10.1371/journal.pone.0276836) · [Trang PLOS](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0276836).

### Dữ liệu và pipeline

SkiNet dùng hai bài toán ISIC 2018:

- **Task 1 segmentation:** khoảng 2.594 ảnh RGB và ground-truth masks.
- **Task 3 classification:** 10.015 ảnh dermoscopy, 7 lớp; augmentation offline tạo tập 13.302 ảnh dẫn xuất.

Pipeline là **segmentation → đánh giá bất định → classification → giải thích**. Bayesian MultiResUNet tạo mask và bất định vùng; nếu segmentation quá bất định, hệ thống dùng ảnh gốc thay vì chỉ dựa vào vùng cắt. Bayesian DenseNet-169 phân loại. MC Dropout và test-time augmentation (TTA) chạy nhiều lượt để xem dự đoán ổn định đến đâu. XRAI, Grad-CAM và Guided Backprop tạo heatmap hỗ trợ xem vùng ảnh có ảnh hưởng đến kết quả.

Tác giả báo Dice **0,852**, Jaccard **0,767** cho segmentation; accuracy classifier Bayesian DenseNet-169 **87,35%**; SkiNet báo prediction accuracy **88,46%** và diagnostic accuracy **73,65%** theo định nghĩa riêng của bài. Không so trực tiếp các metric này với accuracy của P3 vì nhiệm vụ/thiết lập khác nhau.

ISIC cung cấp dữ liệu công khai, nhưng license phụ thuộc task/ảnh. Trang ISIC ghi Task 1 CC0 và Task 3 CC-BY-NC cho collection tổng hợp; cần theo attribution và metadata license khi dùng lại. [ISIC datasets](https://challenge.isic-archive.com/data/) · [ISIC FAQ](https://www.isic-archive.com/blank-1).

### Vận dụng cho PIG CV

- **Có thể mượn ngay:** ảnh không rõ, mờ, ROI bị che hoặc dự đoán không chắc thì trả `needs_review`; không ép mọi ảnh thành một nhãn.
- **Có thể mượn khi có dữ liệu/nguồn lực:** saliency để debug xem model có chú ý vào nền, bóng hoặc vật thể không liên quan hay không.
- **Để sau:** Bayesian segmenter/classifier, nhiều lượt TTA/MC Dropout vì làm tăng chi phí, latency và yêu cầu dữ liệu mask.
- **Không sao chép:** threshold 0,25/0,35 của paper. Threshold phải được chọn trên validation đại diện cho heo và quy trình camera thực tế.

## Tổng hợp: những gì nên làm trong đồ án

### Thứ tự triển khai đề xuất

1. **Chốt dữ liệu và nhãn:** xác định nguồn chính, taxonomy single-label hay multi-label, quyền dùng dữ liệu, xử lý ảnh review và duplicate.
2. **Tạo split group-safe:** cùng con vật, ảnh gốc/augmentation, video hoặc phiên chụp không được rơi sang nhiều tập. Dùng validation để chọn model; giữ test đến đánh giá cuối.
3. **Huấn luyện baseline:** MobileNetV2 trước, EfficientNet-B0 làm đối chứng. Đây là lựa chọn engineering cho PIG CV, không phải kết quả paper về heo.
4. **Đọc lỗi theo lớp:** macro-F1, recall lớp bất thường, confusion matrix, false negative; chỉ sau đó mới thử class weights/sampler hoặc augmentation khác.
5. **Kiểm chứng ROI:** classifier ảnh không tự tìm vùng bệnh trong khung hình đàn. Thử crop có người duyệt trước; đánh giá detector riêng trước khi gọi là video classification.
6. **Thêm luồng xem lại:** quality gate và `needs_review` cho ảnh/ROI chưa đủ tốt. Hiệu chuẩn score hoặc dùng MC Dropout/TTA chỉ khi có validation và cần thiết.
7. **Đánh giá sản phẩm:** ngoài metric phân loại, đo false alerts, tỷ lệ cần review và độ trễ từ frame đến event.

### Mức độ liên quan theo chủ đề

| Chủ đề | Bài tham khảo | Đề xuất của tài liệu |
|---|---|---|
| Transfer learning / backbone baseline | P1, P3 | MobileNetV2 và EfficientNet-B0 trên cùng split; không lấy accuracy paper làm mục tiêu |
| ROI rồi phân loại | P2 | Tạo crop có kiểm soát; đo ROI và classifier riêng; kiểm chứng bằng góc camera thật |
| Mất cân bằng lớp | P2, P4 | Thống kê trước; thử class weights hoặc sampler từng bước, sau baseline |
| Ảnh khó / dự đoán cần người xem | P2, P5 | `needs_review`, `unobservable`, quality gate; chọn threshold trên validation |
| Saliency giải thích | P5 | Dùng heatmap để debug, không coi là bằng chứng chẩn đoán |

**Kết luận:** P2 cho bài học trực tiếp nhất về ROI và chất lượng ảnh trên heo. P1/P3 hỗ trợ lựa chọn quy trình transfer learning. P4 chỉ nên dẫn đến thí nghiệm xử lý imbalance khi dữ liệu địa phương có bằng chứng cần thiết. P5 hữu ích nhất cho thiết kế hệ thống biết từ chối dự đoán và chuyển trường hợp khó cho người xem.

## Thuật ngữ ngắn

- **Backbone:** phần mạng trích đặc trưng từ ảnh.
- **Transfer learning:** dùng trọng số đã học trước, thay đầu ra và fine-tune cho nhiệm vụ mới.
- **ROI:** vùng ảnh được chọn để phân loại; classifier trên crop không chứng minh bước tìm crop đúng.
- **Augmentation:** biến đổi ảnh train để tăng đa dạng hình thức; không tạo thêm mẫu sinh học độc lập.
- **Macro-F1:** tính F1 từng lớp rồi lấy trung bình, giúp lớp nhỏ không bị lớp đông lấn át.
- **BACC:** trung bình recall của các lớp; hữu ích khi số lượng ảnh mỗi lớp lệch nhau.
- **Uncertainty:** mức không chắc của dự đoán; raw Softmax score không tự động là confidence đã hiệu chuẩn.
- **Saliency / heatmap:** hình trực quan vùng có ảnh hưởng đến đầu ra theo một phương pháp giải thích; không chứng minh quan hệ nhân quả.

## Tài liệu nguồn

1. Girmaw (2025), [ScienceDirect / DOI](https://doi.org/10.1016/j.bspc.2024.107334).
2. Brünger et al. (2019), [Cambridge Core / DOI](https://doi.org/10.1017/S1751731118003038), [PDF toàn văn](https://literatur.thuenen.de/digbib_extern/dn065606.pdf).
3. Tajerian et al. (2023), [PLOS ONE](https://doi.org/10.1371/journal.pone.0284437).
4. Yao et al. (2022), [IEEE DOI](https://doi.org/10.1109/TMI.2021.3136682), [arXiv preprint toàn văn](https://arxiv.org/pdf/2102.01284).
5. Singh et al. (2022), [PLOS ONE](https://doi.org/10.1371/journal.pone.0276836).
6. ISIC Archive, [trang dataset và license](https://challenge.isic-archive.com/data/), [FAQ quyền sử dụng ảnh](https://www.isic-archive.com/blank-1).
