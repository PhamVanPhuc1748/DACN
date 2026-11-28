# Dataset report — read-only audit

Ngày kiểm toán: 2026-10-22. Công cụ audit chỉ đọc ảnh; không ảnh gốc nào bị xóa, di chuyển, đổi tên hay ghi đè. Không giải nén archive.

## Nguồn dữ liệu quan sát được

| Nguồn | Quan sát | Ghi chú |
|---|---:|---|
| `data/processed` | 7.599 ảnh, 7.599 đọc được; RGB 224×224 | Nhiều thư mục/export trộn nhau; không mặc định đây là một dataset thống nhất. |
| `data/processed/pig-skin-v4-clean` | 6.796 ảnh; train 4.746, valid 1.034, test 1.016 | Có thể đối chiếu hash với 6.796 hàng CSV hiện có. |
| `data/processed/pig-skin-v4-review` | 203 ảnh | CSV audit cũ cũng có 203 hàng tương ứng; giữ trạng thái review. |
| `data/processed/pig-skin-v4-audit.csv` | 6.999 hàng; train 4.901, valid 1.062, test 1.036 | SHA-256 khớp 6.796 file clean và 203 file review. Split trong CSV bao gồm ảnh review, nên cần duyệt lại trước khi dùng. |
| `data/raw` (thư mục YOLO export) | 737 ảnh, 737 đọc được; RGB 650×650 | `data.yaml` có 4 lớp: Erysipelas, Greasy Pig, Healthy, Sarcoptic Mange. License được export ghi là CC BY 4.0. Đây là object-detection task khác với classification. |
| `Pig Skin Disease Single Label v4...zip` | 2.037 ảnh khi đọc directory listing | 1.596 train / 240 valid / 201 test, 10 lớp. Chỉ đọc metadata ZIP; chưa đối chiếu nội dung ảnh trong archive với các thư mục đã giải nén. |

Không thấy video trong repo (`VIDEO_DATA_UNAVAILABLE`). Chưa có split manifest trong `data/splits` và chưa có model weights.

## Kết quả tính lại

- Trên 7.599 ảnh trong `data/processed`: không ảnh lỗi; 54 nhóm hash SHA-256 có từ hai file trở lên (108 file thành viên tối thiểu); 1.509 cặp ứng viên near-duplicate theo 64-bit dHash với Hamming distance ≤6.
- Trên 737 ảnh YOLO raw: không ảnh lỗi/trùng byte; 17 cặp ứng viên near-duplicate theo cùng heuristic (các ảnh trùng dHash được bỏ khỏi so sánh gần; trùng byte được tính riêng).
- `review_dataset.py` xuất 1.635 ảnh cần xem: 108 exact-duplicate members và 1.547 ảnh xuất hiện trong các cặp near-duplicate. Danh sách đối tác được ghi trong CSV (tối đa 10 partner/ảnh); đây là candidate queue, không phải quyết định nhãn hay xóa.
- DHash/threshold chỉ là heuristic; cặp gần trùng cần xem bằng mắt. Kiểm toán này không khẳng định mọi ảnh cùng stem là cùng con heo/nguồn.
- Có 28 nhóm exact-hash trong toàn `data/processed` chứa đường dẫn thuộc hơn một split marker (train/valid/test); các cặp quan sát được nằm giữa clean và review. Trong riêng `pig-skin-v4-clean` không phát hiện nhóm exact-hash giao qua split. Các candidate near-duplicate vẫn cần kiểm tra cross-split trước khi chốt manifest.
- Kiểm tra trực quan có chọn lọc trên ảnh mẫu: thấy cả chân dung cận cảnh và ảnh nhiều heo/toàn thân. Đây không phải lấy mẫu thống kê, chưa đủ kết luận phân bố framing toàn dataset hoặc dùng được cho camera chuồng.
- Tên thư mục chứa nhãn ghép và `Unlabeled`; taxonomy hiện tại chưa thể ép thành single-label nếu chưa được chủ dữ liệu duyệt.

## Quyền và rủi ro

- YOLO export ghi CC BY 4.0; vẫn cần giữ attribution và kiểm tra nguồn upstream.
- License/nguồn của archive classification và toàn bộ ảnh `data/processed` chưa được xác minh từ metadata trong repo. Không phát tán dữ liệu.
- Audit CSV hiện có trộn ảnh review vào thống kê split. Trước khi train, phải quyết định cách xử lý các 203 review items, xác định taxonomy/label source, và sinh manifest đã duyệt theo group/source.
- Chưa có metadata farm/pig/session. Grouping theo stem chỉ là biện pháp tạm; không bảo đảm tách theo cá thể, nguồn ảnh hoặc recording session.

## Tạo lại báo cáo

Các script audit/review đã được chuyển cùng GUI sang `E:\code\PigSkinResearchStudio\scripts`. Từ PowerShell, có thể gọi chúng như sau:

```powershell
python E:\code\PigSkinResearchStudio\scripts\audit_dataset.py --root E:\code\DACN\data\raw --output-dir E:\code\DACN\data\reports\raw
python E:\code\PigSkinResearchStudio\scripts\audit_dataset.py --root E:\code\DACN\data\processed --output-dir E:\code\DACN\data\reports\processed
python E:\code\PigSkinResearchStudio\scripts\review_dataset.py --audit-csv E:\code\DACN\data\reports\processed\dataset_audit.csv --output-csv E:\code\DACN\data\reports\processed\review_candidates.csv
```

Audit output chỉ gồm metadata/hash; ảnh gốc không bị thay đổi. `data/` đang bị `.gitignore` loại trừ nên report CSV/JSON không được Git theo dõi mặc định.
