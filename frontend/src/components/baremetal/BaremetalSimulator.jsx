import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Server, Cpu, HardDrive, Network, Settings, Tags, Layers,
  Globe, Box, Radio, Database, LayoutGrid, Monitor,
} from 'lucide-react'
import toast from 'react-hot-toast'
import { baremetalApi } from '../../api/baremetal'
import LabChromeBar from '../lab/LabChromeBar'
import { simPanelRoot } from '../../utils/simLayout'
import { TRANSIENT_STATUSES } from './MaasStatusBadge'
import MachinesTable from './MachinesTable'
import MachineDetail from './MachineDetail'
import MaasNavPages from './MaasNavPages'
import './maas-vanilla.scss'
import './maas.css'

const ACCENT = '#77216F'

const NAV = [
  { key: 'machines', label: 'Machines', icon: Server, section: 'Hardware' },
  { key: 'devices', label: 'Devices', icon: Monitor, section: 'Hardware' },
  { key: 'controllers', label: 'Controllers', icon: Database, section: 'Hardware' },
  { key: 'kvm', label: 'KVM', icon: Cpu, section: 'Hardware' },
  { key: 'images', label: 'Images', icon: HardDrive, section: 'Images' },
  { key: 'domains', label: 'DNS', icon: Globe, section: 'Networking' },
  { key: 'subnets', label: 'Subnets', icon: Network, section: 'Networking' },
  { key: 'dhcp', label: 'DHCP', icon: Radio, section: 'Networking' },
  { key: 'zones', label: 'AZs', icon: LayoutGrid, section: 'Organisation' },
  { key: 'pools', label: 'Resource pools', icon: Layers, section: 'Organisation' },
  { key: 'tags', label: 'Tags', icon: Tags, section: 'Organisation' },
  { key: 'settings', label: 'Settings', icon: Settings, section: 'Settings' },
  { key: 'lxd', label: 'LXD', icon: Box, section: 'Secondary' },
  { key: 'ipmi', label: 'IPMI', icon: Radio, section: 'Secondary' },
]

function normalizeMachine(m) {
  if (!m) return m
  const storage = m.storage || []
  const domain = m.domain || 'maas'
  return {
    ...m,
    owner: m.owner ?? '',
    pool: m.pool || 'default',
    zone: m.zone || 'default',
    locked: !!m.locked,
    tags: m.tags || [],
    fabric: m.fabric || 'fabric-0',
    domain,
    fqdn: m.fqdn || `${m.hostname}.${domain}`,
    power_type: m.power_type || 'ipmi',
    disk_count: m.disk_count ?? storage.length,
    storage_gb: m.storage_gb ?? storage.reduce((s, d) => s + (Number(d.size_gb) || 0), 0),
    pci_devices: m.pci_devices || [],
    usb_devices: m.usb_devices || [],
    events: m.events || [],
    commissioning_results: m.commissioning_results || [],
    test_results: m.test_results || [],
    storage_layout: m.storage_layout || 'flat',
    interfaces: (m.interfaces || m.network_interfaces || []).map((iface) => ({
      fabric: m.fabric || 'fabric-0',
      subnet: '',
      ip_mode: 'auto',
      link_speed: 10000,
      ...iface,
    })),
  }
}

