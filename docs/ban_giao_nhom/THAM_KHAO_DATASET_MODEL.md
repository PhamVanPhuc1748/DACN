# Tham khảo: dataset, file và kết quả run

**Cập nhật:** 03/11/2026. Tài liệu này là reference; hướng dẫn thao tác nằm trong [HUONG_DAN_TRAIN_VA_SO_SANH.md](HUONG_DAN_TRAIN_VA_SO_SANH.md).

## Hai thư mục dự án

| Đường dẫn | Vai trò |
|---|---|
| `E:\code\DACN` | Ứng dụng đồ án, UI, backend, tài liệu, bản dataset được tạo để train. |
| `E:\code\PigSkinResearchStudio` | Tool train độc lập, GUI train, script train, checkpoints/logs. |

Các entrypoint chính của tool train:

- `E:\code\PigSkinResearchStudio\training_studio\app.py` — GUI Tkinter.
- `E:\code\PigSkinResearchStudio\run_training_studio.bat` — launcher GUI.
- `E:\code\PigSkinResearchStudio\ml_workspace\train_model.py` — CLI train; hỗ trợ MobileNetV2, MobileNetV3-Large, EfficientNet-B0.
- `E:\code\PigSkinResearchStudio\ml_workspace\runs\<run-id>` — artifacts của từng lượt train.

## Dataset v4 hiện hành

Thư mục: `E:\code\DACN\data\curated\pig_skin_v4_visual_reviewed_v4`

| File/thư mục | Ý nghĩa |
|---|---|
| `train/`, `valid/`, `test/` | Ảnh được liệt kê trong manifest. Tool đọc ảnh theo manifest, không tự suy nhãn từ folder. |
| `manifest.csv` | Danh sách ảnh dùng train/evaluate; các cột là `relative_path, split, labels, group_id`. |
| `classes.json` | Mảng tên 10 lớp theo thứ tự chỉ số đầu ra của model. Giữ nguyên thứ tự khi dùng với checkpoint. |
| `manifest_summary.json` | Số ảnh theo split/lớp và SHA-256 của manifest. |
| `manifest_visual_review.csv` | Lịch sử đường dẫn, split, nhãn gốc và quyết định rà soát. |
| `README_VI.md` | Ghi chú phiên bản dataset và giới hạn rà soát. |
| `review_queue/` | Một ảnh đang để ngoài train/validation/test. |
| `suspected_non_pig/` | Thư mục hiện không có ảnh sau khi người dùng xác nhận các ảnh đó là heo. |

**Split:** train=1.575, val=240, test=201. Manifest SHA-256:

```text
dba25e5585884d3bcb7039e1e6bd921ab73e123cf53334792e973742efe9ea99
```

Lớp theo `classes.json`:

```text
Healthy
Infected_Bacterial_Erysipelas
Infected_Bacterial_Greasy_Pig_Disease
Infected_Environmental_Dermatitis
Infected_Environmental_Sunburn
Infected_Fungal_Pityriasis_Rosea
Infected_Fungal_Ringworm
Infected_Parasitic_Mange
Infected_Viral_Foot_and_Mouth_Disease
Infected_Viral_Swinepox
```

### Giới hạn dữ liệu cần nói rõ

- Nhãn bệnh được kế thừa từ export hiện tại. Chưa có chuyên gia xác minh chẩn đoán từng ảnh.
- Người dùng đã xem và xác nhận 22 ảnh bị cách ly trước đó cùng một ảnh minh họa là hình heo; các ảnh được đưa về split/lớp cũ, không đổi nhãn bệnh.
- Một ảnh còn ở `review_queue` vì bối cảnh ảnh không phù hợp để đưa vào split hiện tại.
- `group_id` bằng relative path từng ảnh. Đây là ID kỹ thuật cho mỗi dòng, **không** phải ID cá thể heo/phiên chụp. Kiểm tra exact SHA giúp phát hiện bản sao byte-identical giữa split nhưng không loại trừ ảnh cùng heo hoặc near-duplicate.
- v3 (`pig_skin_v4_visual_reviewed_v3`) là manifest cũ với 1.552 ảnh train. Không dùng v3 để so với run v4 khi kết luận kiến trúc.

## Các file mỗi run

