import { useState } from 'react'
import { api, grams as fmtGrams, thumbUrl } from '../api.js'
import { rankSpools, bestGuess } from '../colors.js'

// Bambu reports tray colour as RRGGBBAA hex; show the first 6 as a swatch.
function bambuSwatch(hex) {
  const c = typeof hex === 'string' && /^[0-9a-fA-F]{6,8}$/.test(hex) ? `#${hex.slice(0, 6)}` : 'var(--s2)'
  return <span className="bambu-swatch" style={{ background: c }} title={hex || 'unknown'} />
}

const TAG = { completed: ['ok', 'completed'], failed: ['failed', 'failed'] }

// A spool <select> that puts the best colour+type matches first ("Suggested"),
// then all other spools ("expand more"), pre-selecting `value`.
function SpoolSelect({ spools, color, type, value, onChange, allowSkip = true }) {
  const ranked = rankSpools(spools, color, type)
  const suggested = ranked.filter((s) => s._typeMatch && s._cdist < 130).slice(0, 4)
  const sids = new Set(suggested.map((s) => s.id))
  const others = ranked.filter((s) => !sids.has(s.id))
  const opt = (s) => <option key={s.id} value={s.id}>#{s.id} {s.label} — {fmtGrams(s.remaining_g)} g</option>
  return (
    <select value={value} onChange={onChange}>
      <option value="">Choose a spool…</option>
      {allowSkip && <option value="skip">— skip (don't deduct) —</option>}
      {suggested.length > 0 && <optgroup label="Suggested">{suggested.map(opt)}</optgroup>}
      <optgroup label={suggested.length ? 'All spools' : ' '}>{others.map(opt)}</optgroup>
    </select>
  )
}

export default function Pending({ pending, loads, spools, reload }) {
  if (!pending) return <p className="muted">Loading…</p>
  const hasLoads = loads && loads.length > 0
  return (
    <div>
      {hasLoads && (
        <div style={{ marginBottom: 18 }}>
          <div className="row" style={{ marginBottom: 8 }}>
            <h2 className="sec-head" style={{ margin: 0 }}>Filament loaded</h2>
            <span className="muted">confirm what's in each slot so prints pre-fill automatically</span>
          </div>
          {loads.map((l) => <LoadCard key={l.id} load={l} spools={spools} reload={reload} />)}
        </div>
      )}

      <div className="row" style={{ marginBottom: 12 }}>
        <h2 className="sec-head" style={{ margin: 0 }}>Pending prints</h2>
        <span className="muted">from the printer, awaiting confirmation</span>
      </div>
      {pending.length === 0 && (
        <div className="panel muted">
          Nothing pending. When a print finishes it appears here — usually with the spool and grams
          already filled in, so you just confirm.
        </div>
      )}
      {pending.map((cap) => <PendingCard key={cap.id} cap={cap} spools={spools} reload={reload} />)}
    </div>
  )
}

function LoadCard({ load, spools, reload }) {
  const [spoolId, setSpoolId] = useState(bestGuess(load.color, load.type, load.current_spool_id, spools))
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  async function act(fn) {
    setBusy(true); setErr('')
    try { await fn(); await reload() } catch (e) { setErr(e.message); setBusy(false) }
  }

  return (
    <div className="panel" style={{ padding: 14 }}>
      <div className="row" style={{ marginBottom: 8 }}>
        {bambuSwatch(load.color)}
        <b>{load.external ? 'External spool' : `AMS ${(load.ams ?? 0) + 1} · slot ${(load.tray ?? 0) + 1}`}</b>
        <span className="muted">{load.type} loaded · {load.ts}</span>
      </div>
      <div className="row">
        <div style={{ flex: 1, minWidth: 200 }}>
          <SpoolSelect spools={spools} color={load.color} type={load.type} value={spoolId}
            onChange={(e) => setSpoolId(e.target.value)} allowSkip={false} />
        </div>
        <button className="btn" disabled={busy || !spoolId || spoolId === 'skip'}
          onClick={() => act(() => api.assignLoad(load.id, { spool_id: Number(spoolId) }))}>Assign</button>
        <button className="btn ghost" disabled={busy} onClick={() => act(() => api.dismissLoad(load.id))}>Dismiss</button>
      </div>
      {err && <div className="error">{err}</div>}
    </div>
  )
}

function PendingCard({ cap, spools, reload }) {
  const [name, setName] = useState(cap.model || '')
  const [status, setStatus] = useState(cap.status || 'completed')
  const [rows, setRows] = useState(
    cap.materials.map((m) => ({
      slot_key: m.slot_key,
      spool_id: bestGuess(m.color, m.type, m.suggested_spool_id, spools),
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
      if (!name.trim()) throw new Error('Give the print a name.')
      await api.confirmPending(cap.id, { status, name: name.trim(), usage })
      await reload()
    } catch (e) { setErr(e.message); setBusy(false) }
  }

  async function dismiss() {
    if (!window.confirm(`Dismiss "${name}" without logging it?`)) return
    setBusy(true); setErr('')
    try { await api.dismissPending(cap.id); await reload() } catch (e) { setErr(e.message); setBusy(false) }
  }

  const [cls, label] = TAG[status] || ['ok', status]
  const failedPct = cap.printed_fraction != null ? Math.round(cap.printed_fraction * 100) : null
  return (
    <div className="panel">
      <div className="row" style={{ marginBottom: 10 }}>
        {cap.thumbnail && <img className="thumb thumb-lg" src={thumbUrl(cap.thumbnail)} alt="" />}
        <span className={`tag ${cls}`}>{label}</span>
        <button className="linklike" title="change outcome"
          onClick={() => setStatus(status === 'completed' ? 'failed' : 'completed')}>change</button>
        <input className="pending-name" value={name} onChange={(e) => setName(e.target.value)} />
      </div>
      <div className="muted" style={{ fontSize: 13, marginBottom: 10 }}>
        {cap.printer_name}
        {cap.weight_g != null ? ` · ${cap.weight_g} g sliced` : ''}
        {cap.duration_min != null ? ` · ${cap.duration_min} min` : ''} · {cap.captured_at}
        {status === 'failed' && failedPct != null && ` · failed ~${failedPct}% in — grams estimated`}
      </div>

      {rows.map((r, i) => (
        <div className="pending-mat" key={r.slot_key + i}>
          <div className="pending-mat-info">
            {bambuSwatch(r.meta.color)}
            <span>{r.meta.external ? 'External spool' : `AMS ${(r.meta.ams ?? 0) + 1} · slot ${(r.meta.tray ?? 0) + 1}`}</span>
            {r.meta.type && <span className="muted">{r.meta.type}</span>}
            {r.meta.grams_source === 'gcode' && <span className="pill ordered" title="grams from the sliced file">auto</span>}
            {r.meta.grams_source === 'gcode-partial' && <span className="pill switch" title="estimated from % printed">est</span>}
          </div>
          <SpoolSelect spools={spools} color={r.meta.color} type={r.meta.type} value={r.spool_id}
            onChange={(e) => setRow(i, 'spool_id', e.target.value)} />
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
