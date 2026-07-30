/**
 * Shared global search omnibox for lab consoles (Azure/GCP/SOC/DC/storage).
 * Groups: Services · Resources · Recent. Keyboard: / or Alt+S, arrows, Enter, Esc.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Search } from 'lucide-react'

/**
 * @typedef {{ type: 'service'|'resource'|'recent', id: string, label: string, sub?: string, navKey?: string, meta?: object }} SearchHit
 */

/**
 * @param {object} opts
 * @param {Array<{key:string,label:string,keywords?:string}>} opts.services
 * @param {SearchHit[]} opts.resources
 * @param {SearchHit[]} [opts.recents]
 * @param {string} query
 * @param {number} [serviceLimit]
 * @param {number} [resourceLimit]
 */
export function filterSearchIndex({ services = [], resources = [], recents = [] }, query, serviceLimit = 6, resourceLimit = 8) {
  const q = (query || '').trim().toLowerCase()
  if (!q) {
    return {
      services: [],
      resources: [],
      recents: (recents || []).slice(0, 6),
    }
  }
  const match = (hay) => String(hay || '').toLowerCase().includes(q)
  return {
    services: services
      .filter((s) => match(s.label) || match(s.key) || match(s.keywords))
      .slice(0, serviceLimit)
      .map((s) => ({ type: 'service', id: s.key, label: s.label, sub: 'Service', navKey: s.key })),
    resources: resources
      .filter((r) => match(r.hay || `${r.label} ${r.id} ${r.sub}`))
      .slice(0, resourceLimit),
    recents: [],
  }
}

/** Flatten common Azure portal state into searchable resource hits. */
export function indexAzureState(st) {
  const rows = []
  const push = (list, kind, navKey, nameKey = 'name') => {
    ;(list || []).forEach((row) => {
      if (!row || typeof row !== 'object') return
      const name = row[nameKey] || row.id || row.name
      if (!name) return
      rows.push({
        type: 'resource',
        id: String(row.id || name),
        label: String(name),
        sub: `${kind}${row.location ? ` · ${row.location}` : ''}${row.resource_group ? ` · ${row.resource_group}` : ''}`,
        navKey,
        hay: `${name} ${row.id || ''} ${row.location || ''} ${row.resource_group || ''} ${kind}`,
        meta: row,
      })
    })
  }
  push(st?.vms, 'Virtual machine', 'vms')
  push(st?.vmss, 'Scale set', 'vmss')
  push(st?.web_apps, 'App Service', 'appservice')
  push(st?.function_apps, 'Function app', 'functions')
  push(st?.container_apps, 'Container app', 'containerapps')
  push(st?.aks_clusters, 'AKS cluster', 'aks')
  push(st?.vnets, 'Virtual network', 'networking')
  push(st?.nsgs, 'Network security group', 'networking')
  push(st?.load_balancers, 'Load balancer', 'loadbalancers')
  push(st?.firewalls, 'Firewall', 'firewall')
  push(st?.vpn_gateways, 'VPN gateway', 'firewall')
  push(st?.disks, 'Disk', 'disks')
  push(st?.storage_accounts, 'Storage account', 'storage')
  push(st?.cosmos_accounts, 'Cosmos DB', 'cosmos')
  push(st?.key_vaults, 'Key vault', 'keyvault')
  push(st?.resource_groups, 'Resource group', 'overview')
  push(st?.public_ips, 'Public IP', 'overview')
  return rows
}

