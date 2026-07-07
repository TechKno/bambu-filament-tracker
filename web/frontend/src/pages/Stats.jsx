import { useEffect, useState } from 'react'
import { api, money } from '../api.js'

export default function Stats() {
  const [s, setS] = useState(null)
  const [err, setErr] = useState('')
  useEffect(() => { api.stats().then(setS).catch((e) => setErr(e.message)) }, [])

  if (err) return <div className="error">{err}</div>
  if (!s) return <p className="muted">Loading…</p>

  const fc = s.forecast
  return (
    <div>
      <div className="panel">
        <h2>Usage stats</h2>
        <div className="stat-grid">
          <Stat big={s.total_prints} lbl="prints logged" />
          <Stat big={s.success_rate == null ? '—' : `${s.success_rate}%`} lbl={`success (${s.completed}/${s.completed + s.failed})`} />
          <Stat big={`${s.used_total.toLocaleString()} g`} lbl="filament used" />
          <Stat big={`${s.used_failed.toLocaleString()} g`} lbl="lost to fails" />
          <Stat big={s.in_progress} lbl="in progress" />
          <Stat big={s.tracking_days} lbl={`days tracked${s.tracking_since ? ` (since ${s.tracking_since})` : ''}`} />
        </div>
      </div>

      {(s.cost_total > 0 || s.inventory_value > 0) ? (
        <div className="panel">
          <h2>Cost</h2>
          <div className="stat-grid">
            <Stat big={money(s.cost_total)} lbl="spent on prints" />
            <Stat big={money(s.cost_failed)} lbl="lost to failed prints" />
            <Stat big={s.avg_cost_per_print == null ? '—' : money(s.avg_cost_per_print)} lbl="avg / completed print" />
            <Stat big={money(s.inventory_value)} lbl="filament on hand" />
          </div>
        </div>
      ) : (
        <div className="panel muted">Add prices to your spools (Inventory → Edit) to see cost per print and total spend.</div>
      )}

      <div className="row" style={{ alignItems: 'flex-start', gap: 16 }}>
        <div className="panel" style={{ flex: 1, minWidth: 260 }}>
          <h2>Used by material</h2>
          {s.by_material.length === 0 && <p className="muted">No usage yet.</p>}
          {s.by_material.length > 0 && (
          <table>
            <thead><tr><th>Material</th><th className="num">Used</th><th className="num">Cost</th></tr></thead>
            <tbody>
            {s.by_material.map((m) => (
              <tr key={m.material}>
                <td>{m.material}</td>
                <td className="num">{Math.round(m.grams).toLocaleString()} g</td>
                <td className="num">{m.cost > 0 ? money(m.cost) : '—'}</td>
              </tr>
            ))}
            </tbody>
          </table>
          )}
        </div>
        <div className="panel" style={{ flex: 1, minWidth: 260 }}>
          <h2>Used by month</h2>
          {s.by_month.length === 0 && <p className="muted">No usage yet.</p>}
          <table><tbody>
            {s.by_month.map((m) => (
              <tr key={m.month}><td>{m.month}</td><td className="num">{Math.round(m.grams).toLocaleString()} g</td></tr>
            ))}
          </tbody></table>
        </div>
      </div>

      <div className="panel">
        <h2>Projected run-out</h2>
        {fc.ready.length === 0 && fc.insufficient.length === 0 && <p className="muted">Log some prints to build a forecast.</p>}
        {fc.ready.length > 0 && (
          <table>
            <thead><tr><th>Filament</th><th className="num">Rate</th><th className="num">Left</th><th className="num">Runs out</th></tr></thead>
            <tbody>
              {fc.ready.map((f) => (
                <tr key={f.label}>
                  <td>{f.label}</td>
                  <td className="num">{f.rate_g_per_week.toLocaleString()} g/wk</td>
                  <td className="num">{f.estimated ? '~' : ''}{Math.round(f.remaining_g).toLocaleString()} g</td>
                  <td className="num">{f.days_left < 14 ? `~${f.days_left} days` : `~${Math.round(f.days_left / 7)} wk`}<div className="muted" style={{ fontSize: 12 }}>{f.runout_date}</div></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {fc.insufficient.length > 0 && (
          <p className="muted" style={{ marginTop: 10 }}>
            Not enough data yet (need ≥{fc.min_prints} prints over ≥{fc.min_days} days): {fc.insufficient.join(', ')}
          </p>
        )}
      </div>
    </div>
  )
}

function Stat({ big, lbl }) {
  return <div className="stat"><div className="big">{big}</div><div className="lbl">{lbl}</div></div>
}
