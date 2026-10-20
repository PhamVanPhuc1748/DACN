import { BrainCircuit, Server, Layers, Image, Info, Workflow } from 'lucide-react';
import { modelInfo } from '../data/mock';
import { USE_MOCK } from '../services/api';

export default function Model() {
  const details = [
    { icon: BrainCircuit, label: 'Mô hình đề xuất', value: modelInfo.name },
    { icon: Layers, label: 'Phiên bản giao diện', value: modelInfo.version },
    { icon: Image, label: 'Định dạng đầu vào', value: modelInfo.input },
    { icon: Server, label: 'Chế độ kết nối', value: USE_MOCK ? 'API mô phỏng' : 'FastAPI' },
  ];
  const steps = ['Tải ảnh da heo từ giao diện', 'FastAPI tiếp nhận và kiểm tra định dạng', 'Tiền xử lý ảnh rồi chạy bộ phân loại', 'Trả về nhãn, độ tin cậy và vùng phát hiện', 'Hiển thị kết quả và lưu lịch sử trên thiết bị'];

  return (
    <div className="space-y-5">
      <section className="surface flex flex-wrap items-center justify-between gap-4 p-5 md:p-6">
        <div className="flex items-center gap-4">
          <span className="grid h-12 w-12 place-items-center rounded-xl bg-[#e7efe7] text-brand-700"><BrainCircuit size={24} strokeWidth={1.7} /></span>
          <div><h2 className="section-title">Thông tin mô hình</h2><p className="subtle mt-1">Cấu hình hiện tại và trạng thái tích hợp</p></div>
        </div>
        <span className={`pill ${USE_MOCK ? 'pill-warn' : 'pill-ok'}`}>{USE_MOCK ? 'Bản mô tả thử nghiệm' : 'Đã kết nối API'}</span>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {details.map(({ icon: Icon, label, value }) => <div className="surface p-4" key={label}><Icon size={18} className="mb-4 text-[#718875]" strokeWidth={1.8} /><p className="text-xs text-[#818c83]">{label}</p><p className="mt-1.5 text-sm font-semibold leading-relaxed text-[#3e4d43]">{value}</p></div>)}
      </section>

      <div className="grid gap-5 xl:grid-cols-2">
        <section className="surface p-5 md:p-6">
          <h3 className="section-title">Chỉ số đánh giá</h3><p className="subtle mt-1">Chưa có kết quả thực nghiệm được xác thực</p>
          <div className="mt-5 grid grid-cols-2 gap-3">
            {modelInfo.metrics.map((metric) => <div key={metric.name} className="rounded-lg border border-[#e7ebe5] bg-[#f8f9f6] p-4"><p className="text-xs text-[#7e8980]">{metric.name}</p><p className="mt-2 text-lg font-semibold text-[#415247]">{metric.value}</p></div>)}
          </div>
          <p className="mt-4 rounded-lg bg-[#f7f0dc] p-3 text-xs leading-relaxed text-[#74591c]">Không có chỉ số accuracy hoặc mAP được điền sẵn. Hãy cập nhật số liệu sau khi đánh giá trên tập test.</p>
        </section>

        <section className="surface p-5 md:p-6">
          <h3 className="section-title">Luồng xử lý dự kiến</h3>
          <div className="mt-5 space-y-0">
            {steps.map((step, index) => <div className="relative flex gap-3 pb-4 last:pb-0" key={step}>
              {index < steps.length - 1 && <span className="absolute left-[13px] top-7 h-[calc(100%-8px)] w-px bg-[#dce5dc]" />}
              <span className="relative grid h-7 w-7 shrink-0 place-items-center rounded-full bg-[#e8efe8] text-xs font-semibold text-brand-700">{index + 1}</span>
              <p className="pt-1 text-sm leading-relaxed text-[#59675d]">{step}</p>
            </div>)}
          </div>
        </section>
      </div>

      <section className="surface p-5 md:p-6">
        <h3 className="section-title flex items-center gap-2"><Workflow size={18} className="text-[#718875]" />Kết nối backend</h3>
        <p className="subtle mt-1">Đặt <code className="rounded bg-[#f1f3ef] px-1.5 py-0.5 text-xs">VITE_USE_MOCK=false</code> trong file <code className="rounded bg-[#f1f3ef] px-1.5 py-0.5 text-xs">.env</code> để gửi ảnh đến FastAPI.</p>
        <pre className="mt-4 overflow-x-auto rounded-lg bg-[#263b30] p-4 text-xs leading-6 text-[#e1ebe3] md:text-sm">{`POST /predict
Content-Type: multipart/form-data
Form field: file

Response JSON:
{
  "disease": "Tên lớp dự đoán",
  "confidence": 0.94,
  "detections": []
}`}</pre>
        <p className="mt-3 flex gap-2 text-xs leading-relaxed text-[#7d887f]"><Info size={15} className="mt-0.5 shrink-0" />Tọa độ bounding box dùng pixel của ảnh gốc. Mảng detections có thể rỗng nếu mô hình chỉ phân loại toàn ảnh.</p>
      </section>
    </div>
  );
}