/** Flatten common GCP console state into searchable resource hits. */
export function indexGcpState(st) {
  const rows = []
  const push = (list, kind, navKey, nameKey = 'name') => {
    ;(list || []).forEach((row) => {
      if (!row || typeof row !== 'object') return
      const name = row[nameKey] || row.id || row.name
      if (!name) return
      rows.push({
        type: 'resource',
        id: String(row.id || name),
        label: String(name),
        sub: `${kind}${row.zone || row.region || row.location ? ` · ${row.zone || row.region || row.location}` : ''}`,
        navKey,
        hay: `${name} ${row.id || ''} ${row.zone || ''} ${row.region || ''} ${row.location || ''} ${kind}`,
        meta: row,
      })
    })
  }
  push(st?.instances || st?.vms, 'VM instance', 'instances')
  push(st?.disks, 'Persistent disk', 'disks')
  push(st?.gke_clusters || st?.clusters, 'GKE cluster', 'gke')
  push(st?.buckets, 'Storage bucket', 'storage', 'name')
  push(st?.sql_instances || st?.cloud_sql, 'Cloud SQL', 'sql')
  push(st?.spanner_instances, 'Spanner', 'spanner')
  push(st?.bigquery_datasets, 'BigQuery dataset', 'bigquery')
  push(st?.networks || st?.vpcs, 'VPC network', 'networking')
  push(st?.firewalls || st?.firewall_rules, 'Firewall rule', 'networking')
  push(st?.load_balancers, 'Load balancer', 'lb')
  push(st?.run_services || st?.cloud_run, 'Cloud Run', 'run')
  push(st?.functions || st?.cloud_functions, 'Cloud Function', 'functions')
  push(st?.topics || st?.pubsub_topics, 'Pub/Sub topic', 'pubsub')
  push(st?.secrets, 'Secret', 'secrets')
  push(st?.service_accounts, 'Service account', 'iam')
  return rows
}

/** Flatten datacenter twin state. */
export function indexDatacenterState(st) {
  const rows = []
  ;(st?.racks || []).forEach((r) => {
    rows.push({
      type: 'resource', id: r.id, label: r.id,
      sub: `Rack · ${r.row || ''}`.trim(),
      navKey: 'floor',
      hay: `${r.id} rack ${r.row || ''}`,
      meta: r,
    })
  })
  ;(st?.servers || []).forEach((s) => {
    rows.push({
      type: 'resource', id: s.id, label: s.hostname || s.id,
      sub: `Server · ${s.rack_id || s.rack || ''} · ${s.vendor || ''}`.trim(),
      navKey: 'floor',
      hay: `${s.hostname || ''} ${s.id} ${s.rack_id || ''} ${s.rack || ''} ${s.vendor || ''} ${s.model || ''}`,
      meta: s,
    })
  })
  ;(st?.rooms || []).forEach((r) => {
    rows.push({
      type: 'resource', id: r.id, label: r.name || r.id,
      sub: `Room · ${r.type || ''}`,
      navKey: 'rooms',
      hay: `${r.name || ''} ${r.id} ${r.type || ''}`,
      meta: r,
    })
  })
  return rows
}

/** Flatten SOC state. */
export function indexSocState(st) {
  const rows = []
  ;(st?.alerts || []).forEach((a) => {
    rows.push({
      type: 'resource', id: a.id, label: a.title || a.id,
      sub: `Alert · ${a.severity || ''} · ${a.status || ''}`,
      navKey: 'alerts',
      hay: `${a.id} ${a.title || ''} ${a.severity || ''} ${a.source || ''} ${a.asset || ''}`,
      meta: a,
    })
  })
  ;(st?.incidents || []).forEach((inc) => {
    rows.push({
      type: 'resource', id: inc.id, label: inc.title || inc.id,
      sub: `Incident · ${inc.severity || ''} · ${inc.status || ''}`,
      navKey: 'incidents',
      hay: `${inc.id} ${inc.title || ''} ${inc.severity || ''}`,
      meta: inc,
    })
  })
  ;(st?.assets || st?.endpoints || []).forEach((ep) => {
    rows.push({
      type: 'resource', id: ep.id || ep.hostname, label: ep.hostname || ep.id,
      sub: `Asset · ${ep.os || ''} · ${ep.ip || ''}`,
      navKey: 'assets',
      hay: `${ep.hostname || ''} ${ep.id || ''} ${ep.ip || ''} ${ep.os || ''}`,
      meta: ep,
    })
  })
  ;(st?.iocs || []).forEach((ioc) => {
    rows.push({
      type: 'resource', id: ioc.id || ioc.value, label: ioc.value || ioc.id,
      sub: `IoC · ${ioc.type || ''}`,
      navKey: 'threat-intel',
      hay: `${ioc.value || ''} ${ioc.type || ''} ${ioc.id || ''}`,
      meta: ioc,
    })
  })
  return rows
}

