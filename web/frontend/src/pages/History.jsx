import { useEffect, useState } from 'react'
import { api, money, grams, thumbUrl, shortDate } from '../api.js'
import Modal from '../components/Modal.jsx'

const TAG = { completed: ['ok', 'OK'], failed: ['failed', 'FAILED'], in_progress: ['wip', 'WIP'] }

// '—' when nothing is priced; a trailing '+' when only some materials have a price.
function costLabel(p) {
  if (p.cost_status === 'none') return '—'
  return money(p.cost) + (p.cost_status === 'partial' ? '+' : '')
}

export default function History({ reload }) {
  const [prints, setPrints] = useState(null)
  const [editing, setEditing] = useState(null)
  const [err, setErr] = useState('')

  const load = () => api.history().then((d) => setPrints(d.prints)).catch((e) => setErr(e.message))
  useEffect(() => { load() }, [])

  async function del(p) {
    if (!confirm(`Delete print #${p.id} '${p.name}'? Filament will be added back to the spool(s).`)) return
    setErr('')
    try { await api.deletePrint(p.id); await load(); await reload() } catch (e) { setErr(e.message) }
  }

  if (!prints) return <p className="muted">Loading…</p>

  return (
    <div className="panel">
      {err && <div className="error">{err}</div>}
      {prints.length === 0 && <p className="muted">No prints logged yet.</p>}
      {prints.length > 0 && (
        <table>
          <thead><tr><th>#</th><th>Date</th><th>Status</th><th>Name</th><th className="num">Used</th><th className="num">Cost</th><th></th></tr></thead>
          <tbody>
            {prints.map((p) => {
              const [cls, label] = TAG[p.status] || ['ok', p.status]
              return (
                <tr key={p.id}>
                  <td>{p.id}</td>
                  <td className="muted mono">{shortDate(p.date)}</td>
                  <td><span className={`tag ${cls}`}>{label}</span></td>
                  <td>
                    <div className="hist-name">
                      {p.thumbnail
                        ? <img className="thumb" src={thumbUrl(p.thumbnail)} alt="" loading="lazy" />
                        : <span className="thumb thumb-empty" />}
                      <div style={{ minWidth: 0 }}>
                        {p.name}
                        <div className="muted" style={{ fontSize: 12 }}>
                          {p.usage.map((u) => `${u.label}: ${grams(u.grams)}g`).join(' · ')}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="num">{grams(p.total_g)}g{p.status === 'in_progress' ? ' planned' : ''}</td>
                  <td className="num" title={p.cost_status === 'partial' ? 'Partial — some materials have no price' : ''}>{costLabel(p)}</td>
                  <td className="num">
                    <button className="btn ghost small" onClick={() => setEditing(p)}>Edit</button>{' '}
                    <button className="btn danger small" onClick={() => del(p)}>✕</button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}

      {editing && (
        <EditModal print={editing} onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); load(); reload() }} />
      )}
    </div>
  )
}

function EditModal({ print, onClose, onSaved }) {
  const [name, setName] = useState(print.name)
  const [rows, setRows] = useState(print.usage.map((u) => ({ ...u })))
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const setGrams = (i, v) => setRows((rs) => rs.map((r, j) => (j === i ? { ...r, grams: v } : r)))

  async function save() {
    setBusy(true); setErr('')
    try {
      await api.editPrint(print.id, {
        name,
        usage: rows.map((r) => ({ spool_id: r.spool_id, grams: Number(r.grams) })),
      })
      onSaved()
    } catch (e) { setErr(e.message); setBusy(false) }
  }

  return (
    <Modal title={`Edit print #${print.id}`} onClose={onClose}>
      <label className="field"><span>Name</span><input value={name} onChange={(e) => setName(e.target.value)} /></label>
      <span className="muted" style={{ fontSize: 13 }}>Grams used (corrections adjust the spool weight)</span>
      {rows.map((r, i) => (
        <label className="field" key={r.spool_id}>
          <span>{r.label}</span>
          <input type="number" min="0" step="0.01" value={r.grams} onChange={(e) => setGrams(i, e.target.value)} />
        </label>
      ))}
      {err && <div className="error">{err}</div>}
      <div className="row">
        <button className="btn" disabled={busy} onClick={save}>{busy ? 'Saving…' : 'Save'}</button>
        <button className="btn ghost" onClick={onClose}>Cancel</button>
      </div>
    </Modal>
  )
}
