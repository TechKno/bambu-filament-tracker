// Currency shown throughout the UI. Change this one line for $, €, etc.
export const CURRENCY = '£'
// Format a money value; null/undefined -> em dash (unknown/unpriced).
export const money = (n) => (n == null ? '—' : `${CURRENCY}${Number(n).toFixed(2)}`)

// Tiny fetch wrapper around the Flask JSON API.
// Throws { auth: true } on 401 so the app can show the login screen,
// and Error(message) on other failures so callers can surface it.

async function req(method, path, payload) {
  const res = await fetch(`/api${path}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: payload !== undefined ? JSON.stringify(payload) : undefined,
  })
  if (res.status === 401) {
    const err = new Error('Authentication required')
    err.auth = true
    throw err
  }
  let data = {}
  try { data = await res.json() } catch { /* empty body */ }
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`)
  return data
}

export const api = {
  authStatus: () => req('GET', '/auth/status'),
  login: (password) => req('POST', '/login', { password }),
  logout: () => req('POST', '/logout'),
  getSettings: () => req('GET', '/settings'),
  putSettings: (s) => req('PUT', '/settings', s),

  inventory: () => req('GET', '/inventory'),
  options: () => req('GET', '/options'),
  addSpool: (d) => req('POST', '/spools', d),
  patchSpool: (id, d) => req('PATCH', `/spools/${id}`, d),
  deleteSpool: (id) => req('DELETE', `/spools/${id}`),

  history: () => req('GET', '/prints'),
  preflight: (usage) => req('POST', '/prints/preflight', { usage }),
  logPrint: (d) => req('POST', '/prints', d),
  resolvePrint: (id, d) => req('POST', `/prints/${id}/resolve`, d),
  editPrint: (id, d) => req('PATCH', `/prints/${id}`, d),
  deletePrint: (id) => req('DELETE', `/prints/${id}`),

  reorder: () => req('GET', '/reorder'),
  setReorder: (type_id, status) => req('POST', '/reorder', { type_id, status }),
  stats: () => req('GET', '/stats'),
}
