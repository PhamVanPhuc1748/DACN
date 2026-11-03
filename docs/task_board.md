# Task board — tuần 2 đến tuần 4

Owners theo phân vai trong brief: TV1 AI/Data, TV2 Backend/Video, TV3 Frontend/Test. Các tiêu chí dưới đây chặn việc tuyên bố hoàn thành khi chưa có bằng chứng.

| Tuần | Owner | Task | Dependency | Acceptance criteria |
|---|---|---|---|---|
| 2 | TV1 | Chốt nguồn classification, taxonomy/single-vs-multi-label; rà 203 review items và duplicate candidates; duyệt group key; chuẩn bị manifest đề xuất | Chủ dữ liệu/giảng viên trả lời `open_questions.md`; không tự xóa ảnh | Quyết định nhãn có người duyệt; report ghi rõ nguồn/license; manifest giữ path/hash/group và không giao group qua splits; danh sách review còn nguyên |
| 2 | TV2 | Đối chiếu API/schema hiện tại với MVP; thống nhất API contract tối thiểu và event/status model; làm rõ phần mock so với inference thật | TV1 chốt input/class output; thống nhất scope với nhóm | Contract có request/response/error/auth assumptions; schema changes chỉ ở dạng đề xuất; demo không tự nhận là model thật |
| 2 | TV3 | Chốt wireframe use case upload, result, history, alert/review; viết test cases luồng hiện có và mục tiêu MVP | TV2 contract | Wireframe/test case bám API; có trạng thái uncertain, unobservable và monitoring unavailable |
| 3 | TV1 | Tạo split manifest v1 từ tập đã duyệt; dựng MobileNetV2 baseline nhỏ theo config thống nhất | Task tuần 2 được duyệt; dependency Torch/CUDA được thống nhất | Split tái lập, nhóm không leakage, class mapping/config/version lưu lại; báo cáo metrics trên test chỉ sau khi pipeline được kiểm chứng |
| 3 | TV2 | Bổ sung inference adapter phía backend và health/status cho model chưa nạp | TV1 contract/preprocessing; chưa cần thay DB thật | Inference thật hoặc lỗi model-not-ready rõ ràng; không dùng nhãn suy từ filename |
| 3 | TV3 | UI upload/result và hiển thị nguồn/trạng thái inference | API contract + mock/inference behavior | Luồng thành công/lỗi/uncertain có thể trình diễn; không hiển thị mock score như kết quả thật |
| 4 | TV1 | Chạy EfficientNet-B0 comparison trên cùng split; rà lỗi theo class; thu thập mẫu video/ROI nếu có | Baseline MobileNetV2 và dữ liệu/video được duyệt | So sánh trên cùng test; nêu giới hạn domain; chưa có video thì ghi `VIDEO_DATA_UNAVAILABLE` |
| 4 | TV2 | Thử MP4 playback theo clock và sampling giới hạn; đánh giá ROI có kiểm soát trước khi thêm worker/event | Có video được duyệt và ROI contract | Báo cáo frame-to-decision latency và nguồn; video lỗi tách khỏi trạng thái normal; không giả định detector heo phù hợp |
| 4 | TV3 | UI monitoring/history prototype và tiêu chí nhận event/feedback | Event contract + luồng TV2 | Dashboard hiển thị trạng thái nguồn và event test; có kịch bản false alert/manual review |

## Cổng kiểm tra cuối tuần 4

Không tuyên bố realtime trên đàn heo nếu chưa có video kiểm chứng và ROI phù hợp. Không tạo/sửa schema production hoặc cài dependency lớn chỉ để hoàn tất task tuần 3; trình bày kế hoạch và tác động trước khi nhóm chọn.
