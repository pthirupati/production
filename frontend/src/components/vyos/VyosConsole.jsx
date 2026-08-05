import { useCallback, useEffect, useState } from 'react'
import { Network, Terminal } from 'lucide-react'
import LabChromeBar from '../lab/LabChromeBar'
import { vyosApi } from '../../api/vyos'
import { simPanelRoot } from '../../utils/simLayout'
import './vyos.css'

const ACCENT = '#c8a84b'
const EMPTY = {
  interfaces: [],
  routes: [],
  bgp: [],
  ospf: {},
  firewall: { rules: [], counters: {} },
  nat: {},
  vrrp: {},
  dhcp_leases: [],
  revisions: {},
  uncommitted: false,
  diff: '',
}

function bgpTone(state) {
  if (state === 'Established') return 'ok'
  if (state === 'Idle' || state === 'Active') return 'warn'
  return 'err'
}

export default function VyosConsole({
  sessionId,
  scenario,
  onExit,
  onStop,
  onHints,
  onCheck,
  onExtend,
  hintsLabel,
  checkDisabled,
  extendDisabled,
  embedded = false,
  onToggleTerminal,
  simTerminalOpen = false,
}) {
  const slug = scenario?.slug || ''
  const [dash, setDash] = useState(EMPTY)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    if (!sessionId) return
    try {
      const data = await vyosApi.getState(sessionId, slug)
      if (data?.dashboard) setDash(data.dashboard)
      setError('')
    } catch (e) {
      setError(e?.response?.data?.error || e?.message || 'Unable to load VyOS state')
    } finally {
      setLoading(false)
    }
  }, [sessionId, slug])

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 2000)
    return () => clearInterval(t)
  }, [refresh])

  const chromeProps = {
    onHints,
    onCheck,
    onExtend,
    onStop,
    onBackToTerminal: embedded ? (onToggleTerminal || undefined) : onExit,
    hintsLabel,
    checkDisabled,
    extendDisabled,
    backLabel: simTerminalOpen ? 'Hide terminal' : 'Terminal',
  }

  const ifaces = dash.interfaces || []
  const routes = dash.routes || []
  const bgp = dash.bgp || []
  const leases = dash.dhcp_leases || []
  const fwCounters = dash.firewall?.counters || {}
  const fwRules = dash.firewall?.rules || []
  const rev = dash.revisions || {}

  return (
    <div className={simPanelRoot(embedded, 'vyos-root')}>
      <LabChromeBar
        icon={Network}
        title="VyOS"
        subtitle={scenario?.title || slug || 'Router'}
        accent={ACCENT}
        {...chromeProps}
      />
      <div className="vyos-banner">
        <Terminal size={14} style={{ color: ACCENT, flexShrink: 0 }} />
        <span>
          CLI is primary — use <strong>Lab Terminal</strong> for configure / set / commit.
          This panel is a live ops view (polls every 2s).
        </span>
      </div>

      {loading && <div className="vyos-banner">Loading router state…</div>}
      {error && <div className="vyos-banner" style={{ color: '#e06c6c' }}>{error}</div>}

      <div className="vyos-grid">
        <section className="vyos-card">
          <h3>Interfaces</h3>
          {ifaces.length === 0 ? (
            <p className="vyos-empty">No interfaces</p>
          ) : (
            <table className="vyos-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Address</th>
                  <th>Desc</th>
                </tr>
              </thead>
              <tbody>
                {ifaces.map((iface) => (
                  <tr key={iface.name}>
                    <td>{iface.name}</td>
                    <td>{iface.address || '—'}</td>
                    <td>{iface.description || ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="vyos-card">
          <h3>Routes</h3>
          {routes.length === 0 ? (
            <p className="vyos-empty">No routes</p>
          ) : (
            <pre className="vyos-pre">{routes.join('\n')}</pre>
          )}
        </section>

        <section className="vyos-card">
          <h3>BGP neighbors</h3>
          {bgp.length === 0 ? (
            <p className="vyos-empty">No neighbors</p>
          ) : (
            <table className="vyos-table">
              <thead>
                <tr>
                  <th>Neighbor</th>
                  <th>AS</th>
                  <th>State</th>
                  <th>Pfx</th>
                </tr>
              </thead>
              <tbody>
                {bgp.map((n) => (
                  <tr key={n.neighbor}>
                    <td>{n.neighbor}</td>
                    <td>{n.remote_as ?? '—'}</td>
                    <td>
                      <span className={`vyos-pill ${bgpTone(n.state)}`}>{n.state}</span>
                    </td>
                    <td>{n.prefixes ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="vyos-card">
          <h3>Firewall</h3>
          {Object.keys(fwCounters).length === 0 && fwRules.length === 0 ? (
            <p className="vyos-empty">No firewall counters</p>
          ) : (
            <>
              <table className="vyos-table">
                <thead>
                  <tr>
                    <th>Ruleset</th>
                    <th>Pkts</th>
                    <th>Bytes</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(fwCounters).map(([name, c]) => (
                    <tr key={name}>
                      <td>{name}</td>
                      <td>{c.packets ?? 0}</td>
                      <td>{c.bytes ?? 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {fwRules.length > 0 && (
                <pre className="vyos-pre" style={{ marginTop: '0.5rem' }}>
                  {fwRules.map((r) => `set ${r}`).join('\n')}
                </pre>
              )}
            </>
          )}
        </section>

        <section className="vyos-card">
          <h3>VRRP</h3>
          {dash.vrrp?.configured ? (
            <pre className="vyos-pre">{dash.vrrp.summary || 'VRRP active'}</pre>
          ) : (
            <p className="vyos-empty">No VRRP groups</p>
          )}
        </section>

        <section className="vyos-card">
          <h3>DHCP leases</h3>
          {leases.length === 0 ? (
            <p className="vyos-empty">No leases</p>
          ) : (
            <table className="vyos-table">
              <thead>
                <tr>
                  <th>IP</th>
                  <th>MAC</th>
                  <th>Client</th>
                </tr>
              </thead>
              <tbody>
                {leases.map((l) => (
                  <tr key={`${l.ip}-${l.mac}`}>
                    <td>{l.ip}</td>
                    <td>{l.mac}</td>
                    <td>{l.client || l.pool || ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="vyos-card" style={{ gridColumn: '1 / -1' }}>
          <h3>Config revisions</h3>
          <div className="vyos-meta">
            <span>rev {rev.current ?? 0}</span>
            <span>history {rev.history_count ?? 0}</span>
            <span className={`vyos-pill ${dash.uncommitted ? 'warn' : 'ok'}`}>
              {dash.uncommitted ? 'uncommitted changes' : 'clean'}
            </span>
            {dash.nat?.configured && <span>NAT</span>}
            {dash.ospf?.configured && <span>OSPF</span>}
          </div>
          {dash.uncommitted && dash.diff ? (
            <pre className="vyos-pre">{dash.diff}</pre>
          ) : (
            <p className="vyos-empty">Running config matches candidate</p>
          )}
        </section>
      </div>
    </div>
  )
}
