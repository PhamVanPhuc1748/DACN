# Checkpoint được tích hợp trong app

App có thể chọn MobileNetV2 hoặc EfficientNet-B0 ở tab **Phân tích ảnh**. Mỗi checkpoint được chọn theo validation macro-F1 cao nhất trong các run có cùng manifest v4; app không chọn checkpoint dựa vào test score.

| Model | Run | Seed | Validation macro-F1 | Test macro-F1 tham khảo |
|---|---|---:|---:|---:|
| MobileNetV2 | `20261103_125653` | 123 | 72,35% | 63,55% |
| EfficientNet-B0 | `20261103_125004` | 42 | 71,16% | 62,24% |

Cả hai run dùng manifest SHA-256 `dba25e5585884d3bcb7039e1e6bd921ab73e123cf53334792e973742efe9ea99`, 10 lớp và ảnh đầu vào 224×224. Test set đã được xem qua nhiều lần thử nghiệm; các chỉ số test ở trên chỉ là kết quả tham khảo, không phải đánh giá độc lập cuối cùng.

Mỗi thư mục run giữ checkpoint, config và metrics nguồn để app nạp đúng kiến trúc, thứ tự lớp và preprocessing. Không đổi tên file `best_model.pt`, `config.json` hoặc `final_metrics.json`.
