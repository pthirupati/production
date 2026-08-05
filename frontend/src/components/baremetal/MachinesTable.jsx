import { Fragment, useMemo, useState, useRef, useEffect } from 'react'
import { ChevronDown, Plus, Lock, LifeBuoy } from 'lucide-react'
import { MaasStatusBadge, PowerIcon } from './MaasStatusBadge'

const PAGE_SIZE = 25

const COLUMNS = [
  { key: 'fqdn', label: 'FQDN' },
  { key: 'power', label: 'Power' },
  { key: 'status', label: 'Status' },
  { key: 'owner', label: 'Owner' },
  { key: 'pool', label: 'Pool' },
  { key: 'zone', label: 'Zone' },
  { key: 'cpu_count', label: 'Cores' },
  { key: 'ram_gb', label: 'RAM' },
  { key: 'disk_count', label: 'Disks' },
  { key: 'fabric', label: 'Fabric' },
  { key: 'tags', label: 'Tags' },
]

const FACETS = [
  { key: 'status', label: 'Status' },
  { key: 'owner', label: 'Owner' },
  { key: 'pool', label: 'Pool' },
  { key: 'zone', label: 'Zone' },
  { key: 'tags', label: 'Tags' },
]

function parseQuery(raw) {
  const text = (raw || '').trim()
  const filters = { status: null, pool: null, zone: null, tags: null, mac: null, free: '' }
  if (!text) return filters
  const tokens = text.match(/(?:[^\s"]+|"[^"]*")+/g) || []
  const free = []
  for (const tok of tokens) {
    const m = tok.match(/^(status|pool|zone|tags|mac):(=?)?(.+)$/i)
    if (m) {
      const key = m[1].toLowerCase()
      let val = m[3].replace(/^"|"$/g, '')
      if (key === 'status' && val.startsWith('=')) val = val.slice(1)
      if (key === 'status') filters.status = val.toLowerCase()
      else if (key === 'pool') filters.pool = val.toLowerCase()
      else if (key === 'zone') filters.zone = val.toLowerCase()
      else if (key === 'tags') filters.tags = val.toLowerCase()
      else if (key === 'mac') filters.mac = val.toLowerCase()
    } else {
      free.push(tok.replace(/^"|"$/g, ''))
    }
  }
  filters.free = free.join(' ').toLowerCase()
  return filters
}

function machineMatches(m, q, facet) {
  if (facet.status && (m.status || '').toLowerCase() !== facet.status.toLowerCase()) return false
  if (facet.owner && (m.owner || '').toLowerCase() !== facet.owner.toLowerCase()) return false
  if (facet.pool && (m.pool || 'default').toLowerCase() !== facet.pool.toLowerCase()) return false
  if (facet.zone && (m.zone || 'default').toLowerCase() !== facet.zone.toLowerCase()) return false
  if (facet.tag && !(m.tags || []).some((t) => t.toLowerCase() === facet.tag.toLowerCase())) return false

  if (q.status && !(m.status || '').toLowerCase().includes(q.status)) return false
  if (q.pool && !(m.pool || 'default').toLowerCase().includes(q.pool)) return false
  if (q.zone && !(m.zone || 'default').toLowerCase().includes(q.zone)) return false
  if (q.tags && !(m.tags || []).some((t) => t.toLowerCase().includes(q.tags))) return false
  if (q.mac) {
    const macs = (m.interfaces || []).map((i) => (i.mac || '').toLowerCase())
    if (!macs.some((mac) => mac.includes(q.mac))) return false
  }
  if (q.free) {
    const blob = [
      m.hostname, m.fqdn, m.ip, m.status, m.owner, m.pool, m.zone, m.fabric,
      ...(m.tags || []),
    ].join(' ').toLowerCase()
    if (!blob.includes(q.free)) return false
  }
  return true
}

function sortValue(m, key) {
  if (key === 'tags') return (m.tags || []).join(',')
  if (key === 'fqdn') return m.fqdn || `${m.hostname}.${m.domain || 'maas'}`
  if (key === 'ram_gb') return Number(m.ram_gb) || 0
  if (key === 'cpu_count' || key === 'disk_count') return Number(m[key]) || 0
  return (m[key] ?? '').toString().toLowerCase()
}

function ChipFilter({ facet, values, active, onSelect }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  useEffect(() => {
    const onDoc = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])
  return (
    <div className="maas-chip-menu" ref={ref}>
      <button
        type="button"
        className={`maas-chip ${active ? 'is-active' : ''}`}
        onClick={() => setOpen((o) => !o)}
      >
        {facet.label}{active ? `: ${active}` : ''} <ChevronDown size={12} />
      </button>
      {open && (
        <div className="maas-chip-dropdown">
          <button type="button" onClick={() => { onSelect(null); setOpen(false) }}>Any</button>
          {values.map((v) => (
            <button key={v} type="button" onClick={() => { onSelect(v); setOpen(false) }}>{v || '(none)'}</button>
          ))}
        </div>
      )}
    </div>
  )
}

export default function MachinesTable({
  machines = [],
  busy,
  bootResources = [],
  deployImage = '',
  onDeployImageChange,
  onSelectMachine,
  onBulk,
  onAddMachine,
  onEnlist,
  onRefresh,
  zones = [],
  pools = [],
}) {
  const [query, setQuery] = useState('')
  const [facet, setFacet] = useState({ status: null, owner: null, pool: null, zone: null, tag: null })
  const [sortKey, setSortKey] = useState('fqdn')
  const [sortDir, setSortDir] = useState('asc')
  const [selected, setSelected] = useState(() => new Set())
  const [groupBy, setGroupBy] = useState('none')
  const [page, setPage] = useState(0)
  const [dialog, setDialog] = useState(null)
  const [dialogVal, setDialogVal] = useState('')

  const parsed = useMemo(() => parseQuery(query), [query])

  const facetOptions = useMemo(() => {
    const statuses = [...new Set(machines.map((m) => m.status).filter(Boolean))].sort()
    const owners = [...new Set(machines.map((m) => m.owner || '').filter((x) => x !== undefined))].sort()
    const poolVals = [...new Set([
      ...machines.map((m) => m.pool || 'default'),
      ...pools.map((p) => p.name),
    ])].sort()
    const zoneVals = [...new Set([
      ...machines.map((m) => m.zone || 'default'),
      ...zones.map((z) => z.name),
    ])].sort()
    const tags = [...new Set(machines.flatMap((m) => m.tags || []))].sort()
    return { status: statuses, owner: owners, pool: poolVals, zone: zoneVals, tags }
  }, [machines, pools, zones])

  const filtered = useMemo(() => {
    let rows = machines.filter((m) => machineMatches(m, parsed, facet))
    rows = [...rows].sort((a, b) => {
      const av = sortValue(a, sortKey)
      const bv = sortValue(b, sortKey)
      if (av < bv) return sortDir === 'asc' ? -1 : 1
      if (av > bv) return sortDir === 'asc' ? 1 : -1
      return 0
    })
    return rows
  }, [machines, parsed, facet, sortKey, sortDir])

  useEffect(() => { setPage(0) }, [query, facet, groupBy])

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const pageRows = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

  const grouped = useMemo(() => {
    if (groupBy === 'none') return [{ key: null, rows: pageRows }]
    const map = new Map()
    for (const m of pageRows) {
      const k = groupBy === 'tags'
        ? (m.tags || [])[0] || '(untagged)'
        : (m[groupBy] || (groupBy === 'owner' ? '(unowned)' : 'default'))
      if (!map.has(k)) map.set(k, [])
      map.get(k).push(m)
    }
    return [...map.entries()].map(([key, rows]) => ({ key, rows }))
  }, [pageRows, groupBy])

  const toggleSort = (key) => {
    if (sortKey === key) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    else { setSortKey(key); setSortDir('asc') }
  }

  const allPageIds = pageRows.map((m) => m.id)
  const allSelected = allPageIds.length > 0 && allPageIds.every((id) => selected.has(id))

  const toggleAll = () => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (allSelected) allPageIds.forEach((id) => next.delete(id))
      else allPageIds.forEach((id) => next.add(id))
      return next
    })
  }

  const toggleOne = (id) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const selectedIds = [...selected]
  const runBulk = (action, extra = {}) => {
    if (!selectedIds.length) return
    onBulk?.(action, selectedIds, extra)
  }

  const openDialog = (kind) => {
    setDialogVal('')
    setDialog(kind)
  }

  const confirmDialog = () => {
    if (dialog === 'zone') runBulk('setZone', { zone: dialogVal || 'default' })
    else if (dialog === 'pool') runBulk('setPool', { pool: dialogVal || 'default' })
    else if (dialog === 'tag') runBulk('addTag', { tag: dialogVal || 'lab' })
    else if (dialog === 'add') {
      onAddMachine?.({
        hostname: dialogVal || undefined,
        power_type: 'ipmi',
      })
    }
    setDialog(null)
  }

  return (
    <div>
      <div className="maas-toolbar">
        <h1 className="maas-page-title" style={{ margin: 0, flex: '1 1 auto' }}>Machines</h1>
        <label className="maas-label" style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
          Group
          <select className="maas-select" value={groupBy} onChange={(e) => setGroupBy(e.target.value)}>
            <option value="none">None</option>
            <option value="status">Status</option>
            <option value="owner">Owner</option>
            <option value="pool">Pool</option>
            <option value="zone">Zone</option>
          </select>
        </label>
        <label className="maas-label" style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
          Deploy image
          <select
            className="maas-select"
            value={deployImage}
            onChange={(e) => onDeployImageChange?.(e.target.value)}
          >
            {bootResources.map((r) => (
              <option key={r.name} value={r.name}>{r.name}</option>
            ))}
            {!bootResources.length && <option value="">ubuntu/jammy</option>}
          </select>
        </label>
        <button type="button" className="maas-btn" disabled={busy} onClick={onEnlist}>Enlist</button>
        <button type="button" className="maas-btn maas-btn-positive" disabled={busy} onClick={() => openDialog('add')}>
          <Plus size={14} /> Add hardware
        </button>
        <button type="button" className="maas-btn" onClick={onRefresh}>Refresh</button>
      </div>

      <div className="maas-chips">
        {FACETS.map((f) => (
          <ChipFilter
            key={f.key}
            facet={f}
            values={facetOptions[f.key === 'tags' ? 'tags' : f.key] || []}
            active={f.key === 'tags' ? facet.tag : facet[f.key]}
            onSelect={(v) => setFacet((prev) => ({
              ...prev,
              ...(f.key === 'tags' ? { tag: v } : { [f.key]: v }),
            }))}
          />
        ))}
      </div>

      <div className="maas-toolbar">
        <input
          className="maas-input maas-search"
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter: status:(=ready) pool:default zone: tags:gpu mac:52:54…"
        />
        <span className="maas-page-sub" style={{ margin: 0 }}>
          {filtered.length} machine{filtered.length === 1 ? '' : 's'}
        </span>
      </div>

      {selectedIds.length > 0 && (
        <div className="maas-bulk-bar">
          <span className="maas-bulk-count">{selectedIds.length} selected</span>
          <button type="button" className="maas-btn maas-btn-sm" disabled={busy} onClick={() => runBulk('commission')}>Commission</button>
          <button type="button" className="maas-btn maas-btn-sm" disabled={busy} onClick={() => runBulk('deploy', { boot_resource: deployImage })}>Deploy</button>
          <button type="button" className="maas-btn maas-btn-sm" disabled={busy} onClick={() => runBulk('release')}>Release</button>
          <button type="button" className="maas-btn maas-btn-sm" disabled={busy} onClick={() => runBulk('abort')}>Abort</button>
          <button type="button" className="maas-btn maas-btn-sm" disabled={busy} onClick={() => runBulk('test')}>Test</button>
          <button type="button" className="maas-btn maas-btn-sm" disabled={busy} onClick={() => runBulk('lock')}>
            <Lock size={12} /> Lock
          </button>
          <button type="button" className="maas-btn maas-btn-sm" disabled={busy} onClick={() => runBulk('enterRescue')}>
            <LifeBuoy size={12} /> Enter rescue
          </button>
          <button type="button" className="maas-btn maas-btn-sm" disabled={busy} onClick={() => runBulk('exitRescue')}>
            <LifeBuoy size={12} /> Exit rescue
          </button>
          <button type="button" className="maas-btn maas-btn-sm" disabled={busy} onClick={() => openDialog('zone')}>Set zone</button>
          <button type="button" className="maas-btn maas-btn-sm" disabled={busy} onClick={() => openDialog('pool')}>Set pool</button>
          <button type="button" className="maas-btn maas-btn-sm" disabled={busy} onClick={() => openDialog('tag')}>Add tag</button>
          <button type="button" className="maas-btn maas-btn-sm" disabled={busy} onClick={() => runBulk('markBroken')}>Mark broken</button>
          <button type="button" className="maas-btn maas-btn-sm" disabled={busy} onClick={() => runBulk('markFixed')}>Mark fixed</button>
          <button type="button" className="maas-btn maas-btn-sm maas-btn-negative" disabled={busy} onClick={() => runBulk('delete')}>Delete</button>
          <button type="button" className="maas-btn maas-btn-sm" onClick={() => setSelected(new Set())}>Clear</button>
        </div>
      )}

      <div className="maas-table-wrap">
        <table className="maas-table">
          <thead>
            <tr>
              <th className="no-sort" style={{ width: 36 }}>
                <input type="checkbox" checked={allSelected} onChange={toggleAll} aria-label="Select all" />
              </th>
              {COLUMNS.map((col) => (
                <th key={col.key} onClick={() => toggleSort(col.key)}>
                  {col.label}
                  {sortKey === col.key ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {grouped.map((g) => (
              <Fragment key={g.key ?? '__all'}>
                {g.key != null && (
                  <tr className="maas-group-row">
                    <td colSpan={COLUMNS.length + 1}>{groupBy}: {g.key} ({g.rows.length})</td>
                  </tr>
                )}
                {g.rows.map((m) => {
                  const fqdn = m.fqdn || `${m.hostname}.${m.domain || 'maas'}`
                  return (
                    <tr key={m.id} className={selected.has(m.id) ? 'is-selected' : ''}>
                      <td>
                        <input
                          type="checkbox"
                          checked={selected.has(m.id)}
                          onChange={() => toggleOne(m.id)}
                          aria-label={`Select ${fqdn}`}
                        />
                      </td>
                      <td>
                        <button type="button" className="maas-link-btn" onClick={() => onSelectMachine?.(m.id)}>
                          {fqdn}
                          {m.locked ? ' 🔒' : ''}
                        </button>
                      </td>
                      <td><PowerIcon power={m.power} /></td>
                      <td><MaasStatusBadge status={m.status} /></td>
                      <td>{m.owner || '—'}</td>
                      <td>{m.pool || 'default'}</td>
                      <td>{m.zone || 'default'}</td>
                      <td>{m.cpu_count ?? '—'}</td>
                      <td>{m.ram_gb != null ? `${m.ram_gb} GiB` : '—'}</td>
                      <td>{m.disk_count ?? (m.storage || []).length ?? '—'}</td>
                      <td className="mono">{m.fabric || 'fabric-0'}</td>
                      <td>
                        <div className="maas-tags">
                          {(m.tags || []).map((t) => <span key={t} className="maas-tag">{t}</span>)}
                          {!(m.tags || []).length && '—'}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </Fragment>
            ))}
            {!filtered.length && (
              <tr>
                <td colSpan={COLUMNS.length + 1}>
                  <div className="maas-empty">No machines match this filter.</div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="maas-pagination">
        <span>
          Showing {filtered.length ? page * PAGE_SIZE + 1 : 0}–
          {Math.min((page + 1) * PAGE_SIZE, filtered.length)} of {filtered.length}
        </span>
        <div className="maas-pagination-btns">
          <button type="button" className="maas-btn maas-btn-sm" disabled={page <= 0} onClick={() => setPage((p) => p - 1)}>
            Previous
          </button>
          <span>Page {page + 1} / {pageCount}</span>
          <button type="button" className="maas-btn maas-btn-sm" disabled={page >= pageCount - 1} onClick={() => setPage((p) => p + 1)}>
            Next
          </button>
        </div>
      </div>

      {dialog && (
        <div className="maas-dialog-backdrop" onClick={() => setDialog(null)} role="presentation">
          <div className="maas-dialog" onClick={(e) => e.stopPropagation()} role="dialog">
            <div className="maas-dialog-head">
              {dialog === 'zone' && 'Set zone'}
              {dialog === 'pool' && 'Set resource pool'}
              {dialog === 'tag' && 'Add tag'}
              {dialog === 'add' && 'Add hardware'}
            </div>
            <div className="maas-dialog-body">
              {dialog === 'zone' && (
                <label className="maas-label">
                  Zone
                  <select className="maas-select" value={dialogVal} onChange={(e) => setDialogVal(e.target.value)}>
                    <option value="">default</option>
                    {zones.map((z) => <option key={z.name} value={z.name}>{z.name}</option>)}
                  </select>
                </label>
              )}
              {dialog === 'pool' && (
                <label className="maas-label">
                  Pool
                  <select className="maas-select" value={dialogVal} onChange={(e) => setDialogVal(e.target.value)}>
                    <option value="">default</option>
                    {pools.map((p) => <option key={p.name} value={p.name}>{p.name}</option>)}
                  </select>
                </label>
              )}
              {dialog === 'tag' && (
                <label className="maas-label">
                  Tag name
                  <input className="maas-input" value={dialogVal} onChange={(e) => setDialogVal(e.target.value)} placeholder="gpu" />
                </label>
              )}
              {dialog === 'add' && (
                <label className="maas-label">
                  Hostname
                  <input className="maas-input" value={dialogVal} onChange={(e) => setDialogVal(e.target.value)} placeholder="node-04" />
                </label>
              )}
            </div>
            <div className="maas-dialog-foot">
              <button type="button" className="maas-btn" onClick={() => setDialog(null)}>Cancel</button>
              <button type="button" className="maas-btn maas-btn-positive" disabled={busy} onClick={confirmDialog}>
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
