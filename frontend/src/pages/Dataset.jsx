import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Check, Database, FileUp, GitBranch, ShieldCheck, ShieldAlert, Tags, Wand2, X } from 'lucide-react'
import { api } from '../api'
import { Card, ClassTag, Empty, fmtTime, pct, useApp, useLoad } from '../ui'

const SPLIT_COLORS = { train: '#2ee6a6', val: '#22c3e6', test: '#a78bfa' }

export default function Dataset() {
  const { user, diseases, toast } = useApp()
  const isEng = ['AI_ENGINEER', 'ADMIN'].includes(user.role)
  const [versions, reloadVersions] = useLoad(() => api('/api/datasets'))
  const [queue, reloadQueue, qLoading] = useLoad(() => api('/api/datasets/unlabeled'))
  const [vid, setVid] = useState(null)
  const [busy, setBusy] = useState(false)
  const [picks, setPicks] = useState({})
  const [newVer, setNewVer] = useState('')

  const v = versions?.find((x) => x.id === vid) || versions?.at(-1)
  const chart = v && Object.values(v.distribution.reduce((acc, r) => {
    acc[r.code] ??= { code: r.code, train: 0, val: 0, test: 0 }
    acc[r.code][r.split] = r.n
    return acc
  }, {}))

  const act = async (fn, msg) => {
    setBusy(true)
    try { const r = await fn(); toast(msg(r)); reloadQueue(); reloadVersions() }
    catch (e) { toast(e.message, true) } finally { setBusy(false) }
  }
  const review = (it, action) => act(
    () => api(`/api/datasets/labels/${it.label_id}/review`, { method: 'POST', body: { action, class_code: picks[it.id] || null } }),
    () => (action === 'approve' ? `Đã duyệt ${it.stem_id}` : `Đã loại ${it.stem_id}`))

  const labeled = queue?.items.filter((i) => i.label_id) ?? []
  const unlabeled = (queue?.items.length ?? 0) - labeled.length

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Dataset & gán nhãn bán giám sát</h1>
          <p>Phiên bản dữ liệu chia theo <code>stem_id</code> (chống rò rỉ), hàng đợi pseudo-label chờ chuyên gia duyệt.</p>
        </div>
        {versions && (
          <select id="sel-version" className="select" style={{ width: 200 }} value={v?.id} onChange={(e) => setVid(Number(e.target.value))}>
            {versions.map((x) => <option key={x.id} value={x.id}>{x.name} ({x.version})</option>)}
          </select>
        )}
      </div>

      {!v ? <div className="skeleton" style={{ height: 120 }} /> : (
        <div className="grid g-4">
          {['train', 'val', 'test'].map((s) => (
            <Card key={s} className="kpi">
              <div className="kpi-icon" style={{ color: SPLIT_COLORS[s], background: `${SPLIT_COLORS[s]}1f` }}><Database size={20} /></div>
              <div className="kpi-val">{v.splits[s] ?? 0}</div>
              <div className="kpi-label">{s.toUpperCase()} · {pct((v.splits[s] ?? 0) / (v.total_stems || 1), 0)} stem</div>
            </Card>
          ))}
          <Card className="kpi">
            <div className="kpi-icon" style={v.leaked_stems ? { color: 'var(--bad)', background: 'rgba(251,90,118,.12)' } : undefined}>
              {v.leaked_stems ? <ShieldAlert size={20} /> : <ShieldCheck size={20} />}
            </div>
            <div className="kpi-val">{v.leaked_stems}</div>
            <div className="kpi-label">stem rò rỉ giữa các split {v.leaked_stems ? '⚠' : '· sạch'}</div>
          </Card>
        </div>
      )}

      <div className="grid g-side">
        <Card title="Phiên bản" icon={GitBranch}>
          <div className="stack">
            {versions?.map((x) => (
              <button key={x.id} className={`class-opt ${x.id === v?.id ? 'active' : ''}`} onClick={() => setVid(x.id)} style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 2 }}>
                <span className="row" style={{ width: '100%' }}><b>{x.version}</b><span className="spacer" /><span className="faint small">{fmtTime(x.created_at)}</span></span>
                <span className="muted small">{x.total_stems} stem · seed {x.seed}</span>
                {x.notes && <span className="faint small">{x.notes}</span>}
              </button>
            ))}
            {isEng && (
              <>
                <div className="divider" />
                <span className="muted small">Tạo phiên bản mới = bản gần nhất + {queue?.approved_pending_release ?? 0} ảnh đã duyệt (chỉ thêm vào train, test đóng băng).</span>
                <div className="row">
                  <input id="in-version" className="input" style={{ flex: 1, width: 'auto' }} placeholder="VD: v2" value={newVer} onChange={(e) => setNewVer(e.target.value)} />
                  <button id="btn-new-version" className="btn btn-primary" disabled={busy || !newVer.trim()}
                    onClick={() => act(() => api('/api/datasets/versions', { method: 'POST', body: { version: newVer.trim() } }),
                      (r) => { setNewVer(''); setVid(r.id); return `Đã tạo phiên bản (+${r.added} ảnh train)` })}>Tạo</button>
                </div>
              </>
            )}
          </div>
        </Card>

        <Card title="Phân bố nhãn theo split (số stem)" icon={Tags}>
          {!chart ? <div className="skeleton" style={{ height: 300 }} /> : (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={chart}>
                <CartesianGrid stroke="rgba(148,178,220,.08)" vertical={false} />
                <XAxis dataKey="code" tick={{ fontSize: 11 }} interval={0} angle={-25} textAnchor="end" height={60} />
                <YAxis />
                <Tooltip cursor={{ fill: 'rgba(148,178,220,.06)' }} />
                <Legend />
                {Object.entries(SPLIT_COLORS).map(([k, c]) => <Bar key={k} dataKey={k} stackId="s" fill={c} radius={k === 'test' ? [6, 6, 0, 0] : 0} />)}
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>

      <Card title={`Hàng đợi ảnh chưa gán nhãn${queue ? ` · ${labeled.length} pseudo-label chờ duyệt, ${unlabeled} chưa gán` : ''}`} icon={Wand2}
        actions={isEng && (
          <>
            <button id="btn-import-csv" className="btn btn-sm" disabled={busy} title={queue?.csv_path}
              onClick={() => act(() => api('/api/datasets/unlabeled/import-csv', { method: 'POST' }), (r) => `Đã nhập ${r.imported} ảnh`)}><FileUp size={14} />Nhập {queue?.csv_found ? 'unlabeled.csv' : '(chưa có CSV)'}</button>
            <button id="btn-pseudo" className="btn btn-sm btn-primary" disabled={busy || !unlabeled}
              onClick={() => act(() => api('/api/datasets/unlabeled/pseudo-label', { method: 'POST', body: {} }), (r) => `${r.model} đã gán ${r.labeled} nhãn giả`)}><Wand2 size={14} />Chạy pseudo-label</button>
          </>
        )}>
        {qLoading && !queue ? <div className="skeleton" style={{ height: 200 }} /> : !labeled.length ? (
          <Empty>{unlabeled ? `${unlabeled} ảnh chưa có nhãn giả — ${isEng ? 'bấm “Chạy pseudo-label”' : 'chờ kỹ sư AI chạy pseudo-label'}` : 'Không còn ảnh nào chờ duyệt'}</Empty>
        ) : (
          <div className="table-wrap" style={{ maxHeight: 480 }}>
            <table className="table">
              <thead><tr><th>Stem</th><th>Nhãn giả (AI)</th><th>Tin cậy</th><th>Sửa nhãn trước khi duyệt</th><th /></tr></thead>
              <tbody>
                {labeled.map((it) => (
                  <tr key={it.id}>
                    <td className="mono">{it.stem_id}</td>
                    <td><ClassTag code={it.pseudo_code} name={it.pseudo_name} /></td>
                    <td className="mono">{pct(it.pseudo_conf)}</td>
                    <td>
                      <select className="select" style={{ maxWidth: 220 }} value={picks[it.id] || ''} onChange={(e) => setPicks({ ...picks, [it.id]: e.target.value })}>
                        <option value="">Giữ nhãn AI</option>
                        {diseases.map((d) => <option key={d.code} value={d.code}>{d.name}</option>)}
                      </select>
                    </td>
                    <td>
                      <div className="row" style={{ flexWrap: 'nowrap' }}>
                        <button className="btn btn-sm btn-ok" disabled={busy} onClick={() => review(it, 'approve')}><Check size={14} />Duyệt</button>
                        <button className="btn btn-sm btn-danger" disabled={busy} onClick={() => review(it, 'reject')}><X size={14} />Loại</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
