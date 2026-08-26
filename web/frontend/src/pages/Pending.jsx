import { useState } from 'react'
import { api, grams as fmtGrams } from '../api.js'

// Bambu reports tray colour as RRGGBBAA hex; show the first 6 as a swatch.
function bambuSwatch(hex) {
  const c = typeof hex === 'string' && /^[0-9a-fA-F]{6,8}$/.test(hex) ? `#${hex.slice(0, 6)}` : 'var(--panel-2)'
  return <span className="bambu-swatch" style={{ background: c }} title={hex || 'unknown'} />
}

const TAG = { completed: ['ok', 'completed'], failed: ['failed', 'failed'] }

export default function Pending({ pending, spools, reload }) {
  if (!pending) return <p className="muted">Loading…</p>
  return (
    <div>
      <div className="row" style={{ marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>Pending prints</h2>
        <span className="muted">from the printer, awaiting confirmation</span>
      </div>
      {pending.length === 0 && (
        <div className="panel muted">
          Nothing pending. When a print finishes on the printer, it'll appear here for you to
          confirm which spool it used.
        </div>
      )}
      {pending.map((cap) => (
        <PendingCard key={cap.id} cap={cap} spools={spools} reload={reload} />
      ))}
    </div>
  )
}

function PendingCard({ cap, spools, reload }) {
  const [status, setStatus] = useState(cap.status || 'completed')
  const [rows, setRows] = useState(
    cap.materials.map((m) => ({
      slot_key: m.slot_key,
      spool_id: m.suggested_spool_id ? String(m.suggested_spool_id) : '',
      grams: m.suggested_grams != null ? String(m.suggested_grams) : '',
      meta: m,
    }))
  )
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const setRow = (i, k, v) => setRows((rs) => rs.map((r, j) => (j === i ? { ...r, [k]: v } : r)))

  async function confirm() {
    setBusy(true); setErr('')
    try {
      const usage = rows
        .filter((r) => r.spool_id && r.spool_id !== 'skip' && r.grams !== '')
        .map((r) => ({ spool_id: Number(r.spool_id), grams: Number(r.grams), slot_key: r.slot_key }))
      if (!usage.length) throw new Error('Assign at least one material to a spool and enter grams.')
      await api.confirmPending(cap.id, { status, name: cap.model, usage })
      await reload()
    } catch (e) { setErr(e.message); setBusy(false) }
  }

  async function dismiss() {
    if (!confirm_(`Dismiss "${cap.model}" without logging it?`)) return
    setBusy(true); setErr('')
    try { await api.dismissPending(cap.id); await reload() } catch (e) { setErr(e.message); setBusy(false) }
  }
  // window.confirm shadowed by our confirm(); alias it
  function confirm_(m) { return window.confirm(m) }

  const [cls, label] = TAG[cap.status] || ['ok', cap.status]
  return (
    <div className="panel">
      <div className="row" style={{ marginBottom: 10 }}>
        <span className={`tag ${cls}`}>{label}</span>
        <b>{cap.model}</b>
        <span className="muted">
          {cap.printer_name}{cap.weight_g != null ? ` · ${cap.weight_g} g sliced` : ''}
          {cap.duration_min != null ? ` · ${cap.duration_min} min` : ''} · {cap.captured_at}
        </span>
      </div>

      <div className="field">
        <span>Outcome</span>
        <div className="row">
          <label className="checkbox"><input type="radio" checked={status === 'completed'} onChange={() => setStatus('completed')} /><span>Completed</span></label>
          <label className="checkbox"><input type="radio" checked={status === 'failed'} onChange={() => setStatus('failed')} /><span>Failed</span></label>
        </div>
      </div>

      <span className="muted" style={{ fontSize: 13 }}>Materials the printer reported — assign each to a spool:</span>
      {rows.map((r, i) => (
        <div className="pending-mat" key={r.slot_key + i}>
          <div className="pending-mat-info">
            {bambuSwatch(r.meta.color)}
            <span>{r.meta.external ? 'External spool' : `AMS ${r.meta.ams ?? '?'} · tray ${r.meta.tray ?? '?'}`}</span>
            {r.meta.type && <span className="muted">{r.meta.type}</span>}
            {r.meta.grams_source === 'gcode' && <span className="pill ordered" title="grams read from the sliced file">auto</span>}
          </div>
          <select value={r.spool_id} onChange={(e) => setRow(i, 'spool_id', e.target.value)}>
            <option value="">Choose a spool…</option>
            <option value="skip">— skip (don't deduct) —</option>
            {spools.map((s) => (
              <option key={s.id} value={s.id}>#{s.id} {s.label} — {fmtGrams(s.remaining_g)} g</option>
            ))}
          </select>
          <input type="number" min="0" step="0.01" placeholder="grams" value={r.grams}
            onChange={(e) => setRow(i, 'grams', e.target.value)} />
        </div>
      ))}

      {err && <div className="error">{err}</div>}
      <div className="row" style={{ marginTop: 8 }}>
        <button className="btn" disabled={busy} onClick={confirm}>{busy ? 'Working…' : 'Confirm & log'}</button>
        <button className="btn ghost" disabled={busy} onClick={dismiss}>Dismiss</button>
      </div>
    </div>
  )
}
