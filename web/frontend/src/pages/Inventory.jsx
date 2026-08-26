import { useEffect, useState } from 'react'
import { api, money, grams, CURRENCY } from '../api.js'
import Modal from '../components/Modal.jsx'
import SpoolIcon from '../components/SpoolIcon.jsx'

function barClass(pct) {
  if (pct < 10) return 'bar low'
  if (pct < 40) return 'bar mid'
  return 'bar'
}

function statePill(item) {
  if (item.reorder_status === 'ordered') return <span className="pill ordered">on order</span>
  if (item.reorder_status === 'ignored') return <span className="pill ignored">ignored</span>
  if (item.state === 'out') return <span className="pill low">OUT — reorder</span>
  if (item.state === 'low') return <span className="pill low">low — reorder</span>
  if (item.state === 'switch') return <span className="pill switch">switch roll soon</span>
  return null
}

export default function Inventory({ inv, reload }) {
  const [open, setOpen] = useState({})
  const [formSpool, setFormSpool] = useState(undefined) // undefined=closed, null=add, obj=edit
  const [weighSpool, setWeighSpool] = useState(null)
  const [err, setErr] = useState('')

  if (!inv) return <p className="muted">Loading…</p>

  async function act(fn) {
    setErr('')
    try { await fn(); await reload() } catch (e) { setErr(e.message) }
  }

  const totalValue = inv.items.reduce((a, i) => a + (i.value || 0), 0)

  return (
    <div>
      <div className="row" style={{ marginBottom: 12 }}>
        {totalValue > 0 && <span className="muted">{money(totalValue)} on hand</span>}
        <span className="spacer" />
        <button className="btn" onClick={() => setFormSpool(null)}>+ Add spool</button>
      </div>
      {err && <div className="error">{err}</div>}

      {inv.items.length === 0 && <div className="panel muted">No spools yet — add one to get started.</div>}

      {inv.items.map((item) => (
        <div className="inv-item" key={item.type_id}>
          <div className="inv-head" onClick={() => setOpen((o) => ({ ...o, [item.type_id]: !o[item.type_id] }))}>
            <SpoolIcon color={item.color} />
            <div style={{ minWidth: 0 }}>
              <div className="inv-title">{item.label}</div>
              <div className="inv-sub">
                {item.roll_count} roll{item.roll_count === 1 ? '' : 's'}
                {item.roll_count > 1 && ` · ${item.total_estimated ? '~' : ''}${grams(item.total_remaining)} g total`}
                {item.value > 0 && ` · ${money(item.value)}`}
              </div>
            </div>
            <span className="spacer" />
            {statePill(item)}
            {item.current_estimated && <span className="pill est" title="estimated weight">~est</span>}
            <div className={barClass(item.current_pct)}><div style={{ width: `${Math.min(100, item.current_pct)}%` }} /></div>
            <div className="weight">{item.current_estimated ? '~' : ''}{grams(item.current_g)} g</div>
          </div>

          {open[item.type_id] && (
            <div className="inv-rolls">
              {item.rolls.map((r) => (
                <div className="roll" key={r.id}>
                  <span className="muted">#{r.id}</span>
                  <span>{r.is_empty ? <span className="muted">empty</span> : `${r.estimated ? '~' : ''}${grams(r.remaining_g)} g (${r.percent_left}%)`}</span>
                  {r.price > 0 && <span className="muted" title="price per full roll">{money(r.price)}/roll</span>}
                  <span className="spacer" />
                  <button className="btn small ghost" onClick={() => setWeighSpool(r)}>Weigh</button>
                  <button className="btn small ghost" onClick={() => act(() => api.patchSpool(r.id, { action: 'refill' }))}>Refill</button>
                  {!r.is_empty && <button className="btn small ghost" onClick={() => act(() => api.patchSpool(r.id, { action: 'run_out' }))}>Run out</button>}
                  <button className="btn small ghost" onClick={() => setFormSpool(r)}>Edit</button>
                  <button className="btn small danger" onClick={() => { if (confirm(`Remove spool #${r.id} ${item.label}?`)) act(() => api.deleteSpool(r.id)) }}>✕</button>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}

      {formSpool !== undefined && (
        <SpoolForm spool={formSpool} onClose={() => setFormSpool(undefined)}
          onSaved={() => { setFormSpool(undefined); reload() }} />
      )}
      {weighSpool && (
        <WeighModal spool={weighSpool} onClose={() => setWeighSpool(null)}
          onSaved={() => { setWeighSpool(null); reload() }} />
      )}
    </div>
  )
}

function SpoolForm({ spool, onClose, onSaved }) {
  const editing = !!spool
  const [opts, setOpts] = useState({ brands: [], materials: [], colors: [] })
  const [f, setF] = useState({
    brand: spool?.brand || '', material: spool?.material || '', color: spool?.color || '',
    total_g: spool?.total_g || 1000, full: true, remaining_g: '',
    price: spool?.price ? String(spool.price) : '', notes: spool?.notes || '',
  })
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => { api.options().then(setOpts).catch(() => {}) }, [])
  const set = (k) => (e) => setF((s) => ({ ...s, [k]: e.target.value }))

  async function save(e) {
    e.preventDefault()
    setBusy(true); setErr('')
    try {
      const price = Number(f.price || 0)
      if (editing) {
        await api.patchSpool(spool.id, { action: 'edit', brand: f.brand, material: f.material, color: f.color, notes: f.notes, price })
      } else {
        await api.addSpool({
          brand: f.brand, material: f.material, color: f.color,
          total_g: Number(f.total_g), full: f.full,
          remaining_g: f.full ? Number(f.total_g) : Number(f.remaining_g || 0), notes: f.notes, price,
        })
      }
      onSaved()
    } catch (e2) { setErr(e2.message) } finally { setBusy(false) }
  }

  return (
    <Modal title={editing ? `Edit spool #${spool.id}` : 'Add spool'} onClose={onClose}>
      <form onSubmit={save}>
        <datalist id="brands">{opts.brands.map((b) => <option key={b} value={b} />)}</datalist>
        <datalist id="materials">{opts.materials.map((b) => <option key={b} value={b} />)}</datalist>
        <datalist id="colors">{opts.colors.map((b) => <option key={b} value={b} />)}</datalist>
        <div className="inline-fields">
          <label className="field"><span>Brand</span><input list="brands" value={f.brand} onChange={set('brand')} required /></label>
          <label className="field"><span>Material</span><input list="materials" value={f.material} onChange={set('material')} required /></label>
        </div>
        <label className="field"><span>Colour</span><input list="colors" value={f.color} onChange={set('color')} required /></label>
        <label className="field"><span>Price for a full roll ({CURRENCY}, optional)</span>
          <input type="number" min="0" step="0.01" value={f.price} onChange={set('price')} placeholder="e.g. 18.99" />
          <span className="muted" style={{ fontSize: 12 }}>Used to work out cost per print.</span></label>
        {!editing && (
          <>
            <label className="field"><span>Full filament weight (g)</span>
              <input type="number" min="1" step="0.01" value={f.total_g} onChange={set('total_g')} required /></label>
            <label className="checkbox" style={{ marginBottom: 12 }}>
              <input type="checkbox" checked={f.full} onChange={(e) => setF((s) => ({ ...s, full: e.target.checked }))} />
              <span>Brand-new / full roll</span>
            </label>
            {!f.full && (
              <label className="field"><span>Estimated grams remaining now</span>
                <input type="number" min="0" step="0.01" value={f.remaining_g} onChange={set('remaining_g')} required />
                <span className="muted" style={{ fontSize: 12 }}>Marked as estimated until you weigh it.</span></label>
            )}
          </>
        )}
        <label className="field"><span>Notes (optional)</span><textarea rows="2" value={f.notes} onChange={set('notes')} /></label>
        {err && <div className="error">{err}</div>}
        <div className="row">
          <button className="btn" disabled={busy}>{busy ? 'Saving…' : 'Save'}</button>
          <button type="button" className="btn ghost" onClick={onClose}>Cancel</button>
        </div>
      </form>
    </Modal>
  )
}

function WeighModal({ spool, onClose, onSaved }) {
  const [remaining, setRemaining] = useState(spool.remaining_g)
  const [measured, setMeasured] = useState(true)
  const [err, setErr] = useState('')

  async function save(e) {
    e.preventDefault()
    setErr('')
    try {
      await api.patchSpool(spool.id, { action: 'set_remaining', remaining_g: Number(remaining), measured })
      onSaved()
    } catch (e2) { setErr(e2.message) }
  }

  return (
    <Modal title={`Weigh / set remaining — #${spool.id}`} onClose={onClose}>
      <form onSubmit={save}>
        <label className="field"><span>Filament remaining (g) of {grams(spool.total_g)} g</span>
          <input type="number" min="0" max={spool.total_g} step="0.01" autoFocus value={remaining} onChange={(e) => setRemaining(e.target.value)} /></label>
        <label className="checkbox" style={{ marginBottom: 12 }}>
          <input type="checkbox" checked={measured} onChange={(e) => setMeasured(e.target.checked)} />
          <span>This is a measured weight (clears the “estimated” flag)</span>
        </label>
        {err && <div className="error">{err}</div>}
        <div className="row">
          <button className="btn">Save</button>
          <button type="button" className="btn ghost" onClick={onClose}>Cancel</button>
        </div>
      </form>
    </Modal>
  )
}
