export const pct = (value) => `${Math.round((value || 0) * 100)}%`;
export const dateTime = (value) => new Date(value).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' });

export function Status({ abnormal }) {
  return <span className={`pill ${abnormal ? 'pill-bad' : 'pill-ok'}`}>{abnormal ? 'Cần quan sát' : 'Bình thường'}</span>;
}

export function Empty({ children }) {
  return <div className="py-12 text-center text-sm text-[#879188]">{children}</div>;
}
