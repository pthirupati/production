import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { vmwareApi } from '../../api/vmware'
import {
  Server, HardDrive, Network, Power, PowerOff, RefreshCw, AlertTriangle,
  ChevronRight, Activity, ArrowLeft, Loader2,
} from 'lucide-react'
import toast from 'react-hot-toast'

function StatusDot({ status }) {
  const color = status === 'connected' || status === 'poweredOn' ? 'bg-emerald-400'
    : status === 'disconnected' || status === 'poweredOff' ? 'bg-red-400'
    : 'bg-amber-400'
  return <span className={`inline-block w-2 h-2 rounded-full ${color}`} />
}

export default function VMwareSimulator() {
  const { sessionId } = useParams()
  const [state, setState] = useState(null)
  const [loading, setLoading] = useState(true)
  const [acting, setActing] = useState(false)
  const [selectedVm, setSelectedVm] = useState(null)
  const [tab, setTab] = useState('inventory')

  const load = useCallback(async () => {
    try {
      const data = await vmwareApi.getState(sessionId)
      setState(data)
      if (!selectedVm && data.inventory?.vms?.length) {
        setSelectedVm(data.inventory.vms[0])
      }
    } catch {
      toast.error('Could not load VMware simulator')
    } finally {
      setLoading(false)
    }
  }, [sessionId, selectedVm])

  useEffect(() => { load() }, [load])

  const runAction = async (action, payload = {}) => {
    setActing(true)
    try {
      const res = await vmwareApi.action(sessionId, action, payload)
      if (res.state) setState(res.state)
      else await load()
      toast.success(res.message || 'Action completed')
    } catch (err) {
      toast.error(err.response?.data?.error || 'Action failed')
    } finally {
      setActing(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-[#1a1f2e] flex items-center justify-center">
        <Loader2 className="animate-spin text-[#4fa7e8]" size={32} />
      </div>
    )
  }

  const inv = state?.inventory || {}
  const summary = state?.summary || {}

  return (
    <div className="min-h-screen bg-[#1a1f2e] text-[#e8eaed] flex flex-col">
      <header className="h-12 bg-[#0f1419] border-b border-[#2d3548] flex items-center px-4 gap-4 shrink-0">
        <Link to={`/lab/${sessionId}`} className="text-[#8b9cb3] hover:text-white flex items-center gap-1 text-sm">
          <ArrowLeft size={16} /> Back to lab
        </Link>
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded bg-[#4fa7e8]/20 flex items-center justify-center">
            <Server size={16} className="text-[#4fa7e8]" />
          </div>
          <span className="font-semibold text-sm">VMware vCenter Simulator</span>
          <span className="text-xs text-[#8b9cb3]">| {inv.datacenter} / {inv.cluster}</span>
        </div>
        <div className="ml-auto flex items-center gap-3 text-xs text-[#8b9cb3]">
          <span>{summary.hosts_connected}/{summary.hosts_total} hosts</span>
          <span>{summary.vms_on}/{summary.vms_total} VMs on</span>
          {summary.active_alarms > 0 && (
            <span className="text-amber-400 flex items-center gap-1"><AlertTriangle size={12} /> {summary.active_alarms} alarms</span>
          )}
          <button type="button" onClick={load} className="p-1.5 hover:bg-[#2d3548] rounded"><RefreshCw size={14} /></button>
        </div>
      </header>

      <div className="flex flex-1 min-h-0">
        <aside className="w-64 bg-[#141824] border-r border-[#2d3548] overflow-y-auto shrink-0">
          <div className="p-2 text-[10px] uppercase tracking-wider text-[#6b7c93] font-semibold">Inventory</div>
          <div className="px-2 pb-1 text-xs text-[#4fa7e8] font-medium flex items-center gap-1">
            <ChevronRight size={12} className="-rotate-90" /> {inv.datacenter}
          </div>
          <div className="px-4 pb-2 text-xs text-[#8b9cb3]">{inv.cluster}</div>
          {(inv.hosts || []).map(host => (
            <div key={host.id} className="px-3 py-1.5 text-xs flex items-center gap-2 text-[#c5cdd8]">
              <StatusDot status={host.status} />
              <Server size={12} className="text-[#6b7c93]" />
              <span className="truncate">{host.name}</span>
              {host.maintenance && <span className="text-amber-400 text-[10px]">Maint</span>}
            </div>
          ))}
          <div className="p-2 mt-2 text-[10px] uppercase tracking-wider text-[#6b7c93] font-semibold">Virtual Machines</div>
          {(inv.vms || []).map(vm => (
            <button
              key={vm.id}
              type="button"
              onClick={() => setSelectedVm(vm)}
              className={`w-full px-3 py-2 text-left text-xs flex items-center gap-2 hover:bg-[#1e2433] ${selectedVm?.id === vm.id ? 'bg-[#243044] border-l-2 border-[#4fa7e8]' : ''}`}
            >
              <StatusDot status={vm.power} />
              <span className="truncate font-medium">{vm.name}</span>
            </button>
          ))}
        </aside>

        <main className="flex-1 flex flex-col min-w-0">
          <div className="flex border-b border-[#2d3548] bg-[#141824]">
            {['inventory', 'monitor', 'events'].map(t => (
              <button
                key={t}
                type="button"
                onClick={() => setTab(t)}
                className={`px-4 py-2.5 text-xs font-medium capitalize ${tab === t ? 'text-[#4fa7e8] border-b-2 border-[#4fa7e8]' : 'text-[#8b9cb3] hover:text-white'}`}
              >
                {t}
              </button>
            ))}
          </div>

          <div className="flex-1 overflow-y-auto p-4">
            {tab === 'inventory' && selectedVm && (
              <div className="max-w-2xl space-y-4">
                <h2 className="text-lg font-semibold flex items-center gap-2">
                  <StatusDot status={selectedVm.power} />
                  {selectedVm.name}
                </h2>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div className="bg-[#141824] rounded-lg p-3 border border-[#2d3548]">
                    <p className="text-[#6b7c93] text-xs">Power state</p>
                    <p className="font-medium mt-1">{selectedVm.power}</p>
                  </div>
                  <div className="bg-[#141824] rounded-lg p-3 border border-[#2d3548]">
                    <p className="text-[#6b7c93] text-xs">Guest OS</p>
                    <p className="font-medium mt-1">{selectedVm.guest_os}</p>
                  </div>
                  <div className="bg-[#141824] rounded-lg p-3 border border-[#2d3548]">
                    <p className="text-[#6b7c93] text-xs">CPU / Memory</p>
                    <p className="font-medium mt-1">{selectedVm.cpu} vCPU · {selectedVm.memory_mb} MB</p>
                  </div>
                  <div className="bg-[#141824] rounded-lg p-3 border border-[#2d3548]">
                    <p className="text-[#6b7c93] text-xs">IP / Tools</p>
                    <p className="font-medium mt-1">{selectedVm.ip} · {selectedVm.tools}</p>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  {selectedVm.power !== 'poweredOn' && (
                    <button
                      type="button"
                      disabled={acting}
                      onClick={() => runAction('power_on', { vm_name: selectedVm.name })}
                      className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium disabled:opacity-50"
                    >
                      <Power size={16} /> Power On
                    </button>
                  )}
                  {selectedVm.power === 'poweredOn' && (
                    <button
                      type="button"
                      disabled={acting}
                      onClick={() => runAction('power_off', { vm_name: selectedVm.name })}
                      className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-[#2d3548] hover:bg-[#3d4558] text-sm font-medium disabled:opacity-50"
                    >
                      <PowerOff size={16} /> Power Off
                    </button>
                  )}
                </div>
              </div>
            )}

            {tab === 'monitor' && (
              <div className="grid md:grid-cols-2 gap-4">
                {(inv.hosts || []).map(host => (
                  <div key={host.id} className="bg-[#141824] rounded-lg border border-[#2d3548] p-4">
                    <h3 className="font-medium text-sm flex items-center gap-2 mb-3">
                      <StatusDot status={host.status} /> {host.name}
                    </h3>
                    <div className="space-y-2 text-xs">
                      {[
                        ['CPU', host.cpu_pct, 'bg-[#4fa7e8]'],
                        ['Memory', host.mem_pct, 'bg-purple-500'],
                        ['Storage', host.storage_pct, 'bg-amber-500'],
                      ].map(([label, pct, bar]) => (
                        <div key={label}>
                          <div className="flex justify-between text-[#8b9cb3] mb-1"><span>{label}</span><span>{pct}%</span></div>
                          <div className="h-1.5 bg-[#2d3548] rounded-full overflow-hidden">
                            <div className={`h-full ${bar} rounded-full`} style={{ width: `${pct}%` }} />
                          </div>
                        </div>
                      ))}
                    </div>
                    {host.status === 'disconnected' && (
                      <button
                        type="button"
                        disabled={acting}
                        onClick={() => runAction('reconnect_host', { host_name: host.name })}
                        className="mt-3 text-xs text-[#4fa7e8] hover:underline"
                      >
                        Reconnect host
                      </button>
                    )}
                  </div>
                ))}
                <div className="bg-[#141824] rounded-lg border border-[#2d3548] p-4">
                  <h3 className="font-medium text-sm flex items-center gap-2 mb-3"><HardDrive size={14} /> Datastores</h3>
                  {(inv.datastores || []).map(ds => (
                    <div key={ds.id} className="text-xs py-2 border-b border-[#2d3548] last:border-0">
                      <p className="font-medium">{ds.name} <span className="text-[#6b7c93]">({ds.type})</span></p>
                      <p className="text-[#8b9cb3] mt-0.5">{ds.free_gb} GB free of {ds.capacity_gb} GB</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {tab === 'events' && (
              <div className="space-y-1 max-w-3xl">
                {(inv.events || []).slice().reverse().map((ev, i) => (
                  <div key={i} className="text-xs py-2 px-3 rounded bg-[#141824] border border-[#2d3548] flex gap-3">
                    <span className="text-[#6b7c93] shrink-0 font-mono">{ev.time?.slice(11, 19)}</span>
                    <span className={ev.severity === 'critical' ? 'text-red-400' : ev.severity === 'warning' ? 'text-amber-400' : 'text-[#c5cdd8]'}>
                      {ev.message}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  )
}