function enrichState(raw) {
  const st = raw || {}
  const maas = { ...(st.maas || {}) }
  maas.machines = (maas.machines || []).map(normalizeMachine)
  if (!maas.fabrics?.length) {
    maas.fabrics = [{ name: 'fabric-0', vlans: ['untagged', 'pxe', 'mgmt'] }]
  }
  const controllers = st.controllers || maas.controllers || [
    {
      name: 'region-01',
      type: 'region',
      health: 'ok',
      services: {
        regiond: 'running', bind9: 'running', proxy: 'running',
        http: 'running', ntp: 'running', syslog: 'running',
      },
    },
    {
      name: 'rack-01',
      type: 'rack',
      health: 'ok',
      services: {
        rackd: 'running', dhcpd: 'running', tftp: 'running',
        http: 'running', ntp: 'running',
      },
    },
  ]
  const domains = st.domains || maas.domains || [
    {
      name: 'maas',
      authoritative: true,
      records: (maas.machines || []).filter((m) => m.ip).map((m) => ({
        type: 'A', name: m.hostname, data: m.ip,
      })),
    },
  ]
  const zones = st.zones || maas.zones || [
    { name: 'default', description: 'Default availability zone' },
  ]
  const resource_pools = st.resource_pools || maas.resource_pools || [
    { name: 'default', description: 'Default pool', machine_count: (maas.machines || []).length },
  ]
  const devices = st.devices || maas.devices || [
    { hostname: 'mgmt-switch-01', ip: '10.10.1.2', mac: '52:54:00:11:22:01', zone: 'default', owner: 'admin' },
  ]
  const dhcp = st.dhcp || maas.dhcp || {
    enabled: true,
    vlan: 'untagged',
    primary_rack: 'rack-01',
    dynamic_ranges: ['10.10.1.100-10.10.1.200'],
    snippets: [],
  }
  const settings = st.settings || maas.settings || {
    maas_name: 'maas',
    maas_url: 'http://region.maas:5240/MAAS',
    default_distro: 'ubuntu/jammy',
    ntp_servers: 'ntp.ubuntu.com',
    dns_forwarder: '8.8.8.8',
    http_proxy: '',
    enable_http_proxy: false,
  }
  return {
    ...st,
    maas,
    controllers,
    domains,
    zones,
    resource_pools,
    devices,
    dhcp,
    settings,
  }
}