/**
 * Shared omnibox. `variant`: 'light' | 'dark'
 * @param {{
 *  services?: Array<{key:string,label:string,keywords?:string}>,
 *  resources?: import('./GlobalSearch').SearchHit[],
 *  recents?: import('./GlobalSearch').SearchHit[],
 *  placeholder?: string,
 *  variant?: 'light'|'dark',
 *  onSelect: (hit: SearchHit) => void,
 *  className?: string,
 * }} props
 */
export default function GlobalSearch({
  services = [],
  resources = [],
  recents = [],
  placeholder = 'Search resources, services…',
  variant = 'dark',
  onSelect,
  className = '',
}) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [activeIdx, setActiveIdx] = useState(0)
  const inputRef = useRef(null)
  const rootRef = useRef(null)

  const grouped = useMemo(
    () => filterSearchIndex({ services, resources, recents }, query),
    [services, resources, recents, query],
  )
  const flat = useMemo(
    () => [...grouped.services, ...grouped.resources, ...grouped.recents],
    [grouped],
  )

  useEffect(() => { setActiveIdx(0) }, [query])

  useEffect(() => {
    const onKey = (e) => {
      const tag = document.activeElement?.tagName
      const typing = tag === 'INPUT' || tag === 'TEXTAREA' || document.activeElement?.isContentEditable
      if (((e.key === '/' && !typing) || (e.altKey && (e.key === 's' || e.key === 'S')))) {
        e.preventDefault()
        inputRef.current?.focus()
        setOpen(true)
      } else if (e.key === 'Escape') {
        setOpen(false)
        if (document.activeElement === inputRef.current) inputRef.current.blur()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    const onDoc = (e) => {
      if (!rootRef.current?.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  const pick = useCallback((hit) => {
    if (!hit) return
    setOpen(false)
    setQuery('')
    onSelect?.(hit)
  }, [onSelect])

  const onKeyDown = (e) => {
    if (!flat.length) return
    if (e.key === 'ArrowDown') { e.preventDefault(); setActiveIdx((i) => Math.min(flat.length - 1, i + 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActiveIdx((i) => Math.max(0, i - 1)) }
    else if (e.key === 'Enter') { e.preventDefault(); pick(flat[activeIdx]) }
  }

  const light = variant === 'light'
  const showPanel = open && (query.trim() || grouped.recents.length > 0)

  return (
    <div ref={rootRef} className={`sim-global-search ${light ? 'sim-global-search-light' : ''} ${className}`.trim()}>
      <Search size={14} className="sim-global-search-icon" aria-hidden />
      <input
        ref={inputRef}
        value={query}
        onChange={(e) => { setQuery(e.target.value); setOpen(true) }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
        placeholder={placeholder}
        aria-label={placeholder}
        className="sim-global-search-input"
      />
      {showPanel && (
        <div className="sim-global-search-panel" role="listbox">
          {!query.trim() && grouped.recents.length > 0 && (
            <Section title="Recent" items={grouped.recents} activeIdx={activeIdx} flat={flat} onPick={pick} />
          )}
          {query.trim() && flat.length === 0 && (
            <div className="sim-global-search-empty">No results for “{query.trim()}”</div>
          )}
          {grouped.services.length > 0 && (
            <Section title="Services" items={grouped.services} activeIdx={activeIdx} flat={flat} onPick={pick} />
          )}
          {grouped.resources.length > 0 && (
            <Section title="Resources" items={grouped.resources} activeIdx={activeIdx} flat={flat} onPick={pick} />
          )}
        </div>
      )}
    </div>
  )
}

function Section({ title, items, activeIdx, flat, onPick }) {
  return (
    <div className="sim-global-search-section">
      <div className="sim-global-search-heading">{title}</div>
      {items.map((hit) => {
        const idx = flat.indexOf(hit)
        return (
          <button
            key={`${hit.type}-${hit.id}-${hit.navKey || ''}`}
            type="button"
            role="option"
            aria-selected={idx === activeIdx}
            className={`sim-global-search-item ${idx === activeIdx ? 'is-active' : ''}`}
            onClick={() => onPick(hit)}
          >
            <span className="sim-global-search-label">{hit.label}</span>
            {hit.sub && <span className="sim-global-search-sub">{hit.sub}</span>}
          </button>
        )
      })}
    </div>
  )
}
