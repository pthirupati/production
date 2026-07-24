import { Plus } from 'lucide-react'
import { SimDataTable, SimStatusBadge } from '../sim/shared'
import { socApi } from '../../api/soc'

export function renderSocV2Page({ nav, st, sessionId, busy, run }) {
  if (nav === 'pam') {
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold text-[#e6edf3]">Privileged sessions</h2>
          <button type="button" className="soc-btn-primary flex items-center gap-1" disabled={busy}
            onClick={() => run(() => socApi.startPamSession(sessionId, { target: 'SQLSERVER-PROD-01', protocol: 'DB-SQL' }), 'Session started')}>
            <Plus size={14} /> Connect via PSM
          </button>
        </div>
        <SimDataTable
          variant="dark"
          columns={[
            { key: 'id', label: 'Session' },
            { key: 'user', label: 'User' },
            { key: 'target', label: 'Target' },
            { key: 'protocol', label: 'Protocol' },
            { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status={r.status === 'Active' ? 'warning' : 'success'} label={r.status} /> },
            { key: 'suspicious', label: 'Suspicious' },
            {
              key: 'actions', label: '',
              render: (r) => r.status === 'Active' ? (
                <button type="button" className="soc-btn-outline" disabled={busy}
                  onClick={(e) => { e.stopPropagation(); run(() => socApi.endPamSession(sessionId, r.id), 'Terminated') }}>
                  Terminate
                </button>
              ) : null,
            },
          ]} searchKeys={['id', 'user', 'target', 'protocol', 'status', 'suspicious']} rows={st.pam_sessions || []}
        />
      </div>
    )
  }
  if (nav === 'vulns') {
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold text-[#e6edf3]">Vulnerabilities</h2>
          <button type="button" className="soc-btn-primary flex items-center gap-1" disabled={busy}
            onClick={() => run(() => socApi.scanAsset(sessionId, 'WIN-WEB-02'), 'Scan complete')}>
            <Plus size={14} /> Scan asset
          </button>
        </div>
        <SimDataTable
          variant="dark"
          columns={[
            { key: 'cve', label: 'CVE', sortable: true },
            { key: 'title', label: 'Title' },
            { key: 'cvss', label: 'CVSS', sortable: true },
            { key: 'epss', label: 'EPSS' },
            { key: 'asset', label: 'Asset' },
            { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status={r.status === 'Fixed' ? 'success' : 'error'} label={r.status} /> },
            {
              key: 'actions', label: '',
              render: (r) => r.status !== 'Fixed' ? (
                <button type="button" className="soc-btn-outline" disabled={busy}
                  onClick={(e) => { e.stopPropagation(); run(() => socApi.markVulnFixed(sessionId, r.id), 'Marked fixed') }}>
                  Mark fixed
                </button>
              ) : null,
            },
          ]} searchKeys={['cve', 'title', 'cvss', 'epss', 'asset', 'status']} rows={st.vulnerabilities || []}
          searchKeys={['cve', 'asset']}
        />
      </div>
    )
  }
  if (nav === 'firewall') {
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold text-[#e6edf3]">Firewall policies</h2>
          <button type="button" className="soc-btn-primary flex items-center gap-1" disabled={busy}
            onClick={() => run(() => socApi.createFwRule(sessionId, { name: `Block-${Date.now().toString(36).slice(-4)}`, action: 'deny' }), 'Rule created')}>
            <Plus size={14} /> Add rule
          </button>
        </div>
        <SimDataTable
          variant="dark"
          columns={[
            { key: 'priority', label: '#', sortable: true },
            { key: 'name', label: 'Name' },
            { key: 'src_zone', label: 'Src zone' },
            { key: 'dst_zone', label: 'Dst zone' },
            { key: 'app', label: 'App' },
            { key: 'action', label: 'Action' },
            { key: 'enabled', label: 'Enabled', render: (r) => (r.enabled ? 'Yes' : 'No') },
            {
              key: 'actions', label: '',
              render: (r) => (
                <button type="button" className="soc-btn-outline" disabled={busy}
                  onClick={(e) => { e.stopPropagation(); run(() => socApi.toggleFwRule(sessionId, r.id), 'Rule toggled') }}>
                  Toggle
                </button>
              ),
            },
          ]} searchKeys={['priority', 'name', 'src_zone', 'dst_zone', 'app', 'enabled']} rows={st.firewall_policies || []}
        />
      </div>
    )
  }
  if (nav === 'pcap') {
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold text-[#e6edf3]">Packet capture</h2>
          <button type="button" className="soc-btn-primary flex items-center gap-1" disabled={busy}
            onClick={() => run(() => socApi.startPcap(sessionId, { filter: 'tcp port 443' }), 'Capture started')}>
            <Plus size={14} /> Start capture
          </button>
        </div>
        <SimDataTable
          variant="dark"
          columns={[
            { key: 'id', label: 'ID' },
            { key: 'iface', label: 'Interface' },
            { key: 'filter', label: 'BPF filter' },
            { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status={r.status === 'Capturing' ? 'warning' : 'success'} label={r.status} /> },
            { key: 'packets', label: 'Packets' },
            { key: 'bytes', label: 'Bytes' },
            {
              key: 'actions', label: '',
              render: (r) => r.status === 'Capturing' ? (
                <button type="button" className="soc-btn-outline" disabled={busy}
                  onClick={(e) => { e.stopPropagation(); run(() => socApi.stopPcap(sessionId, r.id), 'Capture stopped') }}>
                  Stop
                </button>
              ) : null,
            },
          ]} searchKeys={['id', 'iface', 'filter', 'status', 'packets', 'bytes']} rows={st.packet_captures || []}
        />
      </div>
    )
  }
  if (nav === 'compliance') {
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold text-[#e6edf3]">Compliance frameworks</h2>
          <button type="button" className="soc-btn-primary" disabled={busy}
            onClick={() => run(() => socApi.runComplianceCheck(sessionId), 'Assessment refreshed')}>
            Run assessment
          </button>
        </div>
        <SimDataTable
          variant="dark"
          columns={[
            { key: 'name', label: 'Framework' },
            { key: 'score_pct', label: 'Score %', sortable: true },
            { key: 'passed', label: 'Passed' },
            { key: 'total', label: 'Total' },
            { key: 'last_check', label: 'Last check', render: (r) => r.last_check || '—' },
          ]} searchKeys={['name', 'score_pct', 'passed', 'total', 'last_check']} rows={st.compliance_frameworks || []}
        />
      </div>
    )
  }
  return null
}
