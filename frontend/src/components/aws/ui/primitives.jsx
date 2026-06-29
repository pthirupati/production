import { useEffect, useRef, useState } from 'react'
import { Copy, Check, X, ChevronRight, Search, Info, AlertTriangle, CheckCircle2, XCircle, Inbox } from 'lucide-react'

export function Button({ variant = 'secondary', children, loading, icon: Icon, ...props }) {
  return (
    <button className={`aws-btn aws-btn-${variant}`} {...props} disabled={props.disabled || loading}>
      {loading ? <span className="aws-spinner" style={{ width: 14, height: 14 }} /> : Icon ? <Icon size={14} /> : null}
      {children}
    </button>
  )
}

export function Badge({ state, children }) {
  const s = String(state || '').toLowerCase().replace(/[^a-z]/g, '-')
  return (
    <span className={`aws-badge aws-badge-${s}`}>
      <span className="aws-dot" />
      {children || state}
    </span>
  )
}

export function IDCopy({ value, link, mono = true, onClick }) {
  const [copied, setCopied] = useState(false)
  const copy = (e) => {
    e.stopPropagation()
    try { navigator.clipboard?.writeText(value) } catch { /* noop */ }
    setCopied(true)
    setTimeout(() => setCopied(false), 1200)
  }
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
      {link || onClick ? (
        <a className={mono ? 'aws-mono' : ''} onClick={onClick}>{value}</a>
      ) : (
        <span className={mono ? 'aws-mono' : ''}>{value}</span>
      )}
      <button className="aws-copy-btn" onClick={copy} title="Copy">{copied ? <Check size={13} /> : <Copy size={13} />}</button>
    </span>
  )
}

export function Flash({ items, onDismiss }) {
  const icons = { success: CheckCircle2, error: XCircle, warning: AlertTriangle, info: Info }
  return (
    <div>
      {items.map((f) => {
        const Icon = icons[f.type] || Info
        return (
          <div key={f.id} className={`aws-flash aws-flash-${f.type}`}>
            <Icon size={18} style={{ marginTop: 1, flexShrink: 0 }} />
            <div style={{ flex: 1 }}>{f.message}</div>
            <button className="aws-copy-btn" onClick={() => onDismiss(f.id)}><X size={16} /></button>
          </div>
        )
      })}
    </div>
  )
}

export function Breadcrumb({ items }) {
  return (
    <div className="aws-breadcrumb">
      {items.map((it, i) => (
        <span key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
          {i > 0 && <ChevronRight size={14} style={{ opacity: 0.6 }} />}
          {it.onClick && i < items.length - 1 ? <a onClick={it.onClick}>{it.label}</a> : <span style={{ color: i === items.length - 1 ? 'var(--aws-text-primary)' : undefined }}>{it.label}</span>}
        </span>
      ))}
    </div>
  )
}

export function Tabs({ tabs, active, onChange }) {
  return (
    <div className="aws-tabs">
      {tabs.map((t) => (
        <button key={t.key} className={`aws-tab ${active === t.key ? 'aws-tab-active' : ''}`} onClick={() => onChange(t.key)}>{t.label}</button>
      ))}
    </div>
  )
}

export function Modal({ title, children, onClose, footer, width }) {
  const ref = useRef(null)
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose?.() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div className="aws-modal-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose?.() }}>
      <div className="aws-modal" ref={ref} style={width ? { maxWidth: width } : undefined}>
        <div className="aws-modal-header">
          <span>{title}</span>
          <button className="aws-copy-btn" onClick={onClose}><X size={18} /></button>
        </div>
        <div className="aws-modal-body">{children}</div>
        {footer && <div className="aws-modal-footer">{footer}</div>}
      </div>
    </div>
  )
}

export function ConfirmDialog({
  title = 'Confirm action',
  body,
  confirmLabel = 'Confirm',
  confirmText,
  danger = true,
  onCancel,
  onConfirm,
}) {
  const [typed, setTyped] = useState('')
  const enabled = !confirmText || typed === confirmText
  return (
    <Modal
      title={title}
      onClose={onCancel}
      footer={(
        <>
          <Button onClick={onCancel}>Cancel</Button>
          <Button variant={danger ? 'danger' : 'primary'} disabled={!enabled} onClick={onConfirm}>{confirmLabel}</Button>
        </>
      )}
    >
      <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
        <AlertTriangle size={22} color="var(--aws-warning)" style={{ flexShrink: 0, marginTop: 2 }} />
        <div style={{ flex: 1 }}>
          <div style={{ color: 'var(--aws-text-secondary)', lineHeight: 1.5 }}>{body}</div>
          {confirmText && (
            <div style={{ marginTop: 14 }}>
              <label className="aws-label">Type <span className="aws-mono">{confirmText}</span> to confirm</label>
              <input className="aws-input" value={typed} onChange={(e) => setTyped(e.target.value)} autoFocus />
            </div>
          )}
        </div>
      </div>
    </Modal>
  )
}

