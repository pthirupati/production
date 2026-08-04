import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Menu, Search, ChevronDown, Bell, Settings, Terminal as TerminalIcon, Globe, Moon, Sun,
  Grid3x3, X, Star, Clock, Server, Database, Shield, Network, Activity, Box, Boxes, Workflow,
  CheckCircle2, AlertTriangle, Info,
} from 'lucide-react'
import { useAwsStore } from '../store/awsStore'
import { AWS_REGIONS, REGION_GEO_ORDER, regionName } from '../lib/regions'
import { SERVICES, SERVICE_CATEGORIES, BASE } from './serviceNav'
import AwsLabsMenu from './AwsLabsMenu'

function AwsLogo() {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'flex-end', gap: 2, fontWeight: 700, fontSize: 18, letterSpacing: '-0.5px' }}>
      <span style={{ color: '#fff' }}>aws</span>
      <span style={{ color: 'var(--aws-orange)', fontSize: 16, lineHeight: 1 }}>﹀</span>
    </span>
  )
}

// Compact category -> icon map so favorites / recently-visited / mega-menu can
// show a glyph without a per-service icon table.
const CATEGORY_ICON = {
  Compute: Server,
  Containers: Boxes,
  Storage: Database,
  Database: Database,
  'Networking & Content Delivery': Network,
  'Security, Identity & Compliance': Shield,
  'Management & Governance': Activity,
  'Application Integration': Workflow,
}
function serviceIcon(svc) {
  if (svc?.key === 'ec2') return Server
  if (svc?.key === 's3') return Database
  if (svc?.key === 'iam') return Shield
  if (svc?.key === 'vpc') return Network
  if (svc?.key === 'cloudwatch') return Activity
  return CATEGORY_ICON[svc?.category] || Box
}

const SERVICE_BY_KEY = Object.fromEntries(SERVICES.map((s) => [s.key, s]))

// "Features" are common sub-pages inside a service — matched by the top search.
const FEATURES = [
  { name: 'EC2 Instances', service: 'ec2', path: `${BASE}/ec2/instances`, keywords: 'instance server vm' },
  { name: 'Launch instance', service: 'ec2', path: `${BASE}/ec2/launch`, keywords: 'create ec2 launch' },
  { name: 'Security Groups', service: 'ec2', path: `${BASE}/ec2/security-groups`, keywords: 'firewall sg' },
  { name: 'Key Pairs', service: 'ec2', path: `${BASE}/ec2/key-pairs`, keywords: 'ssh key' },
  { name: 'Volumes (EBS)', service: 'ec2', path: `${BASE}/ec2/volumes`, keywords: 'disk storage ebs' },
  { name: 'Elastic IPs', service: 'ec2', path: `${BASE}/ec2/elastic-ips`, keywords: 'ip address' },
  { name: 'S3 Buckets', service: 's3', path: `${BASE}/s3`, keywords: 'bucket object storage' },
  { name: 'IAM Users', service: 'iam', path: `${BASE}/iam/users`, keywords: 'user identity' },
  { name: 'IAM Roles', service: 'iam', path: `${BASE}/iam/roles`, keywords: 'role assume' },
  { name: 'IAM Policies', service: 'iam', path: `${BASE}/iam/policies`, keywords: 'policy permission' },
  { name: 'VPCs', service: 'vpc', path: `${BASE}/vpc/vpcs`, keywords: 'network vpc' },
  { name: 'Subnets', service: 'vpc', path: `${BASE}/vpc/subnets`, keywords: 'subnet cidr' },
  { name: 'CloudWatch Alarms', service: 'cloudwatch', path: `${BASE}/cloudwatch/alarms`, keywords: 'alarm alert metric' },
]

