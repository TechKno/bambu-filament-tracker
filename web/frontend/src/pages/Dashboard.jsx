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

export default function Dashboard({ data, go }) {
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
        <div className="stat-grid">
          <Tile big={data.totals.spools} lbl="spools in stock" onClick={() => go('inventory')} />
          <Tile big={money(data.totals.inventory_value)} lbl="filament value" onClick={() => go('inventory')} />
          <Tile big={`${grams(data.totals.month_grams)} g`} lbl={`used in ${data.totals.month_label}`} onClick={() => go('stats')} />
          <Tile big={data.totals.prints} lbl="prints logged" onClick={() => go('history')} />
          <Tile big={data.totals.success_rate == null ? '—' : `${data.totals.success_rate}%`} lbl="success rate" onClick={() => go('stats')} />
          <Tile big={money(data.totals.cost_total)} lbl="spent on prints" onClick={() => go('stats')} />
        </div>
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
            {p.weight_g ? ` · ${grams(p.weight_g)} g planned` : ''}
            {p.remaining_min ? ` · ${fmtEta(p.remaining_min)} left` : ''}
          </div>
          <div className={`bar${paused ? ' mid' : ''}`} style={{ maxWidth: 'none', marginTop: 8 }}>
            <div style={{ width: `${pct}%` }} />
          </div>
          <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>{pct}% complete</div>
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
