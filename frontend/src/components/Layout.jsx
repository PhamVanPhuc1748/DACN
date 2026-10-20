import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { Activity, LayoutDashboard, ScanSearch, History, BrainCircuit, ShieldCheck, Menu, X, Wifi, WifiOff } from 'lucide-react';
import { useState } from 'react';
import { USE_MOCK } from '../services/api';

const navigation = [
  { to: '/', label: 'Tổng quan', icon: LayoutDashboard },
  { to: '/analyze', label: 'Phân tích ảnh', icon: ScanSearch },
  { to: '/history', label: 'Lịch sử phân tích', icon: History },
  { to: '/model', label: 'Thông tin mô hình', icon: BrainCircuit },
];
const descriptions = {
  '/': 'Theo dõi các lượt quan sát và kết quả gần đây',
  '/analyze': 'Tải ảnh lên để xem kết quả phân tích',
  '/history': 'Tra cứu những ảnh đã phân tích trên thiết bị này',
  '/model': 'Cấu hình và trạng thái tích hợp mô hình',
};

export default function Layout() {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const current = navigation.find((item) => item.to === location.pathname);
  const closeMenu = () => setOpen(false);

  return (
    <div className="min-h-screen lg:flex">
      <div className="sticky top-0 z-20 flex items-center justify-between border-b border-[#dfe5dd] bg-[#f8f9f6] px-4 py-3 lg:hidden">
        <div className="flex items-center gap-2.5 text-brand-900">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-brand-700 text-white"><Activity size={19} /></span>
          <span className="font-bold tracking-tight">PigSkin <span className="font-normal text-[#88938a]">/ field notes</span></span>
        </div>
        <button type="button" className="rounded-lg p-2 text-[#405347]" aria-label={open ? 'Đóng menu' : 'Mở menu'} aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? <X size={21} /> : <Menu size={21} />}
        </button>
      </div>

      {open && <button type="button" aria-label="Đóng menu" className="fixed inset-0 z-30 bg-[#1e3028]/30 lg:hidden" onClick={closeMenu} />}
      <aside className={`${open ? 'translate-x-0' : '-translate-x-full'} fixed inset-y-0 left-0 z-40 flex h-screen w-[268px] shrink-0 flex-col border-r border-[#263f34] bg-[#203b30] text-white transition-transform duration-200 lg:sticky lg:top-0 lg:z-10 lg:translate-x-0`}>
        <div className="px-6 pb-8 pt-7">
          <div className="flex items-center gap-3">
            <span className="grid h-11 w-11 place-items-center rounded-xl bg-[#c4d7c6] text-brand-900"><Activity size={23} /></span>
            <div>
              <div className="text-lg font-bold tracking-tight">PigSkin</div>
              <div className="mt-0.5 text-[11px] text-[#aabbb0]">SỔ THEO DÕI SỨC KHỎE DA</div>
            </div>
          </div>
        </div>

        <div className="px-4">
          <p className="mb-3 px-3 text-[11px] font-semibold text-[#9aad9f]">Không gian làm việc</p>
          <nav aria-label="Điều hướng chính" className="space-y-1">
            {navigation.map(({ to, label, icon: Icon }) => (
              <NavLink key={to} to={to} end={to === '/'} onClick={closeMenu} className={({ isActive }) => `group flex items-center gap-3 rounded-lg px-3 py-3 text-sm transition-colors ${isActive ? 'bg-[#dce9dc] font-semibold text-brand-900' : 'text-[#d0dbd3] hover:bg-white/10 hover:text-white'}`}>
                <Icon size={18} strokeWidth={1.8} />{label}
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="mt-auto px-5 pb-6">
          <div className="rounded-xl border border-white/10 bg-white/[.06] p-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-[#e1ebe3]"><ShieldCheck size={16} /> Công cụ nghiên cứu</div>
            <p className="mt-2 text-xs leading-relaxed text-[#b8c8bd]">Kết quả hỗ trợ quan sát, không thay thế đánh giá của bác sĩ thú y.</p>
          </div>
          <p className="mt-5 px-1 text-[11px] text-[#8ea396]">© 2026 PigSkin · Bản nghiên cứu</p>
        </div>
      </aside>

      <div className="min-w-0 flex-1">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[#e0e5df] bg-[#f8f9f6] px-5 py-4 md:px-9">
          <div>
            <h1 className="text-lg font-semibold tracking-tight text-[#34443a]">{current?.label || 'PigSkin'}</h1>
            <p className="mt-0.5 text-xs text-[#808c83]">{descriptions[location.pathname]}</p>
          </div>
          <span className={`pill ${USE_MOCK ? 'pill-warn' : 'pill-ok'}`}>
            {USE_MOCK ? <WifiOff size={13} /> : <Wifi size={13} />}
            {USE_MOCK ? 'Đang dùng dữ liệu mô phỏng' : 'Đã kết nối FastAPI'}
          </span>
        </header>
        <main className="mx-auto max-w-[1440px] p-4 md:p-8 lg:px-10 lg:py-9"><Outlet /></main>
      </div>
    </div>
  );
}