export function EmptyState({ title, body, action }) {
  return (
    <div style={{ textAlign: 'center', padding: '48px 20px', color: 'var(--aws-text-secondary)' }}>
      <Inbox size={40} style={{ opacity: 0.4 }} />
      <h3 style={{ marginTop: 12, color: 'var(--aws-text-primary)' }}>{title}</h3>
      {body && <p style={{ marginTop: 6 }}>{body}</p>}
      {action && <div style={{ marginTop: 16 }}>{action}</div>}
    </div>
  )
}

export function SectionLabel({ children, info }) {
  return (
    <div className="aws-section-label" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <span>{children}</span>
      {info && <a style={{ fontWeight: 400, textTransform: 'none', letterSpacing: 0 }}><Info size={12} style={{ display: 'inline', marginRight: 2 }} />Info</a>}
    </div>
  )
}

export function SearchBar({ value, onChange, placeholder }) {
  return (
    <div style={{ position: 'relative', flex: 1, maxWidth: 420 }}>
      <Search size={15} style={{ position: 'absolute', left: 8, top: 8, color: 'var(--aws-text-muted)' }} />
      <input className="aws-input" style={{ paddingLeft: 28 }} value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
    </div>
  )
}

// Sortable, selectable, searchable table with pagination + right-click context menu.
// rowActions: optional (row) => [{ label, onClick, danger }] — powers the
// per-row context menu (right-click) matching the page's Actions dropdown.
export function DataTable({ columns, rows, getRowKey, selectable, selected, onSelect, onRowClick, rowActions, tableId, emptyTitle = 'No resources', emptyBody }) {
  const [sortKey, setSortKey] = useState(null)
  const [sortDir, setSortDir] = useState('asc')
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(20)
  const [menu, setMenu] = useState(null) // { x, y, row }
  const [prefsOpen, setPrefsOpen] = useState(false)
  const prefKey = tableId ? `aws-sim-table-columns:${tableId}` : null
  const columnKeySignature = columns.map((c) => c.key).join('|')
  const [visibleKeys, setVisibleKeys] = useState(() => {
    if (!prefKey) return columns.map((c) => c.key)
    try {
      const saved = JSON.parse(localStorage.getItem(prefKey) || 'null')
      return Array.isArray(saved) && saved.length ? saved : columns.map((c) => c.key)
    } catch {
      return columns.map((c) => c.key)
    }
  })

  useEffect(() => {
    const keys = columns.map((c) => c.key)
    setVisibleKeys((existing) => {
      const next = existing.filter((k) => keys.includes(k))
      const withNew = [...next, ...keys.filter((k) => !next.includes(k))]
      const resolved = withNew.length ? withNew : keys
      return resolved.join('|') === existing.join('|') ? existing : resolved
    })
  }, [columnKeySignature])

  useEffect(() => {
    if (prefKey) localStorage.setItem(prefKey, JSON.stringify(visibleKeys))
  }, [prefKey, visibleKeys])

  useEffect(() => {
    if (!menu) return undefined
    const close = () => setMenu(null)
    window.addEventListener('click', close)
    window.addEventListener('scroll', close, true)
    return () => { window.removeEventListener('click', close); window.removeEventListener('scroll', close, true) }
  }, [menu])

  const visibleColumns = columns.filter((c) => visibleKeys.includes(c.key))
  const toggleColumn = (key) => {
    setVisibleKeys((keys) => {
      if (keys.includes(key)) return keys.length > 1 ? keys.filter((k) => k !== key) : keys
      return [...keys, key]
    })
  }

  let sorted = rows
  if (sortKey) {
    const col = columns.find((c) => c.key === sortKey)
    sorted = [...rows].sort((a, b) => {
      const av = col.sortValue ? col.sortValue(a) : a[sortKey]
      const bv = col.sortValue ? col.sortValue(b) : b[sortKey]
      if (av === bv) return 0
      return (av > bv ? 1 : -1) * (sortDir === 'asc' ? 1 : -1)
    })
  }

  const total = sorted.length
  const pageCount = Math.max(1, Math.ceil(total / pageSize))
  const safePage = Math.min(page, pageCount - 1)
  const start = safePage * pageSize
  const display = sorted.slice(start, start + pageSize)

  const allSelected = selectable && display.length > 0 && display.every((r) => selected?.includes(getRowKey(r)))

  if (!rows.length) {
    return <EmptyState title={emptyTitle} body={emptyBody} />
  }

  const openMenu = (e, row) => {
    if (!rowActions) return
    e.preventDefault()
    setMenu({ x: e.clientX, y: e.clientY, row })
  }

  return (
    <div>
      <div style={{ overflowX: 'auto', border: '1px solid var(--aws-table-border)', borderRadius: 'var(--aws-radius-md)' }}>
        <table className="aws-table">
          <thead>
            <tr>
              {selectable && (
                <th style={{ width: 36 }}>
                  <input type="checkbox" aria-label="Select all rows" checked={allSelected} onChange={(e) => onSelect(e.target.checked ? display.map(getRowKey) : [])} />
                </th>
              )}
              {visibleColumns.map((c) => (
                <th key={c.key} onClick={() => c.sortable !== false && (sortKey === c.key ? setSortDir((d) => (d === 'asc' ? 'desc' : 'asc')) : (setSortKey(c.key), setSortDir('asc')))} style={{ cursor: c.sortable !== false ? 'pointer' : 'default' }}>
                  {c.label}{sortKey === c.key ? (sortDir === 'asc' ? ' ▲' : ' ▼') : ''}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {display.map((r) => {
              const key = getRowKey(r)
              const isSel = selected?.includes(key)
              return (
                <tr key={key} className={isSel ? 'aws-row-selected' : ''} onClick={() => onRowClick?.(r)} onContextMenu={(e) => openMenu(e, r)} style={{ cursor: onRowClick ? 'pointer' : 'default' }}>
                  {selectable && (
                    <td onClick={(e) => e.stopPropagation()}>
                      <input type="checkbox" aria-label="Select row" checked={isSel || false} onChange={(e) => onSelect(e.target.checked ? [...(selected || []), key] : selected.filter((k) => k !== key))} />
                    </td>
                  )}
                  {visibleColumns.map((c) => <td key={c.key}>{c.render ? c.render(r) : r[c.key]}</td>)}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 10, fontSize: 13, color: 'var(--aws-text-secondary)' }}>
        <span>Viewing {total === 0 ? 0 : start + 1} to {Math.min(start + pageSize, total)} of {total}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button className="aws-btn aws-btn-secondary" style={{ height: 28 }} onClick={() => setPrefsOpen(true)}>Preferences</button>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            Page size
            <select className="aws-select" style={{ width: 72, height: 28 }} value={pageSize} onChange={(e) => { setPageSize(Number(e.target.value)); setPage(0) }}>
              {[10, 20, 50, 100, 200].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
          <button className="aws-btn aws-btn-secondary" style={{ height: 28 }} disabled={safePage === 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>‹</button>
          <span>{safePage + 1} / {pageCount}</span>
          <button className="aws-btn aws-btn-secondary" style={{ height: 28 }} disabled={safePage >= pageCount - 1} onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}>›</button>
        </div>
      </div>

      {menu && rowActions && (
        <div style={{ position: 'fixed', top: menu.y, left: menu.x, zIndex: 1200, background: 'var(--aws-content-bg)', border: '1px solid var(--aws-border)', borderRadius: 4, boxShadow: 'var(--aws-shadow-md)', minWidth: 180, padding: '4px 0' }}>
          {rowActions(menu.row).map((a, i) => (
            <div
              key={i}
              onClick={(e) => { e.stopPropagation(); setMenu(null); a.onClick(menu.row) }}
              style={{ padding: '8px 16px', fontSize: 13, cursor: 'pointer', color: a.danger ? 'var(--aws-error)' : 'var(--aws-text-primary)' }}
              onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--aws-sidebar-hover-bg)' }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
            >
              {a.label}
            </div>
          ))}
        </div>
      )}
      {prefsOpen && (
        <Modal
          title="Table preferences"
          onClose={() => setPrefsOpen(false)}
          footer={(
            <>
              <Button onClick={() => setVisibleKeys(columns.map((c) => c.key))}>Reset to default</Button>
              <Button variant="primary" onClick={() => setPrefsOpen(false)}>Confirm</Button>
            </>
          )}
        >
          <SectionLabel>Visible columns</SectionLabel>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 8 }}>
            {columns.map((c) => (
              <label key={c.key} style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                <input type="checkbox" checked={visibleKeys.includes(c.key)} onChange={() => toggleColumn(c.key)} disabled={visibleKeys.length === 1 && visibleKeys.includes(c.key)} />
                <span>{c.label}</span>
              </label>
            ))}
          </div>
          <div className="aws-hint" style={{ marginTop: 12 }}>At least one column must remain visible. Preferences are persisted locally for this simulation.</div>
        </Modal>
      )}
    </div>
  )
}

export { ChevronRight }
