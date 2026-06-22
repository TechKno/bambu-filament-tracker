import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function Settings({ auth, refreshAuth }) {
  const [s, setS] = useState(null)
  const [password, setPassword] = useState('')
  const [enabled, setEnabled] = useState(false)
  const [err, setErr] = useState('')
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.getSettings().then((d) => { setS(d); setEnabled(d.auth_enabled) }).catch((e) => setErr(e.message))
  }, [])

  async function save(e) {
    e.preventDefault()
    setErr(''); setMsg(''); setBusy(true)
    try {
      const payload = { auth_enabled: enabled }
      if (password) payload.password = password
      const res = await api.putSettings(payload)
      setS(res); setPassword(''); setMsg('Settings saved.')
      await refreshAuth()
    } catch (e2) { setErr(e2.message) } finally { setBusy(false) }
  }

  if (!s) return <p className="muted">{err || 'Loading…'}</p>

  return (
    <div className="panel" style={{ maxWidth: 520 }}>
      <h2>Settings</h2>
      <form onSubmit={save}>
        <label className="checkbox" style={{ marginBottom: 14 }}>
          <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
          <span>Require a password to use this app</span>
        </label>

        <label className="field">
          <span>{s.has_password ? 'Set a new password (leave blank to keep current)' : 'Password'}</span>
          <input type="password" value={password} placeholder={s.has_password ? '••••••••' : ''}
            onChange={(e) => setPassword(e.target.value)} />
          {enabled && !s.has_password && !password && (
            <span className="muted" style={{ fontSize: 12 }}>Set a password before enabling login.</span>
          )}
        </label>

        {err && <div className="error">{err}</div>}
        {msg && <div className="success">{msg}</div>}
        <button className="btn" disabled={busy}>{busy ? 'Saving…' : 'Save settings'}</button>
      </form>

      <hr style={{ border: 'none', borderTop: '1px solid var(--border)', margin: '20px 0' }} />
      <p className="muted" style={{ fontSize: 13 }}>
        Login is currently <b>{auth.enabled ? 'on' : 'off'}</b>. When off, anyone who can reach this
        page on your network can use it — keep it on your trusted LAN and don’t forward the port to
        the internet. Data and rolling backups live in the mounted <code>data/</code> volume.
      </p>
    </div>
  )
}