| File | Nội dung |
|---|---|
| `config.json` | Model, seed, preprocessing, thông số train, manifest path/hash, split counts và môi trường. Dùng xác minh hai run có cùng điều kiện không. |
| `history.csv` | Loss và validation metrics theo epoch; dùng xem học tiến bộ hay overfit. |
| `best_model.pt` | Checkpoint tốt nhất được chọn theo validation macro-F1. |
| `best_validation.json` | Metrics và confusion matrix tại checkpoint tốt nhất. |
| `final_metrics.json` | Kết quả test của checkpoint đã chọn. Không dùng test để tune tiếp. |

## Các run trên manifest v4

Các điểm dưới đây đều dùng manifest hash `dba25e...ea99`, split 1.575/240/201, pretrained ImageNet, image 224, batch 16, seed ghi bên dưới; test có 201 ảnh.

| Model | Seed | Run | Val macro-F1 | Test accuracy | Test macro-F1 | Tình trạng |
|---|---:|---|---:|---:|---:|---|
| MobileNetV2 | 42 | `20261103_124605` | 69,1% | 60,7% | 59,8% | Hoàn tất |
| EfficientNet-B0 | 42 | `20261103_125004` | 71,2% | 62,7% | 62,2% | Hoàn tất |
| MobileNetV2 | 123 | `20261103_125653` | 72,4% | 64,2% | 63,6% | Hoàn tất |
| EfficientNet-B0 | 123 | `20261103_130213` | 70,8% | 60,2% | 59,9% | Hoàn tất |
| MobileNetV2 | 2026 | `20261103_130855` | 71,5% | 64,2% | 63,3% | Hoàn tất |
| EfficientNet-B0 | 2026 | `20261103_131518` | 70,9% | 65,2% | 64,6% | Hoàn tất; best epoch 11 |

Qua ba seed, test macro-F1 trung bình là khoảng 62,2% cho cả hai kiến trúc (EfficientNet-B0 62,25%; MobileNetV2 62,21%). Validation macro-F1 trung bình cũng gần như ngang nhau (EfficientNet-B0 70,94%; MobileNetV2 71,00%). Kiến trúc xếp hạng đổi theo seed, nên chưa có bằng chứng model nào thắng ổn định. Dùng validation macro-F1 và per-class recall để chọn; mỗi lớp test chỉ có 13–31 ảnh nên metric theo lớp biến động theo vài ảnh.

Ở seed 2026, EfficientNet-B0 đạt test macro-F1 64,6% và accuracy 65,2%, cao hơn MobileNetV2 cùng seed (63,3% và 64,2%). Chênh lệch tương ứng khoảng 1,3 điểm phần trăm macro-F1 và 2 ảnh đúng trên 201 ảnh. Xem đây là kết quả tốt nhất của một run, không phải kết luận chắc chắn về ưu thế kiến trúc.

EfficientNet-B0 seed 2026 đạt validation macro-F1 cao nhất ở epoch 11 (70,9%; val loss 0,8693). Train loss tiếp tục giảm trong khi validation loss nhìn chung tăng về sau, phù hợp với dấu hiệu overfit; checkpoint tốt nhất đã được lưu đúng ở epoch 11. Trên test, Mange có F1 31,6%, Erysipelas 50,0% và Dermatitis 53,7%; đây là các lớp cần ưu tiên rà lỗi/nhãn.

Run MobileNetV2 seed 2026 có train loss giảm còn khoảng 0,07 ở cuối, trong khi val loss tăng trên 1,2; đây là dấu hiệu overfit ở các epoch cuối. Checkpoint của run được chọn theo validation macro-F1, không phải epoch cuối.

## Tình trạng ứng dụng đồ án

`PigSkinTech` là ứng dụng demo riêng với luồng suy luận checkpoint và dữ liệu hồ sơ cục bộ. Backend FastAPI là một luồng riêng; README hiện ghi API chưa được nối với suy luận checkpoint thật. Không coi trạng thái trong `docs/current_state.md` (snapshot 22/10) là trạng thái run/model mới nhất.

## Chia sẻ sang máy khác

`data/` bị loại khỏi Git và training workspace hiện nằm ngoài repo DACN. Người nhận cần được cấp bản sao hợp lệ của dataset v4 và thư mục `E:\code\PigSkinResearchStudio`; các đường dẫn tuyệt đối phải đổi theo máy nhận. Không chỉ dựa vào manifest: manifest chứa đường dẫn tương đối, nhưng ảnh cần có trong thư mục gốc tương ứng.
