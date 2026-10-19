# Kế Hoạch Chuẩn Hóa & Phân Chia Dataset Raw
## Dự án: Nhận Diện Bệnh Trên Da Heo (Pig Skin Disease Detection)

> **Mục tiêu:** Xử lý triệt để bài toán rò rỉ dữ liệu (Data Leakage), chuẩn hóa nhãn đa bệnh (Multi-label / Single-label), loại bỏ ảnh trùng lặp/augment sẵn của Roboflow, và xây dựng bộ manifest phân chia (Train / Validation / Test) chuẩn mực, có thể tái lập (reproducible) phục vụ huấn luyện mô hình thị giác máy tính.

---

## 1. Hiện Trạng & Phát Hiện Bất Thường Từ Dữ Liệu Raw

Qua rà soát thực tế bộ dữ liệu `data/raw/Pig Skin Disease Single Label v2.v3i.folder`:

### 1.1. Hiện tượng "ảo ảnh số lượng" (Data Inflation)
- **Số lượng file bề nổi:** **29.148 file ảnh JPG** (Train: 27.800 ảnh ~ 95.4%, Valid: 680 ảnh ~ 2.3%, Test: 668 ảnh ~ 2.3%).
- **Thực tế gốc (Ground Truth):** Chỉ có **1.217 ảnh gốc duy nhất (unique stems)**!
- Nguyên nhân: Bộ dữ liệu xuất từ Roboflow đã bị áp dụng augmentation tĩnh offline (xoay, lật, co giãn, noise, v.v.) nhân bản từ 5x đến hơn 25x lần mỗi ảnh gốc trước/trong khi export.

### 1.2. Rò rỉ dữ liệu nghiêm trọng (Data Leakage)
- Do quá trình chia tập của Roboflow diễn ra sau hoặc không nhóm theo ảnh gốc:
  - **48 ảnh gốc** xuất hiện đồng thời ở cả **Train và Valid**.
  - **34 ảnh gốc** xuất hiện đồng thời ở cả **Train và Test**.
  - **31 ảnh gốc** xuất hiện đồng thời ở cả **Valid và Test**.
- **Hệ quả:** Nếu huấn luyện trên tập Train và đánh giá trên Valid/Test hiện tại, mô hình sẽ nhớ mặt ảnh gốc (memorization), dẫn đến chỉ số Accuracy/F1 cao giả tạo nhưng thất bại hoàn toàn khi triển khai ứng dụng thực tế trên điện thoại di động.

### 1.3. Bất thường phân bố nhãn & Cấu trúc thư mục
- **Thiếu lớp Healthy ở Valid & Test:** Thư mục `Healthy` có 164 ảnh gốc ở `train`, nhưng **hoàn toàn vắng bóng** ở cả `valid` và `test` mặc định.
- **Hiện tượng nhãn ghép (Compound folder names):** Có tới hơn 106 thư mục con khác nhau do tên folder ghép nhiều bệnh (ví dụ: `Infected_Bacterial_Erysipelas Infected_Environmental_Dermatitis`).
- **Xung đột nhãn:** 86 ảnh gốc bị đặt phân tán ở các folder nhãn khác nhau.
- **Dữ liệu chưa gán nhãn:** Có **153 ảnh gốc** nằm trong thư mục `Unlabeled`.

---

## 2. Danh Mục Nhãn Chuẩn Hóa (Taxonomy Standardization)

Hệ thống rút gọn về 10 lớp phân loại chính (9 bệnh da liễu truyền nhiễm/môi trường thường gặp ở heo + 1 lớp đối chứng khỏe mạnh):

| STT | Mã lớp (`class_code`) | Tên bệnh / Phân loại | Tên tiếng Việt |
|:---:|:---|:---|:---|
| 1 | `HEALTHY` | Healthy | Heo khỏe mạnh, da bình thường |
| 2 | `BACT_ERY` | Bacterial Erysipelas | Bệnh đóng dấu lợn |
| 3 | `BACT_GPD` | Bacterial Greasy Pig Disease | Viêm da tiết dịch / Rỉ cặn |
| 4 | `ENV_DERM` | Environmental Dermatitis | Viêm da tiếp xúc do môi trường |
| 5 | `ENV_SUN` | Environmental Sunburn | Cháy nắng / Bỏng nắng |
| 6 | `FUNG_ROSEA` | Fungal Pityriasis Rosea | Vảy phấn hồng |
| 7 | `FUNG_RING` | Fungal Ringworm | Nấm da / Lác đồng tiền |
| 8 | `PARA_MANGE` | Parasitic Mange | Ghẻ sảy / Ghẻ do ký sinh trùng |
| 9 | `VIRA_FMD` | Viral Foot and Mouth Disease | Lở mồm long móng |
| 10 | `VIRA_POX` | Viral Swinepox | Đậu heo |

