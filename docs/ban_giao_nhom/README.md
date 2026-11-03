# Bàn giao nhóm: nâng chất lượng model da heo

**Cập nhật:** 03/11/2026  
**Mục tiêu:** chia công việc cho hai thành viên: một người rà dữ liệu/nhãn, một người đánh giá model. Hai nhánh dùng chung dataset v4 nhưng không sửa chồng lên nhau.

## Trạng thái hiện tại

- Dataset đang dùng: `E:\code\DACN\data\curated\pig_skin_v4_visual_reviewed_v4`.
- Có 1.575 ảnh train, 240 validation, 201 test; tổng 2.016 ảnh trong manifest.
- 22 ảnh và một ảnh minh họa đã được người dùng xác nhận là heo và đưa lại vào nhãn/split ban đầu. Việc xác nhận loài **không xác nhận bệnh**; nhãn bệnh hiện vẫn là nhãn nguồn.
- Một ảnh còn nằm trong `review_queue`, không thuộc manifest train.
- MobileNetV2 và EfficientNet-B0 đã chạy trên cùng manifest v4. Kết quả theo seed dao động; xem [tổng quan dữ liệu và run](THAM_KHAO_DATASET_MODEL.md).
- Run EfficientNet-B0 seed 2026 (`20261103_131518`) đã hoàn tất: best epoch 11, validation macro-F1 70,9%, test accuracy 65,2%, test macro-F1 64,6%. Đây là test macro-F1 cao nhất trong các run hiện có; xem bảng và lưu ý so sánh nhiều seed trong tài liệu tham khảo.

## Chia việc

### Thành viên A — rà dữ liệu và nhãn

1. Đọc [tham khảo dataset/model](THAM_KHAO_DATASET_MODEL.md) và `manifest_visual_review.csv`.
2. Xem ảnh trong `review_queue`; kiểm tra ảnh thuộc loài nào, có dùng được cho bài toán ảnh heo sống hay không.
3. Rà ảnh model nhầm ở các lớp Mange, Erysipelas, Greasy Pig Disease; ghi lại quyết định ở một CSV mới, không ghi đè manifest v4.
4. Chỉ đề xuất đổi nhãn bệnh khi có nguồn xác minh đáng tin. Nếu chỉ xác nhận ảnh là heo, giữ nhãn bệnh hiện tại và ghi rõ chưa xác minh.

**Bàn giao đầu ra:** CSV quyết định gồm `relative_path`, `nhãn hiện tại`, `đề xuất`, `lý do`, `nguồn xác minh`, `người rà`. Không sửa ảnh gốc hay manifest v4.

### Thành viên B — thí nghiệm model

1. Đọc [hướng dẫn train và so sánh](HUONG_DAN_TRAIN_VA_SO_SANH.md).
2. Đối chiếu đủ sáu run MobileNetV2/EfficientNet-B0 trên cùng manifest v4 với seed 42, 123, 2026; run 131518 đã hoàn tất.
3. Ghi manifest SHA-256, config và metric từng run; kết quả ba seed hiện chưa cho thấy kiến trúc nào thắng ổn định.
4. Chọn kiến trúc dựa trên trung bình validation macro-F1 và per-class recall; dùng test để báo cáo, không tiếp tục điều chỉnh dựa trên test.
5. Xuất confusion matrix và danh sách ảnh sai phân loại để chuyển cho thành viên A.

**Bàn giao đầu ra:** bảng run/seed/config/hash/validation/test và danh sách lỗi theo lớp. Không sửa dataset hay nhãn.

## Quy ước phối hợp

- A làm trên bản sao/bảng quyết định; B chỉ đọc manifest v4 cố định.
- Không thay manifest giữa các model/seed trong cùng một vòng so sánh.
- Nếu A đề nghị đổi nhãn hoặc loại ảnh, tạo một phiên bản dataset mới và manifest mới; ghi hash, số ảnh từng split và lý do thay đổi.
- Không chọn model chỉ vì test score cao. Test hiện đã được xem qua nhiều lần chạy, nên xem các test score hiện tại là kết quả thử nghiệm; muốn có đánh giá độc lập cần một tập test mới từ nguồn/cá thể khác.
- `group_id` hiện là đường dẫn từng ảnh, không đại diện cho cá thể heo hoặc phiên chụp. Không tuyên bố đã split theo heo nếu chưa có metadata đó.

## Tài liệu liên quan

- [Tham khảo dataset, file và kết quả run](THAM_KHAO_DATASET_MODEL.md)
- [Cách cấu hình, chạy và so sánh model](HUONG_DAN_TRAIN_VA_SO_SANH.md)
- Hướng dẫn đầy đủ tool train: `E:\code\PigSkinResearchStudio\ml_workspace\README_TRAINING.md`
- Hướng dẫn GUI train/audit: `E:\code\PigSkinResearchStudio\docs\GUI_TRAINING.md`
- `docs/current_state.md` và `docs/dataset_report.md` là snapshot từ 22/10/2026; tham khảo cấu trúc repo/audit cũ, không dùng làm số liệu run mới nhất.

## Trước khi bàn giao cho người dùng máy khác

Các đường dẫn trong hướng dẫn là đường dẫn cục bộ trên máy hiện tại. `/data/` bị `.gitignore` loại khỏi Git; thư mục `E:\code\PigSkinResearchStudio` là workspace train nằm ngoài repo DACN và không có `.git` riêng. Vì vậy, chỉ gửi/commit ba file tài liệu này thì bạn bè **chưa có ảnh dataset hoặc tool train**. Hãy chia sẻ thư mục dataset v4 và workspace train qua ổ chung/drive phù hợp, giữ nguyên manifest và hash; không đưa ảnh/checkpoint lên Git công khai. Trên máy khác, thay các đường dẫn `E:\...` trong GUI theo vị trí thực tế.
