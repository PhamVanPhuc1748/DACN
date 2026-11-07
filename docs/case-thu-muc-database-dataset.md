# Quy ước thư mục, cơ sở dữ liệu và chia dataset

Tài liệu này mô tả trạng thái hiện tại của dự án nhận diện bệnh da heo, đồng thời đề xuất cách tổ chức dữ liệu để dễ huấn luyện, đánh giá và tích hợp với ứng dụng. Những phần ghi **Hiện trạng** được quan sát từ repository; phần **Đề xuất** là hướng triển khai, chưa phải chức năng đã có.

## 1. Các case sử dụng

| Case | Luồng xử lý | Dữ liệu liên quan |
|---|---|---|
| Thu thập dữ liệu | Nhận ảnh và thông tin nguồn, giữ bản gốc, ghi nhận quyền sử dụng | Ảnh gốc, nguồn, thời điểm thu thập |
| Gán nhãn | Người gán nhãn chọn không, một hoặc nhiều bệnh; ảnh chưa rõ được đánh dấu riêng | Ảnh, danh mục bệnh, nhãn, trạng thái duyệt |
| Tạo phiên bản dataset | Chọn các ảnh/nhãn đã duyệt, chia train/validation/test và lưu manifest | Manifest, seed, phiên bản nhãn |
| Huấn luyện và đánh giá | Dataloader đọc manifest, huấn luyện model trên train, chọn cấu hình trên validation, báo cáo cuối trên test | Dataset version, cấu hình, model, metrics |
| Dự đoán từ ứng dụng | API nhận ảnh, tiền xử lý, chạy model và trả nhãn cùng độ tin cậy | Ảnh tạm hoặc URI, model version, kết quả dự đoán |
| Theo dõi kết quả | Lưu yêu cầu và kết quả nếu sản phẩm cần lịch sử; không tự xem dự đoán là chẩn đoán xác nhận | Prediction, model version, thời gian |

## 2. Cấu trúc thư mục

### Hiện trạng

Repository đang có `data/raw`, `data/processed`, `data/splits`. Dataset ảnh thô nằm trong:

```text
data/raw/Pig Skin Disease Single Label v2.v3i.folder/
├── train/
├── valid/
├── test/
├── README.dataset.txt
└── README.roboflow.txt
```

Các ảnh nằm trong thư mục con theo tên lớp. Hai thư mục `data/processed` và `data/splits` hiện chưa có nội dung đáng kể. Phần huấn luyện và API trong repository còn ở mức khung; endpoint `/predict` hiện trả kết quả giả lập, chưa gọi model thật.

### Cấu trúc đề xuất

```text
data/
├── raw/                         # Bản tải về nguyên trạng, không sửa trực tiếp
│   └── pig-skin-v2/             # Ghi nguồn và phiên bản
├── processed/                   # Ảnh đã chuẩn hóa; có thể tái tạo từ raw
│   └── <pipeline-version>/
├── splits/                      # Manifest phân chia, không cần nhân bản ảnh
│   └── <dataset-version>/
│       ├── train.csv
│       ├── validation.csv
│       ├── test.csv
│       └── dataset.yaml
└── reports/                     # Thống kê nhãn, lỗi, trùng ảnh, metrics
```

Manifest nên lưu tối thiểu `image_id`, đường dẫn tương đối, nhãn, split, nguồn và checksum. Dùng đường dẫn tương đối để repository có thể chuyển máy. Dữ liệu ảnh lớn nên được quản lý ngoài Git (ví dụ object storage hoặc DVC); Git lưu mã, cấu hình và manifest nhẹ.

## 3. Cơ sở dữ liệu

### Hiện trạng

Trong mã nguồn đã kiểm tra chưa thấy cấu hình hoặc schema của SQLite, PostgreSQL, MySQL hay dịch vụ database. API hiện chưa lưu ảnh hoặc kết quả dự đoán. Vì vậy, database bên dưới là **thiết kế đề xuất**, không phải database đang chạy.

### Schema đề xuất

| Bảng | Trường chính | Mục đích |
|---|---|---|
| `disease_classes` | `id`, `code`, `name`, `description` | Danh mục bệnh/nhãn chuẩn, mã ổn định không phụ thuộc tên thư mục |
| `images` | `id`, `uri`, `sha256`, `width`, `height`, `source`, `created_at` | Metadata và vị trí ảnh; lưu ảnh ở filesystem/object storage, không nhét blob vào DB mặc định |
| `image_labels` | `image_id`, `class_id`, `status`, `annotator`, `reviewed_at` | Quan hệ nhiều-nhiều giữa ảnh và nhãn; hỗ trợ nhãn chưa duyệt |
| `dataset_versions` | `id`, `name`, `version`, `seed`, `created_at`, `notes` | Đóng băng một phiên bản dataset có thể tái lập |
| `dataset_members` | `dataset_version_id`, `image_id`, `split` | Ghi ảnh thuộc train/validation/test của phiên bản nào |
| `model_versions` | `id`, `dataset_version_id`, `artifact_uri`, `config`, `metrics`, `created_at` | Theo dõi model được huấn luyện từ dataset và cấu hình nào |
| `predictions` | `id`, `image_uri`, `model_version_id`, `predicted_class_id`, `confidence`, `created_at` | Lịch sử dự đoán nếu nghiệp vụ cần lưu |

