import { useState } from 'react'
import { api } from '../api.js'
import Modal from '../components/Modal.jsx'

export default function ResolveModal({ print, onClose, onDone }) {
  const [status, setStatus] = useState('completed')
  const [rows, setRows] = useState(print.usage.map((u) => ({ ...u, grams: u.grams })))
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const setGrams = (i, v) => setRows((rs) => rs.map((r, j) => (j === i ? { ...r, grams: v } : r)))

  async function save() {
    setBusy(true); setErr('')
    try {
      await api.resolvePrint(print.id, {
        status,
        usage: rows.map((r) => ({ spool_id: r.spool_id, grams: Number(r.grams) })),
      })
      onDone()
    } catch (e) { setErr(e.message); setBusy(false) }
  }

  return (
    <Modal title={`Resolve #${print.id} — ${print.name}`} onClose={onClose}>
      <div className="field">
        <span>Outcome</span>
        <div className="row">
          <label className="checkbox"><input type="radio" checked={status === 'completed'} onChange={() => setStatus('completed')} /><span>Completed</span></label>
          <label className="checkbox"><input type="radio" checked={status === 'failed'} onChange={() => setStatus('failed')} /><span>Failed</span></label>
        </div>
      </div>
      <p className="muted" style={{ fontSize: 13, marginTop: 4 }}>
        {status === 'failed' ? 'Enter how much was actually used before it failed.' : 'Confirm or adjust the grams used.'}
      </p>
      {rows.map((r, i) => (
        <label className="field" key={r.spool_id}>
          <span>{r.label} — grams used</span>
          <input type="number" min="0" step="0.01" value={r.grams} onChange={(e) => setGrams(i, e.target.value)} />
        </label>
      ))}
      {err && <div className="error">{err}</div>}
      <div className="row">
        <button className="btn" disabled={busy} onClick={save}>{busy ? 'Saving…' : 'Mark ' + status}</button>
        <button className="btn ghost" onClick={onClose}>Cancel</button>
      </div>
    </Modal>
  )
}
