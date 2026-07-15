import { useNavigate } from 'react-router-dom'
import { Sun, Moon, Globe, Check } from 'lucide-react'
import { useAwsStore } from '../store/awsStore'
import { AWS_REGIONS, REGION_GEO_ORDER, regionName } from '../lib/regions'
import { Breadcrumb, Tabs, SectionLabel } from '../ui/primitives'
import { BASE } from '../layout/serviceNav'
import { useState } from 'react'

// Unified console settings — default region + display theme. Theme is the source
// of truth in settings.theme but also drives store.darkMode so the whole console
// re-themes immediately.
export default function SettingsPage() {
  const navigate = useNavigate()
  const settings = useAwsStore((s) => s.settings) || {}
  const updateSettings = useAwsStore((s) => s.updateSettings)
  const region = useAwsStore((s) => s.region)
  const setRegion = useAwsStore((s) => s.setRegion)
  const darkMode = useAwsStore((s) => s.darkMode)
  const toggleDark = useAwsStore((s) => s.toggleDarkMode)

  const [tab, setTab] = useState('general')
  const theme = darkMode ? 'dark' : (settings.theme || 'light')

  const applyTheme = (next) => {
    updateSettings({ theme: next })
    const wantDark = next === 'dark'
    if (wantDark !== darkMode) toggleDark()
  }

  const applyRegion = (code) => {
    setRegion(code)
    const next = [code, ...(settings.recentRegions || []).filter((c) => c !== code)].slice(0, 4)
    updateSettings({ region: code, recentRegions: next })
  }

  return (
    <div className="aws-page">
      <Breadcrumb items={[
        { label: 'Console Home', onClick: () => navigate(`${BASE}/console/home`) },
        { label: 'Settings' },
      ]}
      />
      <div className="aws-page-header">
        <h1>Settings</h1>
      </div>

      <Tabs
        tabs={[{ key: 'general', label: 'General' }, { key: 'display', label: 'Display' }]}
        active={tab}
        onChange={setTab}
      />

      {tab === 'general' && (
        <div className="aws-card" style={{ marginTop: 16 }}>
          <SectionLabel info>Default Region</SectionLabel>
          <p style={{ color: 'var(--aws-text-secondary)', fontSize: 13, marginBottom: 12 }}>
            The default AWS Region for the console. Currently <strong>{regionName(region)}</strong> ({region}).
          </p>
          <div style={{ maxWidth: 420 }}>
            <label className="aws-label" htmlFor="settings-region">Region</label>
            <div style={{ position: 'relative' }}>
              <Globe size={15} style={{ position: 'absolute', left: 8, top: 9, color: 'var(--aws-text-muted)', pointerEvents: 'none' }} />
              <select
                id="settings-region"
                className="aws-select"
                style={{ paddingLeft: 28 }}
                value={region}
                onChange={(e) => applyRegion(e.target.value)}
              >
                {REGION_GEO_ORDER.map((geo) => (
                  <optgroup key={geo} label={geo}>
                    {AWS_REGIONS.filter((r) => r.geo === geo).map((r) => (
                      <option key={r.code} value={r.code}>{r.name} — {r.code}</option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </div>
          </div>
        </div>
      )}

      {tab === 'display' && (
        <div className="aws-card" style={{ marginTop: 16 }}>
          <SectionLabel>Visual mode</SectionLabel>
          <p style={{ color: 'var(--aws-text-secondary)', fontSize: 13, marginBottom: 12 }}>
            Choose a light or dark appearance for the console.
          </p>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            {[
              { key: 'light', label: 'Light', Icon: Sun },
              { key: 'dark', label: 'Dark', Icon: Moon },
            ].map(({ key, label, Icon }) => {
              const active = theme === key
              return (
                <button
                  key={key}
                  onClick={() => applyTheme(key)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 10, padding: '12px 18px', cursor: 'pointer',
                    border: `2px solid ${active ? 'var(--aws-sidebar-active-border)' : 'var(--aws-border)'}`,
                    background: active ? 'var(--aws-sidebar-active-bg)' : 'var(--aws-content-bg)',
                    color: 'var(--aws-text-primary)', borderRadius: 'var(--aws-radius-md)', minWidth: 160,
                  }}
                >
                  <Icon size={18} />
                  <span style={{ fontWeight: 600, flex: 1, textAlign: 'left' }}>{label}</span>
                  {active && <Check size={16} color="var(--aws-sidebar-active-text)" />}
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