export default function BaremetalSimulator({
  sessionId, scenario, onExit, onStop, onHints, onCheck, onExtend,
  hintsLabel, checkDisabled, extendDisabled, embedded = false,
  onToggleTerminal, simTerminalOpen = false, vmwareHref,
}) {
  const [state, setState] = useState(null)
  const [loading, setLoading] = useState(true)
  const [nav, setNav] = useState('machines')
  const [busy, setBusy] = useState(false)
  const [detailId, setDetailId] = useState(null)
  const [deployImage, setDeployImage] = useState('')
  const slug = scenario?.slug || ''
  const pollRef = useRef(null)

  const refresh = useCallback(async () => {
    const data = await baremetalApi.getState(sessionId, slug)
    setState(data)
    setLoading(false)
  }, [sessionId, slug])

  useEffect(() => { refresh() }, [refresh])

  useEffect(() => {
    const s = (slug || '').toLowerCase()
    if (s.includes('lxd') || s.includes('lxc')) setNav('lxd')
    else if (s.includes('kvm') || s.includes('virsh')) setNav('kvm')
    else if (s.includes('pxe') || s.includes('ipmi')) setNav('ipmi')
    else if (s.includes('maas') || s.includes('baremetal')) setNav('machines')
  }, [slug])

  const st = useMemo(() => enrichState(state?.state), [state])
  const loggedIn = st?.session?.logged_in
  const goal = st?.goal || {}
  const machines = useMemo(() => st.maas?.machines || [], [st.maas])
  const bootResources = useMemo(() => st.maas?.boot_resources || [], [st.maas])
  const user = st?.session?.user || 'admin'

  useEffect(() => {
    if (!bootResources.length) return undefined
    if (deployImage && bootResources.some((r) => r.name === deployImage)) return undefined
    const prefer = bootResources.find((r) => (r.name || '').startsWith('custom/'))
      || bootResources.find((r) => r.name === 'ubuntu/jammy')
      || bootResources[0]
    if (prefer?.name) setDeployImage(prefer.name)
    return undefined
  }, [bootResources, deployImage])

  const anyTransient = useMemo(
    () => machines.some((m) => TRANSIENT_STATUSES.has(m.status)),
    [machines],
  )

  // ── Live updates over WebSocket, with polling fallbacks ──
  const wsRef = useRef(null)
  const [wsConnected, setWsConnected] = useState(false)
  const wsAttemptsRef = useRef(0)
  const wsReconnectTimerRef = useRef(null)
  const slowPollRef = useRef(null)

  const applyWsPayload = useCallback((raw) => {
    if (!raw || typeof raw !== 'object') return
    if (raw.type === 'ping' || raw.type === 'pong') return
    const payload = raw.payload && typeof raw.payload === 'object' ? raw.payload : raw
    if (payload.state && typeof payload.state === 'object') {
      setState(payload)
    } else if (payload.maas || payload.session) {
      setState({ state: payload })
    }
  }, [])

  // Same-origin WS (like LabTerminal), max 5 reconnect attempts with backoff;
  // once exhausted the slow/fast poll effects below take over permanently
  // (until this effect re-runs, e.g. after a re-login).
  useEffect(() => {
    if (!loggedIn) return undefined
    let disposed = false

    const clearReconnectTimer = () => {
      if (wsReconnectTimerRef.current) {
        clearTimeout(wsReconnectTimerRef.current)
        wsReconnectTimerRef.current = null
      }
    }

    const buildWsUrl = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
      return `${protocol}://${window.location.host}/ws/baremetal/${sessionId}/`
    }

    const connect = () => {
      if (disposed) return
      clearReconnectTimer()
      let ws
      try {
        ws = new WebSocket(buildWsUrl())
      } catch {
        return
      }
      wsRef.current = ws
      ws.onopen = () => {
        if (disposed) return
        wsAttemptsRef.current = 0
        setWsConnected(true)
      }
      ws.onmessage = (event) => {
        try { applyWsPayload(JSON.parse(event.data)) } catch { /* ignore malformed frame */ }
      }
      ws.onerror = () => { /* handled by onclose */ }
      ws.onclose = (e) => {
        if (wsRef.current === ws) wsRef.current = null
        setWsConnected(false)
        if (disposed || e.code === 1000) return
        wsAttemptsRef.current += 1
        if (wsAttemptsRef.current > 5) return  // give up — polling fallbacks take over
        const delay = Math.min(1000 * 2 ** (wsAttemptsRef.current - 1), 16000)
        wsReconnectTimerRef.current = setTimeout(connect, delay)
      }
    }

    connect()

    return () => {
      disposed = true
      clearReconnectTimer()
      const ws = wsRef.current
      if (ws) {
        ws.onclose = null
        ws.onerror = null
        ws.onmessage = null
        if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) ws.close(1000)
      }
      wsRef.current = null
      wsAttemptsRef.current = 0
      setWsConnected(false)
    }
  }, [loggedIn, sessionId, applyWsPayload])

  // Slow baseline poll — only while the WebSocket is connecting, retrying, or
  // has permanently given up (transient-only status changes are still caught
  // faster by the 2s poll below).
  useEffect(() => {
    if (!loggedIn || wsConnected) {
      if (slowPollRef.current) { clearInterval(slowPollRef.current); slowPollRef.current = null }
      return undefined
    }
    if (slowPollRef.current) return undefined
    slowPollRef.current = setInterval(() => { refresh() }, 8000)
    return () => { if (slowPollRef.current) { clearInterval(slowPollRef.current); slowPollRef.current = null } }
  }, [loggedIn, wsConnected, refresh])

  // Fast transient-only poll — a stopgap for machines mid-commission/deploy
  // while the WebSocket is down; the WS pushes updates instantly once back up.
  useEffect(() => {
    if (!loggedIn || !anyTransient || wsConnected) {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
      return undefined
    }
    if (pollRef.current) return undefined
    pollRef.current = setInterval(() => { refresh() }, 2000)
    return () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null } }
  }, [loggedIn, anyTransient, wsConnected, refresh])

  useEffect(() => () => {
    if (pollRef.current) clearInterval(pollRef.current)
    if (slowPollRef.current) clearInterval(slowPollRef.current)
  }, [])

  const run = async (fn, okMsg) => {
    if (busy) return
    setBusy(true)
    try {
      const res = await fn()
      if (res?.ok === false) toast.error(res.error || 'Action failed')
      else if (okMsg) toast.success(res?.message || okMsg)
      if (res?.state) setState(res.state)
      else await refresh()
    } finally { setBusy(false) }
  }

  const chromeProps = {
    onHints, onCheck, onExtend, onStop,
    onBackToTerminal: onExit || onToggleTerminal,
    hintsLabel, checkDisabled, extendDisabled,
    backLabel: simTerminalOpen ? 'Hide terminal' : (onExit ? 'Close' : 'Terminal'),
    vmwareHref,
  }

  const applyMachineAction = async (action, machineId, extra = {}) => {
    const mid = machineId
    const m = machines.find((x) => x.id === mid)
    switch (action) {
      case 'commission':
        return run(() => baremetalApi.commission(sessionId, mid), 'Commissioning started')
      case 'deploy':
        return run(
          () => baremetalApi.deploy(sessionId, mid, { boot_resource: extra.boot_resource || deployImage || undefined }),
          'Deploy started',
        )
      case 'release':
        return run(() => baremetalApi.release(sessionId, mid, extra), 'Release started')
      case 'abort':
        return run(() => baremetalApi.abort(sessionId, mid), 'Aborted')
      case 'test':
        return run(() => baremetalApi.testHardware(sessionId, mid), 'Testing started')
      case 'lock':
        return run(() => baremetalApi.lock(sessionId, mid), 'Locked')
      case 'unlock':
        return run(() => baremetalApi.unlock(sessionId, mid), 'Unlocked')
      case 'enterRescue':
        return run(() => baremetalApi.enterRescue(sessionId, mid), 'Entering rescue mode')
      case 'exitRescue':
        return run(() => baremetalApi.exitRescue(sessionId, mid), 'Exiting rescue mode')
      case 'markBroken':
        return run(() => baremetalApi.markBroken(sessionId, mid, extra.comment || ''), 'Marked broken')
      case 'markFixed':
        return run(() => baremetalApi.markFixed(sessionId, mid), 'Marked fixed')
      case 'overrideFailedTesting':
        return run(() => baremetalApi.overrideFailedTesting(sessionId, mid), 'Testing overridden')
      case 'setZone':
        return run(() => baremetalApi.setZone(sessionId, mid, extra.zone || 'default'), 'Zone updated')
      case 'setPool':
        return run(() => baremetalApi.setPool(sessionId, mid, extra.pool || 'default'), 'Pool updated')
      case 'addTag':
        return run(() => baremetalApi.tagMachine(sessionId, m?.hostname || '', extra.tag || 'lab'), 'Tagged')
      case 'delete':
        return run(() => baremetalApi.deleteMachine(sessionId, mid, m?.hostname), 'Machine deleted')
      case 'power':
        return run(() => baremetalApi.power(sessionId, mid, extra.power), 'Power toggled')
      case 'setBootInterface':
        return run(() => baremetalApi.setBootInterface(sessionId, mid, extra.iface), 'Boot interface set')
      case 'applyStorageLayout':
        return run(() => baremetalApi.applyStorageLayout(sessionId, mid, extra.layout || 'flat'), 'Storage layout applied')
      default:
        return run(() => baremetalApi.action(sessionId, action, { machine_id: mid, ...extra }), 'Done')
    }
  }

  const onBulk = async (action, machineIds, extra = {}) => {
    const map = {
      commission: 'maas_commission',
      deploy: 'maas_deploy',
      release: 'maas_release',
      abort: 'maas_abort',
      test: 'maas_test',
      lock: 'maas_lock',
      markBroken: 'maas_mark_broken',
      markFixed: 'maas_mark_fixed',
      delete: 'maas_delete',
      setZone: 'maas_set_zone',
      setPool: 'maas_set_pool',
      enterRescue: 'maas_enter_rescue',
      exitRescue: 'maas_exit_rescue',
    }
    if (action === 'addTag') {
      setBusy(true)
      try {
        for (const id of machineIds) {
          const m = machines.find((x) => x.id === id)
          if (!m) continue
          const res = await baremetalApi.tagMachine(sessionId, m.hostname, extra.tag || 'lab')
          if (res?.ok === false) { toast.error(res.error || 'Tag failed'); break }
        }
        toast.success('Tags applied')
        await refresh()
      } finally { setBusy(false) }
      return
    }
    const apiAction = map[action]
    if (!apiAction) {
      for (const id of machineIds) await applyMachineAction(action, id, extra)
      return
    }
    await run(
      () => baremetalApi.bulkAction(sessionId, apiAction, machineIds, {
        ...extra,
        boot_resource: extra.boot_resource || deployImage || undefined,
        zone: extra.zone,
        pool: extra.pool,
      }),
      `${action} applied`,
    )
  }

  if (!loading && state && !loggedIn) {
    return (
      <div className={simPanelRoot(embedded, 'maas-app bm-shell')}>
        <LabChromeBar title="MAAS" subtitle={scenario?.title || slug} accent={ACCENT} {...chromeProps} />
        <div className="maas-login-wrap">
          <div className="maas-login-card">
            <div className="maas-login-head">
              <span className="maas-wordmark-mark">M</span>
              <div>
                <div style={{ fontWeight: 500, fontSize: '1.1rem' }}>MAAS</div>
                <div style={{ fontSize: '0.75rem', opacity: 0.8 }}>Metal as a Service</div>
              </div>
            </div>
            <div className="maas-login-body">
              <p>Sign in to the region controller to manage machines, images, and networking.</p>
              <label className="maas-label">
                Username
                <input className="maas-input" defaultValue="admin" readOnly />
              </label>
              <label className="maas-label">
                Password
                <input className="maas-input" type="password" defaultValue="••••••••" readOnly />
              </label>
              <button
                type="button"
                className="maas-btn maas-btn-positive"
                style={{ width: '100%', justifyContent: 'center', padding: '0.55rem' }}
                disabled={busy}
                onClick={() => run(() => baremetalApi.login(sessionId), 'Signed in')}
              >
                Log in
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  const detailMachine = detailId != null ? machines.find((m) => m.id === detailId) : null
  const sections = [...new Set(NAV.map((n) => n.section))]

  return (
    <div className={simPanelRoot(embedded, 'maas-app bm-shell sim-product')}>
      <LabChromeBar title="MAAS" subtitle={scenario?.title || slug} accent={ACCENT} {...chromeProps} />

      {goal.objective && (
        <div className="maas-goal-bar">
          <strong>{goal.title}:</strong> {goal.objective}
        </div>
      )}

      <div className="maas-header">
        <div className="maas-wordmark">
          <span className="maas-wordmark-mark">M</span>
          MAAS
        </div>
        <div className="maas-header-meta">
          <span>{st.summary?.version || 'MAAS 3.4'}</span>
          <span className="maas-header-user">{user}</span>
        </div>
      </div>

      <div className="maas-body">
        <nav className="maas-sidenav p-side-navigation" aria-label="MAAS navigation">
          <ul className="p-side-navigation__list">
            {sections.map((sec) => (
              <li key={sec} className="maas-sidenav-group">
                <div className="maas-sidenav-section p-side-navigation__label">{sec}</div>
                {NAV.filter((n) => n.section === sec).map(({ key, label, icon: Icon }) => (
                  <div className="p-side-navigation__item" key={key}>
                    <button
                      type="button"
                      className={`maas-sidenav-item p-side-navigation__link ${nav === key && !detailMachine ? 'is-active' : ''}`}
                      aria-current={nav === key && !detailMachine ? 'page' : undefined}
                      onClick={() => { setNav(key); setDetailId(null) }}
                    >
                      <Icon size={15} /> {label}
                    </button>
                  </div>
                ))}
              </li>
            ))}
          </ul>
        </nav>

        <main className="maas-main">
          {nav === 'machines' && detailMachine && (
            <MachineDetail
              machine={detailMachine}
              busy={busy}
              bootResources={bootResources}
              deployImage={deployImage}
              onDeployImageChange={setDeployImage}
              onBack={() => setDetailId(null)}
              onAction={(action, extra) => applyMachineAction(action, detailMachine.id, {
                ...extra,
                boot_resource: deployImage,
              })}
            />
          )}

          {nav === 'machines' && !detailMachine && (
            <MachinesTable
              machines={machines}
              busy={busy}
              bootResources={bootResources}
              deployImage={deployImage}
              onDeployImageChange={setDeployImage}
              onSelectMachine={setDetailId}
              onBulk={onBulk}
              onAddMachine={(fields) => run(() => baremetalApi.addMachine(sessionId, fields), 'Machine added')}
              onEnlist={() => run(() => baremetalApi.action(sessionId, 'maas_enlist', {}), 'Machine enlisted')}
              onRefresh={refresh}
              zones={st.zones || []}
              pools={st.resource_pools || []}
            />
          )}

          {nav !== 'machines' && (
            <MaasNavPages
              page={nav}
              state={st}
              busy={busy}
              sessionId={sessionId}
              run={run}
              machines={machines}
            />
          )}
        </main>
      </div>
    </div>
  )
}