// Build a flat, searchable index of live store resources (id/name/tag).
function useResourceIndex() {
  const instances = useAwsStore((s) => s.instances)
  const buckets = useAwsStore((s) => s.s3Buckets)
  const vpcs = useAwsStore((s) => s.vpcs)
  const securityGroups = useAwsStore((s) => s.securityGroups)
  const iamUsers = useAwsStore((s) => s.iamUsers)
  const iamRoles = useAwsStore((s) => s.iamRoles)
  const genericResources = useAwsStore((s) => s.genericResources)

  return useMemo(() => {
    const rows = []
    const tagText = (t) => Object.entries(t || {}).map(([k, v]) => `${k}=${v}`).join(' ')
    const objs = (list) => (list || []).filter((x) => x && typeof x === 'object')
    objs(instances).forEach((i) => rows.push({ kind: 'EC2 instance', id: i.id, name: i.name || i.id, hay: `${i.id} ${i.name} ${tagText(i.tags)}`, path: `${BASE}/ec2/instances/${i.id}` }))
    objs(buckets).forEach((b) => rows.push({ kind: 'S3 bucket', id: b.name, name: b.name, hay: b.name, path: `${BASE}/s3/buckets/${encodeURIComponent(b.name)}` }))
    objs(vpcs).forEach((v) => rows.push({ kind: 'VPC', id: v.id, name: v.name || v.id, hay: `${v.id} ${v.name} ${v.cidr}`, path: `${BASE}/vpc/vpcs` }))
    objs(securityGroups).forEach((g) => rows.push({ kind: 'Security group', id: g.id, name: g.name, hay: `${g.id} ${g.name} ${g.description}`, path: `${BASE}/ec2/security-groups` }))
    objs(iamUsers).forEach((u) => rows.push({ kind: 'IAM user', id: u.name, name: u.name, hay: u.name, path: `${BASE}/iam/users` }))
    objs(iamRoles).forEach((r) => rows.push({ kind: 'IAM role', id: r.name, name: r.name, hay: r.name, path: `${BASE}/iam/roles` }))
    Object.entries(genericResources || {}).forEach(([svc, resources]) => {
      Object.entries(resources || {}).forEach(([res, list]) => {
        objs(list).forEach((row) => {
          if (!row.id) return
          rows.push({
            kind: `${SERVICE_BY_KEY[svc]?.name || svc}`,
            id: row.id, name: row.name || row.id,
            hay: `${row.id} ${row.name} ${tagText(row.tags)}`,
            path: `${BASE}/${svc}/${res}/${encodeURIComponent(row.id)}`,
          })
        })
      })
    })
    return rows
  }, [instances, buckets, vpcs, securityGroups, iamUsers, iamRoles, genericResources])
}

