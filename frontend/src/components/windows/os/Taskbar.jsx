import { useEffect, useState } from 'react'
import { Wifi, Volume2, Bell, ChevronUp, Shield, Search } from 'lucide-react'
import { useOS } from './store'
import { APPS, AppIcon } from './apps/registry'
import { useCtxMenu } from './ui'

const PINNED = [
  { app: 'FileExplorer', props: { path: 'This PC' } },
  { app: 'ServerManager' },
  { app: 'Terminal', props: { shell: 'ps' } },
  { app: 'Terminal', props: { shell: 'cmd' }, key: 'cmd', title: 'Command Prompt' },
  { app: 'TaskManager' },
]

export default function Taskbar() {
  const os = useOS()
  const ctx = useCtxMenu()
  const [now, setNow] = useState(new Date())
  const [flyout, setFlyout] = useState(null)
  const [hovered, setHovered] = useState(null)

  useEffect(() => { const t = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(t) }, [])

  const running = os.windows
  const launch = (app, props, title) => {
    const existing = running.find((w) => w.app === app && JSON.stringify(w.props || {}) === JSON.stringify(props || {}))
    if (existing) { existing.minimized ? os.focusWindow(existing.id) : (os.activeWindowId === existing.id ? os.minimizeWindow(existing.id) : os.focusWindow(existing.id)) }
    else os.openApp(app, props || {}, { title: title || APPS[app]?.title })
  }

  const taskbarCtx = (e) => {
    e.preventDefault()
    ctx.open(e.clientX, e.clientY, [
      { label: 'Cascade windows', onClick: () => os.windows.forEach((w, i) => os.setWindowBounds(w.id, { x: 60 + i * 30, y: 40 + i * 30, maximized: false })) },
      { label: 'Show windows side by side' },
      { label: 'Show the desktop', onClick: () => os.windows.forEach((w) => os.minimizeWindow(w.id)) },
      { sep: true },
      { label: 'Task Manager', onClick: () => os.openApp('TaskManager', {}, { title: 'Task Manager' }) },
      { sep: true },
      { label: 'Taskbar settings', onClick: () => os.openApp('Settings', {}, { title: 'Settings' }) },
    ])
  }

  const windowCtx = (e, win, fallback) => {
    e.preventDefault()
    e.stopPropagation()
    if (!win) {
      ctx.open(e.clientX, e.clientY, [
        { label: 'Open', onClick: () => launch(fallback.app, fallback.props, fallback.title) },
        { sep: true },
        { label: 'Pin to taskbar', disabled: true },
      ])
      return
    }
    ctx.open(e.clientX, e.clientY, [
      { label: 'Restore', disabled: !win.minimized && !win.maximized, onClick: () => os.focusWindow(win.id) },
      { label: 'Move' },
      { label: 'Size' },
      { label: 'Minimize', disabled: win.minimized, onClick: () => os.minimizeWindow(win.id) },
      { label: 'Maximize', disabled: win.maximized, onClick: () => os.toggleMaximize(win.id) },
      { sep: true },
      { label: `Open ${APPS[win.app]?.title || win.app}`, onClick: () => os.openApp(win.app, win.props || {}, { title: APPS[win.app]?.title }) },
      { label: 'Recent', sub: [
        { label: 'C:\\Users\\Administrator\\Desktop\\notes.txt', onClick: () => os.openApp('Notepad', { path: 'C:\\Users\\Administrator\\Desktop\\notes.txt' }, { title: 'notes.txt - Notepad' }) },
        { label: 'D:\\Logs\\app-2024-01-17.log', onClick: () => os.openApp('Notepad', { path: 'D:\\Logs\\app-2024-01-17.log' }, { title: 'app-2024-01-17.log - Notepad' }) },
      ] },
      { sep: true },
      { label: 'Close window', onClick: () => os.closeWindow(win.id) },
    ])
  }

  return (
    <div className="winos-taskbar" onContextMenu={taskbarCtx}>
      <div className={`winos-start ${os.startOpen ? 'on' : ''}`} onMouseDown={(e) => { e.stopPropagation(); os.setStartOpen((v) => !v) }} title="Start">
        <WinLogo />
      </div>
      <div className="winos-tray-btn" style={{ width: 200 }} onClick={() => os.setStartOpen(true)}>
        <Search size={15} /><span style={{ fontSize: 11.5, color: '#bbb' }}>Type here to search</span>
      </div>
      <div className="winos-tasks">
        {PINNED.map((p) => {
          const win = running.find((w) => w.app === p.app && JSON.stringify(w.props || {}) === JSON.stringify(p.props || {}))
          return (
            <button key={p.app + (p.key || '')} className={`winos-taskbtn ${win && os.activeWindowId === win.id ? 'active' : ''}`} title={p.title || APPS[p.app]?.title}
              onClick={() => launch(p.app, p.props, p.title)}
              onMouseEnter={() => win && setHovered(win.id)}
              onMouseLeave={() => setHovered(null)}
              onContextMenu={(e) => windowCtx(e, win, p)}>
              <AppIcon app={p.app} size={18} />
              {win && <span className="ul" />}
            </button>
          )
        })}
        {/* non-pinned running apps */}
        {running.filter((w) => !PINNED.some((p) => p.app === w.app && JSON.stringify(p.props || {}) === JSON.stringify(w.props || {}))).map((w) => (
          <button key={w.id} className={`winos-taskbtn ${os.activeWindowId === w.id ? 'active' : ''}`} title={w.title}
            onClick={() => w.minimized ? os.focusWindow(w.id) : (os.activeWindowId === w.id ? os.minimizeWindow(w.id) : os.focusWindow(w.id))}
            onMouseEnter={() => setHovered(w.id)}
            onMouseLeave={() => setHovered(null)}
            onContextMenu={(e) => windowCtx(e, w)}>
            <AppIcon app={w.app} size={18} />
            <span style={{ maxWidth: 130, overflow: 'hidden', textOverflow: 'ellipsis' }}>{w.title}</span>
            <span className="ul" />
          </button>
        ))}
      </div>

      <div className="winos-tray">
        <button className="winos-tray-btn" onClick={() => setFlyout(flyout === 'hidden' ? null : 'hidden')}><ChevronUp size={14} /></button>
        <button className="winos-tray-btn" title="Windows Defender"><Shield size={15} /></button>
        <button className="winos-tray-btn" onClick={() => setFlyout(flyout === 'net' ? null : 'net')} title="Network"><Wifi size={15} /></button>
        <button className="winos-tray-btn" onClick={() => setFlyout(flyout === 'vol' ? null : 'vol')} title="Volume"><Volume2 size={15} /></button>
        <button className="winos-tray-btn winos-clock" onClick={() => setFlyout(flyout === 'cal' ? null : 'cal')}>
          <div>{now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
          <div>{now.toLocaleDateString([], { month: '2-digit', day: '2-digit', year: 'numeric' })}</div>
        </button>
        <button className="winos-tray-btn" onClick={() => setFlyout(flyout === 'ac' ? null : 'ac')} title="Action Center"><Bell size={15} /></button>
      </div>

      {flyout && <Flyout type={flyout} now={now} os={os} onClose={() => setFlyout(null)} />}
      {hovered && <TaskPreview win={running.find((w) => w.id === hovered)} os={os} />}
    </div>
  )
}

function TaskPreview({ win, os }) {
  if (!win) return null
  return (
    <div style={{
      position: 'absolute',
      bottom: 46,
      left: Math.min(Math.max(70, win.x || 120), window.innerWidth - 250),
      width: 230,
      background: 'rgba(35,35,35,0.96)',
      color: '#fff',
      border: '1px solid #555',
      borderRadius: 6,
      padding: 8,
      boxShadow: '0 10px 30px rgba(0,0,0,.5)',
      zIndex: 9600,
      pointerEvents: 'none',
    }}>
      <div style={{ height: 115, background: '#f4f4f4', border: '1px solid #777', marginBottom: 8, color: '#1b1b1b', display: 'flex', flexDirection: 'column' }}>
        <div style={{ height: 18, background: '#fff', borderBottom: '1px solid #ddd', fontSize: 9, padding: '2px 4px' }}>{win.title}</div>
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#666', fontSize: 11 }}>
          <AppIcon app={win.app} size={28} />
        </div>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 12 }}>{win.title}</span>
        <span style={{ pointerEvents: 'auto', cursor: 'default', color: '#ffb3b3' }} onClick={() => os.closeWindow(win.id)}>×</span>
      </div>
    </div>
  )
}

