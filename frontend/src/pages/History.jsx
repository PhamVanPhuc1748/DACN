import { useMemo, useState } from 'react';
import { Search, Trash2, Download, History as HistoryIcon } from 'lucide-react';
import { useHistory } from '../services/history';
import { Status, dateTime, pct, Empty } from '../components/Shared';

export default function History() {
  const { history, clear } = useHistory();
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const rows = useMemo(() => history.filter((item) => (filter === 'all' || (filter === 'abnormal' ? item.abnormal : !item.abnormal)) && `${item.id} ${item.name} ${item.label}`.toLowerCase().includes(query.toLowerCase())), [history, filter, query]);

  function exportCSV() {
    const header = ['Mã phân tích', 'Tên ảnh', 'Thời gian', 'Kết quả', 'Độ tin cậy', 'Nguồn'];
    const data = rows.map((item) => [item.id, item.name, item.createdAt, item.label, item.confidence, item.source]);
    const content = [header, ...data].map((row) => row.map((value) => `"${String(value ?? '').replace(/"/g, '""')}"`).join(',')).join('\r\n');
    const url = URL.createObjectURL(new Blob(['\ufeff' + content], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a'); link.href = url; link.download = 'lich-su-phan-tich.csv'; link.click(); URL.revokeObjectURL(url);
  }

  return (
    <section className="surface overflow-hidden">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-[#e8ece6] p-5 md:p-6">
        <div><h2 className="section-title">Nhật ký phân tích</h2><p className="subtle mt-1">{rows.length} kết quả · Thông tin được lưu trên trình duyệt này</p></div>
        <div className="flex flex-wrap gap-2">
          <button className="btn-secondary text-sm" onClick={exportCSV} disabled={!rows.length}><Download size={15} />Xuất CSV</button>
          <button className="btn-secondary text-sm text-[#9a4e3e]" disabled={!history.length} onClick={() => { if (window.confirm('Xóa toàn bộ lịch sử phân tích trên trình duyệt này?')) clear(); }}><Trash2 size={15} />Xóa lịch sử</button>
        </div>
      </div>
      <div className="flex flex-wrap gap-3 p-4 md:p-5">
        <label className="relative min-w-[220px] flex-1">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#879188]" />
          <input className="field pl-9 text-sm" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm mã, tên ảnh hoặc kết quả…" />
        </label>
        <select aria-label="Lọc kết quả" className="field w-auto min-w-[175px] bg-white text-sm" value={filter} onChange={(event) => setFilter(event.target.value)}>
          <option value="all">Tất cả kết quả</option><option value="normal">Bình thường</option><option value="abnormal">Cần quan sát</option>
        </select>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="bg-[#f5f7f3] text-xs text-[#7c887e]"><tr>{['Mã phân tích', 'Tên ảnh', 'Thời gian', 'Kết quả', 'Độ tin cậy', 'Nguồn'].map((label) => <th key={label} className="px-5 py-3 font-semibold">{label}</th>)}</tr></thead>
          <tbody>{rows.map((item) => (
            <tr key={item.id} className="border-t border-[#edf0eb] transition-colors hover:bg-[#f8f9f6]">
              <td className="px-5 py-4 font-semibold text-brand-700">{item.id}</td>
              <td className="max-w-48 truncate px-5 py-4 font-medium text-[#435148]">{item.name}</td>
              <td className="whitespace-nowrap px-5 py-4 text-[#7e8980]">{dateTime(item.createdAt)}</td>
              <td className="px-5 py-4"><Status abnormal={item.abnormal} /></td>
              <td className="px-5 py-4 font-semibold text-[#46554b]">{pct(item.confidence)}</td>
              <td className="px-5 py-4 text-[#7e8980]">{item.source || '—'}</td>
            </tr>
          ))}</tbody>
        </table>
        {!rows.length && <div className="py-5"><Empty><HistoryIcon className="mx-auto mb-2" size={21} />Không tìm thấy kết quả phù hợp</Empty></div>}
      </div>
      <div className="border-t border-[#e8ece6] bg-[#f8f9f6] px-5 py-4 text-xs leading-relaxed text-[#7e8980]">Ảnh gốc không được lưu trong trình duyệt, chỉ lưu thông tin kết quả. Lịch sử ban đầu là dữ liệu ví dụ.</div>
    </section>
  );
}
