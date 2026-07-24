import { Plus } from 'lucide-react'
import { SimDataTable, SimStatusBadge } from '../sim/shared'
import { netappApi } from '../../api/netapp'

export function renderNetAppV2Page({ nav, st, sessionId, busy, run }) {
  if (nav === 'flexgroups') {
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold">FlexGroup volumes</h2>
          <button type="button" className="na-btn-primary flex items-center gap-1" disabled={busy}
            onClick={() => run(() => netappApi.createFlexgroup(sessionId, { name: `fg_${Date.now().toString(36).slice(-4)}` }), 'FlexGroup created')}>
            <Plus size={14} /> Create
          </button>
        </div>
        <SimDataTable columns={[
          { key: 'name', label: 'Name' },
          { key: 'svm', label: 'SVM' },
          { key: 'size_tb', label: 'Size (TB)' },
          { key: 'constituents', label: 'Constituents' },
          { key: 'used_pct', label: 'Used %' },
          { key: 'health', label: 'Health', render: (r) => <SimStatusBadge status="success" label={r.health} /> },
        ]} searchKeys={['name', 'svm', 'size_tb', 'constituents', 'used_pct', 'health']} rows={st.flexgroups || []} />
      </div>
    )
  }
  if (nav === 'snaplock') {
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold">SnapLock (WORM)</h2>
          <button type="button" className="na-btn-primary flex items-center gap-1" disabled={busy}
            onClick={() => run(() => netappApi.enableSnaplock(sessionId, { name: `vol_worm_${Date.now().toString(36).slice(-3)}`, type: 'Compliance' }), 'SnapLock enabled')}>
            <Plus size={14} /> Enable SnapLock
          </button>
        </div>
        <SimDataTable columns={[
          { key: 'name', label: 'Volume' },
          { key: 'svm', label: 'SVM' },
          { key: 'type', label: 'Type' },
          { key: 'retention_days', label: 'Retention (d)' },
          { key: 'worm_files', label: 'WORM files' },
        ]} searchKeys={['name', 'svm', 'type', 'retention_days', 'worm_files']} rows={st.snaplock_volumes || []} />
      </div>
    )
  }
  if (nav === 'svmdr') {
    return (
      <div className="space-y-3">
        <h2 className="text-lg font-semibold mb-2">SVM disaster recovery</h2>
        <SimDataTable columns={[
          { key: 'source_svm', label: 'Source SVM' },
          { key: 'dest_svm', label: 'Destination SVM' },
          { key: 'state', label: 'State', render: (r) => <SimStatusBadge status={r.state === 'snapmirrored' ? 'success' : 'warning'} label={r.state} /> },
          { key: 'lag_sec', label: 'Lag (s)' },
          { key: 'last_transfer', label: 'Last transfer' },
          {
            key: 'actions', label: '',
            render: (r) => (
              <button type="button" className="na-btn-sm" disabled={busy}
                onClick={(e) => { e.stopPropagation(); run(() => netappApi.svmDrFailover(sessionId, r.id), 'Failover complete') }}>
                Failover
              </button>
            ),
          },
        ]} searchKeys={['source_svm', 'dest_svm', 'state', 'lag_sec', 'last_transfer']} rows={st.svm_dr || []} />
      </div>
    )
  }
  if (nav === 's3') {
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold">ONTAP S3</h2>
          <button type="button" className="na-btn-primary flex items-center gap-1" disabled={busy}
            onClick={() => run(() => netappApi.createS3Bucket(sessionId, { name: `bucket-${Date.now().toString(36).slice(-4)}` }), 'Bucket created')}>
            <Plus size={14} /> Create bucket
          </button>
        </div>
        <SimDataTable columns={[
          { key: 'name', label: 'Bucket' },
          { key: 'svm', label: 'SVM' },
          { key: 'capacity_gb', label: 'Capacity (GB)' },
          { key: 'objects', label: 'Objects' },
          { key: 'versioning', label: 'Versioning', render: (r) => (r.versioning ? 'On' : 'Off') },
        ]} searchKeys={['name', 'svm', 'capacity_gb', 'objects', 'versioning']} rows={st.s3_buckets || []} />
      </div>
    )
  }
  if (nav === 'security') {
    return (
      <div className="space-y-5">
        <div>
          <div className="flex justify-between items-center mb-2 flex-wrap gap-2">
            <h2 className="text-lg font-semibold">Anti-ransomware (ARP)</h2>
            <button type="button" className="na-btn-sm" disabled={busy}
              onClick={() => run(() => netappApi.arpSetMode(sessionId, 'active'), 'ARP mode updated')}>
              Set active
            </button>
          </div>
          <SimDataTable columns={[
            { key: 'id', label: 'ID' },
            { key: 'volume', label: 'Volume' },
            { key: 'mode', label: 'Mode' },
            { key: 'severity', label: 'Severity' },
            { key: 'detail', label: 'Detail' },
            { key: 'time', label: 'Time' },
          ]} searchKeys={['id', 'volume', 'mode', 'severity', 'detail', 'time']} rows={st.arp_events || []} />
        </div>
        <div>
          <h2 className="text-lg font-semibold mb-2">Multi-admin verification</h2>
          <SimDataTable columns={[
            { key: 'operation', label: 'Operation' },
            { key: 'target', label: 'Target' },
            { key: 'requested_by', label: 'Requested by' },
            { key: 'approvals', label: 'Approvals' },
            { key: 'status', label: 'Status' },
            {
              key: 'actions', label: '',
              render: (r) => r.status === 'Pending' ? (
                <button type="button" className="na-btn-sm" disabled={busy}
                  onClick={(e) => { e.stopPropagation(); run(() => netappApi.mavApprove(sessionId, r.id), 'Approved') }}>
                  Approve
                </button>
              ) : null,
            },
          ]} searchKeys={['operation', 'target', 'requested_by', 'approvals', 'status']} rows={st.mav_approvals || []} />
        </div>
        <div>
          <div className="flex justify-between items-center mb-2 flex-wrap gap-2">
            <h2 className="text-lg font-semibold">FlexCache</h2>
            <button type="button" className="na-btn-primary flex items-center gap-1" disabled={busy}
              onClick={() => run(() => netappApi.createFlexcache(sessionId, {
                name: `cache_${Date.now().toString(36).slice(-4)}`,
                origin: 'vol_data',
              }), 'FlexCache created')}>
              <Plus size={14} /> Create FlexCache
            </button>
          </div>
          <SimDataTable columns={[
            { key: 'name', label: 'Cache' },
            { key: 'origin', label: 'Origin' },
            { key: 'svm', label: 'SVM' },
            { key: 'size_gb', label: 'Size (GB)' },
            { key: 'hit_ratio_pct', label: 'Hit ratio %' },
          ]} searchKeys={['name', 'origin', 'svm', 'size_gb', 'hit_ratio_pct']} rows={st.flexcaches || []} />
        </div>
      </div>
    )
  }
  return null
}
