import { useEffect, useState, useCallback } from 'react'
import { api } from './api.js'
import Login from './components/Login.jsx'
import Inventory from './pages/Inventory.jsx'
import LogPrint from './pages/LogPrint.jsx'
import History from './pages/History.jsx'
import Stats from './pages/Stats.jsx'
import Reorder from './pages/Reorder.jsx'
import Settings from './pages/Settings.jsx'
import ResolveModal from './pages/ResolveModal.jsx'

const TABS = [
  ['inventory', 'Inventory'],
  ['log', 'Log print'],
  ['history', 'History'],
  ['stats', 'Stats'],
  ['reorder', 'Reorder'],
  ['settings', 'Settings'],
]

export default function App() {
  const [auth, setAuth] = useState({ loading: true, enabled: false, authed: false })
  const [view, setView] = useState('inventory')
  const [inv, setInv] = useState(null)
  const [resolveTarget, setResolveTarget] = useState(null)

  const loadInv = useCallback(async () => {
    try {
      setInv(await api.inventory())
    } catch (err) {
      if (err.auth) setAuth((a) => ({ ...a, authed: false }))
    }
  }, [])

  const checkAuth = useCallback(async () => {
    const s = await api.authStatus()
    setAuth({ loading: false, enabled: s.auth_enabled, authed: !s.auth_enabled || s.authenticated })
  }, [])

  useEffect(() => { checkAuth() }, [checkAuth])
  useEffect(() => { if (auth.authed) loadInv() }, [auth.authed, loadInv])

  if (auth.loading) return <div className="app"><p className="muted" style={{ marginTop: 40 }}>Loading…</p></div>
  if (auth.enabled && !auth.authed) {
    return <Login onSuccess={() => setAuth((a) => ({ ...a, authed: true }))} />
  }

  const spools = inv ? inv.items.flatMap((it) => it.rolls).filter((r) => !r.is_empty) : []

  async function logout() {
    await api.logout()
    setAuth((a) => ({ ...a, authed: !a.enabled }))
  }

  return (
    <div className="app">
      <header className="top">
        <h1><span>◆</span> Filament Tracker</h1>
        <nav>
          {TABS.map(([id, label]) => (
            <button key={id} className={view === id ? 'active' : ''} onClick={() => setView(id)}>
              {label}
            </button>
          ))}
          {auth.enabled && auth.authed && (
            <button onClick={logout} title="Log out">Log out</button>
          )}
        </nav>
      </header>

      {inv && <Alerts inv={inv} onResolve={setResolveTarget} onGoReorder={() => setView('reorder')} />}

      {view === 'inventory' && <Inventory inv={inv} reload={loadInv} />}
      {view === 'log' && <LogPrint spools={spools} reload={loadInv} onDone={() => setView('inventory')} />}
      {view === 'history' && <History reload={loadInv} />}
      {view === 'stats' && <Stats />}
      {view === 'reorder' && <Reorder reload={loadInv} />}
      {view === 'settings' && <Settings auth={auth} refreshAuth={checkAuth} />}

      {resolveTarget && (
        <ResolveModal
          print={resolveTarget}
          onClose={() => setResolveTarget(null)}
          onDone={() => { setResolveTarget(null); loadInv() }}
        />
      )}
    </div>
  )
}

function Alerts({ inv, onResolve, onGoReorder }) {
  const wip = inv.in_progress || []
  const low = inv.low_stock || []
  if (!wip.length && !low.length) return null
  return (
    <>
      {wip.length > 0 && (
        <div className="banner red">
          <b>{wip.length} print{wip.length > 1 ? 's' : ''} in progress — don’t forget to finish {wip.length > 1 ? 'them' : 'it'}</b>
          {wip.map((p) => (
            <div className="line" key={p.id}>
              <span>#{p.id} {p.name} <span className="muted">(started {p.date})</span></span>
              <span className="spacer" />
              <button className="btn small" onClick={() => onResolve(p)}>Resolve</button>
            </div>
          ))}
        </div>
      )}
      {low.length > 0 && (
        <div className="banner yellow">
          <b>{low.length} filament{low.length > 1 ? 's' : ''} running low</b>
          {low.map((t) => (
            <div className="line" key={t.type_id}>
              <span>{t.label} — {t.state === 'needs' && t.current_pct === 0 ? 'OUT' : `${t.current_pct}%`}</span>
              <span className="spacer" />
              <button className="btn small ghost" onClick={onGoReorder}>Reorder</button>
            </div>
          ))}
        </div>
      )}
    </>
  )
}
