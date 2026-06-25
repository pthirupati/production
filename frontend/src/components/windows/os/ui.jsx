import { useEffect, useRef, useState, createContext, useContext } from 'react'
import { ChevronRight, X } from 'lucide-react'

export function fmtBytes(n) {
  if (n == null) return ''
  if (n === 0) return '0 bytes'
  const u = ['bytes', 'KB', 'MB', 'GB', 'TB']
  let i = 0; let v = n
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++ }
  return `${i === 0 ? v : v.toFixed(1)} ${u[i]}`
}

export function fmtKB(n) {
  if (n == null) return ''
  return `${Math.max(1, Math.round(n / 1024)).toLocaleString()} KB`
}

// ── Context menu ───────────────────────────────────────────────────────────
const CtxContext = createContext(null)
export function useCtxMenu() { return useContext(CtxContext) }

export function ContextMenuProvider({ children }) {
  const [menu, setMenu] = useState(null) // { x, y, items }
  const open = (x, y, items) => setMenu({ x, y, items })
  const close = () => setMenu(null)
  return (
    <CtxContext.Provider value={{ open, close }}>
      {children}
      {menu && <ContextMenu {...menu} onClose={close} />}
    </CtxContext.Provider>
  )
}

function ContextMenu({ x, y, items, onClose }) {
  const ref = useRef(null)
  const [pos, setPos] = useState({ x, y })
  useEffect(() => {
    const r = ref.current?.getBoundingClientRect()
    if (r) {
      let nx = x, ny = y
      if (x + r.width > window.innerWidth) nx = window.innerWidth - r.width - 6
      if (y + r.height > window.innerHeight) ny = window.innerHeight - r.height - 6
      setPos({ x: Math.max(4, nx), y: Math.max(4, ny) })
    }
    const h = () => onClose()
    window.addEventListener('mousedown', h)
    window.addEventListener('blur', h)
    return () => { window.removeEventListener('mousedown', h); window.removeEventListener('blur', h) }
  }, [x, y, onClose])
  return (
    <div ref={ref} className="winos-ctx" style={{ left: pos.x, top: pos.y }} onMouseDown={(e) => e.stopPropagation()}>
      {items.map((it, i) => it.sep
        ? <div key={i} className="winos-ctx-sep" />
        : <CtxItem key={i} item={it} onClose={onClose} />)}
    </div>
  )
}

function CtxItem({ item, onClose }) {
  const [subOpen, setSubOpen] = useState(false)
  if (item.sub) {
    return (
      <div className="winos-ctx-item" onMouseEnter={() => setSubOpen(true)} onMouseLeave={() => setSubOpen(false)}>
        {item.icon}{item.label}<ChevronRight size={13} className="chev" />
        {subOpen && (
          <div className="winos-ctx winos-ctx-sub">
            {item.sub.map((s, i) => s.sep ? <div key={i} className="winos-ctx-sep" /> : <CtxItem key={i} item={s} onClose={onClose} />)}
          </div>
        )}
      </div>
    )
  }
  return (
    <div className={`winos-ctx-item ${item.disabled ? 'disabled' : ''}`}
      onClick={() => { if (!item.disabled) { item.onClick?.(); onClose() } }}>
      {item.icon}{item.label}{item.right && <span className="chev">{item.right}</span>}
    </div>
  )
}

// ── Dialog ─────────────────────────────────────────────────────────────────
export function Dialog({ title, children, onClose, footer, width }) {
  return (
    <div className="winos-dlg-backdrop" onMouseDown={(e) => e.stopPropagation()}>
      <div className="winos-dlg" style={width ? { width } : undefined}>
        <div className="winos-dlg-title">
          <span>{title}</span>
          {onClose && <X size={15} style={{ cursor: 'default' }} onClick={onClose} />}
        </div>
        <div className="winos-dlg-body">{children}</div>
        {footer && <div className="winos-dlg-foot">{footer}</div>}
      </div>
    </div>
  )
}

// ── Tabs ───────────────────────────────────────────────────────────────────
export function Tabs({ tabs, active, onChange }) {
  return (
    <div className="winos-tabs">
      {tabs.map((t) => (
        <div key={t} className={`winos-tab ${active === t ? 'active' : ''}`} onClick={() => onChange(t)}>{t}</div>
      ))}
    </div>
  )
}

// ── Tree node ──────────────────────────────────────────────────────────────
export function TreeNode({ label, icon, depth = 0, expandable, expanded, onToggle, selected, onSelect, onContext }) {
  return (
    <div className={`winos-tree-row ${selected ? 'sel' : ''}`} style={{ paddingLeft: 8 + depth * 14 }}
      onClick={onSelect} onContextMenu={onContext}>
      {expandable
        ? <ChevronRight size={13} style={{ transform: expanded ? 'rotate(90deg)' : 'none', transition: 'transform .1s' }} onClick={(e) => { e.stopPropagation(); onToggle?.() }} />
        : <span style={{ width: 13, display: 'inline-block' }} />}
      {icon}
      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{label}</span>
    </div>
  )
}
