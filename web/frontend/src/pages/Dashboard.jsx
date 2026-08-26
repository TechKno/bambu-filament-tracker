import { api, money, grams, thumbUrl } from '../api.js'
import SpoolIcon from '../components/SpoolIcon.jsx'

// A contextual landing page: every block below appears only when it has
// something to say, so a quiet workshop shows a short page and a busy one
// surfaces exactly what needs attention.

const fmtEta = (min) => {
  if (!min) return null
  const h = Math.floor(min / 60), m = min % 60
  return h ? `${h}h ${m}m` : `${m}m`
}

// Clock time the print should finish, from the minutes the printer reports.
const finishTime = (min) => {
  if (min == null) return null
  const end = new Date(Date.now() + min * 60000)
  const hhmm = end.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  // Day delta from copies — never mutate the Date the display string came from.
  const midnight = (d) => new Date(d).setHours(0, 0, 0, 0)
  const days = Math.round((midnight(end) - midnight(new Date())) / 86400000)
  if (days === 0) return hhmm
  if (days === 1) return `${hhmm} tomorrow`
  return `${hhmm} in ${days} days`
}

export default function Dashboard({ data, go, setMonth }) {
  if (!data) return <p className="muted">Loading…</p>

  const printing = (data.printers || []).filter((p) => p.printing)
  const idle = (data.printers || []).filter((p) => !p.printing)
  const actions = (data.pending_count || 0) + (data.loads?.length || 0) + (data.in_progress?.length || 0)
  const quiet = !printing.length && !actions && !data.needs_reorder?.length

  return (
    <div>
      {printing.map((p) => <ActivePrint key={p.serial} p={p} />)}

      {quiet && (
        <div className="panel dash-quiet">
          <div className="dash-quiet-mark">✓</div>
          <div>
            <b>All clear</b>
            <div className="muted">
              Nothing printing, nothing to confirm, no filament running low.
              {idle.length > 0 && ` ${idle.map((p) => p.name).join(', ')} idle.`}
            </div>
          </div>
        </div>
      )}

      {actions > 0 && (
        <div className="panel">
          <h2>Needs you</h2>
          {data.pending_count > 0 && (
            <Row onClick={() => go('pending')} icon="📥"
              title={`${data.pending_count} finished print${data.pending_count > 1 ? 's' : ''} to confirm`}
              sub="Spool and grams are pre-filled — just check and log." action="Review" />
          )}
          {(data.loads || []).map((l) => (
            <Row key={l.id} onClick={() => go('pending')} icon={<SpoolIcon color={l.type} size={20} />}
              title={`Filament loaded in ${l.external ? 'the external spool' : `AMS ${(l.ams ?? 0) + 1} slot ${(l.tray ?? 0) + 1}`}`}
              sub={`${l.type || 'Unknown'} — tell it which spool this is`} action="Assign" />
          ))}
          {(data.in_progress || []).map((j) => (
            <Row key={j.id} onClick={() => go('history')} icon="⏳"
              title={`"${j.name}" still marked in progress`}
              sub={`Started ${j.date} — resolve it to deduct the filament`} action="Resolve" />
          ))}
        </div>
      )}

      {data.needs_reorder?.length > 0 && (
        <div className="panel">
          <h2>Running low</h2>
          {data.needs_reorder.map((r) => (
            <Row key={r.type_id} onClick={() => go('reorder')} icon={<SpoolIcon color={r.color} size={20} />}
              title={r.label}
              sub={r.current_pct === 0 ? 'Out of stock' : `${r.current_pct}% left (${grams(r.current_g)} g)`}
              action="Reorder" />
          ))}
        </div>
      )}

      <div className="panel">
        <h2>At a glance</h2>
        <div className="stat-grid" style={{ marginBottom: 16 }}>
          <Tile big={data.now.spools} lbl="spools in stock" onClick={() => go('inventory')} />
          <Tile big={money(data.now.inventory_value)} lbl="filament value" onClick={() => go('inventory')} />
          <Tile big={data.now.prints_all_time} lbl="prints all time" onClick={() => go('history')} />
        </div>
        <Periods periods={data.periods} setMonth={setMonth} />
      </div>

      {data.forecast?.length > 0 && (
        <div className="panel">
          <h2>Running out next</h2>
          {data.forecast.map((f) => (
            <div className="roll" key={f.label}>
              <span>{f.label}</span>
              <span className="muted">{f.rate_g_per_week} g/wk</span>
              <span className="spacer" />
              <span className={f.days_left < 14 ? 'pill low' : 'muted'}>
                {f.days_left < 14 ? `~${f.days_left} days` : `~${Math.round(f.days_left / 7)} weeks`}
              </span>
            </div>
          ))}
        </div>
      )}

      {data.recent?.length > 0 && (
        <div className="panel">
          <div className="row" style={{ marginBottom: 10 }}>
            <h2 style={{ margin: 0 }}>Recent prints</h2>
            <span className="spacer" />
            <button className="btn ghost small" onClick={() => go('history')}>All history</button>
          </div>
          <div className="dash-recent">
            {data.recent.map((r) => (
              <div className="dash-card" key={r.id} title={r.name}>
                {r.thumbnail
                  ? <img className="dash-card-img" src={thumbUrl(r.thumbnail)} alt="" loading="lazy" />
                  : <div className="dash-card-img dash-card-empty">no image</div>}
                <div className="dash-card-name">{r.name}</div>
                <div className="muted" style={{ fontSize: 12 }}>
                  {grams(r.total_g)} g{r.cost_status !== 'none' ? ` · ${money(r.cost)}` : ''}
                  {r.status === 'failed' && ' · failed'}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function ActivePrint({ p }) {
  const paused = p.gcode_state === 'PAUSE'
  const pct = Math.min(100, p.percent ?? 0)
  const shortfalls = (p.projection || []).filter((x) => !x.enough)
  return (
    <div className="panel dash-active">
      <div className="dash-active-head">
        {p.thumbnail
          ? <img className="dash-active-img" src={thumbUrl(p.thumbnail)} alt="" />
          : <div className="dash-active-img dash-card-empty">no image</div>}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="row" style={{ gap: 8 }}>
            <span className="dot" style={{ background: paused ? 'var(--yellow)' : 'var(--green)' }} />
            <b>{paused ? 'Paused' : 'Printing'}</b>
            <span className="muted">on {p.name}</span>
          </div>
          <div className="dash-active-name">{p.model || 'Print'}</div>
          <div className="muted" style={{ fontSize: 13 }}>
            {p.layer != null && p.total_layers ? `Layer ${p.layer} of ${p.total_layers}` : ''}
            {p.weight_g ? ` · ${grams(p.weight_g)} g` : ''}
            {p.cost != null && ` · ${money(p.cost)}${p.cost_status === 'partial' ? '+' : ''}`}
          </div>
          <div className={`bar${paused ? ' mid' : ''}`} style={{ maxWidth: 'none', marginTop: 8 }}>
            <div style={{ width: `${pct}%` }} />
          </div>
          <div className="dash-eta">
            <span>{pct}% complete</span>
            {p.remaining_min > 0 ? (
              <span>
                <b>Finishes ~{finishTime(p.remaining_min)}{paused ? ' (if resumed)' : ''}</b>
                {' '}· {fmtEta(p.remaining_min)} left
              </span>
            ) : p.remaining_min === 0 && !paused ? (
              <span><b>Finishing now</b></span>
            ) : null}
          </div>
        </div>
      </div>

      {(p.projection || []).length > 0 && (
        <div className="dash-proj">
          {shortfalls.length > 0
            ? <div className="banner red" style={{ margin: 0 }}>
                <b>May run out before this finishes</b>
                {shortfalls.map((s) => (
                  <div className="line" key={s.slot_key}>
                    {s.label}: needs ~{grams(s.needed_g)} g more, {grams(s.remaining_g)} g left
                    <b style={{ marginLeft: 6 }}>(short ~{grams(s.short_by)} g)</b>
                  </div>
                ))}
              </div>
            : <div className="dash-ok">
                ✓ Enough filament to finish
                {p.projection.map((s) => (
                  <span className="muted" key={s.slot_key}>
                    {' '}· {s.label}: {grams(s.remaining_g)} g left, needs ~{grams(s.needed_g)} g
                  </span>
                ))}
              </div>}
        </div>
      )}
    </div>
  )
}

// Month vs year side by side, with arrows to page back through months that
// have prints (the current month is always offered, even if empty).
// A period cost is only as knowable as its spool prices: '—' when nothing is
// priced (matching History), a '+' suffix when only some prints are priced.
const periodCost = (s) =>
  s.cost_status === 'none' ? '—' : money(s.cost) + (s.cost_status === 'partial' ? '+' : '')

const periodWaste = (s) => {
  if (!s.failed) return '—'
  const g = `${grams(s.wasted_g)} g`
  return s.cost_status === 'none' ? g : `${g} · ${money(s.wasted_cost)}${s.cost_status === 'partial' ? '+' : ''}`
}

function Periods({ periods, setMonth }) {
  const list = periods.available
  const i = list.indexOf(periods.selected)
  const older = i >= 0 && i < list.length - 1 ? list[i + 1] : null
  const newer = i > 0 ? list[i - 1] : null
  const m = periods.month_stats, y = periods.year_stats

  const rows = [
    ['Filament used', `${grams(m.grams)} g`, `${grams(y.grams)} g`],
    ['Cost', periodCost(m), periodCost(y)],
    ['Prints', m.prints, y.prints],
    ['Success rate', m.success_rate == null ? '—' : `${m.success_rate}%`,
      y.success_rate == null ? '—' : `${y.success_rate}%`],
    ['Lost to failures', periodWaste(m), periodWaste(y)],
    ['Average per print', m.avg_g == null ? '—' : `${grams(m.avg_g)} g`,
      y.avg_g == null ? '—' : `${grams(y.avg_g)} g`],
  ]

  return (
    <div>
      <div className="row" style={{ marginBottom: 8 }}>
        <button className="btn ghost small" disabled={!older} onClick={() => setMonth(older)}>‹</button>
        <b style={{ minWidth: 130, textAlign: 'center' }}>{periods.selected_label}</b>
        <button className="btn ghost small" disabled={!newer} onClick={() => setMonth(newer)}>›</button>
        {!periods.is_current_month && (
          <button className="linklike" onClick={() => setMonth(null)}>back to this month</button>
        )}
      </div>
      <table className="period-table">
        <thead>
          <tr><th></th><th className="num">{periods.selected_label}</th><th className="num">{periods.year}</th></tr>
        </thead>
        <tbody>
          {rows.map(([label, mv, yv]) => (
            <tr key={label}><td>{label}</td><td className="num">{mv}</td><td className="num">{yv}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Row({ icon, title, sub, action, onClick }) {
  return (
    <div className="dash-row" onClick={onClick}>
      <span className="dash-row-icon">{icon}</span>
      <div style={{ minWidth: 0 }}>
        <div>{title}</div>
        <div className="muted" style={{ fontSize: 13 }}>{sub}</div>
      </div>
      <span className="spacer" />
      <button className="btn small">{action}</button>
    </div>
  )
}

function Tile({ big, lbl, onClick }) {
  return (
    <div className="stat dash-tile" onClick={onClick}>
      <div className="big">{big}</div>
      <div className="lbl">{lbl}</div>
    </div>
  )
}
