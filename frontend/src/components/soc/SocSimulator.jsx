import { useState } from 'react'
import { socApi } from '../../api/soc'
import LabChromeBar from '../lab/LabChromeBar'
import {
  LogIn, ShieldAlert, Siren, Search, ListChecks, Server, AlertTriangle,
  Terminal, CheckCircle2, ArrowUpCircle, Ban, Lock, PlayCircle, Radio,
  KeyRound, Bug, BrickWall, Activity, Scale,
} from 'lucide-react'
import { simPanelRoot } from '../../utils/simLayout'
import { SimSidebar, SimBreadcrumbs, SimDataTable, SimStatusBadge, useSimSession } from '../sim/shared'
import { renderSocV2Page } from './SocV2Panels'
import '../../styles/sim-products.css'
import './soc.css'

const SOC_LAB_USER = 'lab_soc'
const SOC_LAB_PASS = 'lab_soc@123'
const ACCENT = '#ef4444'

const SIDEBAR = [
  { key: 'alerts', label: 'Alerts', icon: Siren },
  { key: 'incidents', label: 'Incidents', icon: ShieldAlert },
  { key: 'log-search', label: 'Log Search', icon: Search },
  { key: 'playbooks', label: 'Playbooks', icon: ListChecks },
  { key: 'threat-intel', label: 'Threat Intel', icon: Radio },
  { key: 'rules', label: 'Detection Rules', icon: ListChecks },
  { key: 'assets', label: 'Assets', icon: Server },
  { key: 'pam', label: 'PAM Sessions', icon: KeyRound },
  { key: 'vulns', label: 'Vulnerabilities', icon: Bug },
  { key: 'firewall', label: 'Firewall', icon: BrickWall },
  { key: 'pcap', label: 'Packet Capture', icon: Activity },
  { key: 'compliance', label: 'Compliance', icon: Scale },
  { key: 'activity', label: 'Activity', icon: Server },
]

const SEVERITY_ORDER = { critical: 0, high: 1, medium: 2, low: 3 }

function SeverityBadge({ severity }) {
  const cls = {
    critical: 'soc-sev-critical', high: 'soc-sev-high', medium: 'soc-sev-medium', low: 'soc-sev-low',
  }[severity] || 'soc-sev-low'
  return <span className={`soc-sev-badge ${cls}`}>{severity}</span>
}

