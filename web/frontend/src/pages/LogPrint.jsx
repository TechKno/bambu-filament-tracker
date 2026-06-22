import { useState } from 'react'
import { api } from '../api.js'

const OUTCOMES = [
  ['completed', 'Completed'],
  ['failed', 'Failed'],
  ['in_progress', 'In progress'],
]

export default function LogPrint({ spools, reload, onDone }) {
  const [name, setName] = useState('')
  const [rows, setRows] = useState([{ spool_id: '', grams: '' }])
  const [status, setStatus] = useState('completed')
  const [shortfalls, setShortfalls] = useState(null)
  const [err, setErr] = useState('')
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  if (!spools) return <p className="muted">Loading…</p>
  if (spools.length === 0) return <div className="panel muted">No spools with filament available — add one in Inventory first.</div>

  const setRow = (i, k, v) => setRows((rs) => rs.map((r, j) => (j === i ? { ...r, [k]: v } : r)))
  const addRow = () => setRows((rs) => [...rs, { spool_id: '', grams: '' }])
  const delRow = (i) => setRows((rs) => rs.filter((_, j) => j !== i))

  function usagePayload() {
    return rows
      .filter((r) => r.spool_id && r.grams !== '')
      .map((r) => ({ spool_id: Number(r.spool_id), grams: Number(r.grams) }))
  }

  async function submit(e) {
    e.preventDefault()
    setErr(''); setMsg('')
    const usage = usagePayload()
    if (!name.trim()) return setErr('Give the print a name.')
    if (!usage.length) return setErr('Add at least one material with grams.')

    setBusy(true)
    try {
      // Pre-flight unless the user already acknowledged a shortfall.
      if (!shortfalls) {
        const { shortfalls: sf } = await api.preflight(usage)
        if (sf.length) { setShortfalls(sf); setBusy(false); return }
      }
      await api.logPrint({ name: name.trim(), usage, status })
      setMsg(status === 'in_progress'
        ? 'Started — mark it done later from the in-progress banner.'
        : 'Print logged.')
      setName(''); setRows([{ spool_id: '', grams: '' }]); setStatus('completed'); setShortfalls(null)
      await reload()
      if (status !== 'in_progress') setTimeout(onDone, 600)
    } catch (e2) {
      setErr(e2.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="panel">
      <h2>Log a print</h2>
      <form onSubmit={submit}>
        <label className="field"><span>Print name</span>
          <input value={name} autoFocus onChange={(e) => setName(e.target.value)} placeholder="e.g. Benchy" /></label>

        <span className="muted" style={{ fontSize: 13 }}>Materials</span>
        {rows.map((r, i) => (
          <div className="mat-row" key={i}>
            <label className="field" style={{ margin: 0 }}>
              <select value={r.spool_id} onChange={(e) => { setRow(i, 'spool_id', e.target.value); setShortfalls(null) }}>
                <option value="">Choose a spool…</option>
                {spools.map((s) => (
                  <option key={s.id} value={s.id}>#{s.id} {s.label} — {Math.round(s.remaining_g)} g left</option>
                ))}
              </select>
            </label>
            <label className="field" style={{ margin: 0 }}>
              <input type="number" min="0" placeholder="grams" value={r.grams}
                onChange={(e) => { setRow(i, 'grams', e.target.value); setShortfalls(null) }} />
            </label>
            {rows.length > 1
              ? <button type="button" className="btn ghost small" onClick={() => delRow(i)}>✕</button>
              : <span />}
          </div>
        ))}
        <button type="button" className="btn ghost small" onClick={addRow}>+ Add material (multi-material)</button>

        <div className="field" style={{ marginTop: 16 }}>
          <span>Outcome</span>
          <div className="row">
            {OUTCOMES.map(([id, label]) => (
              <label className="checkbox" key={id}>
                <input type="radio" name="status" checked={status === id} onChange={() => setStatus(id)} />
                <span>{label}</span>
              </label>
            ))}
          </div>
        </div>

        {shortfalls && (
          <div className="banner yellow">
            <b>Not enough filament to finish on:</b>
            {shortfalls.map((s) => (
              <div className="line" key={s.spool_id}>
                {s.label}: short by {Math.round(s.short_by)} g
                {s.spares ? ` — you have ${s.spares} spare(s)` : ' — no spares!'}
              </div>
            ))}
            <div className="muted" style={{ marginTop: 6 }}>Submit again to log it anyway.</div>
          </div>
        )}

        {err && <div className="error">{err}</div>}
        {msg && <div className="success">{msg}</div>}

        <div className="row" style={{ marginTop: 8 }}>
          <button className="btn" disabled={busy}>
            {busy ? 'Working…' : shortfalls ? 'Log anyway' : 'Log print'}
          </button>
        </div>
      </form>
    </div>
  )
}
