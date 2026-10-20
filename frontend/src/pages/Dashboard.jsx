import { Link } from 'react-router-dom';
import { Images, ShieldCheck, AlertTriangle, ArrowUpRight, ScanSearch, Activity } from 'lucide-react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts';
import { trend } from '../data/mock';
import { useHistory } from '../services/history';
import { Status, dateTime, pct, Empty } from '../components/Shared';

export default function Dashboard() {
  const { history } = useHistory();
  const normal = history.filter((item) => !item.abnormal).length;
  const abnormal = history.length - normal;
  const stats = [
    { label: 'Lượt phân tích', value: history.length, icon: Images },
    { label: 'Da bình thường', value: normal, icon: ShieldCheck },
    { label: 'Cần quan sát thêm', value: abnormal, icon: AlertTriangle },
    { label: 'Tỷ lệ bất thường', value: history.length ? `${Math.round((abnormal / history.length) * 100)}%` : '0%', icon: Activity },
  ];

  return (
    <div className="space-y-6 md:space-y-7">
      <section className="relative isolate min-h-[258px] overflow-hidden rounded-[18px] bg-[#203b30] text-white md:min-h-[292px]">
        <img src="/assets/pig-farm-study.webp" alt="Heo khỏe mạnh trong khu chăn nuôi sáng thoáng" className="absolute inset-0 -z-20 h-full w-full object-cover object-[center_54%]" />
        <div className="absolute inset-0 -z-10 bg-gradient-to-r from-[#172e25]/95 via-[#1d382b]/80 to-[#1d382b]/5" />
        <div className="flex min-h-[258px] max-w-[680px] flex-col items-start justify-center px-6 py-8 md:min-h-[292px] md:px-10">
          <p className="text-sm text-[#d7e3d8]">Quan sát da heo, từng ảnh một</p>
          <h2 className="display-type mt-3 max-w-[560px] text-3xl leading-[1.12] text-white md:text-[42px]">Phát hiện sớm bắt đầu từ một lần nhìn kỹ.</h2>
          <p className="mt-3 max-w-[430px] text-sm leading-relaxed text-[#e3ebe4]">Tải ảnh lên để nhận gợi ý từ mô hình và lưu lại những gì cần theo dõi.</p>
          <Link to="/analyze" className="mt-6 inline-flex items-center gap-2 rounded-lg bg-[#dce9dc] px-4 py-3 text-sm font-semibold text-[#203b30] transition-colors hover:bg-white">
            Phân tích ảnh <ArrowUpRight size={16} />
          </Link>
        </div>
      </section>

      <section className="surface overflow-hidden" aria-label="Tóm tắt hoạt động">
        <div className="grid grid-cols-2 divide-x divide-y divide-[#e5e9e3] md:grid-cols-4 md:divide-y-0">
          {stats.map(({ label, value, icon: Icon }) => (
            <div key={label} className="flex items-start gap-3 px-4 py-5 md:px-5">
              <span className="mt-0.5 text-[#63806a]"><Icon size={18} strokeWidth={1.8} /></span>
              <div><p className="text-xs text-[#808a81]">{label}</p><p className="mt-1 text-2xl font-semibold tracking-tight text-[#2e4135]">{value}</p></div>
            </div>
          ))}
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[1.35fr_.85fr]">
        <section className="surface p-5 md:p-6">
          <div className="flex flex-wrap items-end justify-between gap-2">
            <div><h3 className="section-title">Nhịp độ quan sát</h3><p className="subtle mt-1">Biểu đồ minh họa, chưa lấy dữ liệu từ lịch sử thật</p></div>
            <span className="text-xs text-[#8b958d]">7 ngày gần đây</span>
          </div>
          <div className="mt-5 h-[255px]" role="img" aria-label="Biểu đồ lượt phân tích theo ngày, dữ liệu minh họa">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trend} margin={{ top: 8, right: 6, left: -24, bottom: 0 }}>
                <defs><linearGradient id="leafFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#64816b" stopOpacity={0.22} /><stop offset="100%" stopColor="#64816b" stopOpacity={0} /></linearGradient></defs>
                <CartesianGrid stroke="#e8ece6" strokeDasharray="3 5" vertical={false} />
                <XAxis dataKey="day" tickLine={false} axisLine={false} tick={{ fill: '#879188', fontSize: 12 }} />
                <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fill: '#879188', fontSize: 11 }} />
                <Tooltip contentStyle={{ border: '1px solid #e1e6df', borderRadius: 9, boxShadow: 'none' }} />
                <Area name="Lượt phân tích" dataKey="total" type="monotone" stroke="#456a52" strokeWidth={2.5} fill="url(#leafFill)" activeDot={{ r: 4, fill: '#315b49' }} />
                <Area name="Bất thường" dataKey="abnormal" type="monotone" stroke="#bd765c" strokeWidth={2} fill="transparent" activeDot={{ r: 3, fill: '#bd765c' }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="surface p-5 md:p-6">
          <div className="flex items-center justify-between gap-3">
            <div><h3 className="section-title">Ghi nhận gần đây</h3><p className="subtle mt-1">Những ảnh được phân tích gần nhất</p></div>
            <Link to="/history" className="text-sm font-semibold text-brand-700 hover:text-brand-900">Xem lịch sử</Link>
          </div>
          <div className="mt-3">
            {history.length ? history.slice(0, 5).map((item) => (
              <div className="flex items-center justify-between gap-3 border-b border-[#edf0eb] py-3.5 last:border-0" key={item.id}>
                <div className="flex min-w-0 items-center gap-3">
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-[#eef3ee] text-[#607d67]"><ScanSearch size={17} /></span>
                  <div className="min-w-0"><div className="truncate text-sm font-semibold text-[#425047]">{item.name}</div><p className="mt-1 text-xs text-[#8a948c]">{dateTime(item.createdAt)} · {pct(item.confidence)}</p></div>
                </div>
                <Status abnormal={item.abnormal} />
              </div>
            )) : <Empty>Chưa có ảnh nào được phân tích</Empty>}
          </div>
        </section>
      </div>

      <p className="px-1 text-xs leading-relaxed text-[#818b82]">Các kết quả mô phỏng chỉ minh họa luồng giao diện, không phản ánh tình trạng trong ảnh và không dùng để chẩn đoán thú y.</p>
    </div>
  );
}