export default function SocSimulator({
  sessionId, scenario, onExit, onStop, onHints, onCheck, onExtend,
  hintsLabel, checkDisabled, extendDisabled, embedded = false,
  onToggleTerminal, simTerminalOpen = false, vmwareHref = null,
}) {
  const slug = scenario?.slug || ''
  const { state, loading, busy, run } = useSimSession(sessionId, slug, socApi)
  const [nav, setNav] = useState('alerts')
  const [loginUser, setLoginUser] = useState('')
  const [loginPass, setLoginPass] = useState('')
  const [loginError, setLoginError] = useState('')
  const [selectedAlertId, setSelectedAlertId] = useState(null)
  const [query, setQuery] = useState('')
  const [searchResults, setSearchResults] = useState(null)

  const st = state?.state || {}
  const loggedIn = st?.session?.logged_in
  const goal = st?.goal || {}
  const broken = st?.broken || {}
  const alerts = [...(st.alerts || [])].sort((a, b) => (SEVERITY_ORDER[a.severity] ?? 9) - (SEVERITY_ORDER[b.severity] ?? 9))
  const selectedAlert = selectedAlertId ? alerts.find((a) => a.id === selectedAlertId) : null
  const relatedIncident = selectedAlert ? (st.incidents || []).find((i) => i.alert_id === selectedAlert.id) : null

  const chromeProps = {
    onHints, onCheck, onExtend, onStop,
    onBackToTerminal: embedded ? (onToggleTerminal || undefined) : onExit,
    hintsLabel, checkDisabled, extendDisabled,
    backLabel: simTerminalOpen ? 'Hide terminal' : 'Terminal',
    vmwareHref,
  }

  const breadcrumbs = [{ label: st?.summary?.platform || 'SOC Console', onClick: () => setNav('alerts') }]
  if (nav !== 'alerts') breadcrumbs.push({ label: SIDEBAR.find((s) => s.key === nav)?.label || nav })

  if (!loading && state && !loggedIn) {
    const submitLogin = (e) => {
      e.preventDefault()
      if (busy) return
      const u = loginUser.trim().toLowerCase()
      const ok = (u === SOC_LAB_USER && loginPass === SOC_LAB_PASS) || (u === 'analyst' && loginPass === 'analyst')
      if (ok) {
        setLoginError('')
        run(() => socApi.login(sessionId), 'Signed in')
      } else {
        setLoginError(`Invalid credentials. Use ${SOC_LAB_USER} / ${SOC_LAB_PASS} for training labs.`)
      }
    }
    return (
      <div className={simPanelRoot(embedded, 'bg-[#0a0c12]')}>
        <LabChromeBar title="SOC Console" subtitle={scenario?.title || slug} accent={ACCENT} {...chromeProps} />
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="bg-[#12141c] border border-[#232838] rounded-lg shadow-2xl w-[400px] overflow-hidden">
            <div className="px-6 py-4 text-white font-semibold flex items-center gap-2" style={{ background: '#1a1015' }}>
              <ShieldAlert size={18} className="text-red-400" /> FixItLab SIEM
            </div>
            <form onSubmit={submitLogin} className="p-6 space-y-4">
              <p className="text-sm text-slate-400">Sign in to the Security Operations Center console.</p>
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1">Analyst ID</label>
                <input value={loginUser} onChange={(e) => setLoginUser(e.target.value)} autoFocus autoComplete="username"
                  placeholder={SOC_LAB_USER}
                  className="w-full border border-slate-700 bg-[#0a0c12] text-slate-100 rounded px-3 py-2 text-sm focus:outline-none focus:border-red-500" />
              </div>
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1">Password</label>
                <input type="password" value={loginPass} onChange={(e) => setLoginPass(e.target.value)} autoComplete="current-password"
                  className="w-full border border-slate-700 bg-[#0a0c12] text-slate-100 rounded px-3 py-2 text-sm focus:outline-none focus:border-red-500" />
              </div>
              {loginError && (
                <p className="text-xs text-red-400 bg-red-950/40 border border-red-800 rounded px-3 py-2">{loginError}</p>
              )}
              <button type="submit" disabled={busy}
                className="soc-btn-primary w-full py-2 flex items-center justify-center gap-2">
                <LogIn size={16} /> Sign In
              </button>
              <button type="button"
                onClick={() => { setLoginUser(SOC_LAB_USER); setLoginPass(SOC_LAB_PASS); setLoginError('') }}
                className="w-full py-1.5 text-xs text-slate-400 border border-slate-700 rounded hover:bg-white/5">
                Use lab credentials (autofill)
              </button>
              <p className="text-[10px] text-slate-500 text-center pt-2 border-t border-slate-800">
                Training credentials: <span className="font-mono text-slate-300">{SOC_LAB_USER}</span> / <span className="font-mono text-slate-300">{SOC_LAB_PASS}</span>
              </p>
            </form>
          </div>
        </div>
      </div>
    )
  }

  const renderContent = () => {
    const v2 = renderSocV2Page({ nav, st, sessionId, busy, run })
    if (v2) return v2
    if (nav === 'alerts') {
      return (
        <div className="soc-split">
          <div className="soc-list-col">
            <h2 className="soc-h">Alert Queue</h2>
            <SimDataTable columns={[
              { key: 'id', label: 'ID', sortable: true },
              { key: 'severity', label: 'Severity', sortable: true, render: (r) => <SeverityBadge severity={r.severity} /> },
              { key: 'title', label: 'Alert', sortable: true },
              { key: 'asset', label: 'Asset', sortable: true },
              { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status={r.status === 'new' ? 'warning' : r.status === 'closed' ? 'success' : 'info'} label={r.status} /> },
            ]} rows={alerts} searchKeys={['title', 'asset', 'id']} onRowClick={(r) => setSelectedAlertId(r.id)} />
          </div>
          {selectedAlert && (
            <div className="soc-detail-col">
              <div className="soc-detail-head">
                <SeverityBadge severity={selectedAlert.severity} />
                <span className="soc-detail-title">{selectedAlert.title}</span>
              </div>
              <div className="soc-detail-meta">
                <div><span className="soc-meta-k">Asset</span> {selectedAlert.asset}</div>
                <div><span className="soc-meta-k">Source IP</span> <span className="font-mono">{selectedAlert.source_ip}</span></div>
                <div><span className="soc-meta-k">Status</span> {selectedAlert.status}</div>
              </div>
              <div className="soc-action-row">
                {!selectedAlert.acknowledged && (
                  <button type="button" disabled={busy} className="soc-btn-outline"
                    onClick={() => run(() => socApi.acknowledgeAlert(sessionId, selectedAlert.id), 'Alert acknowledged')}>
                    <CheckCircle2 size={13} /> Acknowledge
                  </button>
                )}
                {!relatedIncident && selectedAlert.status !== 'closed' && (
                  <button type="button" disabled={busy} className="soc-btn-outline"
                    onClick={() => run(() => socApi.escalateIncident(sessionId, selectedAlert.id), 'Escalated to incident')}>
                    <ArrowUpCircle size={13} /> Escalate
                  </button>
                )}
                <button type="button" disabled={busy} className="soc-btn-outline"
                  onClick={() => run(() => socApi.enrichAlert(sessionId, selectedAlert.id), 'Alert enriched')}>
                  <Search size={13} /> Enrich IOCs
                </button>
                <button type="button" disabled={busy} className="soc-btn-outline"
                  onClick={() => run(() => socApi.quarantineHost(sessionId, selectedAlert.asset), 'Host quarantined')}>
                  <Lock size={13} /> Quarantine {selectedAlert.asset}
                </button>
                <button type="button" disabled={busy} className="soc-btn-outline"
                  onClick={() => run(() => socApi.blockIp(sessionId, selectedAlert.source_ip), `IP ${selectedAlert.source_ip} blocked`)}>
                  <Ban size={13} /> Block {selectedAlert.source_ip}
                </button>
                {selectedAlert.status !== 'closed' && (
                  <button type="button" disabled={busy} className="soc-btn-danger"
                    onClick={() => run(() => socApi.closeIncident(sessionId, relatedIncident?.id, selectedAlert.id), 'Closed')}>
                    Close
                  </button>
                )}
              </div>
              {selectedAlert.enriched && (selectedAlert.ioc_matches || []).length > 0 && (
                <div className="soc-incident-note">IOC matches: {(selectedAlert.ioc_matches || []).map((i) => i.value).join(', ')}</div>
              )}
              {relatedIncident && (
                <div className="soc-incident-note">Linked incident <strong>{relatedIncident.id}</strong> · {relatedIncident.status}</div>
              )}
            </div>
          )}
        </div>
      )
    }
    if (nav === 'incidents') {
      return (
        <div className="space-y-3">
          <h2 className="soc-h">Incidents</h2>
          <SimDataTable columns={[
            { key: 'id', label: 'Incident', sortable: true },
            { key: 'title', label: 'Title', sortable: true },
            { key: 'asset', label: 'Asset', sortable: true },
            { key: 'severity', label: 'Severity', render: (r) => <SeverityBadge severity={r.severity} /> },
            { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status={r.status === 'closed' ? 'success' : 'warning'} label={r.status} /> },
          ]} rows={st.incidents || []} searchKeys={['title', 'asset']} emptyMessage="No incidents opened yet — escalate an alert." />
          {(st.cases || []).length > 0 && (
            <>
              <h2 className="soc-h pt-2">Cases</h2>
              <SimDataTable columns={[
                { key: 'id', label: 'Case', sortable: true },
                { key: 'title', label: 'Title', sortable: true },
                { key: 'status', label: 'Status', sortable: true },
                { key: 'created', label: 'Opened', sortable: true },
              ]} rows={st.cases || []} searchKeys={['title']} />
            </>
          )}
        </div>
      )
    }
    if (nav === 'log-search') {
      const submit = async (e) => {
        e.preventDefault()
        const res = await run(() => socApi.searchLogs(sessionId, query))
        setSearchResults(res?.results || [])
      }
      return (
        <div className="space-y-3">
          <h2 className="soc-h">Log Search</h2>
          <form onSubmit={submit} className="flex gap-2">
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search host, message, IP…"
              className="soc-input flex-1" />
            <button type="submit" className="soc-btn-primary" disabled={busy}><Search size={13} /> Search</button>
          </form>
          <div className="soc-log-panel">
            {(searchResults ?? st.log_index ?? []).length === 0 && <div className="text-xs text-slate-500 p-3">No matching log entries.</div>}
            {(searchResults ?? st.log_index ?? []).map((e, i) => (
              <div key={`${e.time}-${i}`} className="soc-log-row">
                <span className="soc-log-time">{e.time}</span>
                <span className="soc-log-source">{e.source}</span>
                <span className="soc-log-host">{e.host}</span>
                <span className="soc-log-msg">{e.message}</span>
              </div>
            ))}
          </div>
        </div>
      )
    }
    if (nav === 'playbooks') {
      return (
        <div className="space-y-3">
          <h2 className="soc-h">Response Playbooks</h2>
          {(st.playbooks || []).map((pb) => (
            <div key={pb.id} className="soc-panel p-3">
              <div className="flex justify-between items-center">
                <div className="font-semibold flex items-center gap-2"><ListChecks size={14} /> {pb.name}</div>
                <button type="button" disabled={busy} className="soc-btn-outline"
                  onClick={() => run(() => socApi.runPlaybook(sessionId, pb.id), `${pb.name} executed`)}>
                  <PlayCircle size={13} /> Run
                </button>
              </div>
              <ol className="mt-2 text-xs text-slate-400 list-decimal list-inside space-y-0.5">
                {(pb.steps || []).map((s) => <li key={s}>{s}</li>)}
              </ol>
            </div>
          ))}
        </div>
      )
    }
    if (nav === 'assets') {
      return (
        <div className="space-y-3">
          <h2 className="soc-h">Monitored Assets</h2>
          <SimDataTable columns={[
            { key: 'name', label: 'Asset', sortable: true },
            { key: 'ip', label: 'IP', sortable: true },
            { key: 'risk', label: 'Risk', render: (r) => <SeverityBadge severity={r.risk} /> },
            { key: 'quarantined', label: 'Network', render: (r) => <SimStatusBadge status={r.quarantined ? 'error' : 'success'} label={r.quarantined ? 'Quarantined' : 'Connected'} /> },
            { key: 'actions', label: 'Actions', render: (r) => r.quarantined && (
              <button type="button" className="soc-btn-outline" onClick={(e) => {
                e.stopPropagation()
                run(() => socApi.unquarantineHost(sessionId, r.name), 'Host unquarantined')
              }}>Release</button>
            ) },
          ]} rows={st.assets || []} searchKeys={['name', 'ip']} />
          {(st.blocked_ips || []).length > 0 && (
            <div className="soc-panel p-3">
              <div className="font-semibold text-xs uppercase tracking-wide text-slate-400 mb-2 flex items-center gap-1"><Radio size={12} /> Blocked at firewall</div>
              <div className="flex flex-wrap gap-1.5">
                {(st.blocked_ips || []).map((ip) => (
                  <button key={ip} type="button" className="soc-ip-chip font-mono" onClick={() => run(() => socApi.unblockIp(sessionId, ip), `IP ${ip} unblocked`)}>
                    {ip} ×
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )
    }
    if (nav === 'threat-intel') {
      return (
        <div className="space-y-3">
          <div className="flex justify-between items-center">
            <h2 className="soc-h">Indicators of Compromise</h2>
            <button type="button" className="soc-btn-outline" disabled={busy}
              onClick={() => run(() => socApi.addIoc(sessionId, 'ip', '203.0.113.99', 'scanner'), 'IOC added')}>
              Add sample IOC
            </button>
          </div>
          <SimDataTable columns={[
            { key: 'type', label: 'Type', sortable: true },
            { key: 'value', label: 'Value', sortable: true },
            { key: 'threat', label: 'Threat', sortable: true },
            { key: 'confidence', label: 'Confidence', sortable: true },
          ]} rows={st.iocs || []} searchKeys={['value', 'threat']} />
        </div>
      )
    }
    if (nav === 'rules') {
      return (
        <div className="space-y-3">
          <h2 className="soc-h">Detection Rules</h2>
          <SimDataTable columns={[
            { key: 'name', label: 'Rule', sortable: true },
            { key: 'severity', label: 'Severity', render: (r) => <SeverityBadge severity={r.severity} /> },
            { key: 'enabled', label: 'State', render: (r) => <SimStatusBadge status={r.enabled ? 'success' : 'disabled'} label={r.enabled ? 'Enabled' : 'Disabled'} /> },
            { key: 'actions', label: 'Actions', render: (r) => (
              <button type="button" className="soc-btn-outline" onClick={(e) => {
                e.stopPropagation()
                run(() => (r.enabled ? socApi.disableRule(sessionId, r.id) : socApi.enableRule(sessionId, r.id)), r.enabled ? 'Rule disabled' : 'Rule enabled')
              }}>{r.enabled ? 'Disable' : 'Enable'}</button>
            ) },
          ]} rows={st.detection_rules || []} searchKeys={['name']} />
        </div>
      )
    }
    if (nav === 'activity') {
      return (
        <div className="space-y-3">
          <h2 className="soc-h">Analyst Activity</h2>
          <SimDataTable columns={[
            { key: 'time', label: 'Time', sortable: true },
            { key: 'severity', label: 'Severity', sortable: true },
            { key: 'message', label: 'Message', sortable: true },
          ]} rows={st.activity_log || st.events || []} searchKeys={['message']} emptyMessage="No activity yet." />
        </div>
      )
    }
    return null
  }

  return (
    <div className={simPanelRoot(embedded, 'soc-shell sim-product')}>
      <LabChromeBar title="SOC Console" subtitle={scenario?.title || slug}
        accent={ACCENT} className="lab-chrome-bar !bg-[#1a1015]" {...chromeProps}>
        {onToggleTerminal && (
          <button type="button" className="lab-chrome-btn flex items-center gap-1" onClick={onToggleTerminal}>
            <Terminal size={13} /> {simTerminalOpen ? 'Hide terminal' : 'Terminal'}
          </button>
        )}
      </LabChromeBar>

      {goal.objective && (
        <div className="sim-goal-banner">
          <AlertTriangle size={14} className="shrink-0" />
          <span><strong>{goal.title}:</strong> {goal.objective}</span>
        </div>
      )}

      <div className="px-4 py-2 bg-[#0e1017] border-b border-black/30 flex items-center justify-between">
        <SimBreadcrumbs items={breadcrumbs} className="!text-slate-400" />
        <span className="text-xs text-slate-500">{st?.session?.user || 'analyst'} · {Object.keys(broken).length > 0 ? `${Object.keys(broken).length} open item(s)` : 'clear'}</span>
      </div>

      <div className="flex flex-1 min-h-0">
        <SimSidebar sections={SIDEBAR} activeKey={nav} onSelect={(k) => { setNav(k); setSelectedAlertId(null) }} accent={ACCENT}
          className="!w-[200px] !bg-[#0e1017] soc-sidebar" />
        <main className="flex-1 overflow-auto p-5 bg-[#0a0c12]">{renderContent()}</main>
      </div>
    </div>
  )
}