export default function TopNav({ onToggleSidebar, onToggleCloudShell }) {
  const navigate = useNavigate()
  const region = useAwsStore((s) => s.region)
  const setRegion = useAwsStore((s) => s.setRegion)
  const account = useAwsStore((s) => s.account) || { id: '123456789012', alias: 'my-aws-lab', email: 'admin@example.com' }
  const darkMode = useAwsStore((s) => s.darkMode)
  const toggleDark = useAwsStore((s) => s.toggleDarkMode)
  const alarms = useAwsStore((s) => s.cwAlarms) || []
  const favorites = useAwsStore((s) => s.favorites) || []
  const recentServices = useAwsStore((s) => s.recentServices) || []
  const toggleFavorite = useAwsStore((s) => s.toggleFavorite)
  const pushRecentService = useAwsStore((s) => s.pushRecentService)
  const settings = useAwsStore((s) => s.settings) || {}
  const updateSettings = useAwsStore((s) => s.updateSettings)

  const [openMenu, setOpenMenu] = useState(null) // 'services' | 'region' | 'account' | 'search' | 'notifications'
  const [query, setQuery] = useState('')
  const [megaQuery, setMegaQuery] = useState('')
  const [regionQuery, setRegionQuery] = useState('')
  const [activeIdx, setActiveIdx] = useState(0)
  const searchRef = useRef(null)
  const resourceIndex = useResourceIndex()

  // Global shortcuts: "/" or Alt+S focuses search; Escape closes any open menu.
  useEffect(() => {
    const onKey = (e) => {
      const tag = document.activeElement?.tagName
      const typing = tag === 'INPUT' || tag === 'TEXTAREA' || document.activeElement?.isContentEditable
      if (((e.key === '/' && !typing) || (e.altKey && (e.key === 's' || e.key === 'S')))) {
        e.preventDefault()
        searchRef.current?.focus()
        setOpenMenu('search')
      } else if (e.key === 'Escape') {
        setOpenMenu(null)
        if (typing && document.activeElement === searchRef.current) searchRef.current.blur()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const close = () => setOpenMenu(null)
  const go = (path, serviceKey) => {
    close()
    setQuery('')
    setMegaQuery('')
    if (serviceKey) pushRecentService(serviceKey)
    navigate(path)
  }

  // Unified top search, grouped into Services / Features / Resources.
  const q = query.trim().toLowerCase()
  const grouped = useMemo(() => {
    if (!q) return { services: [], features: [], resources: [] }
    const services = SERVICES
      .filter((s) => s.built && (s.name.toLowerCase().includes(q) || s.desc.toLowerCase().includes(q) || s.key.includes(q)))
      .slice(0, 6)
      .map((s) => ({ type: 'service', label: s.name, sub: s.desc, path: s.path, serviceKey: s.key }))
    const features = FEATURES
      .filter((f) => f.name.toLowerCase().includes(q) || f.keywords.includes(q))
      .slice(0, 6)
      .map((f) => ({ type: 'feature', label: f.name, sub: SERVICE_BY_KEY[f.service]?.name, path: f.path, serviceKey: f.service }))
    const resources = resourceIndex
      .filter((r) => r.hay.toLowerCase().includes(q))
      .slice(0, 8)
      .map((r) => ({ type: 'resource', label: r.name, sub: `${r.kind} · ${r.id}`, path: r.path }))
    return { services, features, resources }
  }, [q, resourceIndex])

  const flatResults = [...grouped.services, ...grouped.features, ...grouped.resources]
  useEffect(() => { setActiveIdx(0) }, [q])

  const onSearchKey = (e) => {
    if (!flatResults.length) return
    if (e.key === 'ArrowDown') { e.preventDefault(); setActiveIdx((i) => Math.min(flatResults.length - 1, i + 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActiveIdx((i) => Math.max(0, i - 1)) }
    else if (e.key === 'Enter') {
      e.preventDefault()
      const hit = flatResults[activeIdx]
      if (hit) go(hit.path, hit.serviceKey)
    }
  }

  const inAlarm = alarms.filter((a) => a && a.state === 'ALARM').length
  const favServices = favorites.map((k) => SERVICE_BY_KEY[k]).filter(Boolean)
  const recentServiceObjs = recentServices.map((k) => SERVICE_BY_KEY[k]).filter(Boolean)

  // Region dropdown: filter + recently-used group (persisted in settings.recentRegions).
  const recentRegions = (settings.recentRegions || []).map((c) => AWS_REGIONS.find((r) => r.code === c)).filter(Boolean)
  const chooseRegion = (code) => {
    setRegion(code)
    const next = [code, ...(settings.recentRegions || []).filter((c) => c !== code)].slice(0, 4)
    updateSettings({ recentRegions: next, region: code })
    setRegionQuery('')
    close()
  }
  const rq = regionQuery.trim().toLowerCase()
  const regionMatches = (r) => r.name.toLowerCase().includes(rq) || r.code.includes(rq)

  const notifications = [
    ...alarms.filter((a) => a && a.state === 'ALARM').map((a) => ({ type: 'error', title: `Alarm: ${a.name}`, body: `${a.metric} ${a.threshold}` })),
    { type: 'success', title: 'Welcome to the AWS Management Console', body: 'Explore services, launch resources, and complete guided labs.' },
    { type: 'info', title: 'Free tier usage', body: 'You are within Free Tier limits this month.' },
  ]
  const notifIcon = { error: AlertTriangle, success: CheckCircle2, info: Info }

  return (
    <div className="aws-topnav">
      <button className="aws-topnav-btn" onClick={onToggleSidebar} title="Toggle navigation"><Menu size={18} /></button>
      <button className="aws-topnav-btn" onClick={() => go(`${BASE}/console/home`)}><AwsLogo /></button>
      <button className="aws-topnav-btn" onClick={() => setOpenMenu(openMenu === 'services' ? null : 'services')}>
        <Grid3x3 size={15} /> Services <ChevronDown size={13} />
      </button>
      <AwsLabsMenu />

      {/* Unified search: Services / Features / Resources */}
      <div style={{ position: 'relative', flex: 1, maxWidth: 480, margin: '0 8px' }}>
        <Search size={15} style={{ position: 'absolute', left: 10, top: 8, color: '#8b96a5' }} />
        <input
          ref={searchRef}
          value={query}
          onChange={(e) => { setQuery(e.target.value); setOpenMenu('search') }}
          onFocus={() => setOpenMenu('search')}
          onKeyDown={onSearchKey}
          placeholder="Search for services, features, and resources [Alt+S]"
          style={{ width: '100%', height: 32, background: '#1b2532', border: '1px solid #37475a', borderRadius: 2, color: '#fff', padding: '0 10px 0 30px', fontSize: 13 }}
        />
        {openMenu === 'search' && q && flatResults.length > 0 && (
          <div className="aws-topnav-dropdown" style={{ position: 'absolute', top: 36, left: 0, right: 0, background: 'var(--aws-content-bg)', borderRadius: 4, boxShadow: 'var(--aws-shadow-lg)', maxHeight: 420, overflowY: 'auto', zIndex: 300, border: '1px solid var(--aws-border)' }}>
            {[
              ['Services', grouped.services],
              ['Features', grouped.features],
              ['Resources', grouped.resources],
            ].map(([label, items]) => {
              if (!items.length) return null
              return (
                <div key={label}>
                  <div style={{ padding: '8px 12px 4px', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: 'var(--aws-text-secondary)' }}>{label}</div>
                  {items.map((it) => {
                    const idx = flatResults.indexOf(it)
                    const active = idx === activeIdx
                    return (
                      <div
                        key={`${it.type}-${it.label}-${it.sub}`}
                        onMouseDown={(e) => e.preventDefault()}
                        onMouseEnter={() => setActiveIdx(idx)}
                        onClick={() => go(it.path, it.serviceKey)}
                        style={{ padding: '8px 12px', cursor: 'pointer', background: active ? 'var(--aws-sidebar-active-bg)' : 'transparent' }}
                      >
                        <div style={{ fontWeight: 600, color: 'var(--aws-text-link)' }}>{it.label}</div>
                        {it.sub && <div style={{ fontSize: 12, color: 'var(--aws-text-secondary)' }}>{it.sub}</div>}
                      </div>
                    )
                  })}
                </div>
              )
            })}
          </div>
        )}
        {openMenu === 'search' && q && flatResults.length === 0 && (
          <div className="aws-topnav-dropdown" style={{ position: 'absolute', top: 36, left: 0, right: 0, background: 'var(--aws-content-bg)', borderRadius: 4, boxShadow: 'var(--aws-shadow-lg)', zIndex: 300, border: '1px solid var(--aws-border)', padding: '14px 12px', color: 'var(--aws-text-secondary)', fontSize: 13 }}>
            No matches for &quot;{query}&quot;
          </div>
        )}
      </div>

      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 4 }}>
        <button className="aws-topnav-btn" onClick={onToggleCloudShell} title="CloudShell"><TerminalIcon size={16} /></button>

        {/* Notifications bell */}
        <div style={{ position: 'relative' }}>
          <button className="aws-topnav-btn" title="Notifications" style={{ position: 'relative' }} onClick={() => setOpenMenu(openMenu === 'notifications' ? null : 'notifications')}>
            <Bell size={16} />
            {inAlarm > 0 && <span style={{ position: 'absolute', top: 2, right: 2, background: 'var(--aws-error)', color: '#fff', borderRadius: 8, fontSize: 9, padding: '0 4px' }}>{inAlarm}</span>}
          </button>
          {openMenu === 'notifications' && (
            <div className="aws-topnav-dropdown" style={{ position: 'absolute', top: 38, right: 0, width: 340, maxHeight: 420, overflowY: 'auto', background: 'var(--aws-content-bg)', borderRadius: 4, boxShadow: 'var(--aws-shadow-lg)', color: 'var(--aws-text-primary)', zIndex: 300, border: '1px solid var(--aws-border)' }}>
              <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--aws-border-light)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontWeight: 700 }}>Notifications</span>
                <a onClick={() => go(`${BASE}/cloudwatch/alarms`, 'cloudwatch')} style={{ fontSize: 12 }}>View alarms</a>
              </div>
              {notifications.map((n, i) => {
                const NIcon = notifIcon[n.type] || Info
                const color = n.type === 'error' ? 'var(--aws-error)' : n.type === 'success' ? 'var(--aws-success)' : 'var(--aws-info)'
                return (
                  <div key={i} style={{ padding: '10px 14px', borderBottom: '1px solid var(--aws-border-light)', display: 'flex', gap: 10 }}>
                    <NIcon size={16} style={{ color, flexShrink: 0, marginTop: 2 }} />
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600 }}>{n.title}</div>
                      <div style={{ fontSize: 12, color: 'var(--aws-text-secondary)' }}>{n.body}</div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        <button className="aws-topnav-btn" onClick={toggleDark} title="Toggle theme">{darkMode ? <Sun size={16} /> : <Moon size={16} />}</button>

        {/* Region selector with filter + recently-used */}
        <div style={{ position: 'relative' }}>
          <button className="aws-topnav-btn" onClick={() => setOpenMenu(openMenu === 'region' ? null : 'region')}>
            <Globe size={15} /> {regionName(region)} <ChevronDown size={13} />
          </button>
          {openMenu === 'region' && (
            <div className="aws-topnav-dropdown" style={{ position: 'absolute', top: 38, right: 0, width: 360, maxHeight: 480, overflowY: 'auto', background: 'var(--aws-content-bg)', borderRadius: 4, boxShadow: 'var(--aws-shadow-lg)', color: 'var(--aws-text-primary)', zIndex: 300, border: '1px solid var(--aws-border)' }}>
              <div style={{ padding: 10, borderBottom: '1px solid var(--aws-border-light)', position: 'sticky', top: 0, background: 'var(--aws-content-bg)' }}>
                <div style={{ position: 'relative' }}>
                  <Search size={14} style={{ position: 'absolute', left: 8, top: 9, color: 'var(--aws-text-muted)' }} />
                  <input className="aws-input" autoFocus style={{ paddingLeft: 28, height: 30 }} placeholder="Filter regions" value={regionQuery} onChange={(e) => setRegionQuery(e.target.value)} />
                </div>
              </div>
              {!rq && recentRegions.length > 0 && (
                <div>
                  <div style={{ padding: '8px 14px 2px', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: 'var(--aws-text-secondary)' }}>Recently used</div>
                  {recentRegions.map((r) => (
                    <div key={`recent-${r.code}`} onClick={() => chooseRegion(r.code)} style={{ padding: '7px 14px', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', background: r.code === region ? 'var(--aws-sidebar-active-bg)' : undefined }}>
                      <span>{r.flag} {r.name}</span>
                      <span className="aws-mono" style={{ color: 'var(--aws-text-secondary)', fontSize: 12 }}>{r.code}</span>
                    </div>
                  ))}
                </div>
              )}
              {REGION_GEO_ORDER.map((geo) => {
                const list = AWS_REGIONS.filter((r) => r.geo === geo && regionMatches(r))
                if (!list.length) return null
                return (
                  <div key={geo}>
                    <div style={{ padding: '8px 14px 2px', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: 'var(--aws-text-secondary)' }}>{geo}</div>
                    {list.map((r) => (
                      <div key={r.code} onClick={() => chooseRegion(r.code)} style={{ padding: '7px 14px', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', background: r.code === region ? 'var(--aws-sidebar-active-bg)' : undefined }}>
                        <span>{r.flag} {r.name}</span>
                        <span className="aws-mono" style={{ color: 'var(--aws-text-secondary)', fontSize: 12 }}>{r.code}</span>
                      </div>
                    ))}
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Account */}
        <div style={{ position: 'relative' }}>
          <button className="aws-topnav-btn" onClick={() => setOpenMenu(openMenu === 'account' ? null : 'account')}>
            {account.alias} <ChevronDown size={13} />
          </button>
          {openMenu === 'account' && (
            <div className="aws-topnav-dropdown" style={{ position: 'absolute', top: 38, right: 0, width: 280, background: 'var(--aws-content-bg)', borderRadius: 4, boxShadow: 'var(--aws-shadow-lg)', color: 'var(--aws-text-primary)', zIndex: 300, padding: 8, border: '1px solid var(--aws-border)' }}>
              <div style={{ padding: 8, borderBottom: '1px solid var(--aws-border-light)' }}>
                <div style={{ fontWeight: 700 }}>{account.alias}</div>
                <div className="aws-mono" style={{ fontSize: 12, color: 'var(--aws-text-secondary)' }}>{account.id}</div>
              </div>
              {[
                { label: 'Account', path: `${BASE}/console/home` },
                { label: 'Organization', path: `${BASE}/organizations/home` },
                { label: 'Service Quotas', path: `${BASE}/servicequotas/home` },
                { label: 'Billing Dashboard', path: `${BASE}/billing/home` },
                { label: 'Settings', path: `${BASE}/console/settings` },
                { label: 'Security credentials', path: `${BASE}/iam/home` },
              ].map(({ label, path }) => (
                <div key={label} onClick={() => go(path)} style={{ padding: '7px 8px', cursor: 'pointer' }}>{label}</div>
              ))}
              <div style={{ borderTop: '1px solid var(--aws-border-light)', padding: '7px 8px', cursor: 'pointer', color: 'var(--aws-text-link)' }}>Sign out</div>
            </div>
          )}
        </div>
        <button className="aws-topnav-btn" title="Settings" onClick={() => go(`${BASE}/console/settings`)}><Settings size={16} /></button>
      </div>

      {/* Favorites bar (below the top row) */}
      {favServices.length > 0 && (
        <div className="aws-favbar">
          <Star size={12} fill="var(--aws-orange)" color="var(--aws-orange)" />
          {favServices.map((s) => {
            const Icon = serviceIcon(s)
            return (
              <button key={s.key} className="aws-favbar-item" onClick={() => go(s.path, s.key)} title={s.desc}>
                <Icon size={13} /> {s.name}
              </button>
            )
          })}
        </div>
      )}

      {/* Services mega-menu: in-panel search + Recently-visited column + star-to-favorite */}
      {openMenu === 'services' && (
        <div style={{ position: 'fixed', top: 48, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.4)', zIndex: 250 }} onClick={close}>
          <div onClick={(e) => e.stopPropagation()} className="aws-topnav-dropdown" style={{ background: 'var(--aws-content-bg)', maxHeight: '80vh', overflowY: 'auto', padding: 20, borderBottom: '1px solid var(--aws-border)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, gap: 16 }}>
              <h2 style={{ color: 'var(--aws-text-primary)' }}>Services</h2>
              <div style={{ position: 'relative', flex: 1, maxWidth: 360 }}>
                <Search size={15} style={{ position: 'absolute', left: 10, top: 9, color: 'var(--aws-text-muted)' }} />
                <input className="aws-input" autoFocus style={{ paddingLeft: 30 }} placeholder="Search services" value={megaQuery} onChange={(e) => setMegaQuery(e.target.value)} />
              </div>
              <button className="aws-copy-btn" onClick={close}><X size={18} /></button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: 24 }}>
              {/* Recently-visited column */}
              <div>
                <div style={{ fontWeight: 700, color: 'var(--aws-text-primary)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}><Clock size={14} /> Recently visited</div>
                {recentServiceObjs.length === 0 && <div style={{ fontSize: 12, color: 'var(--aws-text-secondary)' }}>Services you open will appear here.</div>}
                {recentServiceObjs.map((s) => {
                  const Icon = serviceIcon(s)
                  return (
                    <div key={s.key} onClick={() => go(s.path, s.key)} style={{ padding: '6px 0', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Icon size={15} style={{ color: 'var(--aws-text-secondary)' }} />
                      <span style={{ color: 'var(--aws-text-link)', fontWeight: 600 }}>{s.name}</span>
                    </div>
                  )
                })}
              </div>

              {/* Categorized services with star-to-favorite */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 20 }}>
                {SERVICE_CATEGORIES.map((cat) => {
                  const mq = megaQuery.trim().toLowerCase()
                  const items = SERVICES.filter((s) => s.category === cat && (!mq || s.name.toLowerCase().includes(mq) || s.desc.toLowerCase().includes(mq)))
                  if (!items.length) return null
                  return (
                    <div key={cat}>
                      <div style={{ fontWeight: 700, color: 'var(--aws-text-primary)', marginBottom: 6 }}>{cat}</div>
                      {items.map((s) => {
                        const fav = favorites.includes(s.key)
                        return (
                          <div key={s.key} className="aws-mega-item" style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 0' }}>
                            <button
                              className="aws-copy-btn"
                              title={fav ? 'Remove from favorites' : 'Add to favorites'}
                              onClick={(e) => { e.stopPropagation(); toggleFavorite(s.key) }}
                            >
                              <Star size={14} fill={fav ? 'var(--aws-orange)' : 'none'} color={fav ? 'var(--aws-orange)' : 'var(--aws-text-muted)'} />
                            </button>
                            <span onClick={() => go(s.path, s.key)} style={{ cursor: 'pointer', flex: 1 }}>
                              <span style={{ color: 'var(--aws-text-link)', fontWeight: 600 }}>{s.name}</span>
                              <span style={{ fontSize: 12, color: 'var(--aws-text-secondary)', marginLeft: 6 }}>{s.desc}</span>
                            </span>
                          </div>
                        )
                      })}
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
