import { useState } from 'react'
import { ArrowLeft, ArrowRight, RotateCw, Home, Star, MoreHorizontal } from 'lucide-react'

const DEFAULT_URL = 'https://localhost/'
const HOME_HTML = {
  title: 'FixitLab — Windows Server Lab',
  body: (
    <div style={{ fontFamily: 'Segoe UI, system-ui, sans-serif', padding: 32, maxWidth: 720, margin: '0 auto' }}>
      <h1 style={{ fontSize: 28, fontWeight: 600, color: '#1b1b1b', marginBottom: 8 }}>FixitLab Lab Environment</h1>
      <p style={{ color: '#444', lineHeight: 1.6, marginBottom: 16 }}>
        This Microsoft Edge session runs inside the Windows Server 2022 lab. Use it to browse lab documentation,
        internal portals, and certificate endpoints configured in your scenario.
      </p>
      <div style={{ display: 'grid', gap: 12 }}>
        {[
          ['Server Manager', 'Manage roles, features, and local server settings.'],
          ['IIS Manager', 'Configure sites, application pools, and bindings.'],
          ['Event Viewer', 'Review Application, System, and Security logs.'],
        ].map(([t, d]) => (
          <div key={t} style={{ border: '1px solid #e0e0e0', borderRadius: 6, padding: 12, background: '#fafafa' }}>
            <div style={{ fontWeight: 600, color: '#0078d4' }}>{t}</div>
            <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>{d}</div>
          </div>
        ))}
      </div>
    </div>
  ),
}

function normalizeUrl(raw) {
  const t = (raw || '').trim()
  if (!t) return DEFAULT_URL
  if (/^https?:\/\//i.test(t)) return t
  if (t.includes('.') || t.startsWith('localhost')) return `https://${t}`
  return `https://www.bing.com/search?q=${encodeURIComponent(t)}`
}

export default function Edge() {
  const [url, setUrl] = useState(DEFAULT_URL)
  const [input, setInput] = useState(DEFAULT_URL)
  const [history, setHistory] = useState([DEFAULT_URL])
  const [histIdx, setHistIdx] = useState(0)
  const [loading, setLoading] = useState(false)

  const navigate = (next) => {
    const u = normalizeUrl(next)
    setLoading(true)
    setTimeout(() => {
      setUrl(u)
      setInput(u)
      setHistory((h) => [...h.slice(0, histIdx + 1), u])
      setHistIdx((i) => i + 1)
      setLoading(false)
    }, 350)
  }

  const back = () => {
    if (histIdx <= 0) return
    const i = histIdx - 1
    setHistIdx(i)
    setUrl(history[i])
    setInput(history[i])
  }

  const forward = () => {
    if (histIdx >= history.length - 1) return
    const i = histIdx + 1
    setHistIdx(i)
    setUrl(history[i])
    setInput(history[i])
  }

  const page = url.includes('localhost') || url.includes('127.0.0.1') ? HOME_HTML : {
    title: url,
    body: (
      <div style={{ padding: 32, textAlign: 'center', color: '#666' }}>
        <div style={{ fontSize: 48, marginBottom: 12 }}>🌐</div>
        <div style={{ fontWeight: 600, marginBottom: 8 }}>{url}</div>
        <p style={{ fontSize: 13 }}>Lab page — external sites are not fetched in this lab environment.</p>
      </div>
    ),
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#fff' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 8px', background: '#f3f3f3', borderBottom: '1px solid #ddd' }}>
        <button type="button" className="winos-btn min-h-[44px] min-w-[44px] inline-flex items-center justify-center" disabled={histIdx <= 0} onClick={back} title="Back" aria-label="Back"><ArrowLeft size={14} /></button>
        <button type="button" className="winos-btn min-h-[44px] min-w-[44px] inline-flex items-center justify-center" disabled={histIdx >= history.length - 1} onClick={forward} title="Forward" aria-label="Forward"><ArrowRight size={14} /></button>
        <button type="button" className="winos-btn min-h-[44px] min-w-[44px] inline-flex items-center justify-center" onClick={() => navigate(url)} title="Refresh" aria-label="Refresh"><RotateCw size={14} className={loading ? 'animate-spin' : ''} /></button>
        <button type="button" className="winos-btn min-h-[44px] min-w-[44px] inline-flex items-center justify-center" onClick={() => navigate(DEFAULT_URL)} title="Home" aria-label="Home"><Home size={14} /></button>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && navigate(input)}
          aria-label="Address bar"
          style={{ flex: 1, fontSize: 12, padding: '5px 10px', border: '1px solid #ccc', borderRadius: 14, outline: 'none' }}
        />
        <button type="button" className="winos-btn min-h-[44px] min-w-[44px] inline-flex items-center justify-center" title="Favorites" aria-label="Favorites"><Star size={14} /></button>
        <button type="button" className="winos-btn min-h-[44px] min-w-[44px] inline-flex items-center justify-center" title="Settings and more" aria-label="Settings and more"><MoreHorizontal size={14} /></button>
      </div>
      <div style={{ flex: 1, overflow: 'auto', background: '#fff' }}>
        {loading ? (
          <div style={{ padding: 24, color: '#888', fontSize: 12 }}>Loading…</div>
        ) : page.body}
      </div>
    </div>
  )
}
