import { useEffect, useState, useCallback, useRef } from 'react'
import { api } from './api.js'
import Login from './components/Login.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Inventory from './pages/Inventory.jsx'
import Pending from './pages/Pending.jsx'
import LogPrint from './pages/LogPrint.jsx'
import History from './pages/History.jsx'
import Stats from './pages/Stats.jsx'
import Reorder from './pages/Reorder.jsx'
import Settings from './pages/Settings.jsx'
import Printers from './pages/Printers.jsx'
import ResolveModal from './pages/ResolveModal.jsx'

// Primary group appears in the mobile tab bar; the rest live behind "More".
const PRIMARY = [['dashboard', 'Dashboard'], ['pending', 'Pending'], ['inventory', 'Inventory']]
const SECONDARY = [['history', 'History'], ['stats', 'Stats'], ['log', 'Log print']]
const TERTIARY = [['reorder', 'Reorder'], ['printers', 'Printers'], ['settings', 'Settings']]
const TITLES = Object.fromEntries([...PRIMARY, ...SECONDARY, ...TERTIARY])
const VIEWS = Object.keys(TITLES)

// Views live in the URL hash, so screens are linkable and the browser's back
// button works. Anything unrecognised falls back to the dashboard.
const viewFromHash = () => {
  const v = decodeURIComponent((window.location.hash || '').replace(/^#\/?/, ''))
  return VIEWS.includes(v) ? v : 'dashboard'
}

function useTheme() {
  const [theme, setTheme] = useState(() => {
    try { return localStorage.getItem('ft-theme') || 'dark' } catch { return 'dark' }
  })
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    try { localStorage.setItem('ft-theme', theme) } catch { /* private mode */ }
  }, [theme])
  return [theme, setTheme]
}

