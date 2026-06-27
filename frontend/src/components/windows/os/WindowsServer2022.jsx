import { useEffect, useRef, useState } from 'react'
import './os.css'
import { useOS } from './store'
import { ContextMenuProvider } from './ui'
import Desktop from './Desktop'
import Taskbar from './Taskbar'
import StartMenu from './StartMenu'
import WindowFrame from './WindowFrame'
import { APPS, AppIcon } from './apps/registry'

export default function WindowsServer2022({ autoOpen = 'ServerManager', backendState = null }) {
  const os = useOS()
  // Select actions individually — these references are stable across store
  // updates, so effects that depend on them won't re-fire on every render
  // (depending on the whole `os` object caused a React #185 infinite loop).
  const hydrateFromBackend = useOS((s) => s.hydrateFromBackend)
  const booted = useRef(false)
  const [altTab, setAltTab] = useState(null) // { index } when held

  useEffect(() => {
    if (backendState) hydrateFromBackend(backendState)
  }, [backendState, hydrateFromBackend])

  // Auto-open Server Manager on first login (like real Windows Server)
  useEffect(() => {
    if (booted.current) return
    booted.current = true
    if (autoOpen && os.windows.length === 0) {
      os.openApp(autoOpen, {}, { title: APPS[autoOpen]?.title, x: 140, y: 60, width: APPS[autoOpen]?.w, height: APPS[autoOpen]?.h })
    }
  }, []) // eslint-disable-line

  // Alt+Tab switcher — read live state via getState() so the listeners don't
  // need to be re-bound on every store update.
  useEffect(() => {
    const onKey = (e) => {
      if (e.altKey && e.key === 'Tab') {
        e.preventDefault()
        const wins = useOS.getState().windows
        if (!wins.length) return
        setAltTab((prev) => ({ index: ((prev?.index ?? -1) + 1) % wins.length }))
      } else if (e.key === 'Escape') {
        useOS.getState().setStartOpen(false)
      }
    }
    const onUp = (e) => {
      if (e.key === 'Alt' && altTab) {
        const wins = useOS.getState().windows
        const target = wins[altTab.index]
        if (target) useOS.getState().focusWindow(target.id)
        setAltTab(null)
      }
    }
    window.addEventListener('keydown', onKey)
    window.addEventListener('keyup', onUp)
    return () => { window.removeEventListener('keydown', onKey); window.removeEventListener('keyup', onUp) }
  }, [altTab])

  return (
    <ContextMenuProvider>
      <div className="winos">
        <Desktop />

        {os.windows.map((win) => {
          const App = APPS[win.app]?.c
          if (!App) return null
          return (
            <WindowFrame key={win.id} win={win} icon={<AppIcon app={win.app} size={15} />}>
              <App win={win} />
            </WindowFrame>
          )
        })}

        <Taskbar />
        {os.startOpen && <StartMenu />}

        {altTab && (
          <div className="winos-alttab">
            <div className="winos-alttab-grid">
              {os.windows.map((w, i) => (
                <div key={w.id} className={`winos-alttab-card ${i === altTab.index ? 'sel' : ''}`}>
                  <AppIcon app={w.app} size={36} />
                  <div style={{ fontSize: 12, padding: '0 8px', textAlign: 'center' }}>{w.title}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </ContextMenuProvider>
  )
}
