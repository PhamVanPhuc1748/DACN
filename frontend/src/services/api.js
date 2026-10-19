/** Contract dự kiến: POST /predict (multipart/form-data, key `file`)
 * JSON: {id?,label,confidence,abnormal,detections?:[{label,confidence,bbox:[x1,y1,x2,y2]}],image_url?}
 * bbox dùng tọa độ pixel TRÊN ẢNH GỐC. Backend nên trả image_width/image_height nếu bbox tồn tại.
 */
export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false';
const BASE_URL=(import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/,'');
const delay=(ms)=>new Promise(r=>setTimeout(r,ms));
export async function predictImage(file){
 if(USE_MOCK){await delay(1300);const abnormal=Math.random()>.42;return {id:`PIG-${Date.now()}`,label:abnormal?'Bất thường':'Bình thường',confidence:Number((.83+Math.random()*.15).toFixed(2)),abnormal,detections:[],source:'Kết quả MÔ PHỎNG – không phải AI thật',createdAt:new Date().toISOString()};}
 const form=new FormData();form.append('file',file);
 let response;try{response=await fetch(`${BASE_URL}/predict`,{method:'POST',body:form});}catch{throw new Error('Không kết nối được FastAPI. Kiểm tra server và CORS.');}
 if(!response.ok){let message=`API trả lỗi ${response.status}`;try{const body=await response.json();message=typeof body.detail==='string'?body.detail:message;}catch{}throw new Error(message);}

const data = await response.json();

if (typeof data.disease !== 'string' ||
    typeof data.confidence !== 'number') {
  throw new Error('Kết quả API không đúng định dạng.');
}

return {
  id: `PIG-${Date.now()}`,
  label: data.disease,
  confidence: data.confidence / 100,
  abnormal: true,
  detections: [],
  createdAt: new Date().toISOString(),
  source: 'FastAPI MOCK - Chưa tích hợp AI thật'
};
}