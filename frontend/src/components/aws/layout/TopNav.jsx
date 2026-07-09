import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Menu, Search, ChevronDown, Bell, Settings, Terminal as TerminalIcon, Globe, Moon, Sun, Grid3x3, X } from 'lucide-react'
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

export default function TopNav({ onToggleSidebar, onToggleCloudShell }) {
  const navigate = useNavigate()
  const region = useAwsStore((s) => s.region)
  const setRegion = useAwsStore((s) => s.setRegion)
  const account = useAwsStore((s) => s.account)
  const darkMode = useAwsStore((s) => s.darkMode)
  const toggleDark = useAwsStore((s) => s.toggleDarkMode)
  const alarms = useAwsStore((s) => s.cwAlarms)

  const [openMenu, setOpenMenu] = useState(null) // 'services' | 'region' | 'account' | 'search'
  const [query, setQuery] = useState('')
  const searchRef = useRef(null)

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
  const go = (path) => { close(); navigate(path) }

  const results = query
    ? SERVICES.filter((s) => s.built && (s.name.toLowerCase().includes(query.toLowerCase()) || s.desc.toLowerCase().includes(query.toLowerCase())))
    : []

  const inAlarm = alarms.filter((a) => a.state === 'ALARM').length

  return (
    <div className="aws-topnav">
      <button className="aws-topnav-btn" onClick={onToggleSidebar} title="Toggle navigation"><Menu size={18} /></button>
      <button className="aws-topnav-btn" onClick={() => go(`${BASE}/console/home`)}><AwsLogo /></button>
      <button className="aws-topnav-btn" onClick={() => setOpenMenu(openMenu === 'services' ? null : 'services')}>
        <Grid3x3 size={15} /> Services <ChevronDown size={13} />
      </button>
      <AwsLabsMenu />

      {/* Search */}
      <div style={{ position: 'relative', flex: 1, maxWidth: 460, margin: '0 8px' }}>
        <Search size={15} style={{ position: 'absolute', left: 10, top: 8, color: '#8b96a5' }} />
        <input
          ref={searchRef}
          value={query}
          onChange={(e) => { setQuery(e.target.value); setOpenMenu('search') }}
          onFocus={() => setOpenMenu('search')}
          placeholder="Search for services, features, and resources [Alt+S]"
          style={{ width: '100%', height: 32, background: '#1b2532', border: '1px solid #37475a', borderRadius: 2, color: '#fff', padding: '0 10px 0 30px', fontSize: 13 }}
        />
        {openMenu === 'search' && results.length > 0 && (
          <div className="aws-topnav-dropdown" style={{ position: 'absolute', top: 36, left: 0, right: 0, background: 'var(--aws-content-bg)', borderRadius: 4, boxShadow: 'var(--aws-shadow-lg)', maxHeight: 360, overflowY: 'auto', zIndex: 300, border: '1px solid var(--aws-border)' }}>
            <div style={{ padding: '8px 12px', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: 'var(--aws-text-secondary)' }}>Services</div>
            {results.map((s) => (
              <div key={s.key} onClick={() => { setQuery(''); go(s.path) }} style={{ padding: '8px 12px', cursor: 'pointer', color: 'var(--aws-text-primary)' }} onMouseDown={(e) => e.preventDefault()}>
                <div style={{ fontWeight: 700, color: 'var(--aws-text-link)' }}>{s.name}</div>
                <div style={{ fontSize: 12, color: 'var(--aws-text-secondary)' }}>{s.desc}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 4 }}>
        <button className="aws-topnav-btn" onClick={onToggleCloudShell} title="CloudShell"><TerminalIcon size={16} /></button>
        <button className="aws-topnav-btn" title="Alarms" style={{ position: 'relative' }} onClick={() => go(`${BASE}/cloudwatch/alarms`)}>
          <Bell size={16} />
          {inAlarm > 0 && <span style={{ position: 'absolute', top: 2, right: 2, background: 'var(--aws-error)', color: '#fff', borderRadius: 8, fontSize: 9, padding: '0 4px' }}>{inAlarm}</span>}
        </button>
        <button className="aws-topnav-btn" onClick={toggleDark} title="Dark mode">{darkMode ? <Sun size={16} /> : <Moon size={16} />}</button>

        {/* Region */}
        <div style={{ position: 'relative' }}>
          <button className="aws-topnav-btn" onClick={() => setOpenMenu(openMenu === 'region' ? null : 'region')}>
            <Globe size={15} /> {regionName(region)} <ChevronDown size={13} />
          </button>
          {openMenu === 'region' && (
            <div className="aws-topnav-dropdown" style={{ position: 'absolute', top: 38, right: 0, width: 340, maxHeight: 460, overflowY: 'auto', background: 'var(--aws-content-bg)', borderRadius: 4, boxShadow: 'var(--aws-shadow-lg)', color: 'var(--aws-text-primary)', zIndex: 300, border: '1px solid var(--aws-border)' }}>
              {REGION_GEO_ORDER.map((geo) => (
                <div key={geo}>
                  <div style={{ padding: '8px 14px 2px', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: 'var(--aws-text-secondary)' }}>{geo}</div>
                  {AWS_REGIONS.filter((r) => r.geo === geo).map((r) => (
                    <div key={r.code} onClick={() => { setRegion(r.code); close() }} style={{ padding: '7px 14px', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', background: r.code === region ? 'var(--aws-sidebar-active-bg)' : undefined }}>
                      <span>{r.flag} {r.name}</span>
                      <span className="aws-mono" style={{ color: 'var(--aws-text-secondary)', fontSize: 12 }}>{r.code}</span>
                    </div>
                  ))}
                </div>
              ))}
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
                { label: 'Security credentials', path: `${BASE}/iam/home` },
              ].map(({ label, path }) => (
                <div key={label} onClick={() => go(path)} style={{ padding: '7px 8px', cursor: 'pointer' }}>{label}</div>
              ))}
              <div style={{ borderTop: '1px solid var(--aws-border-light)', padding: '7px 8px', cursor: 'pointer', color: 'var(--aws-text-link)' }}>Sign out</div>
            </div>
          )}
        </div>
        <button className="aws-topnav-btn" title="Settings" onClick={() => go(`${BASE}/billing/home`)}><Settings size={16} /></button>
      </div>

      {/* Services mega-menu */}
      {openMenu === 'services' && (
        <div style={{ position: 'fixed', top: 48, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.4)', zIndex: 250 }} onClick={close}>
          <div onClick={(e) => e.stopPropagation()} className="aws-topnav-dropdown" style={{ background: 'var(--aws-content-bg)', maxHeight: '80vh', overflowY: 'auto', padding: 20, borderBottom: '1px solid var(--aws-border)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <h2 style={{ color: 'var(--aws-text-primary)' }}>Services</h2>
              <button className="aws-copy-btn" onClick={close}><X size={18} /></button>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 20 }}>
              {SERVICE_CATEGORIES.map((cat) => {
                const items = SERVICES.filter((s) => s.category === cat)
                if (!items.length) return null
                return (
                  <div key={cat}>
                    <div style={{ fontWeight: 700, color: 'var(--aws-text-primary)', marginBottom: 6 }}>{cat}</div>
                    {items.map((s) => (
                      <div
                        key={s.key}
                        onClick={() => s.built && go(s.path)}
                        style={{ padding: '5px 0', cursor: s.built ? 'pointer' : 'default', opacity: s.built ? 1 : 0.45 }}
                      >
                        <span style={{ color: s.built ? 'var(--aws-text-link)' : 'var(--aws-text-secondary)', fontWeight: s.built ? 600 : 400 }}>{s.name}</span>
                        <span style={{ fontSize: 12, color: 'var(--aws-text-secondary)', marginLeft: 6 }}>{s.desc}</span>
                      </div>
                    ))}
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
