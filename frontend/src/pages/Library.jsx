import { useState } from 'react'
import { BookOpen, History, Save, Search, Settings2, ShieldAlert, UserPlus, Users } from 'lucide-react'
import { api } from '../api'
import { Card, Empty, Modal, ROLES, fmtTime, useApp, useLoad } from '../ui'

export default function Library() {
  const { user } = useApp()
  const [tab, setTab] = useState('library')
  const isAdmin = user.role === 'ADMIN'
  const TABS = [['library', 'Cẩm nang bệnh', BookOpen], ...(isAdmin ? [['settings', 'Cấu hình', Settings2], ['users', 'Người dùng', Users], ['audit', 'Nhật ký hệ thống', History]] : [])]

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>{isAdmin ? 'Cẩm nang & quản trị' : 'Cẩm nang thú y'}</h1>
          <p>Tra cứu 10 nhóm bệnh da heo: nguyên nhân, dấu hiệu, xử lý, phòng ngừa.</p>
        </div>
        {TABS.length > 1 && (
          <div className="tabs">
            {TABS.map(([id, l, I]) => <button key={id} id={`tab-${id}`} className={`tab ${tab === id ? 'active' : ''}`} onClick={() => setTab(id)}><I size={14} />{l}</button>)}
          </div>
        )}
      </div>
      {tab === 'library' && <Diseases />}
      {tab === 'settings' && <SettingsForm />}
      {tab === 'users' && <UsersAdmin />}
      {tab === 'audit' && <Audit />}
    </div>
  )
}

function Diseases() {
  const { diseases } = useApp()
  const [q, setQ] = useState('')
  const [sel, setSel] = useState(null)
  const list = diseases.filter((d) => `${d.name} ${d.name_en} ${d.code} ${d.group_name}`.toLowerCase().includes(q.toLowerCase()))
  return (
    <>
      <div className="row">
        <div style={{ position: 'relative', width: 320 }}>
          <Search size={16} style={{ position: 'absolute', left: 12, top: 11, color: 'var(--faint)' }} />
          <input id="in-search" className="input" style={{ paddingLeft: 36 }} placeholder="Tìm bệnh…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>
      {!list.length ? <Empty /> : (
        <div className="grid g-4">
          {list.map((d) => (
            <Card key={d.code} className="disease-card" onClick={() => setSel(d)}>
              <div className="disease-cover" style={{ background: `radial-gradient(circle at 30% 30%, ${d.color}aa, ${d.color}22 70%)` }}>
                <BookOpen size={34} color="#fff" style={{ opacity: 0.85 }} />
                <span className="code">{d.code}</span>
                {!!d.is_dangerous && <span className="badge bad" style={{ position: 'absolute', top: 8, right: 8 }}><ShieldAlert size={12} />Nguy hiểm</span>}
              </div>
              <div><h3>{d.name}</h3><span className="muted small">{d.name_en} · {d.group_name}</span></div>
              <p className="muted small" style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{d.description}</p>
            </Card>
          ))}
        </div>
      )}
      {sel && (
        <Modal title={sel.name} onClose={() => setSel(null)}>
          <div className="stack">
            <div className="row"><span className="badge" style={{ color: sel.color, borderColor: `${sel.color}55` }}><span className="dot" style={{ background: sel.color }} />{sel.code}</span><span className="muted">{sel.name_en} · {sel.group_name}</span></div>
            {!!sel.is_dangerous && <div className="note bad"><ShieldAlert size={16} /><span>Bệnh nguy hiểm — theo dõi ổ dịch trên dashboard.</span></div>}
            {[['Nguyên nhân', sel.cause], ['Dấu hiệu nhận biết', sel.description], ['Xử lý', sel.treatment], ['Phòng ngừa', sel.prevention]].map(([t, v]) => (
              <div key={t}><h3>{t}</h3><p className="muted">{v}</p></div>
            ))}
          </div>
        </Modal>
      )}
    </>
  )
}

const FIELDS = [
  ['default_conf_threshold', 'Ngưỡng hiển thị bbox / Grad-CAM', 0, 1, 0.01],
  ['review_threshold', 'Độ tin cậy dưới ngưỡng → cần bác sĩ khám lại', 0, 1, 0.01],
  ['outbreak_threshold', 'Số ca bệnh nguy hiểm / khu chuồng để cảnh báo', 1, 50, 1],
  ['outbreak_window_days', 'Cửa sổ thời gian cảnh báo (ngày)', 1, 90, 1],
]

