import { useState } from 'react'
import { api } from '../api.js'

export default function Login({ onSuccess }) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await api.login(password)
      onSuccess()
    } catch (err) {
      setError(err.message || 'Login failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="app">
      <div className="login-wrap panel">
        <h2>Filament Tracker</h2>
        <p className="muted">This tracker is password protected.</p>
        <form onSubmit={submit}>
          <label className="field">
            <span>Password</span>
            <input type="password" autoFocus value={password}
              onChange={(e) => setPassword(e.target.value)} />
          </label>
          {error && <div className="error">{error}</div>}
          <button className="btn" disabled={busy || !password}>
            {busy ? 'Checking…' : 'Log in'}
          </button>
        </form>
      </div>
    </div>
  )
}