> **Quy ước xử lý:**
> - Thư mục ghép (chứa 2 bệnh trở lên): Tách thành vector nhãn Multi-hot `[0, 1, 0, ..., 1]`.
> - Thư mục `Unlabeled`: Đưa vào tập riêng biệt `unlabeled_pool.csv` phục vụ Semi-supervised learning hoặc gán nhãn bổ sung, **tuyệt đối không đưa vào tập Train/Val/Test có giám sát**.

---

## 3. Chiến Lược Phân Chia Tập Dữ Liệu (Splitting Strategy)

### 3.1. Nguyên tắc cốt lõi (Guiding Principles)
1. **Chia theo Group ID (Stem-level Split):** Mọi biến thể augment hoặc crop của cùng một ảnh gốc (cùng `stem_id`) bắt buộc phải thuộc cùng một split (100% Train HOẶC 100% Val HOẶC 100% Test). Triệt tiêu 100% Data Leakage.
2. **Loại bỏ Offline Augmentations khỏi Val/Test:** Tập Validation và Test chỉ chứa ảnh gốc thuần khiết (hoặc 1 đại diện chuẩn nhất), không đưa các bản augment làm lệch thước đo.
3. **Phân tầng đa nhãn (Multilabel Stratified Split):** Giữ tỷ lệ phân bố giữa các loại bệnh đồng đều giữa Train / Val / Test.
4. **Quản lý bằng Manifest (CSV/YAML):** Không copy di chuyển file vật lý làm tốn dung lượng ổ đĩa. Quản lý đường dẫn tương đối qua file chỉ mục.

### 3.2. Tỷ lệ phân chia đề xuất
Dựa trên tập dữ liệu sạch (~1.064 ảnh gốc có nhãn xác định):

| Phân vùng | Tỷ lệ đề xuất | Số lượng ảnh gốc ước tính | Vai trò trong hệ thống |
|:---|:---:|:---:|:---|
| **Train Set** | **70% - 75%** | ~750 - 800 stems | Huấn luyện mô hình (kèm Online Augmentation) |
| **Validation Set** | **15%** | ~150 - 160 stems | Tinh chỉnh Hyperparameters, Early Stopping, chọn Model checkpoint |
| **Test Set** | **15%** | ~150 - 160 stems | Đánh giá độc lập cuối cùng, báo cáo đồ án |

---

## 4. Kế Hoạch Triển Khai Chi Tiết (5 Giai Đoạn)

### Giai đoạn 1: Khám phá, Rà soát & Đánh chỉ mục (Audit & Indexing)
- [ ] **Bước 1.1:** Viết script `audit_dataset.py` quét toàn bộ 29.148 file trong `data/raw`:
  - Trích xuất `stem_id` từ filename (`filename.split('.rf.')[0]`).
  - Tính mã băm `sha256` của từng file ảnh để phát hiện trùng byte tuyệt đối.
  - Phân loại file: Ảnh gốc vs Ảnh đã qua augment Roboflow.
- [ ] **Bước 1.2:** Phân giải nhãn (Label Parsing):
  - Phân tích tên thư mục cha thành tập danh sách bệnh chuẩn (`list[class_code]`).
  - Phát hiện 86 stems có xung đột nhãn và đưa ra quy tắc hòa giải (ưu tiên nhãn xuất hiện nhiều nhất hoặc multi-label union).
- [ ] **Bước 1.3:** Xuất báo cáo sơ bộ `data/reports/raw_audit_report.json`.

### Giai đoạn 2: Chuẩn hóa Schema & Lọc sạch (Data Cleaning & Normalization)
- [ ] **Bước 2.1:** Loại bỏ tập `Unlabeled` (153 stems) ra khỏi tập split có giám sát, lưu vào `data/splits/unlabeled.csv`.
- [ ] **Bước 2.2:** Lựa chọn đại diện ảnh gốc (Original Reference Image):
  - Với mỗi `stem_id`, xác định ảnh gốc chuẩn nhất (ưu tiên ảnh ít biến dạng hình học/màu sắc nhất).
- [ ] **Bước 2.3:** Xây dựng bảng metadata trung tâm `data/processed/master_metadata.csv` gồm các trường:
  - `stem_id`: Mã nhận diện ảnh gốc duy nhất.
  - `file_path`: Đường dẫn tương đối từ thư mục gốc dự án.
  - `labels`: Danh sách mã bệnh (phân tách bởi dấu chấm phẩy `;` hoặc định dạng JSON).
  - `is_healthy`: Boolean (1 nếu là Healthy, 0 nếu có bệnh).
  - `num_diseases`: Số lượng bệnh xuất hiện trên ảnh (0 cho Healthy, 1 cho Single-label, >=2 cho Multi-label).
  - `sha256`: Mã băm kiểm tra toàn vẹn file.

### Giai đoạn 3: Phân chia tập dữ liệu chống rò rỉ (Leak-free Stratified Splitting)
- [ ] **Bước 3.1:** Cố định ngẫu nhiên `SEED = 42` để đảm bảo tính tái lập.
- [ ] **Bước 3.2:** Áp dụng giải thuật chia tập:
  - Sử dụng `MultilabelStratifiedKFold` (từ thư viện `iterative-stratification`) trên cấp độ `stem_id`.
  - Đảm bảo lớp hiếm (như `FUNG_ROSEA`, `PARA_MANGE`) và lớp `HEALTHY` đều phân bổ cân đối ở cả 3 tập.
