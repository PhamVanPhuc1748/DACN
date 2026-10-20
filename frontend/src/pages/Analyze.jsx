import { useEffect, useRef, useState } from 'react';
import { UploadCloud, Image as ImageIcon, LoaderCircle, CheckCircle2, AlertTriangle, RotateCcw, ScanSearch, Info } from 'lucide-react';
import { predictImage, USE_MOCK } from '../services/api';
import { useHistory } from '../services/history';
import { pct } from '../components/Shared';

const MAX = 10 * 1024 * 1024;
const TYPES = ['image/jpeg', 'image/png', 'image/webp'];

export default function Analyze() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [drag, setDrag] = useState(false);
  const [imgSize, setImgSize] = useState(null);
  const input = useRef(null);
  const { add } = useHistory();

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  function choose(nextFile) {
    setError('');
    setResult(null);
    setImgSize(null);
    if (!nextFile) return;
    if (!TYPES.includes(nextFile.type)) { setError('Hãy chọn ảnh JPG, PNG hoặc WEBP.'); return; }
    if (nextFile.size > MAX) { setError('Ảnh vượt quá dung lượng tối đa 10 MB.'); return; }
    setFile(nextFile);
    setPreview(URL.createObjectURL(nextFile));
  }

  function reset() {
    setFile(null); setResult(null); setError(''); setImgSize(null);
    if (input.current) input.current.value = '';
    setPreview('');
  }

  async function analyze() {
    if (!file || loading) return;
    setLoading(true); setError(''); setResult(null);
    try {
      const response = await predictImage(file);
      setResult(response);
      add({ ...response, name: file.name, imageUrl: null });
    } catch (err) {
      setError(err.message || 'Không thể phân tích ảnh. Hãy kiểm tra kết nối rồi thử lại.');
    } finally { setLoading(false); }
  }

  return (
    <div className="space-y-5">
      <section className="surface p-5 md:p-7">
        <div className="mb-6 flex items-start gap-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[#e7efe7] text-brand-700"><ScanSearch size={19} /></span>
          <div><h2 className="section-title">Một góc ảnh rõ giúp quan sát tốt hơn</h2><p className="subtle mt-1">Chọn ảnh vùng da cần kiểm tra. Mô hình sẽ trả về một gợi ý để bạn tham khảo.</p></div>
        </div>

        <div className="grid gap-5 lg:grid-cols-[1.08fr_.92fr]">
          <div>
            <input ref={input} hidden type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => choose(event.target.files?.[0])} />
            {preview ? (
              <div className="rounded-xl border border-[#dfe5dd] bg-[#f5f7f3] p-3">
                <div className="relative flex min-h-[280px] items-center justify-center overflow-hidden rounded-lg bg-[#e8ece6]">
                  <img className="max-h-[430px] w-full object-contain" src={preview} alt="Ảnh da heo đã chọn" onLoad={(event) => setImgSize({ width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight })} />
                  {result?.detections?.length > 0 && imgSize && <svg className="pointer-events-none absolute inset-0 h-full w-full" viewBox={`0 0 ${imgSize.width} ${imgSize.height}`} preserveAspectRatio="xMidYMid meet">{result.detections.map((detection, index) => Array.isArray(detection.bbox) && detection.bbox.length === 4 ? <g key={index}><rect x={detection.bbox[0]} y={detection.bbox[1]} width={Math.max(0, detection.bbox[2] - detection.bbox[0])} height={Math.max(0, detection.bbox[3] - detection.bbox[1])} stroke="#bd765c" strokeWidth={Math.max(2, imgSize.width / 250)} fill="none" /><text x={detection.bbox[0]} y={Math.max(15, detection.bbox[1] - 5)} fill="#8c4434" fontSize={Math.max(16, imgSize.width / 35)} fontWeight="bold">{detection.label} {pct(detection.confidence)}</text></g> : null)}</svg>}
                </div>
                <p className="break-all px-1 pt-3 text-xs text-[#7d887f]">{file?.name} · {(file?.size / 1024 / 1024).toFixed(2)} MB</p>
              </div>
            ) : (
              <button type="button" onClick={() => input.current?.click()} onDragOver={(event) => { event.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={(event) => { event.preventDefault(); setDrag(false); choose(event.dataTransfer.files?.[0]); }} className={`flex min-h-[318px] w-full flex-col items-center justify-center rounded-xl border border-dashed px-5 text-center transition-colors ${drag ? 'border-brand-600 bg-[#e8f0e8]' : 'border-[#bac9ba] bg-[#f7f9f5] hover:bg-[#f0f4ef]'}`}>
                <span className="grid h-14 w-14 place-items-center rounded-full bg-[#e4ece3] text-brand-700"><UploadCloud size={27} strokeWidth={1.7} /></span>
                <span className="mt-4 font-semibold text-[#3b4c40]">Kéo ảnh vào đây</span>
                <span className="mt-1 text-sm text-[#7f8a80]">hoặc chọn ảnh từ thiết bị</span>
                <span className="mt-4 text-xs text-[#929b93]">JPG, PNG, WEBP · Tối đa 10 MB</span>
              </button>
            )}
            <div className="mt-4 flex flex-wrap gap-2.5">
              {file && <button className="btn-secondary" onClick={() => input.current?.click()}><ImageIcon size={16} />Đổi ảnh</button>}
              <button className="btn-primary flex-1" disabled={!file || loading} onClick={analyze}>{loading ? <LoaderCircle size={17} className="animate-spin" /> : <ScanSearch size={17} />}{loading ? 'Đang xem ảnh…' : 'Phân tích ảnh'}</button>
              {file && <button className="btn-secondary" onClick={reset} aria-label="Xóa ảnh"><RotateCcw size={16} /></button>}
            </div>
            {error && <div role="alert" className="mt-3 rounded-lg border border-[#f0d6ce] bg-[#fbefeb] p-3 text-sm text-[#8e4939]">{error}</div>}
          </div>

          <div className="flex min-h-[380px] flex-col rounded-xl border border-[#e3e8e1] bg-[#f8f9f6] p-5 md:p-6">
            <div><h3 className="section-title">Gợi ý từ mô hình</h3><p className="subtle mt-1">Kết quả và thông tin xử lý ảnh</p></div>
            {result ? (
              <div className="mt-6 space-y-4">
                <div className={`flex gap-3 rounded-xl p-4 ${result.abnormal ? 'bg-[#f8e8e3] text-[#8e4939]' : 'bg-[#e5f0e7] text-[#2c6044]'}`}>
                  {result.abnormal ? <AlertTriangle size={22} /> : <CheckCircle2 size={22} />}
                  <div><p className="text-xs font-semibold">Kết quả dự đoán</p><p className="mt-1 text-lg font-semibold leading-snug">{result.label}</p></div>
                </div>
                <div className="rounded-lg border border-[#e2e7e0] bg-white p-4">
                  <div className="mb-2 flex justify-between gap-3 text-sm"><span className="text-[#78837a]">Độ tin cậy của mô hình</span><span className="font-semibold text-[#35483a]">{pct(result.confidence)}</span></div>
                  <div className="h-2 overflow-hidden rounded-full bg-[#edf0eb]"><div className="h-full rounded-full bg-[#64816b]" style={{ width: `${Math.max(0, Math.min(100, result.confidence * 100))}%` }} /></div>
                </div>
                <dl className="space-y-3 px-1 text-sm">
                  <div className="flex justify-between gap-3"><dt className="text-[#7d887f]">Mã phân tích</dt><dd className="break-all text-right font-medium">{result.id}</dd></div>
                  <div className="flex justify-between gap-3"><dt className="text-[#7d887f]">Vùng được đánh dấu</dt><dd className="font-medium">{result.detections?.length || 0}</dd></div>
                  <div className="flex justify-between gap-3"><dt className="text-[#7d887f]">Nguồn</dt><dd className="text-right font-medium">{result.source}</dd></div>
                </dl>
                {USE_MOCK && <div className="flex gap-2 rounded-lg border border-[#e9d9ae] bg-[#f7f0dc] p-3 text-xs leading-relaxed text-[#74591c]"><Info size={16} className="shrink-0" /><span>Kết quả được tạo ngẫu nhiên để minh họa giao diện, không dựa trên ảnh đã tải lên.</span></div>}
              </div>
            ) : (
              <div className="flex flex-1 flex-col items-center justify-center py-12 text-center">
                <span className="grid h-14 w-14 place-items-center rounded-full bg-[#edf2eb] text-[#8ca08e]"><ScanSearch size={25} strokeWidth={1.6} /></span>
                <p className="mt-4 text-sm font-semibold text-[#526156]">Chưa có kết quả</p>
                <p className="mt-1 max-w-[250px] text-sm leading-relaxed text-[#879188]">Chọn ảnh rồi bắt đầu phân tích để xem gợi ý tại đây.</p>
              </div>
            )}
          </div>
        </div>
      </section>

      <aside className="flex gap-3 rounded-xl border border-[#e2e6df] bg-[#f8f9f6] p-4 text-sm leading-relaxed text-[#78837a]">
        <Info size={17} className="mt-0.5 shrink-0 text-[#748b77]" />
        <p>Đây là công cụ hỗ trợ nghiên cứu, không thay thế bác sĩ thú y. Khi kết nối mô hình phát hiện vùng tổn thương, các vùng đó sẽ được đánh dấu trực tiếp trên ảnh.</p>
      </aside>
    </div>
  );
}
