import { Plus } from 'lucide-react'
import { SimDataTable, SimStatusBadge } from '../sim/shared'
import { commvaultApi } from '../../api/commvault'

export function renderCommvaultV2Page({ nav, st, sessionId, busy, run }) {
  if (nav === 'ransomware') {
    const rw = st.ransomware || {}
    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold">Ransomware protection</h2>
          <button type="button" className="cv-btn-primary" disabled={busy}
            onClick={() => run(() => commvaultApi.enableRansomwareProtection(sessionId), 'Scan completed')}>
            Run threat scan
          </button>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="cv-tile"><div className="cv-tile-label">Status</div><div className="cv-tile-num" style={{ fontSize: 14 }}>{rw.enabled ? 'Enabled' : 'Disabled'}</div></div>
          <div className="cv-tile"><div className="cv-tile-label">Honeypot files</div><div className="cv-tile-num">{rw.honeypot_files ?? 0}</div></div>
          <div className="cv-tile"><div className="cv-tile-label">WORM coverage</div><div className="cv-tile-num">{rw.worm_coverage_pct ?? 0}%</div></div>
          <div className="cv-tile"><div className="cv-tile-label">Last scan</div><div className="cv-tile-num" style={{ fontSize: 11 }}>{rw.threat_scan_last || '—'}</div></div>
        </div>
        <SimDataTable columns={[
          { key: 'id', label: 'ID' },
          { key: 'client', label: 'Client' },
          { key: 'severity', label: 'Severity' },
          { key: 'detail', label: 'Detail' },
          { key: 'time', label: 'Time' },
        ]} searchKeys={['id', 'client', 'severity', 'detail', 'time']} rows={rw.anomaly_events || []} />
      </div>
    )
  }
  if (nav === 'k8s') {
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold">Kubernetes</h2>
          <button type="button" className="cv-btn-primary flex items-center gap-1" disabled={busy}
            onClick={() => run(() => commvaultApi.createK8sBackup(sessionId, { name: `k8s-${Date.now().toString(36).slice(-4)}`, distribution: 'GKE' }), 'App registered')}>
            <Plus size={14} /> Add cluster
          </button>
        </div>
        <SimDataTable columns={[
          { key: 'name', label: 'Cluster' },
          { key: 'distribution', label: 'Distribution' },
          { key: 'namespaces', label: 'Namespaces', render: (r) => (r.namespaces || []).join(', ') },
          { key: 'plan', label: 'Plan' },
          { key: 'pvcs', label: 'PVCs' },
          { key: 'last_backup', label: 'Last backup', render: (r) => <SimStatusBadge status={r.last_backup === 'Success' ? 'success' : 'pending'} label={r.last_backup} /> },
        ]} searchKeys={['name', 'distribution', 'namespaces', 'plan', 'pvcs', 'last_backup']} rows={st.k8s_apps || []} />
      </div>
    )
  }
  if (nav === 'saas') {
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold">SaaS applications</h2>
          <button type="button" className="cv-btn-primary flex items-center gap-1" disabled={busy}
            onClick={() => run(() => commvaultApi.registerSaasApp(sessionId, { name: `Salesforce-${Date.now().toString(36).slice(-3)}`, type: 'Salesforce' }), 'Registered')}>
            <Plus size={14} /> Register
          </button>
        </div>
        <SimDataTable columns={[
          { key: 'name', label: 'Name' },
          { key: 'type', label: 'Type' },
          { key: 'workloads', label: 'Workloads', render: (r) => (r.workloads || []).join(', ') },
          { key: 'users', label: 'Users' },
          { key: 'last_backup', label: 'Last backup' },
        ]} searchKeys={['name', 'type', 'workloads', 'users', 'last_backup']} rows={st.saas_apps || []} />
      </div>
    )
  }
  if (nav === 'plans') {
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold">Plans</h2>
          <button type="button" className="cv-btn-primary flex items-center gap-1" disabled={busy}
            onClick={() => run(() => commvaultApi.createPlan(sessionId, { name: `Plan-${Date.now().toString(36).slice(-4)}`, type: 'VM' }), 'Plan created')}>
            <Plus size={14} /> Create plan
          </button>
        </div>
        <SimDataTable columns={[
          { key: 'name', label: 'Name' },
          { key: 'type', label: 'Type' },
          { key: 'rpo_hours', label: 'RPO (h)' },
          { key: 'retention_days', label: 'Retention (d)' },
          { key: 'encryption', label: 'Encryption' },
          { key: 'secondary_copy', label: 'Secondary', render: (r) => (r.secondary_copy ? 'Yes' : 'No') },
          { key: 'workloads', label: 'Workloads' },
        ]} searchKeys={['name', 'type', 'rpo_hours', 'retention_days', 'encryption', 'secondary_copy']} rows={st.plans || []} />
      </div>
    )
  }
  if (nav === 'reports') {
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold">Reports</h2>
          <button type="button" className="cv-btn-primary flex items-center gap-1" disabled={busy}
            onClick={() => run(() => commvaultApi.runCustomReport(sessionId, { name: 'Backup Summary', source: 'Jobs' }), 'Report ready')}>
            <Plus size={14} /> Run report
          </button>
        </div>
        <SimDataTable columns={[
          { key: 'name', label: 'Report' },
          { key: 'source', label: 'Source' },
          { key: 'rows', label: 'Rows' },
          { key: 'last_run', label: 'Last run' },
        ]} searchKeys={['name', 'source', 'rows', 'last_run']} rows={st.report_defs || []} />
      </div>
    )
  }
  return null
}
