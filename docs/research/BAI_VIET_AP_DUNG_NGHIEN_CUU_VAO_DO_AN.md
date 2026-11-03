# Từ nghiên cứu đã công bố đến quy trình huấn luyện đồ án

## Mục đích

Tài liệu này trả lời hai câu hỏi: các bài báo có công bố thông số huấn luyện nào, và nhóm có thể chuyển những kết quả đó thành các bước cụ thể cho đồ án nhận diện bệnh da heo ra sao.

Các nghiên cứu được chọn gồm hai bài gần trực tiếp với heo sống, một nghiên cứu bệnh da ở vật nuôi khác và hai nghiên cứu phương pháp trên ảnh da người. Vì đối tượng, nhãn và thiết bị chụp khác nhau, các con số trong bài báo là căn cứ tham khảo để thiết kế thí nghiệm, không phải thông số tối ưu có thể sao chép nguyên xi.

## Trả lời ngắn: có nói thông số train không?

Có. Mức độ chi tiết khác nhau. Một số bài nêu learning rate, batch size, số epoch, optimizer, augmentation và cách chia dữ liệu; một số bài chỉ nêu kiến trúc, kích thước ảnh, transfer learning và kết quả. Khi bài báo không công bố một thông số, không nên tự suy đoán.

| Nghiên cứu | Có nêu thông số huấn luyện? | Phần hữu ích nhất với đồ án |
|---|---|---|
| Bery et al. (2024), tổn thương vai heo nái | Có, khá chi tiết cho phát hiện và phân đoạn | Chụp heo sống, khoanh vùng tổn thương, phát hiện khác với phân loại toàn ảnh |
| Bedin et al. (2024), hình thái heo và giám sát sức khỏe | Có, gồm nhiều cấu hình CNN và augmentation | MobileNetV2 trong bài toán dấu hiệu ngoài da ở heo sống; dùng ảnh cận vùng cần xem |
| Girmaw (2025), bệnh da ở gia súc | Bài tóm tắt công bố kiến trúc, kích thước ảnh và kết quả; không đủ chi tiết để tái lập toàn bộ cấu hình | Bằng chứng tham khảo cho transfer learning trên ảnh da vật nuôi và MobileNetV2 |
| Tajerian et al. (2023), phân loại tổn thương da HAM10000 | Có, mô tả quy trình fine-tune và augmentation | Huấn luyện classifier theo hai giai đoạn: đầu phân loại trước, sau đó fine-tune backbone |
| Yao et al. (2022), dữ liệu tổn thương da mất cân bằng | Trọng tâm là kỹ thuật xử lý dữ liệu/loss; không nên lấy một con số cấu hình làm mặc định cho đồ án | Gợi ý đánh giá theo từng lớp và xử lý mất cân bằng sau khi kiểm tra lỗi |

## 1. Bery et al. (2024): tổn thương vai trên heo nái sống