export default function App() {
  const [auth, setAuth] = useState({ loading: true, enabled: false, authed: false })
  const [view, setViewState] = useState(viewFromHash)
  const [inv, setInv] = useState(null)
  const [pend, setPend] = useState({ pending: [], status: {} })
  const [dash, setDash] = useState(null)
  const [month, setMonth] = useState(null)     // null = current month
  const [resolveTarget, setResolveTarget] = useState(null)
  const [moreOpen, setMoreOpen] = useState(false)
  const [theme, setTheme] = useTheme()

  const loadInv = useCallback(async () => {
    try { setInv(await api.inventory()) }
    catch (err) { if (err.auth) setAuth((a) => ({ ...a, authed: false })) }
  }, [])

  // Kept separate: loadPending is month-independent (stable identity), so the
  // poll interval below is created once; only loadDash re-keys on the month.
  const loadPending = useCallback(async () => {
    try { setPend(await api.pending()) }
    catch (err) { if (err.auth) setAuth((a) => ({ ...a, authed: false })) }
  }, [])

  const loadDash = useCallback(async () => {
    try { setDash(await api.dashboard(month)) }
    catch (err) { if (err.auth) setAuth((a) => ({ ...a, authed: false })) }
  }, [month])

  // Keep state and hash in step, in both directions.
  const setView = useCallback((v) => {
    setViewState(v)
    if (viewFromHash() !== v) window.location.hash = v
  }, [])
  useEffect(() => {
    const onHash = () => setViewState(viewFromHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const checkAuth = useCallback(async () => {
    const s = await api.authStatus()
    setAuth({ loading: false, enabled: s.auth_enabled, authed: !s.auth_enabled || s.authenticated })
  }, [])

  useEffect(() => { checkAuth() }, [checkAuth])
  useEffect(() => { if (auth.authed) { loadInv(); loadPending() } }, [auth.authed, loadInv, loadPending])
  useEffect(() => { if (auth.authed) loadDash() }, [auth.authed, loadDash])

  // The interval reads the latest loaders through a ref, so it is created once
  // per session instead of being torn down whenever a dependency changes.
  const tickRef = useRef(() => {})
  useEffect(() => { tickRef.current = () => { loadPending(); loadDash() } }, [loadPending, loadDash])
  useEffect(() => {
    if (!auth.authed) return
    const refresh = () => { if (document.visibilityState === 'visible') tickRef.current() }
    const t = setInterval(refresh, 5000)
    document.addEventListener('visibilitychange', refresh)
    window.addEventListener('focus', refresh)
    return () => {
      clearInterval(t)
      document.removeEventListener('visibilitychange', refresh)
      window.removeEventListener('focus', refresh)
    }
  }, [auth.authed])

  if (auth.loading) return <div className="main"><p className="muted">Loading…</p></div>
  if (auth.enabled && !auth.authed) {
    return <Login onSuccess={() => setAuth((a) => ({ ...a, authed: true }))} />
  }

  const spools = inv ? inv.items.flatMap((it) => it.rolls).filter((r) => !r.is_empty) : []
  const nPrints = pend.pending?.length || 0
  const nLoads = pend.loads?.length || 0
  const pendCount = nPrints + nLoads
  const reloadAll = () => { loadInv(); loadPending(); loadDash() }
  const go = (v) => { setView(v); setMoreOpen(false) }

  async function logout() {
    await api.logout()
    setAuth((a) => ({ ...a, authed: !a.enabled }))
  }

  const NavBtn = ([id, label]) => (
    <button key={id} className={`nav-item${view === id ? ' active' : ''}`} onClick={() => go(id)}>
      {label}
      {id === 'pending' && pendCount > 0 && <span className="badge">{pendCount}</span>}
    </button>
  )

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-dot" /> Filament Tracker</div>
        {PRIMARY.map(NavBtn)}
        {SECONDARY.map(NavBtn)}
        <div className="nav-sep" />
        {TERTIARY.map(NavBtn)}
        <div className="nav-sep" />
        <button className="nav-item" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
          {theme === 'dark' ? 'Light theme' : 'Dark theme'}
        </button>
        {auth.enabled && auth.authed && <button className="nav-item" onClick={logout}>Log out</button>}
      </aside>

      <main className="main">
        <div className="page-head">
          <h1 className="page-title">{TITLES[view] || 'Filament Tracker'}</h1>
        </div>

        {view === 'dashboard' && <Dashboard data={dash} go={go} setMonth={setMonth} />}
        {view === 'inventory' && <Inventory inv={inv} reload={loadInv} />}
        {view === 'pending' && <Pending pending={pend.pending} loads={pend.loads} spools={spools} reload={reloadAll} />}
        {view === 'log' && <LogPrint spools={spools} reload={reloadAll} onDone={() => go('dashboard')} />}
        {view === 'history' && <History reload={reloadAll} />}
        {view === 'stats' && <Stats />}
        {view === 'reorder' && <Reorder reload={reloadAll} />}
        {view === 'printers' && <Printers />}
        {view === 'settings' && <Settings auth={auth} refreshAuth={checkAuth} theme={theme} setTheme={setTheme} />}

        {inv && view !== 'dashboard' && (
          <Alerts inv={inv} onResolve={setResolveTarget} onGoReorder={() => go('reorder')} />
        )}
      </main>

      <nav className="tabbar">
        {PRIMARY.map(([id, label]) => (
          <button key={id} className={view === id ? 'active' : ''} onClick={() => go(id)}>
            {label}
            {id === 'pending' && pendCount > 0 && <span className="badge">{pendCount}</span>}
          </button>
        ))}
        <button className={moreOpen ? 'active' : ''} onClick={() => setMoreOpen((o) => !o)}>More</button>
      </nav>

      {moreOpen && (
        <div className="sheet-backdrop" onMouseDown={() => setMoreOpen(false)}>
          <div className="sheet" onMouseDown={(e) => e.stopPropagation()}>
            <div className="sheet-grab" />
            {[...SECONDARY, ...TERTIARY].map(([id, label]) => (
              <button key={id} className="sheet-row" onClick={() => go(id)}>{label}</button>
            ))}
            <button className="sheet-row" onClick={() => { setTheme(theme === 'dark' ? 'light' : 'dark'); setMoreOpen(false) }}>
              {theme === 'dark' ? 'Light theme' : 'Dark theme'}
            </button>
            {auth.enabled && auth.authed && <button className="sheet-row" onClick={logout}>Log out</button>}
          </div>
        </div>
      )}

      {resolveTarget && (
        <ResolveModal print={resolveTarget} onClose={() => setResolveTarget(null)}
          onDone={() => { setResolveTarget(null); reloadAll() }} />
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
        <div className="card">
          <h2 className="sec-head">In progress</h2>
          {wip.map((p) => (
            <div className="arow" key={p.id} onClick={() => onResolve(p)}>
              <div style={{ minWidth: 0 }}>
                <div className="arow-t">#{p.id} {p.name}</div>
                <div className="arow-s">Started {p.date}</div>
              </div>
              <span className="spacer" />
              <button className="btn small">Resolve</button>
            </div>
          ))}
        </div>
      )}
      {low.length > 0 && (
        <div className="card">
          <h2 className="sec-head">Running low</h2>
          {low.map((t) => (
            <div className="arow" key={t.type_id} onClick={onGoReorder}>
              <div style={{ minWidth: 0 }}>
                <div className="arow-t">{t.label}</div>
                <div className="arow-s" style={{ color: 'var(--warn)' }}>
                  {t.current_pct === 0 ? 'Out of stock' : `${t.current_pct}% left`}
                </div>
              </div>
              <span className="spacer" />
              <button className="btn ghost small">Reorder</button>
            </div>
          ))}
        </div>
      )}
    </>
  )
}
