import { Plus } from 'lucide-react'
import { SimDataTable, SimStatusBadge } from '../sim/shared'
import { dellemcApi } from '../../api/dellemc'

export function renderDellEmcV2Page({ nav, st, sessionId, busy, run }) {
  if (nav === 'powerstore') {
    return (
      <div className="space-y-5">
        <div>
          <div className="flex justify-between items-center mb-2 flex-wrap gap-2">
            <h2 className="text-lg font-semibold">PowerStore Metro</h2>
            <button type="button" className="de-btn-primary flex items-center gap-1" disabled={busy}
              onClick={() => run(() => dellemcApi.enablePowerstoreMetro(sessionId, { name: `metro-${Date.now().toString(36).slice(-4)}` }), 'Metro enabled')}>
              <Plus size={14} /> Enable Metro
            </button>
          </div>
          <SimDataTable columns={[
            { key: 'name', label: 'Volume' },
            { key: 'local', label: 'Local' },
            { key: 'remote', label: 'Remote' },
            { key: 'rpo', label: 'RPO' },
            { key: 'state', label: 'State', render: (r) => <SimStatusBadge status="success" label={r.state} /> },
            { key: 'witness', label: 'Witness' },
          ]} searchKeys={['name', 'local', 'remote', 'rpo', 'state', 'witness']} rows={st.powerstore_metro || []} />
        </div>
        <div>
          <div className="flex justify-between items-center mb-2 flex-wrap gap-2">
            <h2 className="text-lg font-semibold">vVols</h2>
            <button type="button" className="de-btn-primary flex items-center gap-1" disabled={busy}
              onClick={() => run(() => dellemcApi.registerVvol(sessionId, {
                name: `vvol-ds-${Date.now().toString(36).slice(-4)}`,
              }), 'vVol registered')}>
              <Plus size={14} /> Register vVol
            </button>
          </div>
          <SimDataTable columns={[
            { key: 'name', label: 'Datastore' },
            { key: 'vasa', label: 'VASA' },
            { key: 'vms', label: 'VMs' },
            { key: 'policy', label: 'Policy' },
          ]} searchKeys={['name', 'vasa', 'vms', 'policy']} rows={st.vvols || []} />
        </div>
      </div>
    )
  }
  if (nav === 'datadomain') {
    return (
      <div className="space-y-5">
        <div>
          <div className="flex justify-between items-center mb-2 flex-wrap gap-2">
            <h2 className="text-lg font-semibold">Retention Lock</h2>
            <button type="button" className="de-btn-primary flex items-center gap-1" disabled={busy}
              onClick={() => run(() => dellemcApi.enableRetentionLock(sessionId, { mode: 'Compliance' }), 'Lock enabled')}>
              <Plus size={14} /> Enable lock
            </button>
          </div>
          <SimDataTable columns={[
            { key: 'mtree', label: 'MTree' },
            { key: 'mode', label: 'Mode' },
            { key: 'min_days', label: 'Min days' },
            { key: 'locked_files', label: 'Locked files' },
          ]} searchKeys={['mtree', 'mode', 'min_days', 'locked_files']} rows={st.dd_retention_locks || []} />
        </div>
        <div>
          <div className="flex justify-between items-center mb-2 flex-wrap gap-2">
            <h2 className="text-lg font-semibold">DD Boost storage units</h2>
            <button type="button" className="de-btn-sm" disabled={busy}
              onClick={() => run(() => dellemcApi.createDdboostUnit(sessionId, { name: `SU-${Date.now().toString(36).slice(-4)}` }), 'Unit created')}>
              <Plus size={11} /> Create
            </button>
          </div>
          <SimDataTable columns={[
            { key: 'name', label: 'Unit' },
            { key: 'user', label: 'User' },
            { key: 'used_tb', label: 'Used (TB)' },
            { key: 'logical_tb', label: 'Logical (TB)' },
            { key: 'dsp', label: 'DSP', render: (r) => (r.dsp ? 'On' : 'Off') },
          ]} searchKeys={['name', 'user', 'used_tb', 'logical_tb', 'dsp']} rows={st.ddboost_storage_units || []} />
        </div>
      </div>
    )
  }
  if (nav === 'vxrail') {
    return (
      <div className="space-y-3">
        <h2 className="text-lg font-semibold">VxRail clusters</h2>
        <SimDataTable
          columns={[
            { key: 'name', label: 'Cluster' },
            { key: 'nodes', label: 'Nodes' },
            { key: 'version', label: 'Version' },
            { key: 'health', label: 'Health', render: (r) => <SimStatusBadge status="success" label={r.health} /> },
            {
              key: 'lcm', label: 'LCM',
              render: (r) => `${r.lcm?.status || '—'} ${r.lcm?.progress_pct != null ? `(${r.lcm.progress_pct}%)` : ''}`,
            },
            {
              key: 'actions', label: '',
              render: (r) => (
                <button type="button" className="de-btn-sm" disabled={busy}
                  onClick={(e) => { e.stopPropagation(); run(() => dellemcApi.runVxrailLcm(sessionId, r.name), 'LCM started') }}>
                  Start LCM
                </button>
              ),
            },
          ]} searchKeys={['name', 'nodes', 'version', 'health', 'lcm']} rows={st.vxrail_clusters || []}
          expandRow={(r) => (
            <div className="text-sm p-2">Pre-upgrade checks: {r.lcm?.checks_passed}/{r.lcm?.checks_total} · Bundle {r.lcm?.bundle}</div>
          )}
        />
      </div>
    )
  }
  if (nav === 'idrac') {
    return (
      <div className="space-y-3">
        <h2 className="text-lg font-semibold">iDRAC 9</h2>
        <SimDataTable
          columns={[
            { key: 'host', label: 'Host' },
            { key: 'service_tag', label: 'Service tag' },
            { key: 'health', label: 'Health', render: (r) => <SimStatusBadge status={r.health === 'OK' ? 'success' : 'warning'} label={r.health} /> },
            { key: 'power', label: 'Power' },
            { key: 'cpu_temp_c', label: 'CPU °C' },
            { key: 'inlet_c', label: 'Inlet °C' },
            { key: 'psu_w', label: 'PSU (W)' },
            {
              key: 'actions', label: '',
              render: (r) => (
                <button type="button" className="de-btn-sm" disabled={busy}
                  onClick={(e) => { e.stopPropagation(); run(() => dellemcApi.idracPowerCycle(sessionId, r.service_tag), 'Power cycle issued') }}>
                  Power cycle
                </button>
              ),
            },
          ]} searchKeys={['host', 'service_tag', 'health', 'power', 'cpu_temp_c', 'inlet_c']} rows={st.idrac_blades || []}
          expandRow={(r) => (
            <div className="space-y-2 text-sm p-2">
              <div>Fans: {(r.fans_rpm || []).join(' / ')} RPM</div>
              <SimDataTable columns={[
                { key: 'sev', label: 'Severity' },
                { key: 'msg', label: 'Message' },
                { key: 'time', label: 'Time' },
              ]} searchKeys={['sev', 'msg', 'time']} rows={r.sel || []} />
            </div>
          )}
        />
      </div>
    )
  }
  return null
}
