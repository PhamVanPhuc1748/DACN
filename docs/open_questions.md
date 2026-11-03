# Open questions chặn triển khai

1. **Nguồn classification chuẩn:** Dùng `data/processed/pig-skin-v4-clean` (6.796 ảnh), archive v4 2.037 ảnh, các folder nhãn cũ, hay hợp nhất có kiểm soát? Ai xác nhận bản nào là nguồn chuẩn và quyền sử dụng ảnh?
2. **203 ảnh review:** Ai sẽ duyệt danh sách review candidates và xác nhận rule `keep / quarantine / review`? Đến khi duyệt, không dùng chúng làm ground truth.
3. **Bài toán nhãn:** 10 lớp single-label hay multi-label? Các folder ghép biểu thị nhiều bệnh thật, nhãn chưa chắc chắn, hay cấu trúc export? Ai có chuyên môn duyệt mapping folder -> class?
4. **Yêu cầu giảng viên:** Có bắt buộc giữ YOLO object detection export 4 lớp, hay phạm vi đã chốt là classification ảnh? Có rubric/tiêu chí nghiệm thu cụ thể cho cảnh báo/video không?
5. **Video mẫu:** Nhóm có video heo thực tế được phép dùng để kiểm tra ROI/framing không? Nếu có, ở đâu, độ dài/nguồn camera và quyền sử dụng? Repo hiện không có video.
6. **Phạm vi ứng dụng:** Xác nhận có đổi mục tiêu từ desktop upload/history hiện tại sang MVP near-real-time MP4 monitoring không, hay chỉ cần trình diễn inference ảnh?
7. **Thiết bị huấn luyện:** Có cho phép cài PyTorch/torchvision và chạy thử baseline trên RTX 4050 6 GiB sau khi chốt dữ liệu không? Hiện môi trường chưa có Torch.
