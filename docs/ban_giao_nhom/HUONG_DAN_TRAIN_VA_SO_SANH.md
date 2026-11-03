# Hướng dẫn train và so sánh model

**Mục đích:** chạy lại MobileNetV2/EfficientNet-B0 trên đúng dataset v4, giữ điều kiện khớp và ghi lại kết quả.

## Cấu hình nguồn dữ liệu trong GUI

Mở `E:\code\PigSkinResearchStudio\run_training_studio.bat`, tab **Huấn luyện**, nhập ba đường dẫn tuyệt đối:

```text
Manifest CSV:    E:\code\DACN\data\curated\pig_skin_v4_visual_reviewed_v4\manifest.csv
Thư mục gốc ảnh: E:\code\DACN\data\curated\pig_skin_v4_visual_reviewed_v4
Class map JSON:  E:\code\DACN\data\curated\pig_skin_v4_visual_reviewed_v4\classes.json
```

Đối chiếu manifest hash trong `config.json` với:

```text
dba25e5585884d3bcb7039e1e6bd921ab73e123cf53334792e973742efe9ea99
```

Nếu hash khác, dừng so sánh và xác định manifest nào đã được chọn.

## Cấu hình baseline

Dùng các giá trị sau để kết quả đối chiếu các seed/model có thể so sánh:

| Tham số | Giá trị |
|---|---:|
| Model | Chạy mỗi lượt một model: `mobilenet_v2` hoặc `efficientnet_b0` |
| ImageNet pretrained | Bật |
| Epoch tối đa | 30 |
| Head-only epochs | 5 |
| Batch size | 16 |
| Image size | 224 |
| Head LR | 0.001 |
| Fine-tune LR | 0.0001 |
| Weight decay | 0.0001 |
| Early-stop patience | 12 (giữ nguyên để khớp với run hiện có) |
| Augmentation | Bật; flip 0.5, rotation 10°, brightness/contrast 0.1, saturation 0.05 |
| Device | `auto` hoặc `cuda` |
| Seed | 42, 123, 2026 |

RTX 4050 máy này đã chạy batch 16 và ảnh 224. Nếu gặp CUDA out-of-memory, giảm batch size xuống 8 và ghi rõ đây là cấu hình khác.

## Dry-run trước khi train

Từ PowerShell, kiểm tra đường dẫn, nhãn và ảnh trước:

```powershell
& 'E:\code\PigSkinResearchStudio\.venv\Scripts\python.exe' `
  'E:\code\PigSkinResearchStudio\ml_workspace\train_model.py' `
  --manifest 'E:\code\DACN\data\curated\pig_skin_v4_visual_reviewed_v4\manifest.csv' `
  --image-root 'E:\code\DACN\data\curated\pig_skin_v4_visual_reviewed_v4' `
  --classes-file 'E:\code\DACN\data\curated\pig_skin_v4_visual_reviewed_v4\classes.json' `
  --dry-run
```

Chỉ train khi dry-run báo manifest hợp lệ, đủ train/val/test, ảnh đọc được và không có exact-SHA leak qua split.

## Cách so sánh

1. Giữ nguyên manifest hash và mọi cấu hình; chỉ đổi model hoặc seed theo ma trận đã phân công.
2. Sáu run của MobileNetV2 và EfficientNet-B0 cho seed 42, 123, 2026 đã hoàn tất trên cùng manifest v4. Không cần chạy lại để hoàn thiện bảng.
3. Ghi run ID, model, seed, manifest hash, best epoch, validation macro-F1, per-class recall/F1, test macro-F1 và test accuracy.
4. Trung bình validation macro-F1 hiện gần như bằng nhau (EfficientNet-B0 70,94%; MobileNetV2 71,00%). Chọn theo validation macro-F1 qua seed và per-class recall; test đã được xem nhiều lần nên chỉ báo cáo minh bạch, không tune theo nó.
5. Khi kiểm tra overfit, đối chiếu `train_loss` và `val_loss` trong `history.csv`. Dùng `best_model.pt`, không dùng weights epoch cuối nếu checkpoint tốt nhất ở epoch trước.
6. Thay đổi một thông số mỗi thí nghiệm và tạo run mới; không ghi đè artifacts.

## Đọc kết quả

- `macro-F1`: trung bình F1 giữa 10 lớp; dùng để xem model có bỏ quên lớp nào không.
- `per_class` precision/recall/F1: chỉ ra lớp cần rà ảnh hoặc nhãn.
- `confusion_matrix`: hàng là nhãn thật, cột là dự đoán; xem nhầm lẫn giữa bệnh gần nhau.
- `val_loss` khoảng 1 không tự nó kết luận tốt/xấu. Nếu train loss tiếp tục giảm trong khi val loss tăng và val metrics chững/giảm, có dấu hiệu overfit.
- Test split chỉ có 201 ảnh (13–31 ảnh/lớp); chênh lệch vài ảnh có thể làm metric đổi đáng kể.

## Lưu ý về nhãn

Không chuyển ảnh sang nhãn bệnh chỉ vì model dự đoán lớp đó. Người rà dữ liệu cần ghi nguồn xác minh; nếu chưa xác minh được, đánh dấu `review` và giữ manifest v4 nguyên vẹn. Xác nhận ảnh là heo không đồng nghĩa xác nhận bệnh.
