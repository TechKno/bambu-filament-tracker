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

const Preview = ({ src, className, label = 'preview' }) =>
  src ? <img className={`preview ${className}`} src={thumbUrl(src)} alt="" loading="lazy" />
      : <div className={`preview ${className}`}>{label}</div>

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
        <div className="card allclear">
          <div className="mark">✓</div>
          <div>
            <b>All clear</b>
            <div className="muted" style={{ fontSize: 13, marginTop: 2 }}>
              Nothing printing, nothing to confirm, no filament running low.
              {idle.length > 0 && ` ${idle.map((p) => p.name).join(', ')} idle.`}
            </div>
          </div>
        </div>
      )}

      <div className="grid-2">
        <div>
          {actions > 0 && (
            <div className="card">
              <h2 className="sec-head">Needs you</h2>
              {data.pending_count > 0 && (
                <div className="arow" onClick={() => go('pending')}>
                  <span className="count-chip">{data.pending_count}</span>
                  <div style={{ minWidth: 0 }}>
                    <div className="arow-t">
                      {data.pending_count} finished print{data.pending_count > 1 ? 's' : ''} to confirm
                    </div>
                    <div className="arow-s">Spool and grams pre-filled — check and log.</div>
                  </div>
                  <span className="spacer" />
                  <button className="btn small">Review</button>
                </div>
              )}
              {(data.loads || []).map((l) => (
                <div className="arow" key={l.id} onClick={() => go('pending')}>
                  <SpoolIcon color={l.color || l.type} size={26} />
                  <div style={{ minWidth: 0 }}>
                    <div className="arow-t">
                      Filament loaded in {l.external ? 'the external spool' : `AMS ${(l.ams ?? 0) + 1} · slot ${(l.tray ?? 0) + 1}`}
                    </div>
                    <div className="arow-s">{l.type || 'Unknown'} — tell it which spool this is</div>
                  </div>
                  <span className="spacer" />
                  <button className="btn small">Assign</button>
                </div>
              ))}
              {(data.in_progress || []).map((j) => (
                <div className="arow" key={j.id} onClick={() => go('history')}>
                  <span className="count-chip">⏳</span>
                  <div style={{ minWidth: 0 }}>
                    <div className="arow-t">“{j.name}” still marked in progress</div>
                    <div className="arow-s">Started {j.date} — resolve it to deduct the filament</div>
                  </div>
                  <span className="spacer" />
                  <button className="btn small">Resolve</button>
                </div>
              ))}
            </div>
          )}

          <div className="card">
            <h2 className="sec-head">At a glance</h2>
            <div className="tiles">
              <Tile v={data.now.spools} l="spools in stock" onClick={() => go('inventory')} />
              <Tile v={money(data.now.inventory_value)} l="filament value" onClick={() => go('inventory')} />
              <Tile v={data.now.prints_all_time} l="prints all time" onClick={() => go('history')} />
            </div>
          </div>

          <div className="card">
            <Periods periods={data.periods} setMonth={setMonth} />
          </div>
        </div>

        <div>
          {data.needs_reorder?.length > 0 && (
            <div className="card">
              <h2 className="sec-head">Running low</h2>
              {data.needs_reorder.map((r) => (
                <div className="arow" key={r.type_id} onClick={() => go('reorder')}>
                  <SpoolIcon color={r.color} size={26} />
                  <div style={{ minWidth: 0 }}>
                    <div className="arow-t">{r.label}</div>
                    <div className="arow-s mono" style={{ color: 'var(--warn)' }}>
                      {r.current_pct === 0 ? 'Out of stock' : `${grams(r.current_g)} g left · ${r.current_pct}%`}
                    </div>
                  </div>
                  <span className="spacer" />
                  <button className="btn ghost small">Reorder</button>
                </div>
              ))}
            </div>
          )}

          {data.forecast?.length > 0 && (
            <div className="card">
              <h2 className="sec-head">Running out next</h2>
              {data.forecast.map((f) => (
                <div className="arow" key={f.label} style={{ cursor: 'default', minHeight: 48 }}>
                  <SpoolIcon color={f.color} size={20} />
                  <div style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    <span style={{ fontSize: 13.5 }}>{f.label}</span>
                  </div>
                  <span className="spacer" />
                  <span className="mono muted" style={{ fontSize: 12 }}>{f.rate_g_per_week} g/wk</span>
                  <span className={`pill ${f.days_left < 28 ? 'warn' : ''}`}>
                    {f.days_left < 14 ? `~${f.days_left} days` : `~${Math.round(f.days_left / 7)} weeks`}
                  </span>
                </div>
              ))}
            </div>
          )}

          {data.recent?.length > 0 && (
            <div className="card">
              <div className="row-line" style={{ marginBottom: 10 }}>
                <h2 className="sec-head" style={{ margin: 0 }}>Recent prints</h2>
                <span className="spacer" />
                <button className="linklike" onClick={() => go('history')}>All history</button>
              </div>
              <div className="recent">
                {data.recent.map((r) => (
                  <div className="cell" key={r.id} title={r.name}>
                    <Preview src={r.thumbnail} className="" label="no image" />
                    <div className="name">{r.name}</div>
                    <div className="meta">
                      {grams(r.total_g)} g{r.cost_status !== 'none' ? ` · ${money(r.cost)}` : ''}
                      {r.status === 'failed' && ' · failed'}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function ActivePrint({ p }) {
  const paused = p.gcode_state === 'PAUSE'
  const pct = Math.min(100, p.percent ?? 0)
  const shortfalls = (p.projection || []).filter((x) => !x.enough)
  const hasVerdict = (p.projection || []).length > 0

  return (
    <div className="card hero">
      <div className="hero-body">
        <Preview src={p.thumbnail} className="hero" label="model preview" />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="row-line" style={{ gap: 8 }}>
            <span className={`dot ${paused ? 'warn' : 'live'}`} />
            <b style={{ color: paused ? 'var(--warn)' : 'var(--ok)', fontSize: 13.5 }}>
              {paused ? 'Paused' : 'Printing'}
            </b>
            <span className="muted" style={{ fontSize: 13 }}>on {p.name}</span>
            <span className="spacer" />
            <span className="mono muted" style={{ fontSize: 11.5 }}>live · {p.updated_at?.slice(11)}</span>
          </div>

          <div className="hero-name">{p.model || 'Print'}</div>

          <div className={`bar tall ${paused ? 'warn' : 'ok'}`}>
            <div style={{ width: `${pct}%` }} />
          </div>

          <div className="hero-meta">
            <span><b>{pct}%</b></span>
            {p.layer != null && p.total_layers ? <span>layer {p.layer} of {p.total_layers}</span> : null}
            {p.weight_g ? <span>{grams(p.weight_g)} g planned</span> : null}
            <span>{p.cost != null ? `${money(p.cost)}${p.cost_status === 'partial' ? '+' : ''}` : 'cost —'}</span>
          </div>
          <div className="hero-meta">
            {p.remaining_min > 0 ? (
              <span>
                <b>Finishes ~{finishTime(p.remaining_min)}{paused ? ' (if resumed)' : ''}</b>
                {' · '}{fmtEta(p.remaining_min)} left
              </span>
            ) : p.remaining_min === 0 && !paused ? <span><b>Finishing now</b></span> : null}
          </div>
        </div>
      </div>

      {hasVerdict && (
        <div className={`verdict ${shortfalls.length ? 'bad' : 'ok'}`}>
          <b>
            {shortfalls.length
              ? '! May run out before this finishes'
              : '✓ Enough filament to finish'}
          </b>
          {(shortfalls.length ? shortfalls : p.projection).map((s) => (
            <div className="verdict-detail" key={s.slot_key}>
              <SpoolIcon color={s.color} size={18} />
              <span>
                {s.label}: needs ~{grams(s.needed_g)} g, {grams(s.remaining_g)} g left
                {!s.enough && <b style={{ color: 'var(--bad)' }}> — short ~{grams(s.short_by)} g</b>}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

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
      <div className="row-line" style={{ marginBottom: 10 }}>
        <h2 className="sec-head" style={{ margin: 0 }}>This month vs year</h2>
        <span className="spacer" />
        <div className="pager">
          <button className="btn ghost small" disabled={!older} onClick={() => setMonth(older)}>‹</button>
          <span className="label">{periods.selected_label}</span>
          <button className="btn ghost small" disabled={!newer} onClick={() => setMonth(newer)}>›</button>
        </div>
      </div>
      {!periods.is_current_month && (
        <button className="linklike" style={{ marginBottom: 6 }} onClick={() => setMonth(null)}>
          back to this month
        </button>
      )}
      <div className="ptable">
        <div style={{ color: 'var(--mu)' }} />
        <div>{periods.selected_label}</div>
        <div>{periods.year}</div>
        {rows.map(([label, mv, yv]) => (
          <Row3 key={label} a={label} b={mv} c={yv} />
        ))}
      </div>
    </div>
  )
}

const Row3 = ({ a, b, c }) => <><div>{a}</div><div>{b}</div><div>{c}</div></>

function Tile({ v, l, onClick }) {
  return (
    <div className={`tile${onClick ? ' click' : ''}`} onClick={onClick}>
      <div className="v">{v}</div>
      <div className="l">{l}</div>
    </div>
  )
}
