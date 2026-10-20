import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2, ImageOff, Inbox, ShieldCheck, X } from 'lucide-react'

export const ROLES = {
  ADMIN: 'Quản trị viên',
  AI_ENGINEER: 'Kỹ sư AI',
  VET: 'Bác sĩ thú y',
  FARM_OWNER: 'Chủ trại',
}

export const Ctx = createContext(null)
export const useApp = () => useContext(Ctx)

/** Tải dữ liệu bất đồng bộ: [data, reload, loading]. */
export function useLoad(fn, deps = []) {
  const { toast } = useApp()
  const [state, setState] = useState({ data: null, loading: true })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const load = useCallback(() => {
    setState((s) => ({ ...s, loading: true }))
    return fn()
      .then((data) => setState({ data, loading: false }))
      .catch((e) => { setState((s) => ({ ...s, loading: false })); toast(e.message, true) })
  }, deps)
  useEffect(() => { load() }, [load])
  return [state.data, load, state.loading]
}

export const pct = (v, d = 1) => `${(v * 100).toFixed(d)}%`
export const fmtTime = (s) => s && new Date(s.replace(' ', 'T')).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' })

export function Card({ title, icon: Icon, actions, children, className = '', ...rest }) {
  return (
    <section className={`card ${className}`} {...rest}>
      {(title || actions) && (
        <div className="card-head">
          <h2>{Icon && <Icon size={18} />}{title}</h2>
          {actions && <div className="row">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  )
}

export function Switch({ checked, onChange, label, disabled, title }) {
  return (
    <label className={`switch ${disabled ? 'disabled' : ''}`} title={title}>
      <input type="checkbox" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      <i />
      <span>{label}</span>
    </label>
  )
}

export function StatusHero({ status, confidence, name }) {
  const ok = status === 'HEALTHY'
  return (
    <div className={`status-hero ${ok ? 'ok' : 'bad'}`}>
      <div className="ic">{ok ? <ShieldCheck size={28} /> : <AlertTriangle size={28} />}</div>
      <div>
        <b>{ok ? 'HEALTHY' : 'ABNORMAL'}</b>
        <span className="muted">{ok ? 'Heo khỏe — không phát hiện tổn thương' : `Phát hiện bất thường · nghi ${name}`}</span>
      </div>
      <div className="spacer" />
      <div style={{ textAlign: 'right' }}>
        <div className="mono" style={{ fontSize: 22, fontWeight: 700 }}>{pct(confidence)}</div>
        <small className="muted">độ tin cậy</small>
      </div>
    </div>
  )
}

export function ProbBars({ items }) {
  const { diseaseMap } = useApp()
  return (
    <div className="stack" style={{ gap: 14 }}>
      {items.map((t, i) => (
        <div className="prob" key={t.code}>
          <div className="prob-name">
            <span className="dot" style={{ background: diseaseMap[t.code]?.color }} />
            <b>{t.name}</b> <code className="faint">{t.code}</code>
          </div>
          <span className="prob-val">{pct(t.prob)}</span>
          <div className="prob-track">
            <div className="prob-fill" style={{ width: `${t.prob * 100}%`, background: diseaseMap[t.code]?.color, animationDelay: `${i * 0.08}s` }} />
          </div>
        </div>
      ))}
    </div>
  )
}

/** Ảnh + lớp phủ bounding box (YOLO) / vùng nhiệt Grad-CAM (CNN), lọc theo ngưỡng confidence. */
export function Viewer({ src, result, showBox, showHeat, threshold = 0, scanning }) {
  if (!src) return <div className="viewer"><div className="viewer-empty"><div><ImageOff size={36} /><br />Chưa có ảnh</div></div></div>
  const boxes = (result?.boxes || []).filter((b) => b.conf >= threshold)
  const heat = (result?.heatmap || []).filter((h) => h.intensity >= threshold)
  return (
    <div className="viewer">
      <div className="viewer-inner">
        <img src={src} alt="Ảnh da heo cần chẩn đoán" />
        {scanning && <div className="scan-line" />}
        {showHeat && heat.map((h, i) => (
          <div key={i} className="heat" style={{ left: `${h.cx * 100}%`, top: `${h.cy * 100}%`, width: `${h.r * 200}%`, aspectRatio: 1, opacity: 0.35 + h.intensity * 0.6 }} />
        ))}
        {showBox && boxes.map((b, i) => (
          <div key={i} className="bbox" style={{ left: `${b.x * 100}%`, top: `${b.y * 100}%`, width: `${b.w * 100}%`, height: `${b.h * 100}%`, animationDelay: `${i * 0.1}s` }}>
            <span>{b.code} {b.conf.toFixed(2)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export function Modal({ title, onClose, children, wide }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    addEventListener('keydown', onKey)
    return () => removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className={`modal ${wide ? 'wide' : ''}`} onClick={(e) => e.stopPropagation()} role="dialog" aria-label={title}>
        <div className="card-head">
          <h2>{title}</h2>
          <button className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Đóng"><X size={16} /></button>
        </div>
        {children}
      </div>
    </div>
  )
}

export function ClassPicker({ value, onChange, exclude }) {
  const { diseases } = useApp()
  return (
    <div className="class-grid">
      {diseases.filter((d) => d.code !== exclude).map((d) => (
        <button key={d.code} type="button" className={`class-opt ${value === d.code ? 'active' : ''}`} onClick={() => onChange(d.code)}>
          <span className="dot" style={{ background: d.color }} />{d.name}<code>{d.code}</code>
        </button>
      ))}
    </div>
  )
}

export function ReviewBadge({ status }) {
  if (status === 'CONFIRMED') return <span className="badge ok"><CheckCircle2 size={12} />Đã xác nhận</span>
  if (status === 'CORRECTED') return <span className="badge info"><CheckCircle2 size={12} />Đã hiệu chỉnh</span>
  return <span className="badge warn">Chờ duyệt</span>
}

export function ClassTag({ code, name }) {
  const { diseaseMap } = useApp()
  const c = diseaseMap[code]?.color
  return <span className="badge" style={{ color: c, borderColor: `${c}55`, background: `${c}14` }}><span className="dot" style={{ background: c }} />{name || diseaseMap[code]?.name}</span>
}

export function Empty({ children = 'Không có dữ liệu' }) {
  return <div className="empty"><Inbox size={32} />{children}</div>
}
