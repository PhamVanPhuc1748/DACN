import { useState } from 'react'
import { CheckCircle2, ClipboardList, Download, Filter, ImageOff, Pencil, Stethoscope } from 'lucide-react'
import { api, download, qs } from '../api'
import { Card, ClassPicker, ClassTag, Empty, Modal, ProbBars, ReviewBadge, Switch, fmtTime, pct, useApp, useLoad } from '../ui'

const NO_FILTER = { date_from: '', date_to: '', pen: '', class_code: '', low_conf: false, status: '' }

export default function Cases() {
  const { user, diseases, settings } = useApp()
  const [f, setF] = useState(() => (user.role === 'VET' ? { ...NO_FILTER, status: 'PENDING' } : NO_FILTER))
  const [data, reload, loading] = useLoad(() => api(`/api/cases?${qs(f)}`), [JSON.stringify(f)])
  const [sel, setSel] = useState(null)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const reviewTh = Number(settings.review_threshold ?? 0.7)

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Nhật ký ca bệnh</h1>
          <p>Lịch sử chẩn đoán và hàng đợi thẩm định của bác sĩ thú y.</p>
        </div>
        <button id="btn-export" className="btn" onClick={() => download(`/api/cases/export.csv?${qs(f)}`, 'ca-benh.csv')}><Download size={16} />Xuất CSV</button>
      </div>

      <Card title="Bộ lọc" icon={Filter} actions={<button className="btn btn-ghost btn-sm" onClick={() => setF(NO_FILTER)}>Xóa lọc</button>}>
        <div className="row" style={{ alignItems: 'flex-end', gap: 12 }}>
          <label className="field"><span>Từ ngày</span><input id="f-from" type="date" className="input" value={f.date_from} onChange={set('date_from')} /></label>
          <label className="field"><span>Đến ngày</span><input id="f-to" type="date" className="input" value={f.date_to} onChange={set('date_to')} /></label>
          <label className="field"><span>Khu chuồng</span>
            <select id="f-pen" className="select" value={f.pen} onChange={set('pen')}>
              <option value="">Tất cả</option>{data?.pens.map((p) => <option key={p}>{p}</option>)}
            </select>
          </label>
          <label className="field"><span>AI dự đoán</span>
            <select id="f-class" className="select" value={f.class_code} onChange={set('class_code')}>
              <option value="">Tất cả</option>{diseases.map((d) => <option key={d.code} value={d.code}>{d.name}</option>)}
            </select>
          </label>
          <label className="field"><span>Trạng thái</span>
            <select id="f-status" className="select" value={f.status} onChange={set('status')}>
              <option value="">Tất cả</option><option value="PENDING">Chờ duyệt</option><option value="REVIEWED">Đã duyệt</option>
            </select>
          </label>
          <Switch label={`Độ tin cậy < ${pct(reviewTh, 0)}`} checked={f.low_conf} onChange={(low_conf) => setF({ ...f, low_conf })} />
        </div>
      </Card>

      <Card title={`Danh sách ca${data ? ` (${data.items.length})` : ''}`} icon={ClipboardList}>
        {loading && !data ? <div className="skeleton" style={{ height: 240 }} /> : !data?.items.length ? <Empty>Không có ca nào khớp bộ lọc</Empty> : (
          <div className="table-wrap" style={{ maxHeight: 620 }}>
            <table className="table">
              <thead><tr><th>Ca</th><th>Ảnh</th><th>Thời gian</th><th>Khu / đàn</th><th>AI dự đoán</th><th>Tin cậy</th><th>Model</th><th>Trạng thái</th><th>Kết luận BS</th><th /></tr></thead>
              <tbody>
                {data.items.map((c) => (
                  <tr key={c.id}>
                    <td className="mono">#{c.id}</td>
                    <td>{c.image_uri ? <img className="thumb" src={c.image_uri} alt="" /> : <div className="thumb"><ImageOff size={16} /></div>}</td>
                    <td className="muted">{fmtTime(c.created_at)}</td>
                    <td>{c.pen || '—'}<div className="faint small">{c.herd_code}</div></td>
                    <td><ClassTag code={c.predicted_code} name={c.predicted_name} /></td>
                    <td className="mono" style={{ color: c.confidence < reviewTh ? 'var(--warn)' : undefined }}>{pct(c.confidence)}</td>
                    <td className="muted small">{c.model_name}</td>
                    <td><ReviewBadge status={c.review_status} /></td>
                    <td>{c.final_code ? <ClassTag code={c.final_code} name={c.final_name} /> : <span className="faint">—</span>}</td>
                    <td>
                      <button className="btn btn-sm" onClick={() => setSel(c)}>
                        {user.role === 'VET' && c.review_status === 'PENDING' ? <><Stethoscope size={14} />Thẩm định</> : 'Chi tiết'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {sel && <CaseModal c={sel} onClose={() => setSel(null)} onDone={() => { setSel(null); reload() }} />}
    </div>
  )
}

function CaseModal({ c, onClose, onDone }) {
  const { user, toast } = useApp()
  const [mode, setMode] = useState(null)   // null | 'correct'
  const [code, setCode] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const canReview = user.role === 'VET'

  const submit = async (class_code) => {
    setBusy(true)
    try {
      const r = await api(`/api/cases/${c.id}/review`, { method: 'POST', body: { class_code, note } })
      toast(r.review_status === 'CONFIRMED' ? 'Đã xác nhận kết quả AI' : 'Đã hiệu chỉnh — nhãn được đưa vào dữ liệu huấn luyện')
      onDone()
    } catch (e) { toast(e.message, true) } finally { setBusy(false) }
  }

  return (
    <Modal title={`Ca #${c.id} · ${fmtTime(c.created_at)}`} onClose={onClose} wide>
      <div className="grid g-2">
        <div className="stack">
          {c.image_uri ? <img src={c.image_uri} alt="" style={{ width: '100%', borderRadius: 12 }} /> : <div className="viewer-empty" style={{ borderRadius: 12 }}><div><ImageOff size={30} /><br />Ca demo — không có ảnh</div></div>}
          <div className="spec">
            <div><small>Khu chuồng</small><b style={{ fontSize: 14 }}>{c.pen || '—'}</b></div>
            <div><small>Mã đàn</small><b style={{ fontSize: 14 }}>{c.herd_code || '—'}</b></div>
            <div><small>Model</small><b style={{ fontSize: 14 }}>{c.model_name}</b></div>
            <div><small>Suy luận</small><b>{c.inference_ms}ms</b></div>
          </div>
          {c.notes && <div className="note"><span><b>Lâm sàng:</b> {c.notes}</span></div>}
        </div>
        <div className="stack">
          <div className="row"><ReviewBadge status={c.review_status} />{c.reviewed_by_name && <span className="muted small">bởi {c.reviewed_by_name}</span>}</div>
          <h3>AI dự đoán</h3>
          <ProbBars items={c.top3} />
          {c.final_code && <div className="note"><CheckCircle2 size={16} color="var(--ok)" /><span>Kết luận BS: <b>{c.final_name}</b>{c.review_note && <> — {c.review_note}</>}</span></div>}
          {canReview && (
            <>
              <div className="divider" />
              {mode !== 'correct' ? (
                <div className="stack">
                  <label className="field"><span>Ghi chú (tùy chọn)</span><textarea className="textarea" value={note} onChange={(e) => setNote(e.target.value)} /></label>
                  <div className="row">
                    <button id="btn-confirm" className="btn btn-ok" disabled={busy} onClick={() => submit(null)}><CheckCircle2 size={16} />AI đúng</button>
                    <button id="btn-correct" className="btn" disabled={busy} onClick={() => setMode('correct')}><Pencil size={16} />Hiệu chỉnh</button>
                  </div>
                </div>
              ) : (
                <div className="stack">
                  <span className="muted small">Chọn kết luận đúng</span>
                  <ClassPicker value={code} onChange={setCode} exclude={c.predicted_code} />
                  <label className="field"><span>Lý do lâm sàng (bắt buộc)</span><textarea id="in-review-note" className="textarea" value={note} onChange={(e) => setNote(e.target.value)} /></label>
                  <div className="row">
                    <button className="btn btn-ghost" onClick={() => setMode(null)}>Quay lại</button>
                    <button id="btn-submit-correct" className="btn btn-primary" disabled={busy || !code || !note.trim()} onClick={() => submit(code)}>Lưu hiệu chỉnh</button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </Modal>
  )
}