Ràng buộc nên có: `disease_classes.code` duy nhất; `images.sha256` dùng phát hiện ảnh trùng; mỗi ảnh chỉ thuộc một split trong cùng dataset version; khóa ngoại cho nhãn, dataset và model. Nếu một ảnh có nhiều nhãn, kết quả dự đoán cần lưu nhiều dòng chi tiết thay vì chỉ một `predicted_class_id`.

## 4. Dataset hiện có và cách chia

Quan sát thư mục `data/raw/Pig Skin Disease Single Label v2.v3i.folder` cho thấy tổng cộng **29.148 file JPG**:

| Split hiện có | Số ảnh | Tỷ lệ xấp xỉ |
|---|---:|---:|
| `train` | 27.800 | 95,4% |
| `valid` | 680 | 2,3% |
| `test` | 668 | 2,3% |
| **Tổng** | **29.148** | **100%** |

Tên thư mục cho thấy có các lớp bệnh, `Healthy`, `Unlabeled`, và cả thư mục ghép nhiều tên bệnh. Có 46 thư mục lớp/nhóm ở train, 17 ở valid và 28 ở test; một vài thư mục test rỗng. Do đó không nên coi tên thư mục ghép là một lớp bệnh độc lập trước khi xác minh quy tắc annotation từ nhãn gốc/metadata Roboflow. `Unlabeled` cũng cần được xử lý rõ ràng thay vì vô tình đưa vào như một bệnh.

### Quy trình chia dữ liệu đề xuất

1. **Chuẩn hóa nhãn trước khi chia.** Tạo danh mục lớp thống nhất; xác định mỗi ảnh có một nhãn, nhiều nhãn hay chưa có nhãn. Chuyển tên thư mục thành tập nhãn chuẩn chỉ khi đã xác minh quy ước nguồn.
2. **Kiểm tra chất lượng.** Loại/đánh dấu ảnh hỏng, nhãn thiếu, ảnh trùng và ảnh gần trùng. Dùng checksum để bắt trùng byte; ảnh cùng nguồn/đối tượng nên được gom nhóm khi chia để tránh rò rỉ giữa các tập.
3. **Chia theo nhóm và phân tầng.** Chia theo cá thể heo/nguồn chụp nếu thông tin đó tồn tại, rồi cân bằng tỷ lệ từng lớp. Nếu không có nhóm, dùng stratified split theo lớp (multi-label iterative stratification nếu có nhiều nhãn).
4. **Tỷ lệ tham khảo.** Có thể dùng 80/10/10 hoặc 70/15/15. Chọn tỷ lệ dựa trên số lượng từng lớp; tập test phải đủ lớn để đo hiệu năng có ý nghĩa. Các split Roboflow hiện tại rất lệch về train, nên cần xem xét lại nếu chưa có lý do cụ thể.
5. **Cố định và lưu phiên bản.** Cố định random seed, ghi danh sách `image_id` trong manifest và không thay đổi test sau khi bắt đầu so sánh model. Validation dùng chọn model/hyperparameter; test chỉ dùng báo cáo đánh giá cuối.
6. **Augmentation chỉ áp dụng trên train.** Không tạo ảnh augment vào validation/test; tiền xử lý phải giống nhau giữa huấn luyện và suy luận.

Ví dụ manifest CSV:

```csv
image_id,relative_path,labels,split,sha256
img_0001,raw/pig-skin-v2/train/example.jpg,"Infected_Bacterial_Erysipelas",train,<sha256>
```

Trước khi huấn luyện cần xuất báo cáo số ảnh theo từng nhãn ở cả ba split, số ảnh không nhãn, số ảnh trùng, ảnh lỗi và kiểm tra giao nhau giữa các ID. Với dữ liệu nhiều nhãn, báo cáo tần suất theo từng nhãn và các tổ hợp nhãn phổ biến.

## 5. Việc cần làm để áp dụng

1. Xác minh annotation gốc và ý nghĩa các thư mục ghép nhãn.
2. Chốt bài toán single-label hay multi-label và quy tắc cho `Healthy`/`Unlabeled`.
3. Tạo manifest có checksum, chuẩn hóa split và lưu phiên bản.
4. Viết dataloader đọc manifest thay vì suy luận lớp từ chuỗi tên thư mục.
5. Chọn database khi cần quản lý nhãn, phiên bản model hoặc lịch sử dự đoán; hiện tại dự án chưa bắt buộc phải có DB để huấn luyện ảnh từ manifest.
