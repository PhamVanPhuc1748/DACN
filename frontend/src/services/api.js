/**
 * API contract dự kiến: POST /predict với multipart/form-data, khóa `file`.
 * bbox dùng tọa độ pixel của ảnh gốc. Backend nên trả image_width/image_height nếu có bbox.
 */
export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false';
const BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export async function predictImage(file) {
  if (USE_MOCK) {
    await delay(900);
    const abnormal = Math.random() > 0.35;
    return {
      id: `PIG-${Date.now()}`,
      label: abnormal ? 'Có dấu hiệu bất thường (mô phỏng)' : 'Da bình thường (mô phỏng)',
      confidence: Number((0.85 + Math.random() * 0.12).toFixed(2)),
      abnormal,
      detections: abnormal ? [{ label: 'Vùng da cần quan sát', confidence: 0.88, bbox: [50, 60, 220, 240] }] : [],
      source: 'Kết quả mô phỏng',
      createdAt: new Date().toISOString(),
    };
  }

  const form = new FormData();
  form.append('file', file);
  let response;
  try {
    response = await fetch(`${BASE_URL}/predict`, { method: 'POST', body: form });
  } catch {
    throw new Error(`Không thể kết nối đến FastAPI (${BASE_URL}). Hãy kiểm tra trạng thái máy chủ.`);
  }

  if (!response.ok) {
    let message = `API trả về mã lỗi ${response.status}`;
    try { const body = await response.json(); message = typeof body.detail === 'string' ? body.detail : message; } catch { /* Giữ thông báo mặc định khi phản hồi không phải JSON. */ }
    throw new Error(message);
  }

  const data = await response.json();
  if (typeof data.disease !== 'string' || typeof data.confidence !== 'number') {
    throw new Error('Phản hồi từ API không đúng định dạng mong đợi.');
  }
  const confidence = data.confidence > 1 ? data.confidence / 100 : data.confidence;
  return {
    id: `PIG-${Date.now()}`,
    label: data.disease,
    confidence: Number(confidence.toFixed(2)),
    abnormal: true,
    detections: data.detections || [],
    createdAt: new Date().toISOString(),
    source: 'FastAPI',
  };
}
