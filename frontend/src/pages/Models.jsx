import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis, LabelList } from 'recharts'
import { BrainCircuit, FileText, FlaskConical, FolderSearch, Gauge, Star } from 'lucide-react'
import { api } from '../api'
import { Card, Empty, pct, useApp, useLoad } from '../ui'

export default function Models() {
  const { user, toast } = useApp()
  const isEng = ['AI_ENGINEER', 'ADMIN'].includes(user.role)
  const [models, reload] = useLoad(() => api('/api/models'))
  const [exp] = useLoad(() => (isEng ? api('/api/experiments') : Promise.resolve(null)))
  const [busy, setBusy] = useState(false)

  const act = async (fn, msg) => {
    setBusy(true)
    try { toast(msg(await fn())); reload() } catch (e) { toast(e.message, true) } finally { setBusy(false) }
  }

  const chart = models?.filter((m) => m.metrics.accuracy).map((m) => ({
    name: m.name, accuracy: +(m.metrics.accuracy * 100).toFixed(1), macro_f1: +(m.metrics.macro_f1 * 100).toFixed(1),
    latency: m.latency_ms, params: m.metrics.params_m,
  }))
  const best = models?.reduce((a, m) => ((m.metrics.macro_f1 ?? 0) > (a?.metrics.macro_f1 ?? 0) ? m : a), null)
  const def = models?.find((m) => m.is_default)

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Model registry & benchmark</h1>
          <p>So sánh CNN (phân loại + Grad-CAM) và YOLO (phát hiện) trên cùng tập test đóng băng.</p>
        </div>
        {isEng && <button id="btn-scan" className="btn" disabled={busy} onClick={() => act(() => api('/api/models/scan', { method: 'POST' }), (r) => (r.added.length ? `Đã đăng ký ${r.added.length} model mới` : 'Không có file trọng số mới trong ml_workspace/models'))}><FolderSearch size={16} />Quét ml_workspace/models</button>}
      </div>

      <div className="grid g-3">
        <Card className="kpi"><div className="kpi-icon"><Star size={20} /></div><div className="kpi-val" style={{ fontSize: 22 }}>{def?.name ?? '—'}</div><div className="kpi-label">Model mặc định đang phục vụ</div></Card>
        <Card className="kpi"><div className="kpi-icon"><Gauge size={20} /></div><div className="kpi-val" style={{ fontSize: 22 }}>{best ? `${best.name} · ${pct(best.metrics.macro_f1)}` : '—'}</div><div className="kpi-label">Macro-F1 cao nhất</div></Card>
        <Card className="kpi"><div className="kpi-icon"><BrainCircuit size={20} /></div><div className="kpi-val">{models?.length ?? '—'}</div><div className="kpi-label">Phiên bản model đã đăng ký</div></Card>
      </div>

      <Card title="Danh sách model" icon={BrainCircuit}>
        {!models ? <div className="skeleton" style={{ height: 220 }} /> : (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Model</th><th>Nhiệm vụ</th><th>Dataset</th><th>Accuracy</th><th>Macro-F1</th><th>mAP50</th><th>Params</th><th>Latency</th><th>Trọng số</th><th /></tr></thead>
              <tbody>
                {models.map((m) => (
                  <tr key={m.id}>
                    <td><b>{m.name}</b>{!!m.is_default && <span className="badge ok" style={{ marginLeft: 8 }}><Star size={11} />Mặc định</span>}<div className="faint small mono">{m.architecture}</div></td>
                    <td><span className={`badge ${m.task === 'detection' ? 'info' : ''}`}>{m.task === 'detection' ? 'Phát hiện' : 'Phân loại'}</span></td>
                    <td className="mono">{m.dataset_version ?? '—'}</td>
                    <td className="mono">{m.metrics.accuracy ? pct(m.metrics.accuracy) : '—'}</td>
                    <td className="mono" style={{ color: m.id === best?.id ? 'var(--brand)' : undefined }}>{m.metrics.macro_f1 ? pct(m.metrics.macro_f1) : '—'}</td>
                    <td className="mono">{m.metrics.map50 ? pct(m.metrics.map50) : '—'}</td>
                    <td className="mono">{m.metrics.params_m ? `${m.metrics.params_m}M` : '—'}</td>
                    <td className="mono">{m.latency_ms}ms</td>
                    <td>{m.artifact_exists ? <span className="badge ok">Có file</span> : <span className="badge warn" title={m.artifact_uri}>Chưa có · mock</span>}</td>
                    <td>{isEng && !m.is_default && <button className="btn btn-sm" disabled={busy} onClick={() => act(() => api(`/api/models/${m.id}/default`, { method: 'POST' }), () => `${m.name} là model mặc định`)}>Đặt mặc định</button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {chart?.length > 0 && (
        <div className="grid g-2">
          <Card title="Accuracy & Macro-F1 (%)" icon={Gauge}>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={chart}>
                <CartesianGrid stroke="rgba(148,178,220,.08)" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis domain={[70, 100]} />
                <Tooltip cursor={{ fill: 'rgba(148,178,220,.06)' }} />
                <Legend />
                <Bar dataKey="accuracy" name="Accuracy" fill="#22c3e6" radius={[6, 6, 0, 0]} />
                <Bar dataKey="macro_f1" name="Macro-F1" fill="#2ee6a6" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
          <Card title="Đánh đổi tốc độ ↔ chất lượng" icon={FlaskConical}>
            <ResponsiveContainer width="100%" height={280}>
              <ScatterChart margin={{ top: 20, right: 30 }}>
                <CartesianGrid stroke="rgba(148,178,220,.08)" />
                <XAxis type="number" dataKey="latency" name="Latency" unit="ms" />
                <YAxis type="number" dataKey="macro_f1" name="Macro-F1" unit="%" domain={[80, 95]} />
                <ZAxis type="number" dataKey="params" range={[80, 600]} name="Params (M)" />
                <Tooltip cursor={{ strokeDasharray: '3 3' }} />
                <Scatter data={chart} fill="#a78bfa">
                  <LabelList dataKey="name" position="top" style={{ fill: 'var(--muted)', fontSize: 11 }} />
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          </Card>
        </div>
      )}

      {isEng && (
        <Card title={`Kết quả thực nghiệm · ${exp?.dir ?? ''}`} icon={FileText}>
          {!exp?.files.length ? <Empty>Chưa có file trong ml_workspace/experiments (confusion matrix, learning curve…)</Empty> : (
            <div className="grid g-3">
              {exp.files.map((f) => (
                <a key={f.name} href={f.url} target="_blank" rel="noreferrer" className="card" style={{ padding: 10, textDecoration: 'none' }}>
                  {f.kind === 'image' ? <img src={f.url} alt={f.name} style={{ width: '100%', borderRadius: 8, background: '#fff' }} /> : <div className="empty"><FileText size={28} /></div>}
                  <div className="small mono muted" style={{ marginTop: 6 }}>{f.name}</div>
                </a>
              ))}
            </div>
          )}
        </Card>
      )}
    </div>
  )
}
