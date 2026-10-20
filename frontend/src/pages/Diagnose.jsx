import { useRef, useState } from 'react'
import { AlertTriangle, Cpu, FileDown, GitCompare, ImagePlus, Info, Pill, ScanLine, ShieldPlus, Sparkles, X } from 'lucide-react'
import { api } from '../api'
import { Card, Empty, ProbBars, StatusHero, Switch, Viewer, pct, useApp, useLoad } from '../ui'

export default function Diagnose() {
  const { user, settings, toast } = useApp()
  const [models] = useLoad(() => api('/api/models'))
  const [files, setFiles] = useState([])          // [{ file, url, result }]
  const [active, setActive] = useState(0)
  const [meta, setMeta] = useState({ pen: '', herd_code: '', notes: '' })
  const [modelId, setModelId] = useState('')
  const [busy, setBusy] = useState(false)
  const [drag, setDrag] = useState(false)
  const [view, setView] = useState({ box: true, heat: true, th: null })
  const [tab, setTab] = useState('single')
  const [cmpIds, setCmpIds] = useState([])
  const [cmp, setCmp] = useState(null)
  const input = useRef()

  const canCompare = ['AI_ENGINEER', 'ADMIN'].includes(user.role)
  const th = view.th ?? Number(settings.default_conf_threshold ?? 0.35)
  const reviewTh = Number(settings.review_threshold ?? 0.7)
  const cur = files[active]
  const r = cur?.result

  const add = (list) => {
    const imgs = [...list].filter((f) => f.type.startsWith('image/')).slice(0, 20 - files.length)
    if (!imgs.length) return toast('Chỉ nhận file ảnh (JPG/PNG)', true)
    setFiles((fs) => [...fs, ...imgs.map((file) => ({ file, url: URL.createObjectURL(file) }))])
    setCmp(null)
  }
  const remove = (i) => {
    URL.revokeObjectURL(files[i].url)
    setFiles((fs) => fs.filter((_, j) => j !== i))
    setActive((a) => Math.max(0, a >= i ? a - 1 : a))
  }

  const run = async () => {
    const todo = files.map((f, i) => [f, i]).filter(([f]) => !f.result)
    if (!todo.length) return
    const form = new FormData()
    todo.forEach(([f]) => form.append('files', f.file))
    Object.entries(meta).forEach(([k, v]) => form.append(k, v))
    if (modelId) form.append('model_id', modelId)
    setBusy(true)
    try {
      const out = await api('/api/predict', { method: 'POST', form })
      setFiles((fs) => fs.map((f, i) => {
        const k = todo.findIndex(([, j]) => j === i)
        return k >= 0 ? { ...f, result: out[k] } : f
      }))
      setActive(todo[0][1])
      toast(`Đã chẩn đoán ${out.length} ảnh · lưu vào nhật ký ca bệnh`)
    } catch (e) { toast(e.message, true) } finally { setBusy(false) }
  }

  const compare = async () => {
    const form = new FormData()
    form.append('file', cur.file)
    form.append('model_ids', cmpIds.join(','))
    setBusy(true)
    try { setCmp(await api('/api/predict/compare', { method: 'POST', form })) }
    catch (e) { toast(e.message, true) } finally { setBusy(false) }
  }

  const pending = files.filter((f) => !f.result).length

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Trung tâm chẩn đoán</h1>
          <p>Tải ảnh da heo → AI phân loại 10 nhóm bệnh, khoanh vùng tổn thương và gợi ý xử lý.</p>
        </div>
        {canCompare && (
          <div className="tabs no-print">
            <button id="tab-single" className={`tab ${tab === 'single' ? 'active' : ''}`} onClick={() => setTab('single')}><ScanLine size={15} />Chẩn đoán</button>
            <button id="tab-compare" className={`tab ${tab === 'compare' ? 'active' : ''}`} onClick={() => setTab('compare')}><GitCompare size={15} />So sánh model</button>
          </div>
        )}
      </div>

      <div className="grid g-side">
        {/* ===== Cột trái: upload + thông tin ca ===== */}
        <div className="stack no-print" style={{ gap: 18 }}>
          <Card title="Ảnh đầu vào" icon={ImagePlus}>
            <div className="stack">
              <div id="dropzone" className={`dropzone ${drag ? 'drag' : ''}`} onClick={() => input.current.click()}
                onDragOver={(e) => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)}
                onDrop={(e) => { e.preventDefault(); setDrag(false); add(e.dataTransfer.files) }}>
                <div className="dz-icon"><ImagePlus size={24} /></div>
                <b>Kéo thả hoặc bấm để chọn ảnh</b>
                <span className="muted small">JPG / PNG ≤ 10MB · tối đa 20 ảnh / lượt</span>
                <input ref={input} type="file" accept="image/*" multiple hidden onChange={(e) => { add(e.target.files); e.target.value = '' }} />
              </div>
              {files.length > 0 && (
                <div className="file-strip">
                  {files.map((f, i) => (
                    <button key={f.url} type="button" className={`file-chip ${i === active ? 'active' : ''}`} onClick={() => { setActive(i); setCmp(null) }} title={f.file.name}>
                      <img src={f.url} alt={f.file.name} />
                      <span className="x" onClick={(e) => { e.stopPropagation(); remove(i) }}><X size={11} /></span>
                      <span className="st" style={{ background: !f.result ? 'var(--faint)' : f.result.status === 'HEALTHY' ? 'var(--ok)' : 'var(--bad)' }} />
                    </button>
                  ))}
                </div>
              )}
            </div>
          </Card>

          {tab === 'single' ? (
            <Card title="Thông tin ca" icon={Info}>
              <div className="stack">
                <div className="grid g-2" style={{ gap: 10 }}>
                  <label className="field"><span>Khu chuồng</span>
                    <input id="in-pen" className="input" placeholder="VD: Khu A1" value={meta.pen} onChange={(e) => setMeta({ ...meta, pen: e.target.value })} />
                  </label>
                  <label className="field"><span>Mã đàn</span>
                    <input id="in-herd" className="input" placeholder="VD: DH-03" value={meta.herd_code} onChange={(e) => setMeta({ ...meta, herd_code: e.target.value })} />
                  </label>
                </div>
                <label className="field"><span>Biểu hiện lâm sàng</span>
                  <textarea id="in-notes" className="textarea" placeholder="Sốt, bỏ ăn, ngứa, vị trí tổn thương…" value={meta.notes} onChange={(e) => setMeta({ ...meta, notes: e.target.value })} />
                </label>
                <label className="field"><span>Model</span>
                  <select id="in-model" className="select" value={modelId} onChange={(e) => setModelId(e.target.value)}>
                    <option value="">Mặc định hệ thống</option>
                    {models?.map((m) => <option key={m.id} value={m.id}>{m.name} · {m.task === 'detection' ? 'phát hiện' : 'phân loại'}{m.is_default ? ' ★' : ''}</option>)}
                  </select>
                </label>
                <button id="btn-predict" className="btn btn-primary" disabled={busy || !pending} onClick={run}>
                  <Sparkles size={16} />{busy ? 'Đang phân tích…' : pending ? `Chẩn đoán ${pending} ảnh` : 'Đã chẩn đoán tất cả'}
                </button>
              </div>
            </Card>
          ) : (
            <Card title="Chọn tối đa 3 model" icon={Cpu}>
              <div className="stack" style={{ gap: 8 }}>
                {models?.map((m) => (
                  <label key={m.id} className="row" style={{ cursor: 'pointer' }}>
                    <input type="checkbox" checked={cmpIds.includes(m.id)} disabled={!cmpIds.includes(m.id) && cmpIds.length >= 3}
                      onChange={(e) => setCmpIds(e.target.checked ? [...cmpIds, m.id] : cmpIds.filter((x) => x !== m.id))} />
                    <b>{m.name}</b><span className="muted small">{m.task}</span>
                    <span className="spacer" /><code className="faint">{m.latency_ms}ms</code>
                  </label>
                ))}
                <button id="btn-compare" className="btn btn-primary" disabled={busy || !cur || !cmpIds.length} onClick={compare}>
                  <GitCompare size={16} />{busy ? 'Đang chạy…' : 'So sánh trên ảnh đang chọn'}
                </button>
              </div>
            </Card>
          )}
        </div>

        {/* ===== Cột phải: kết quả ===== */}
        {tab === 'compare' ? (
          <Card title="Kết quả so sánh" icon={GitCompare}>
            {!cmp ? <Empty>Chọn ảnh và model rồi bấm “So sánh”</Empty> : (
              <div className={`grid g-${Math.min(cmp.length, 3)}`}>
                {cmp.map((c) => (
                  <div key={c.model.id} className="stack">
                    <div className="row"><b>{c.model.name}</b><span className="spacer" /><code className="faint">{c.inference_ms}ms</code></div>
                    <Viewer src={cur.url} result={c} showBox showHeat threshold={th} />
                    <StatusHero status={c.status} confidence={c.confidence} name={c.top3[0].name} />
                    <ProbBars items={c.top3} />
                  </div>
                ))}
              </div>
            )}
          </Card>
        ) : (
          <div className="stack" style={{ gap: 18 }}>
            <Card title="Ảnh & vùng tổn thương" icon={ScanLine} className="no-print" actions={r && (
              <>
                <Switch label="Bounding box" checked={view.box} disabled={!r.boxes.length} title={!r.boxes.length ? 'Chỉ có với model phát hiện (YOLO)' : ''} onChange={(box) => setView({ ...view, box })} />
                <Switch label="Grad-CAM" checked={view.heat} disabled={!r.heatmap.length} title={!r.heatmap.length ? 'Chỉ có với model phân loại (CNN)' : ''} onChange={(heat) => setView({ ...view, heat })} />
              </>
            )}>
              <div className="stack">
                <Viewer src={cur?.url} result={r} showBox={view.box} showHeat={view.heat} threshold={th} scanning={busy && cur && !r} />
                {r && (r.boxes.length > 0 || r.heatmap.length > 0) && (
                  <label className="field">
                    <span>Ngưỡng hiển thị vùng tổn thương: <b className="mono">{th.toFixed(2)}</b></span>
                    <input id="in-threshold" type="range" min="0" max="1" step="0.01" value={th} onChange={(e) => setView({ ...view, th: Number(e.target.value) })} />
                  </label>
                )}
              </div>
            </Card>

            {!r ? (
              <Card className="no-print"><Empty>{cur ? 'Bấm “Chẩn đoán” để xem kết quả' : 'Chưa có ảnh nào được chọn'}</Empty></Card>
            ) : (
              <>
                <div className="grid g-2 no-print">
                  <Card title="Kết luận AI" icon={Sparkles} actions={<button id="btn-print" className="btn btn-sm" onClick={() => print()}><FileDown size={14} />Xuất phiếu PDF</button>}>
                    <div className="stack">
                      <StatusHero status={r.status} confidence={r.confidence} name={r.disease.name} />
                      {r.confidence < reviewTh && (
                        <div className="note warn"><AlertTriangle size={16} />
                          <span>Độ tin cậy dưới ngưỡng {pct(reviewTh, 0)} — ca đã được đưa vào hàng đợi để bác sĩ thú y khám lại.</span>
                        </div>
                      )}
                      {!!r.disease.is_dangerous && (
                        <div className="note bad"><ShieldPlus size={16} /><span><b>Bệnh nguy hiểm.</b> {r.disease.treatment}</span></div>
                      )}
                      <h3>Top-3 xác suất</h3>
                      <ProbBars items={r.top3} />
                    </div>
                  </Card>
                  <Card title="Thông tin & gợi ý xử lý" icon={Pill}>
                    <div className="stack">
                      <div className="spec">
                        <div><small>Model</small><b style={{ fontSize: 14 }}>{r.model.name}</b></div>
                        <div><small>Thời gian suy luận</small><b>{r.inference_ms}ms</b></div>
                        <div><small>Kích thước ảnh</small><b style={{ fontSize: 14 }}>{r.width}×{r.height}</b></div>
                        <div><small>Mã ca</small><b>#{r.prediction_id}</b> {r.engine === 'mock' && <span className="chip-mock" title="Engine giả lập — chưa nạp trọng số thật">MOCK</span>}</div>
                      </div>
                      <div><h3>Dấu hiệu điển hình</h3><p className="muted">{r.disease.description}</p></div>
                      <div><h3>Xử lý</h3><p className="muted">{r.disease.treatment}</p></div>
                      <div><h3>Phòng ngừa</h3><p className="muted">{r.disease.prevention}</p></div>
                    </div>
                  </Card>
                </div>
                <PrintSheet r={r} meta={meta} user={user} url={cur.url} />
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function PrintSheet({ r, meta, user, url }) {
  return (
    <div className="print-only print-area">
      <h1>PHIẾU KẾT QUẢ CHẨN ĐOÁN BỆNH DA HEO</h1>
      <p className="muted">PigDerm AI · Mã ca #{r.prediction_id} · {new Date().toLocaleString('vi-VN')} · Người thực hiện: {user.full_name}</p>
      <hr />
      <p><b>Khu chuồng:</b> {meta.pen || '—'} &nbsp; <b>Mã đàn:</b> {meta.herd_code || '—'}</p>
      <p><b>Biểu hiện lâm sàng:</b> {meta.notes || '—'}</p>
      <img src={url} alt="" style={{ maxWidth: 320, maxHeight: 240, margin: '12px 0', borderRadius: 8 }} />
      <h2>Kết luận AI: {r.status === 'HEALTHY' ? 'KHỎE MẠNH' : `BẤT THƯỜNG — ${r.disease.name}`} ({pct(r.confidence)})</h2>
      <p>Top-3: {r.top3.map((t) => `${t.name} ${pct(t.prob)}`).join(' · ')}</p>
      <p><b>Xử lý:</b> {r.disease.treatment}</p>
      <p><b>Phòng ngừa:</b> {r.disease.prevention}</p>
      <p className="muted" style={{ marginTop: 16 }}>Model: {r.model.name} · Kết quả AI chỉ mang tính sàng lọc, cần bác sĩ thú y xác nhận.</p>
    </div>
  )
}
