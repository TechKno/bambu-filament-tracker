import { useEffect, useState } from 'react'
import { api } from '../api.js'

const blank = { name: '', ip: '', serial: '', _code: '' }

export default function Printers() {
  const [rows, setRows] = useState(null)
  const [writable, setWritable] = useState(true)
  const [err, setErr] = useState('')
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  const load = () => api.printers()
    .then((d) => { setRows(d.printers.map((p) => ({ ...p, _code: '' }))); setWritable(d.codes_writable) })
    .catch((e) => setErr(e.message))
  useEffect(() => { load() }, [])

  const set = (i, k, v) => setRows((rs) => rs.map((r, j) => (j === i ? { ...r, [k]: v } : r)))

  async function save() {
    setBusy(true); setErr(''); setMsg('')
    try {
      const codes = {}
      rows.forEach((r) => { if (r._code) codes[r.serial] = r._code })
      const res = await api.savePrinters({
        printers: rows.map(({ name, ip, serial }) => ({ name, ip, serial })), codes,
      })
      setMsg(res.code_error ? res.code_error : 'Saved. The listener picks up changes within 30 seconds.')
      await load()
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  if (!rows) return <p className="muted">{err || 'Loading…'}</p>

  return (
    <div className="panel">
      <div className="row" style={{ marginBottom: 6 }}>
        <span className="muted">monitored over local MQTT</span>
        <span className="spacer" />
        <button className="btn ghost small" onClick={() => setRows([...rows, { ...blank }])}>+ Add printer</button>
      </div>
      <p className="muted" style={{ fontSize: 13, marginTop: 0 }}>
        The access code is on the printer under <b>Settings → WLAN → Access Code</b>. It is stored on the
        server and never shown again.
      </p>

      {rows.length === 0 && <p className="muted">No printers configured.</p>}

      {rows.map((r, i) => (
        <div key={i} className="printer-row">
          <div className="row" style={{ marginBottom: 8 }}>
            <span className="dot" style={{ background: r.connected ? 'var(--ok)' : 'var(--mu)' }} />
            <b>{r.name || 'New printer'}</b>
            <span className="muted" style={{ fontSize: 13 }}>
              {r.connected ? `connected · ${(r.gcode_state || '').toLowerCase()}` : 'not connected'}
              {r.serial && (r.has_code ? ' · code set' : ' · no access code')}
            </span>
            <span className="spacer" />
            <button className="btn danger small"
              onClick={() => setRows(rows.filter((_, j) => j !== i))}>Remove</button>
          </div>
          <div className="printer-fields">
            <label className="field"><span>Name</span>
              <input value={r.name} onChange={(e) => set(i, 'name', e.target.value)} placeholder="P1S" /></label>
            <label className="field"><span>IP address</span>
              <input value={r.ip} onChange={(e) => set(i, 'ip', e.target.value)} placeholder="192.168.1.100" /></label>
            <label className="field"><span>Serial</span>
              <input value={r.serial} onChange={(e) => set(i, 'serial', e.target.value)} placeholder="01P00C…" /></label>
            <label className="field"><span>{r.has_code ? 'New access code (optional)' : 'Access code'}</span>
              <input type="password" value={r._code} onChange={(e) => set(i, '_code', e.target.value)}
                placeholder={r.has_code ? '••••••••' : ''} disabled={!writable} /></label>
          </div>
        </div>
      ))}

      {!writable && (
        <div className="muted" style={{ fontSize: 13 }}>
          Access codes can't be saved from here (the secrets folder is read-only). Add them on the
          server in <code>secrets/printer_codes.env</code> as <code>SERIAL=code</code>.
        </div>
      )}
      {err && <div className="error">{err}</div>}
      {msg && <div className="success">{msg}</div>}
      <button className="btn" disabled={busy} onClick={save}>{busy ? 'Saving…' : 'Save printers'}</button>
    </div>
  )
}