**Bài báo:** *Determining the Presence and Size of Shoulder Lesions in Sows Using Computer Vision* — [Animals, MDPI](https://www.mdpi.com/2076-2615/14/1/131).

### Họ làm gì?

Nghiên cứu dùng ảnh RGB của heo nái sống để phát hiện tổn thương vai và ước lượng diện tích. Bộ dữ liệu có 824 ảnh từ 70 con heo, thu trong bốn tuần. Bài báo so sánh các bộ phát hiện YOLO và Faster R-CNN; sau đó dùng U-Net để phân đoạn vùng tổn thương. Nhãn phân đoạn được người nghiên cứu tạo thủ công.

### Thông số được báo cáo

- Phát hiện: YOLOv5s/m, YOLOv8s/m và Faster R-CNN với backbone ResNet-50/ResNet-101; có dùng trọng số khởi tạo COCO/ImageNet.
- Các mô hình được huấn luyện tối đa 300 epoch; dừng sớm sau 50 lượt liên tiếp không cải thiện hiệu năng.
- Faster R-CNN: batch size 8, learning rate 0,00025, ảnh trong khoảng kích thước 800 × 1333. YOLO dùng cấu hình mặc định của mô hình và đầu vào 1280 × 720.
- YOLOv5m đạt mAP@0.5 = 0,92; mAP@[0.5:0.95] = 0,48 trong thiết lập của bài.
- Phân đoạn U-Net: batch size 8, learning rate 0,001, Adam, binary cross-entropy, tối đa 100 epoch; backbone VGG16 được khởi tạo từ ImageNet và đóng băng. Bài so sánh U-Net thường, Attention U-Net và các ngưỡng ảnh Otsu/adaptive.
- Dice của U-Net thay đổi theo tuần quan sát; ngưỡng Otsu có kết quả tốt ở một số tuần. Điều này cho thấy màu sắc và hình dạng tổn thương biến đổi theo giai đoạn, nên không có một phương pháp xử lý ảnh đơn giản luôn thắng.

### Áp dụng vào đồ án

Đây là bằng chứng gần nhất cho mục tiêu ảnh da trên **heo sống**. Tuy vậy, phát hiện và phân đoạn không giống phân loại 10 lớp hiện tại. Classifier của đồ án trả lời “ảnh này thuộc lớp nào”; detector trả lời “tổn thương nằm ở đâu”; segmentation tạo mặt nạ vùng tổn thương.

Áp dụng trước mắt: hướng dẫn chụp ảnh rõ vùng da, giảm nền thừa và kiểm tra ảnh theo từng vùng. Nếu nhóm muốn bổ sung phát hiện/đo diện tích tổn thương, cần tạo bounding box hoặc mặt nạ thủ công cho một tập ảnh riêng; không thể huấn luyện detector/segmenter chỉ từ nhãn thư mục bệnh. Khi chia dữ liệu, nên chia theo mã con heo hoặc nguồn ảnh nếu có để ảnh cùng một con không rơi vào cả train và test.

## 2. Bedin et al. (2024): dấu hiệu hình thái trên heo

**Bài báo:** *Using Deep Learning for Morphological Classification in Pigs with a Focus on Sanitary Monitoring* — [arXiv](https://arxiv.org/abs/2403.08962). Đây là bản tiền công bố trên arXiv; không nên giới thiệu là bài báo đã phản biện nếu chưa xác minh được phiên bản xuất bản.

### Họ làm gì?

Bài toán được chia thành năm tác vụ nhị phân: bình thường/bất thường cho các dấu hiệu như cắn đuôi, tụ máu tai, vết xước, đỏ da và đốm tự nhiên. Tập dữ liệu gồm 715 ảnh ở năm bộ tác vụ. Heo sống được chụp bằng điện thoại, ảnh được cắt quanh vùng hình thái cần phân tích. Sáu kiến trúc CNN được so sánh, trong đó có MobileNetV2, EfficientNet, Xception, DenseNet201, InceptionV3 và InceptionResNetV2.

### Thông số được báo cáo

- Tối ưu hóa bằng SGD; learning rate 0,001; decay 0,0001; batch size 8; tối đa 200 epoch.
- Dropout 0,5; validation chiếm 30% phần dữ liệu huấn luyện; dùng 10-fold stratified cross-validation.
- Augmentation gồm lật ảnh, zoom 10%, dịch ngang/dọc 50%, xoay đến 90 độ và điền vùng trống theo nearest-neighbor.
- Bài dùng precision, recall và F-score, đồng thời dùng Grad-CAM để quan sát vùng ảnh ảnh hưởng tới dự đoán.
- InceptionResNetV2 đạt precision trung bình 0,806 cho tác vụ cắn đuôi. Đây là kết quả của một tác vụ cụ thể, không phải độ chính xác bệnh da và không thể so trực tiếp với kết quả 10 lớp của đồ án.

### Áp dụng vào đồ án

Bài hỗ trợ hai quyết định: MobileNetV2 là một mô hình có tiền lệ dùng cho ảnh heo; ảnh cận vùng tổn thương và kiểm tra vùng mô hình chú ý có thể hữu ích. Nhưng nhãn của họ là năm tác vụ nhị phân về hình thái, còn đồ án phân loại 10 nhóm bệnh/khỏe. Không thể lấy kết quả 0,806 làm mốc cần đạt.

Nhóm có thể xem Grad-CAM như công cụ hỗ trợ kiểm tra: mô hình có nhìn vào vùng da có dấu hiệu hay chỉ dựa vào nền, chuồng, ánh sáng hoặc dấu hiệu chụp ảnh. Grad-CAM không chứng minh mô hình đã hiểu bệnh và không thay thế đánh giá trên tập test.

## 3. Girmaw (2025): bệnh da ở gia súc

**Bài báo:** nghiên cứu phân loại bệnh da trên bò, cừu và dê — [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1746809424013922).

### Nội dung và thông số được công bố

Nghiên cứu báo cáo 1.405 ảnh da vật nuôi, bốn lớp bệnh, nhãn do bác sĩ thú y xác nhận và ảnh được đưa về 224 × 224. Bài so sánh transfer learning với MobileNetV2, EfficientNetB7 và DenseNet201; các đầu ra được phân lớp bằng Softmax. Accuracy được báo cáo lần lượt là 95,31%, 99,01% và 97,08% theo các mô hình được nêu trong bài.

Thông tin công khai trong phần tóm tắt/nguồn truy cập không đủ để xác nhận đầy đủ optimizer, learning rate, batch size, số epoch, tỉ lệ chia cụ thể và lịch đóng/mở backbone. Vì vậy tài liệu này không gán các giá trị đó cho bài báo.

### Áp dụng vào đồ án

Nghiên cứu có giá trị tham khảo vì cùng là ảnh da **động vật**, nhưng không phải da heo và số lớp khác. Nó củng cố việc thử transfer learning và MobileNetV2 như baseline nhẹ. Accuracy cao của bộ dữ liệu đó không phải dự báo accuracy cho tập heo của nhóm: tập ảnh, loài, cách chụp, nhãn và cách chia khác nhau.

## 4. Tajerian et al. (2023): fine-tune EfficientNet trên HAM10000

**Bài báo:** *EfficientNet and transfer learning for skin lesion classification* — [PLOS ONE](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0284437).

### Họ làm gì và thông số nào được nêu?

Bài dùng ảnh dermoscopy của người trong HAM10000, gồm 10.015 ảnh và bảy lớp. Mô hình dựa trên EfficientNet-B1; bài có chỗ gọi tên phiên bản chưa nhất quán giữa B0/B1, nên khi trích dẫn cần giữ đúng cách bài mô tả.

- Ảnh được đổi kích thước 240 × 240; chia 80/20, tương ứng 8.015 ảnh train và 2.000 ảnh test.
- Batch size 32, Adam và categorical cross-entropy.
- Giai đoạn đầu đóng băng backbone, huấn luyện phần phân loại 15 epoch; learning rate ban đầu 0,001, giảm còn 0,0001 khi validation loss chững lại sau epoch 12.
- Giai đoạn sau mở 50 lớp trên cùng để fine-tune thêm 4 epoch, khởi đầu learning rate 0,0001 và giảm theo lịch được mô tả trong bài. Tổng cộng 19 epoch.
- Augmentation gồm dịch ảnh đến khoảng ±20%, shear, lật ngang/dọc và nearest fill. Bài cũng mô tả giảm learning rate khi validation loss không cải thiện trong ba epoch.

### Áp dụng vào đồ án

Ý tưởng chính là transfer learning theo hai giai đoạn: trước hết huấn luyện classifier mới trên backbone đã học trước; sau đó mở một phần backbone và fine-tune với learning rate nhỏ hơn. Tool hiện tại đã có cấu trúc gần với cách này: `train_head_epochs` rồi fine-tune. Có thể thử điều chỉnh số epoch của từng giai đoạn, nhưng phải giữ cố định manifest và chỉ thay một nhóm thông số mỗi thí nghiệm.

Không nên sao chép nguyên kích thước 240, batch 32 hoặc augmentation của ảnh dermoscopy: ảnh da heo có độ phân giải, khoảng cách chụp và biến thiên nền khác. Dùng validation để chọn cấu hình; không chọn cấu hình bằng test.

## 5. Yao et al. (2022): dữ liệu da mất cân bằng và khó

**Bài báo:** *A Closer Look at the Robustness of Deep Learning Based Skin Lesion Classification* / phương pháp xử lý mẫu và mất cân bằng — [arXiv](https://arxiv.org/abs/2102.01284), [mã nguồn tác giả](https://github.com/yaopengUSTC/mbit-skin-cancer).

### Ý tưởng nghiên cứu

Nghiên cứu tập trung vào các vấn đề thường gặp ở bộ ảnh da: số ảnh mỗi lớp không đều, mẫu khó hoặc bất thường và mô hình dễ học lệch. Tác giả khảo sát các cách tăng cường như Dropout, DropBlock, Modified RandAugment, cùng loss có trọng số (MWNL) và chiến lược học tích lũy (CLS). Điểm cần lấy về đồ án là nguyên tắc đánh giá độ vững và nhìn hiệu năng theo từng lớp; không phải áp dụng ngay tất cả kỹ thuật phức tạp.

### Áp dụng vào đồ án

Trong manifest hiện tại, số ảnh train mỗi lớp nằm khoảng 132–202, tỉ lệ lớp lớn nhất/nhỏ nhất xấp xỉ 1,53. Mức chênh này cần theo dõi nhưng chưa đủ để kết luận rằng macro-F1 thấp chủ yếu do mất cân bằng. Kết quả test hiện tại có macro-F1 khoảng 0,6125 và accuracy khoảng 0,6219; một số lớp có F1 thấp hơn rõ rệt các lớp khác.

Trình tự phù hợp là kiểm tra ma trận nhầm lẫn, ảnh lỗi, chất lượng nhãn và số mẫu từng lớp trước. Sau đó mới chạy thí nghiệm có đối chứng, chẳng hạn weighted cross-entropy hoặc sampler cân bằng, mỗi lần thay một yếu tố. So sánh macro-F1 và F1 từng lớp trên cùng split; giữ nguyên test để đánh giá cuối cùng. Không thêm MWNL/CLS chỉ vì bài báo có đề xuất chúng.

## 6. Liên hệ trực tiếp với project hiện tại

Project training studio ở `E:\code\PigSkinResearchStudio`. Run đang được xem có các thông tin chính sau:

- Bài toán phân loại ảnh đơn nhãn, 10 lớp: Healthy và 9 lớp bệnh.
- Manifest có 2.017 ảnh: train 1.576, validation 240, test 201.
- MobileNetV2 pretrained ImageNet; ảnh đầu vào 224 × 224.
- Tối đa 30 epoch; 5 epoch train head; batch size 16; learning rate head 0,001; learning rate fine-tune 0,0001; weight decay 0,0001; seed 42; augmentation bật; chạy CUDA.
- Kết quả được ghi nhận: best epoch 12, test macro-F1 ≈ 0,6125 và test accuracy ≈ 0,6219. Validation macro-F1 khoảng 0,71, validation accuracy khoảng 0,7292.

Tool có các lựa chọn MobileNetV2, MobileNetV3-Large và EfficientNet-B0; mỗi run huấn luyện một model. Để so sánh công bằng, dùng cùng manifest, class map, cách tiền xử lý, seed và ngân sách huấn luyện; chỉ đổi kiến trúc. Chọn mô hình bằng validation, rồi báo cáo một lần trên test.

### Nghiên cứu nào hỗ trợ phần nào?

| Thành phần đồ án | Căn cứ nghiên cứu | Cách đưa vào thực tế |
|---|---|---|
| Chụp ảnh tổn thương trên heo sống | Bery; Bedin | Hướng dẫn ảnh rõ vùng da, hạn chế ảnh mờ/xa; lưu nguồn hoặc mã con heo nếu biết |
| Phân loại bằng CNN gọn | Bedin; Girmaw | Dùng MobileNetV2 làm baseline; so với MobileNetV3-Large và EfficientNet-B0 trên cùng split |
| Transfer learning hai giai đoạn | Tajerian | Huấn luyện head rồi fine-tune backbone với learning rate nhỏ hơn; kiểm tra overfitting bằng train/validation curves |
| Kiểm tra vùng ảnh mà mô hình dùng | Bedin (Grad-CAM) | Tạo ảnh giải thích cho dự đoán mẫu; xem mô hình có tập trung vào tổn thương hay nền |
| Đo vùng tổn thương | Bery | Chỉ là giai đoạn mở rộng; cần bbox hoặc mask do người gán và detector/segmenter riêng |
| Mất cân bằng và lớp khó | Yao | Xem macro-F1, per-class F1, confusion matrix; thử loss có trọng số như một thí nghiệm riêng nếu có bằng chứng |
| Độ tin cậy kết quả | Cả quy trình nghiên cứu | Chia dữ liệu độc lập theo nguồn/con heo nếu có; không để ảnh gần trùng rơi qua nhiều split |

## 7. Quy trình đề xuất cho nhóm

1. **Chốt dữ liệu và nhãn.** Kiểm tra ảnh trùng/gần trùng, ảnh sai lớp, ảnh không nhìn thấy vùng da; lưu manifest và class map có phiên bản.
2. **Giữ baseline hiện tại làm mốc.** Ghi đầy đủ cấu hình MobileNetV2 và metric theo lớp. Không thay nhiều thông số cùng lúc.
3. **So sánh kiến trúc.** Chạy MobileNetV2, MobileNetV3-Large và EfficientNet-B0 trên cùng dữ liệu và seed; dùng macro-F1, F1 từng lớp, thời gian train/suy luận và kích thước model để đánh giá.
4. **Đọc lỗi trước khi chỉnh.** Xem confusion matrix, ảnh dự đoán sai và Grad-CAM. Tách lỗi do nhãn, chất lượng ảnh, lớp giống nhau và mất cân bằng.
5. **Thử từng cải tiến.** Có thể thử augmentation phù hợp, class weights hoặc sampler, rồi so với baseline. Chỉ giữ cải tiến nếu validation cải thiện ổn định và test cuối xác nhận.
6. **Mở rộng theo đúng loại bài toán.** Nếu cần vị trí/diện tích tổn thương, tạo nhãn bbox/mask rồi làm detector/segmenter như hướng của Bery; classifier hiện tại không tự cung cấp tọa độ tổn thương.
7. **Báo cáo giới hạn.** Kết quả trên tập ảnh nội bộ chưa chứng minh hoạt động tốt ngoài thực tế. Cần thêm ảnh từ heo, trang trại, thiết bị và điều kiện ánh sáng khác để đánh giá khả năng tổng quát.

## 8. Cách trình bày ngắn với giảng viên

“Nhóm đã chọn các nghiên cứu theo mức độ gần với đề tài. Nghiên cứu trên heo sống cho thấy có thể dùng computer vision để phát hiện và phân đoạn tổn thương, nhưng các tác vụ đó cần nhãn vị trí hoặc mặt nạ. Một nghiên cứu khác dùng nhiều CNN, trong đó có MobileNetV2, để phân loại dấu hiệu hình thái ở heo. Các bài về ảnh da vật nuôi và ảnh da người cung cấp thêm kinh nghiệm transfer learning, fine-tuning, augmentation và đánh giá theo từng lớp. Nhóm đang áp dụng các ý này ở mức phù hợp: giữ bài toán phân loại 10 lớp, dùng MobileNetV2 làm baseline, so sánh các model trên cùng manifest, đọc macro-F1 và lỗi từng lớp; phần phát hiện/đo diện tích sẽ cần dữ liệu gán nhãn riêng.”

## Tài liệu tham khảo

1. Bery et al. (2024). [Determining the Presence and Size of Shoulder Lesions in Sows Using Computer Vision](https://www.mdpi.com/2076-2615/14/1/131).
2. Bedin et al. (2024). [Using Deep Learning for Morphological Classification in Pigs with a Focus on Sanitary Monitoring](https://arxiv.org/abs/2403.08962). Bản arXiv.
3. Girmaw (2025). [Skin disease classification in livestock using deep learning](https://www.sciencedirect.com/science/article/abs/pii/S1746809424013922).
4. Tajerian et al. (2023). [EfficientNet and transfer learning for skin lesion classification](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0284437).
5. Yao et al. (2022). [A Closer Look at the Robustness of Deep Learning Based Skin Lesion Classification](https://arxiv.org/abs/2102.01284); [mã nguồn tác giả](https://github.com/yaopengUSTC/mbit-skin-cancer).

> **Lưu ý khi trích dẫn:** cần đối chiếu lại tiêu đề, năm, tác giả và phiên bản xuất bản cuối cùng theo yêu cầu định dạng tài liệu tham khảo của trường. Các chỉ số trong những bài khác nhau không nên xếp hạng trực tiếp vì bộ dữ liệu và cách chia khác nhau.