function SettingsForm() {
  const { settings, reloadSettings, toast } = useApp()
  const [v, setV] = useState(null)
  const val = v ?? settings
  const save = async () => {
    try {
      await api('/api/settings', { method: 'PUT', body: Object.fromEntries(FIELDS.map(([k]) => [k, Number(val[k])])) })
      await reloadSettings(); setV(null); toast('Đã lưu cấu hình')
    } catch (e) { toast(e.message, true) }
  }
  return (
    <Card title="Cấu hình hệ thống" icon={Settings2} style={{ maxWidth: 720 }}>
      <div className="stack" style={{ gap: 18 }}>
        {FIELDS.map(([k, label, lo, hi, step]) => (
          <label key={k} className="field">
            <span className="row">{label}<span className="spacer" /><b className="mono">{val[k]}</b></span>
            <input id={`set-${k}`} type="range" min={lo} max={hi} step={step} value={val[k] ?? lo} onChange={(e) => setV({ ...val, [k]: e.target.value })} />
          </label>
        ))}
        <div className="row"><span className="spacer" /><button id="btn-save-settings" className="btn btn-primary" disabled={!v} onClick={save}><Save size={16} />Lưu</button></div>
      </div>
    </Card>
  )
}

function UsersAdmin() {
  const { user: me, toast } = useApp()
  const [users, reload] = useLoad(() => api('/api/admin/users'))
  const [form, setForm] = useState(null)
  const patch = async (u, body) => {
    try { await api(`/api/admin/users/${u.id}`, { method: 'PATCH', body }); toast(`Đã cập nhật ${u.username}`); reload() }
    catch (e) { toast(e.message, true) }
  }
  const create = async (e) => {
    e.preventDefault()
    try { await api('/api/admin/users', { method: 'POST', body: form }); toast('Đã tạo tài khoản'); setForm(null); reload() }
    catch (err) { toast(err.message, true) }
  }
  return (
    <Card title="Người dùng" icon={Users} actions={<button id="btn-new-user" className="btn btn-sm btn-primary" onClick={() => setForm({ username: '', full_name: '', password: '', role: 'FARM_OWNER' })}><UserPlus size={14} />Thêm</button>}>
      {!users ? <div className="skeleton" style={{ height: 200 }} /> : (
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th>Tài khoản</th><th>Họ tên</th><th>Vai trò</th><th>Tạo lúc</th><th>Trạng thái</th><th /></tr></thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td className="mono">{u.username}</td>
                  <td>{u.full_name}</td>
                  <td>
                    <select className="select" style={{ width: 170 }} value={u.role} disabled={u.id === me.id} onChange={(e) => patch(u, { role: e.target.value })}>
                      {Object.entries(ROLES).map(([r, l]) => <option key={r} value={r}>{l}</option>)}
                    </select>
                  </td>
                  <td className="muted">{fmtTime(u.created_at)}</td>
                  <td>{u.is_active ? <span className="badge ok">Hoạt động</span> : <span className="badge bad">Đã khóa</span>}</td>
                  <td>{u.id !== me.id && <button className="btn btn-sm" onClick={() => patch(u, { is_active: !u.is_active })}>{u.is_active ? 'Khóa' : 'Mở khóa'}</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {form && (
        <Modal title="Thêm người dùng" onClose={() => setForm(null)}>
          <form className="stack" onSubmit={create}>
            {[['username', 'Tên đăng nhập (≥ 3 ký tự)'], ['full_name', 'Họ tên'], ['password', 'Mật khẩu (≥ 6 ký tự)']].map(([k, l]) => (
              <label key={k} className="field"><span>{l}</span>
                <input id={`new-${k}`} className="input" type={k === 'password' ? 'password' : 'text'} required={k !== 'full_name'} minLength={k === 'password' ? 6 : k === 'username' ? 3 : undefined} value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
              </label>
            ))}
            <label className="field"><span>Vai trò</span>
              <select className="select" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                {Object.entries(ROLES).map(([r, l]) => <option key={r} value={r}>{l}</option>)}
              </select>
            </label>
            <button id="btn-create-user" className="btn btn-primary">Tạo tài khoản</button>
          </form>
        </Modal>
      )}
    </Card>
  )
}

function Audit() {
  const [logs] = useLoad(() => api('/api/admin/audit'))
  return (
    <Card title="Nhật ký hệ thống (300 gần nhất)" icon={History}>
      {!logs ? <div className="skeleton" style={{ height: 300 }} /> : !logs.length ? <Empty /> : (
        <div className="table-wrap" style={{ maxHeight: 600 }}>
          <table className="table">
            <thead><tr><th>Thời gian</th><th>Người dùng</th><th>Hành động</th><th>Chi tiết</th></tr></thead>
            <tbody>
              {logs.map((l) => (
                <tr key={l.id}>
                  <td className="muted">{fmtTime(l.created_at)}</td>
                  <td className="mono">{l.username ?? '—'}</td>
                  <td><span className="badge">{l.action}</span></td>
                  <td className="muted">{l.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}
