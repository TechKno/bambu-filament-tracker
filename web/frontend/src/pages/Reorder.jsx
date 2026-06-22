import { useEffect, useState } from 'react'
import { api } from '../api.js'

const SECTIONS = [
  ['needs', 'Reorder needed'],
  ['ordered', 'On order'],
  ['ignored', 'Ignored'],
]

export default function Reorder({ reload }) {
  const [types, setTypes] = useState(null)
  const [err, setErr] = useState('')

  const load = () => api.reorder().then((d) => setTypes(d.types)).catch((e) => setErr(e.message))
  useEffect(() => { load() }, [])

  async function setStatus(t, status) {
    setErr('')
    try { await api.setReorder(t.type_id, status); await load(); await reload() } catch (e) { setErr(e.message) }
  }

  if (!types) return <p className="muted">Loading…</p>
  const actionable = types.filter((t) => t.state !== 'ok')

  return (
    <div className="panel">
      <h2>Reorder / low stock</h2>
      {err && <div className="error">{err}</div>}
      {actionable.length === 0 && <p className="muted">Everything is above the 10% threshold. Nothing to reorder.</p>}

      {SECTIONS.map(([state, heading]) => {
        const list = types.filter((t) => t.state === state)
        if (!list.length) return null
        return (
          <div key={state} style={{ marginBottom: 16 }}>
            <h3 style={{ margin: '8px 0', fontSize: 14 }} className="muted">{heading}</h3>
            {list.map((t) => (
              <div className="roll" key={t.type_id}>
                <span>{t.label}</span>
                <span className="muted">{t.current_pct === 0 ? 'OUT' : `${t.estimated ? '~' : ''}${Math.round(t.current_g)} g (${t.current_pct}%)`}</span>
                <span className="spacer" />
                {state !== 'ordered' && <button className="btn small ghost" onClick={() => setStatus(t, 'ordered')}>Mark reordered</button>}
                {state !== 'ignored' && <button className="btn small ghost" onClick={() => setStatus(t, 'ignored')}>Ignore</button>}
                {state !== 'needs' && <button className="btn small ghost" onClick={() => setStatus(t, '')}>Clear</button>}
              </div>
            ))}
          </div>
        )
      })}
    </div>
  )
}
