import { useState } from 'react'
import { LogIn, Microscope, ScanLine, ShieldCheck, Activity } from 'lucide-react'
import { api } from '../api'
import { ROLES, useApp } from '../ui'

const DEMO = { admin: 'ADMIN', engineer: 'AI_ENGINEER', vet: 'VET', owner: 'FARM_OWNER' }

export default function Login({ onLogin }) {
  const { toast } = useApp()
  const [form, setForm] = useState({ username: '', password: '' })
  const [busy, setBusy] = useState(false)

  const submit = async (creds = form) => {
    setBusy(true)
    try { onLogin(await api('/api/auth/login', { method: 'POST', body: creds })) }
    catch (e) { toast(e.message, true) }
    finally { setBusy(false) }
  }

  return (
    <div className="login">
      <section className="login-hero">
        <div className="orb" style={{ width: 380, height: 380, background: '#2ee6a6', top: -80, left: -60 }} />
        <div className="orb" style={{ width: 300, height: 300, background: '#22c3e6', bottom: -60, right: 40, animationDelay: '-5s' }} />
        <div className="logo" style={{ position: 'relative' }}>
          <div className="logo-mark"><Microscope size={20} /></div>
          <div><b>PigDerm AI</b><small>Đồ án chuyên ngành</small></div>
        </div>
        <h1 style={{ position: 'relative' }}>Chẩn đoán bệnh da heo<br /><span className="grad-text">bằng Deep Learning</span></h1>
        <p className="muted" style={{ maxWidth: 480, position: 'relative' }}>
          Sàng lọc nhanh 10 nhóm bệnh da từ ảnh chụp, khoanh vùng tổn thương, chuyển bác sĩ thú y thẩm định
          và cảnh báo sớm ổ dịch theo khu chuồng.
        </p>
        <div className="stack" style={{ position: 'relative', gap: 10 }}>
          {[[ScanLine, 'YOLO / CNN + Grad-CAM khoanh vùng tổn thương'], [ShieldCheck, 'Human-in-the-loop: bác sĩ xác nhận / hiệu chỉnh'],
            [Activity, 'Dashboard dịch tễ & cảnh báo ổ dịch nguy hiểm']].map(([I, t]) => (
            <div key={t} className="row"><I size={18} color="var(--brand)" /><span>{t}</span></div>
          ))}
        </div>
      </section>
      <section className="login-form">
        <form className="card login-card stack" style={{ gap: 16 }} onSubmit={(e) => { e.preventDefault(); submit() }}>
          <div>
            <h2 style={{ fontSize: 22 }}>Đăng nhập</h2>
            <p className="muted">Truy cập theo vai trò được cấp</p>
          </div>
          <label className="field"><span>Tên đăng nhập</span>
            <input id="login-username" className="input" autoComplete="username" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required />
          </label>
          <label className="field"><span>Mật khẩu</span>
            <input id="login-password" className="input" type="password" autoComplete="current-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
          </label>
          <button id="login-submit" className="btn btn-primary" disabled={busy}><LogIn size={16} />{busy ? 'Đang đăng nhập…' : 'Đăng nhập'}</button>
          <div className="divider" />
          <span className="muted small">Tài khoản demo (mật khẩu <code>demo123</code>)</span>
          <div className="role-pick">
            {Object.entries(DEMO).map(([u, r]) => (
              <button key={u} id={`demo-${u}`} type="button" disabled={busy} onClick={() => submit({ username: u, password: 'demo123' })}>
                <b>{ROLES[r]}</b><small>{u}</small>
              </button>
            ))}
          </div>
        </form>
      </section>
    </div>
  )
}