- [ ] **Bước 3.3:** Kiểm tra giao thoa (Cross-contamination sanity check):
  - Khẳng định toán học: $\text{Train}_{\text{stems}} \cap \text{Val}_{\text{stems}} = \emptyset$
  - $\text{Train}_{\text{stems}} \cap \text{Test}_{\text{stems}} = \emptyset$
  - $\text{Val}_{\text{stems}} \cap \text{Test}_{\text{stems}} = \emptyset$

### Giai đoạn 4: Tạo Manifest & Cấu hình Phiên Bản (Manifest Generation)
- [ ] **Bước 4.1:** Xuất các file manifest trong `data/splits/v1/`:
  - `train.csv`: Danh sách ảnh dành cho huấn luyện (có thể bao gồm các biến thể augment nếu muốn train offline, hoặc chỉ ảnh gốc nếu dùng PyTorch online augment).
  - `val.csv`: Danh sách ảnh validation (chỉ ảnh un-augmented).
  - `test.csv`: Danh sách ảnh test (chỉ ảnh un-augmented).
- [ ] **Bước 4.2:** Tạo file cấu hình `data/splits/v1/dataset_info.yaml`:
  - Ghi nhận: ngày tạo, tác giả, random seed, phiên bản nhãn, tổng số lượng từng split, tỷ lệ phân bố từng lớp bệnh.

### Giai đoạn 5: Tích Hợp DataLoader & Báo Cáo Kiểm Định
- [ ] **Bước 5.1:** Viết script kiểm tra tự động `ml_workspace/src/verify_splits.py` để assert:
  - Không có leakage giữa các tập.
  - Không có đường dẫn file bị lỗi (broken paths).
  - Phân bố các lớp bệnh ở Val/Test phản ánh đúng Train.
- [ ] **Bước 5.2:** Cập nhật `ml_workspace/src/data_loader.py`:
  - Tạo `PigSkinDataset(torch.utils.data.Dataset)` nạp dữ liệu từ manifest CSV.
  - Hỗ trợ cả 2 chế độ:
    - Mode A: **Multi-label Classification** (BCEWithLogitsLoss) - Phù hợp nhất với thực tế heo mắc nhiều bệnh cùng lúc.
    - Mode B: **Single-label Classification** (CrossEntropyLoss) - Lọc chỉ các ảnh đơn bệnh + Healthy nếu đề tài giới hạn single-label.
- [ ] **Bước 5.3:** Xuất biểu đồ phân bố nhãn `data/reports/split_distribution.png` đưa vào báo cáo đồ án `docs/report/`.

---

## 5. Tổ Chức Thư Mục Sau Khi Thực Hiện

```text
DACN/
├── data/
│   ├── raw/
│   │   └── Pig Skin Disease Single Label v2.v3i.folder/   # Giữ nguyên bản gốc
│   ├── processed/
│   │   └── master_metadata.csv                            # Toàn bộ metadata đã chuẩn hóa
│   ├── splits/
│   │   └── v1/
│   │       ├── train.csv                                  # Manifest tập train
│   │       ├── val.csv                                    # Manifest tập validation
│   │       ├── test.csv                                   # Manifest tập test
│   │       ├── unlabeled.csv                              # Tập chưa gán nhãn dự phòng
│   │       └── dataset_info.yaml                          # Thông số phiên bản & Seed
│   └── reports/
│       ├── raw_audit_summary.json                         # Báo cáo rà soát lỗi raw
│       └── split_distribution.png                         # Biểu đồ phân bổ dữ liệu
├── ml_workspace/
│   └── src/
│       ├── dataset_cleaner.py                             # Script thực hiện chia & chuẩn hóa
│       ├── data_loader.py                                 # PyTorch Dataset & DataLoader
│       └── verify_splits.py                               # Script assert kiểm tra rò rỉ
└── plan.md                                                # Tài liệu kế hoạch này
```

---

## 6. Lộ Trình Phối Hợp & Thực Hiện (Action Items)

| Thứ tự | Nhiệm vụ | Đầu ra mong đợi |
|:---:|:---|:---|
| **1** | Chốt phạm vi bài toán: Multi-label (khuyên dùng) hay Single-label lọc bỏ ảnh đa bệnh? | Thống nhất cấu hình nhãn |
| **2** | Viết và chạy `ml_workspace/src/dataset_cleaner.py` tạo `data/splits/v1/` | Bộ file manifest `.csv` và `dataset_info.yaml` |
| **3** | Chạy kiểm tra tự động `verify_splits.py` | 100% test pass (Zero Leakage, Zero Missing) |
| **4** | Hoàn thiện `data_loader.py` trong `ml_workspace` | DataLoader sẵn sàng kết nối vào `train.py` |
