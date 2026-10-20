import { useCallback, useEffect, useMemo, useState } from 'react'
import { BookOpen, BrainCircuit, ClipboardList, Database, LayoutDashboard, LogOut, Microscope, ScanLine } from 'lucide-react'
import { api, session } from './api'
import { Ctx, ROLES } from './ui'
import Login from './pages/Login'
import Diagnose from './pages/Diagnose'
import Cases from './pages/Cases'
import Dataset from './pages/Dataset'
import Models from './pages/Models'
import Dashboard from './pages/Dashboard'
import Library from './pages/Library'

const ALL = Object.keys(ROLES)
const PAGES = [
  { id: 'diagnose', label: 'Chẩn đoán', icon: ScanLine, roles: ALL, el: Diagnose },
  { id: 'cases', label: 'Nhật ký ca bệnh', icon: ClipboardList, roles: ALL, el: Cases },
  { id: 'dashboard', label: 'Dashboard dịch tễ', icon: LayoutDashboard, roles: ['FARM_OWNER', 'VET', 'ADMIN'], el: Dashboard },
  { id: 'dataset', label: 'Dataset & gán nhãn', icon: Database, roles: ['AI_ENGINEER', 'VET', 'ADMIN'], el: Dataset },
  { id: 'models', label: 'Model & benchmark', icon: BrainCircuit, roles: ALL, el: Models },
  { id: 'library', label: 'Cẩm nang & quản trị', icon: BookOpen, roles: ALL, el: Library },
]

const useHash = () => {
  const [h, setH] = useState(location.hash.slice(1))
  useEffect(() => {
    const on = () => setH(location.hash.slice(1))
    addEventListener('hashchange', on)
    return () => removeEventListener('hashchange', on)
  }, [])
  return h
}

export default function App() {
  const [sess, setSess] = useState(session.get)
  const [toastMsg, setToastMsg] = useState(null)
  const [diseases, setDiseases] = useState([])
  const [settings, setSettings] = useState({})
  const hash = useHash()

  const toast = useCallback((msg, err = false) => {
    setToastMsg({ msg, err, k: Date.now() })
    setTimeout(() => setToastMsg((t) => (t?.msg === msg ? null : t)), 3500)
  }, [])

  const reloadSettings = useCallback(() => api('/api/settings').then(setSettings), [])

  useEffect(() => {
    if (!sess) return
    api('/api/diseases').then(setDiseases).catch((e) => toast(e.message, true))
    reloadSettings().catch(() => {})
  }, [sess, toast, reloadSettings])

  const logout = () => { session.clear(); setSess(null); location.hash = '' }
  const ctx = useMemo(() => ({
    user: sess?.user, diseases, settings, toast, reloadSettings, logout,
    diseaseMap: Object.fromEntries(diseases.map((d) => [d.code, d])),
  }), [sess, diseases, settings, toast, reloadSettings])

  const toastEl = toastMsg && <div key={toastMsg.k} className={`toast ${toastMsg.err ? 'err' : ''}`} role="status">{toastMsg.msg}</div>

  if (!sess) return <Ctx.Provider value={ctx}><Login onLogin={(s) => { session.set(s); setSess(s) }} />{toastEl}</Ctx.Provider>

  const allowed = PAGES.filter((p) => p.roles.includes(sess.user.role))
  const page = allowed.find((p) => p.id === hash) || allowed[0]
  const Page = page.el

  return (
    <Ctx.Provider value={ctx}>
      <div className="app">
        <aside className="sidebar no-print">
          <div className="logo">
            <div className="logo-mark"><Microscope size={20} /></div>
            <div><b>PigDerm AI</b><small>Chẩn đoán bệnh da heo</small></div>
          </div>
          <div className="nav-label">Chức năng</div>
          {allowed.map((p, i) => (
            <button key={p.id} id={`nav-${p.id}`} className={`nav-item ${p.id === page.id ? 'active' : ''}`} onClick={() => { location.hash = p.id }}>
              <p.icon size={18} />{p.label}<span className="num">0{i + 1}</span>
            </button>
          ))}
          <div className="sidebar-foot stack" style={{ gap: 8 }}>
            <div>
              <b>{sess.user.full_name || sess.user.username}</b>
              <div className="muted small">{ROLES[sess.user.role]}</div>
            </div>
            <button id="btn-logout" className="btn btn-sm" onClick={logout}><LogOut size={14} />Đăng xuất</button>
          </div>
        </aside>
        <main className="main">
          <Page key={page.id} />
        </main>
      </div>
      {toastEl}
    </Ctx.Provider>
  )
}
