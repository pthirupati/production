import { useCallback, useRef } from 'react'
import { Minus, Square, X, Copy } from 'lucide-react'
import { useOS } from './store'

const SNAP_THRESHOLD = 8

export default function WindowFrame({ win, icon, children }) {
  const { focusWindow, closeWindow, minimizeWindow, toggleMaximize, setWindowBounds, snapWindow, activeWindowId } = useOS()
  const dragState = useRef(null)
  const active = activeWindowId === win.id

  const startDrag = useCallback((e) => {
    if (e.button !== 0) return
    if (win.maximized) {
      // un-maximize on drag, keeping cursor over titlebar
      toggleMaximize(win.id)
    }
    focusWindow(win.id)
    const startX = e.clientX, startY = e.clientY
    const ox = win.maximized ? Math.max(0, e.clientX - 200) : win.x
    const oy = win.maximized ? 0 : win.y
    dragState.current = { startX, startY, ox, oy }
    const move = (ev) => {
      const dx = ev.clientX - startX, dy = ev.clientY - startY
      let nx = ox + dx, ny = oy + dy
      setWindowBounds(win.id, { x: nx, y: Math.max(0, ny) })
    }
    const up = (ev) => {
      window.removeEventListener('mousemove', move)
      window.removeEventListener('mouseup', up)
      if (ev.clientY <= SNAP_THRESHOLD) snapWindow(win.id, 'max')
      else if (ev.clientX <= SNAP_THRESHOLD) snapWindow(win.id, 'left')
      else if (ev.clientX >= window.innerWidth - SNAP_THRESHOLD) snapWindow(win.id, 'right')
    }
    window.addEventListener('mousemove', move)
    window.addEventListener('mouseup', up)
  }, [win, focusWindow, setWindowBounds, snapWindow, toggleMaximize])

  const startResize = useCallback((dir) => (e) => {
    e.stopPropagation()
    focusWindow(win.id)
    const sx = e.clientX, sy = e.clientY
    const { x, y, width, height } = win
    const move = (ev) => {
      const dx = ev.clientX - sx, dy = ev.clientY - sy
      let nx = x, ny = y, nw = width, nh = height
      if (dir.includes('e')) nw = Math.max(360, width + dx)
      if (dir.includes('s')) nh = Math.max(200, height + dy)
      if (dir.includes('w')) { nw = Math.max(360, width - dx); nx = x + (width - nw) }
      if (dir.includes('n')) { nh = Math.max(200, height - dy); ny = y + (height - nh) }
      setWindowBounds(win.id, { x: nx, y: ny, width: nw, height: nh })
    }
    const up = () => { window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up) }
    window.addEventListener('mousemove', move)
    window.addEventListener('mouseup', up)
  }, [win, focusWindow, setWindowBounds])

  const style = win.maximized
    ? { left: 0, top: 0, width: '100%', height: '100%', zIndex: win.zIndex }
    : { left: win.x, top: win.y, width: win.width, height: win.height, zIndex: win.zIndex }

  if (win.minimized) return null

  return (
    <div className={`winos-win ${active ? 'active' : ''}`} style={style} onMouseDown={() => focusWindow(win.id)}>
      {!win.maximized && (
        <>
          <div className="winos-rz n" onMouseDown={startResize('n')} />
          <div className="winos-rz s" onMouseDown={startResize('s')} />
          <div className="winos-rz e" onMouseDown={startResize('e')} />
          <div className="winos-rz w" onMouseDown={startResize('w')} />
          <div className="winos-rz ne" onMouseDown={startResize('ne')} />
          <div className="winos-rz nw" onMouseDown={startResize('nw')} />
          <div className="winos-rz se" onMouseDown={startResize('se')} />
          <div className="winos-rz sw" onMouseDown={startResize('sw')} />
        </>
      )}
      <div className="winos-titlebar" onMouseDown={startDrag} onDoubleClick={() => toggleMaximize(win.id)}>
        <div className="winos-title"><span className="twin-icon">{icon}</span>{win.title}</div>
        <div className="winos-caption">
          <button type="button" className="winos-cap-btn" onClick={(e) => { e.stopPropagation(); minimizeWindow(win.id) }} title="Minimize" aria-label="Minimize"><Minus size={15} /></button>
          <button type="button" className="winos-cap-btn" onClick={(e) => { e.stopPropagation(); toggleMaximize(win.id) }} title={win.maximized ? 'Restore' : 'Maximize'} aria-label={win.maximized ? 'Restore' : 'Maximize'}>
            {win.maximized ? <Copy size={12} /> : <Square size={12} />}
          </button>
          <button type="button" className="winos-cap-btn close" onClick={(e) => { e.stopPropagation(); closeWindow(win.id) }} title="Close" aria-label="Close"><X size={15} /></button>
        </div>
      </div>
      <div className="winos-body">{children}</div>
    </div>
  )
}
