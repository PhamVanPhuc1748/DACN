import { useState } from 'react'
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Activity, AlertOctagon, CalendarDays, ClipboardCheck, HeartPulse, PieChart as PieIcon, Siren, Warehouse } from 'lucide-react'
import { api } from '../api'
import { Card, Empty, fmtTime, useLoad } from '../ui'

const RANGES = [[7, '7 ngày'], [30, '30 ngày'], [56, '8 tuần']]

export default function Dashboard() {
  const [days, setDays] = useState(7)
  const [d] = useLoad(() => api(`/api/dashboard?days=${days}`), [days])
  const k = d?.kpi

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Dashboard dịch tễ</h1>
          <p>Tổng hợp theo nhãn hiệu lực (kết luận bác sĩ nếu đã thẩm định, nếu chưa dùng dự đoán AI).</p>
        </div>
        <div className="tabs">
          {RANGES.map(([v, l]) => <button key={v} id={`range-${v}`} className={`tab ${days === v ? 'active' : ''}`} onClick={() => setDays(v)}><CalendarDays size={14} />{l}</button>)}
        </div>
      </div>

      {d?.alerts.map((a) => (
        <div key={a.pen + a.code} className="alert-banner" role="alert">
          <div className="alert-icon"><Siren size={20} /></div>
          <div>
            <b>Cảnh báo ổ dịch: {a.count} ca {a.name} tại {a.pen}</b>
            <div className="small">Vượt ngưỡng {d.settings.outbreak_threshold} ca / {d.settings.outbreak_window_days} ngày · ca gần nhất {fmtTime(a.last_seen)} · cách ly khu chuồng và báo cơ quan thú y.</div>
          </div>
        </div>
      ))}

      <div className="grid g-4">
        {[
          [Activity, k?.today, 'Ca chẩn đoán hôm nay'],
          [ClipboardCheck, k?.period, `Ca trong ${days} ngày`],
          [HeartPulse, k && `${k.healthy_pct}%`, `Khỏe mạnh · bất thường ${k?.abnormal_pct ?? 0}%`],
          [AlertOctagon, k?.pending, `Chờ thẩm định · ${k?.low_conf ?? 0} ca tin cậy thấp`],
        ].map(([I, v, l]) => (
          <Card key={l} className="kpi">
            <div className="kpi-icon"><I size={20} /></div>
            <div className="kpi-val">{v ?? '—'}</div>
            <div className="kpi-label">{l}</div>
          </Card>
        ))}
      </div>

      <div className="grid g-2">
        <Card title="Xu hướng theo tuần (8 tuần)" icon={Activity}>
          {!d ? <div className="skeleton" style={{ height: 280 }} /> : (
            <ResponsiveContainer width="100%" height={280}>
              <AreaChart data={d.weekly}>
                <defs>
                  {[['t', '#22c3e6'], ['a', '#fbbf24'], ['x', '#fb5a76']].map(([id, c]) => (
                    <linearGradient key={id} id={`g-${id}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={c} stopOpacity={0.45} /><stop offset="1" stopColor={c} stopOpacity={0} /></linearGradient>
                  ))}
                </defs>
                <CartesianGrid stroke="rgba(148,178,220,.08)" vertical={false} />
                <XAxis dataKey="week" tick={{ fontSize: 11 }} />
                <YAxis />
                <Tooltip />
                <Legend />
                <Area dataKey="total" name="Tổng ca" stroke="#22c3e6" fill="url(#g-t)" strokeWidth={2} />
                <Area dataKey="abnormal" name="Bất thường" stroke="#fbbf24" fill="url(#g-a)" strokeWidth={2} />
                <Area dataKey="dangerous" name="Bệnh nguy hiểm" stroke="#fb5a76" fill="url(#g-x)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </Card>
        <Card title={`Cơ cấu bệnh · ${days} ngày`} icon={PieIcon}>
          {!d ? <div className="skeleton" style={{ height: 280 }} /> : !d.distribution.length ? <Empty /> : (
            <div className="row" style={{ flexWrap: 'nowrap', alignItems: 'center' }}>
              <ResponsiveContainer width="55%" height={280}>
                <PieChart>
                  <Pie data={d.distribution} dataKey="count" nameKey="name" innerRadius={65} outerRadius={110} paddingAngle={2} stroke="none">
                    {d.distribution.map((x) => <Cell key={x.code} fill={x.color} />)}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
              <div className="stack" style={{ gap: 6, flex: 1 }}>
                {d.distribution.map((x) => (
                  <div key={x.code} className="row small" style={{ flexWrap: 'nowrap' }}>
                    <span className="dot" style={{ background: x.color }} /><span>{x.name}</span><span className="spacer" /><b className="mono">{x.count}</b>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>
      </div>

      <Card title={`Theo khu chuồng · ${days} ngày`} icon={Warehouse}>
        {!d ? <div className="skeleton" style={{ height: 240 }} /> : !d.by_pen.length ? <Empty /> : (
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={d.by_pen.map((p) => ({ ...p, healthy: p.total - p.abnormal }))}>
              <CartesianGrid stroke="rgba(148,178,220,.08)" vertical={false} />
              <XAxis dataKey="pen" />
              <YAxis />
              <Tooltip cursor={{ fill: 'rgba(148,178,220,.06)' }} />
              <Legend />
              <Bar dataKey="healthy" name="Khỏe mạnh" stackId="p" fill="#34d399" />
              <Bar dataKey="abnormal" name="Bất thường" stackId="p" fill="#fb5a76" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </Card>
    </div>
  )
}
