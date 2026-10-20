/** Contract dự kiến: POST /predict (multipart/form-data, key `file`)
 * JSON: {id?,label,confidence,abnormal,detections?:[{label,confidence,bbox:[x1,y1,x2,y2]}],image_url?}
 * bbox dùng tọa độ pixel TRÊN ẢNH GỐC. Backend nên trả image_width/image_height nếu bbox tồn tại.
 */
export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false';
const BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const delay = (ms) => new Promise(r => setTimeout(r, ms));

export async function predictImage(file) {
  if (USE_MOCK) {
    await delay(1200);
    const abnormal = Math.random() > 0.35;
    return {
      id: `PIG-${Date.now()}`,
      label: abnormal ? 'Phát hiện tổn thương (Mô phỏng)' : 'Da bình thường (Khỏe mạnh)',
      confidence: Number((0.85 + Math.random() * 0.12).toFixed(2)),
      abnormal,
      detections: abnormal ? [
        { label: 'Vùng viêm da đỏ', confidence: 0.88, bbox: [50, 60, 220, 240] }
      ] : [],
      source: 'Giao diện mô phỏng (Offline Mock)',
      createdAt: new Date().toISOString()
    };
  }

  const form = new FormData();
  form.append('file', file);

  let response;
  try {
    response = await fetch(`${BASE_URL}/predict`, {
      method: 'POST',
      body: form
    });
  } catch (err) {
    throw new Error('Không thể kết nối đến FastAPI Backend (http://127.0.0.1:8000). Vui lòng kiểm tra server.');
  }

  if (!response.ok) {
    let message = `API trả mã lỗi ${response.status}`;
    try {
      const body = await response.json();
      message = typeof body.detail === 'string' ? body.detail : message;
    } catch {}
    throw new Error(message);
  }

  const data = await response.json();

  if (typeof data.disease !== 'string' || typeof data.confidence !== 'number') {
    throw new Error('Kết quả phản hồi từ API không đúng định dạng chuẩn.');
  }

  return {
    id: `PIG-${Date.now()}`,
    label: data.disease,
    confidence: data.confidence > 1 ? Number((data.confidence / 100).toFixed(2)) : Number(data.confidence.toFixed(2)),
    abnormal: true,
    detections: data.detections || [],
    createdAt: new Date().toISOString(),
    source: 'FastAPI Backend Server'
  };
}