function Flyout({ type, now, os, onClose }) {
  return (
    <div className="winos-flyout" onMouseDown={(e) => e.stopPropagation()} style={type === 'cal' ? {} : { width: 300 }}>
      {type === 'net' && (
        <div>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>Ethernet</div>
          {os.adapters.map((a) => (
            <div key={a.id} style={{ marginBottom: 8, fontSize: 12.5 }}>
              <div style={{ color: '#7fd0ff' }}>{a.name} — {a.status}</div>
              <div style={{ color: '#bbb', fontSize: 11.5 }}>{a.desc}<br />IPv4: {a.ipv4}</div>
            </div>
          ))}
          <div style={{ borderTop: '1px solid #444', marginTop: 8, paddingTop: 8 }}>
            <span style={{ color: '#7fd0ff', cursor: 'default', fontSize: 12 }} onClick={() => { os.openApp('Settings', {}, { title: 'Settings' }); onClose() }}>Network &amp; Internet settings</span>
          </div>
        </div>
      )}
      {type === 'vol' && (
        <div>
          <div style={{ fontWeight: 600, marginBottom: 10 }}>Speakers (High Definition Audio)</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Volume2 size={18} /><input type="range" min={0} max={100} defaultValue={68} style={{ flex: 1 }} /><span>68</span>
          </div>
        </div>
      )}
      {type === 'cal' && (
        <div style={{ width: 280 }}>
          <div style={{ fontSize: 22, fontWeight: 300 }}>{now.toLocaleTimeString()}</div>
          <div style={{ color: '#bbb', marginBottom: 10 }}>{now.toLocaleDateString([], { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</div>
          <MiniCalendar now={now} />
        </div>
      )}
      {type === 'ac' && (
        <div>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>Notifications</div>
          <div style={{ fontSize: 12, color: '#bbb', marginBottom: 12 }}>No new notifications</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6 }}>
            {['Network', 'Volume', 'Brightness', 'VPN', 'Airplane', 'Night light', 'Connect', 'All settings'].map((q) => (
              <div key={q} style={{ background: '#3a3a3a', borderRadius: 4, padding: '10px 4px', textAlign: 'center', fontSize: 10.5, cursor: 'default' }} onClick={() => { if (q === 'All settings') { os.openApp('Settings', {}, { title: 'Settings' }); onClose() } }}>{q}</div>
            ))}
          </div>
        </div>
      )}
      {type === 'hidden' && (
        <div style={{ display: 'flex', gap: 12 }}>
          <Shield size={18} /><Wifi size={18} /><Volume2 size={18} />
          <span style={{ fontSize: 11.5, color: '#bbb' }}>ENG</span>
        </div>
      )}
    </div>
  )
}

function MiniCalendar({ now }) {
  const year = now.getFullYear(), month = now.getMonth()
  const first = new Date(year, month, 1).getDay()
  const days = new Date(year, month + 1, 0).getDate()
  const cells = [...Array(first).fill(null), ...Array.from({ length: days }, (_, i) => i + 1)]
  return (
    <div>
      <div style={{ fontWeight: 600, marginBottom: 6 }}>{now.toLocaleDateString([], { month: 'long', year: 'numeric' })}</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7,1fr)', gap: 2, fontSize: 11, textAlign: 'center' }}>
        {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((d, i) => <div key={i} style={{ color: '#888' }}>{d}</div>)}
        {cells.map((c, i) => (
          <div key={i} style={{ padding: 4, borderRadius: 3, background: c === now.getDate() ? '#0078d4' : 'transparent' }}>{c || ''}</div>
        ))}
      </div>
    </div>
  )
}

function WinLogo() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24"><rect x="1" y="1" width="10" height="10" fill="#fff" /><rect x="13" y="1" width="10" height="10" fill="#fff" /><rect x="1" y="13" width="10" height="10" fill="#fff" /><rect x="13" y="13" width="10" height="10" fill="#fff" /></svg>
  )
}
