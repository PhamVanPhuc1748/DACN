export const trend = [
  { day: 'T2', total: 18, abnormal: 4 },
  { day: 'T3', total: 24, abnormal: 6 },
  { day: 'T4', total: 19, abnormal: 3 },
  { day: 'T5', total: 28, abnormal: 7 },
  { day: 'T6', total: 32, abnormal: 8 },
  { day: 'T7', total: 15, abnormal: 2 },
  { day: 'CN', total: 12, abnormal: 1 },
];

export const seedHistory = [
  {
    id: 'PIG-HIST-001',
    name: 'heo_chuong_01_tai.jpg',
    label: 'Bệnh đóng dấu lợn (Erysipelas)',
    confidence: 0.94,
    abnormal: true,
    detections: [
      { label: 'Vùng ban đỏ dạng kim cương', confidence: 0.93, bbox: [45, 60, 180, 210] }
    ],
    createdAt: new Date(Date.now() - 3600000 * 2).toISOString(),
    source: 'Hệ thống mô phỏng'
  },
  {
    id: 'PIG-HIST-002',
    name: 'heo_chuong_02_lung.jpg',
    label: 'Bình thường (Khỏe mạnh)',
    confidence: 0.98,
    abnormal: false,
    detections: [],
    createdAt: new Date(Date.now() - 3600000 * 5).toISOString(),
    source: 'Hệ thống mô phỏng'
  },
  {
    id: 'PIG-HIST-003',
    name: 'heo_chuong_03_bung.jpg',
    label: 'Viêm da tiết dịch (Greasy Pig)',
    confidence: 0.89,
    abnormal: true,
    detections: [
      { label: 'Vết vảy nhờn nâu', confidence: 0.88, bbox: [30, 40, 150, 190] }
    ],
    createdAt: new Date(Date.now() - 3600000 * 24).toISOString(),
    source: 'Hệ thống mô phỏng'
  },
  {
    id: 'PIG-HIST-004',
    name: 'heo_chuong_01_mong.jpg',
    label: 'Lở mồm long móng (FMD)',
    confidence: 0.96,
    abnormal: true,
    detections: [
      { label: 'Mụn nước và loét kẽ móng', confidence: 0.95, bbox: [60, 80, 210, 230] }
    ],
    createdAt: new Date(Date.now() - 3600000 * 48).toISOString(),
    source: 'Hệ thống mô phỏng'
  }
];

export const modelInfo = {
  name: 'YOLOv8x / Swin-Transformer PigSkin',
  version: '1.0.0-dev',
  input: '224x224 / 640x640 RGB (JPG/PNG/WEBP)',
  metrics: [
    { name: 'mAP@50 (Dự kiến)', value: 'Chờ train' },
    { name: 'F1-Score', value: 'Chờ train' },
    { name: 'Precision', value: 'Chờ train' },
    { name: 'Recall', value: 'Chờ train' },
  ]
};
