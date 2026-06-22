import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles/index.css'

// Self-heal stale-chunk failures. After a deploy, a browser holding an old
// index.html requests chunk hashes that no longer exist (404) → Vite throws a
// dynamic-import error and the app renders blank. Reload ONCE (guarded against a
// loop) so the browser revalidates index.html (now served no-cache) and fetches
// the current chunks. Covers both the Vite preload event and a generic chunk
// load error from React.lazy.
function recoverFromStaleChunk(reason) {
  const KEY = 'fixitlab:chunk-reload'
  const last = Number(sessionStorage.getItem(KEY) || 0)
  // Only auto-reload if we haven't already tried in the last 10s (prevents loops).
  if (Date.now() - last < 10000) return
  sessionStorage.setItem(KEY, String(Date.now()))
  // eslint-disable-next-line no-console
  console.warn('[fixitlab] stale chunk detected, reloading to refresh assets:', reason)
  window.location.reload()
}

window.addEventListener('vite:preloadError', (e) => {
  e.preventDefault()
  recoverFromStaleChunk(e?.payload?.message || 'vite:preloadError')
})
window.addEventListener('error', (e) => {
  const msg = String(e?.message || '')
  if (/dynamically imported module|Importing a module script failed|ChunkLoadError|Failed to fetch/i.test(msg)) {
    recoverFromStaleChunk(msg)
  }
})
// React.lazy() dynamic-import failures surface as REJECTED PROMISES, not window
// 'error' events — so catch those too. This is the path that fires for the
// "Failed to fetch dynamically imported module" the admin pages were hitting.
window.addEventListener('unhandledrejection', (e) => {
  const msg = String(e?.reason?.message || e?.reason || '')
  if (/dynamically imported module|Importing a module script failed|ChunkLoadError|Failed to fetch dynamically/i.test(msg)) {
    recoverFromStaleChunk(msg)
  }
})

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
