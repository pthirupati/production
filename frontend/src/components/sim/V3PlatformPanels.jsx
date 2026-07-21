import { Plus } from 'lucide-react'
import { SimDataTable, SimStatusBadge } from '../sim/shared'
import { cicdApi } from '../../api/cicd'
import { openstackApi } from '../../api/openstack'
import { aimlApi } from '../../api/aiml'
import { monitoringApi } from '../../api/monitoring'

/** GitOps blades rendered inside CI/CD pipeline lab. */
export function renderCicdGitOpsPage({ nav, st, sessionId, busy, run }) {
  if (nav === 'argocd') {
    return (
      <div className="space-y-3 p-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold text-[#e6edf3]">Argo CD Applications</h2>
        </div>
        <SimDataTable
          variant="dark"
          columns={[
            { key: 'name', label: 'Name', sortable: true },
            { key: 'namespace', label: 'Namespace' },
            { key: 'sync_status', label: 'Sync', render: (r) => <SimStatusBadge status={r.sync_status === 'Synced' ? 'success' : 'warning'} label={r.sync_status} /> },
            { key: 'health', label: 'Health', render: (r) => <SimStatusBadge status={r.health === 'Healthy' ? 'success' : 'error'} label={r.health} /> },
            { key: 'repo', label: 'Repo' },
            { key: 'path', label: 'Path' },
            {
              key: 'actions', label: '',
              render: (r) => r.sync_status !== 'Synced' ? (
                <button type="button" className="cicd-btn cicd-btn-approve text-xs" disabled={busy}
                  onClick={(e) => { e.stopPropagation(); run(() => cicdApi.argoSync(sessionId, r.name), 'Synced') }}>
                  Sync
                </button>
              ) : null,
            },
          ]}
          rows={st.argo_apps || []}
          searchKeys={['name', 'namespace']}
        />
      </div>
    )
  }
  if (nav === 'flux') {
    const flux = st.flux || {}
    return (
      <div className="space-y-5 p-3">
        <div>
          <h2 className="text-lg font-semibold text-[#e6edf3] mb-2">Kustomizations</h2>
          <SimDataTable
            variant="dark"
            columns={[
              { key: 'name', label: 'Name' },
              { key: 'ready', label: 'Ready', render: (r) => <SimStatusBadge status={r.ready ? 'success' : 'warning'} label={r.ready ? 'True' : 'False'} /> },
              { key: 'revision', label: 'Revision' },
              { key: 'path', label: 'Path' },
              { key: 'suspended', label: 'Suspended', render: (r) => (r.suspended ? 'Yes' : 'No') },
              {
                key: 'actions', label: '',
                render: (r) => !r.ready ? (
                  <button type="button" className="cicd-btn cicd-btn-approve text-xs" disabled={busy}
                    onClick={(e) => { e.stopPropagation(); run(() => cicdApi.fluxReconcile(sessionId, r.name), 'Reconciled') }}>
                    Reconcile
                  </button>
                ) : null,
              },
            ]}
            rows={flux.kustomizations || []}
          />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-[#e6edf3] mb-2">HelmReleases</h2>
          <SimDataTable variant="dark" columns={[
            { key: 'name', label: 'Name' },
            { key: 'namespace', label: 'Namespace' },
            { key: 'chart', label: 'Chart' },
            { key: 'version', label: 'Version' },
            { key: 'ready', label: 'Ready', render: (r) => <SimStatusBadge status={r.ready ? 'success' : 'warning'} label={r.ready ? 'True' : 'False'} /> },
          ]} rows={flux.helm_releases || []} />
        </div>
      </div>
    )
  }
  return null
}

export function renderOpenStackV2Page({ nav, st, sessionId, busy, run }) {
  if (nav === 'routers') {
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <h2 className="text-lg font-semibold">Routers</h2>
          <button type="button" className="os-btn-primary flex items-center gap-1" disabled={busy}
            onClick={() => run(() => openstackApi.action(sessionId, 'create_router', { name: `router-${Date.now() % 1000}` }), 'Router created')}>
            <Plus size={14} /> Create Router
          </button>
        </div>
        <SimDataTable columns={[
          { key: 'name', label: 'Name' },
          { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status="success" label={r.status} /> },
          { key: 'external_network', label: 'External Network' },
          { key: 'ha', label: 'HA', render: (r) => (r.ha ? 'Yes' : 'No') },
          { key: 'interfaces', label: 'Interfaces', render: (r) => (r.interfaces || []).length },
        ]} rows={st.routers || []} />
      </div>
    )
  }
  if (nav === 'loadbalancers') {
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <h2 className="text-lg font-semibold">Load Balancers</h2>
          <button type="button" className="os-btn-primary flex items-center gap-1" disabled={busy}
            onClick={() => run(() => openstackApi.action(sessionId, 'create_load_balancer', { name: `lb-${Date.now() % 1000}` }), 'LB created')}>
            <Plus size={14} /> Create LB
          </button>
        </div>
        <SimDataTable columns={[
          { key: 'name', label: 'Name' },
          { key: 'vip', label: 'VIP' },
          { key: 'status', label: 'Status' },
          { key: 'pool', label: 'Algorithm', render: (r) => r.pool?.algorithm },
          { key: 'members', label: 'Members', render: (r) => r.pool?.members },
        ]} rows={st.load_balancers || []} />
      </div>
    )
  }
  if (nav === 'orchestration') {
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <h2 className="text-lg font-semibold">Heat Stacks</h2>
          <button type="button" className="os-btn-primary flex items-center gap-1" disabled={busy}
            onClick={() => run(() => openstackApi.action(sessionId, 'create_heat_stack', { name: `stack-${Date.now() % 1000}` }), 'Stack created')}>
            <Plus size={14} /> Launch Stack
          </button>
        </div>
        <SimDataTable columns={[
          { key: 'name', label: 'Name' },
          { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status="success" label={r.status} /> },
          { key: 'resources', label: 'Resources', render: (r) => (r.resources || []).length },
          { key: 'created', label: 'Created' },
        ]} rows={st.heat_stacks || []}
          expandRow={(r) => (
            <div className="text-sm p-2 space-y-1">
              {(r.resources || []).map((res) => (
                <div key={res.name}>{res.type} / {res.name} — {res.status}</div>
              ))}
            </div>
          )}
        />
      </div>
    )
  }
  if (nav === 'keypairs') {
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <h2 className="text-lg font-semibold">Key Pairs</h2>
          <button type="button" className="os-btn-primary flex items-center gap-1" disabled={busy}
            onClick={() => run(() => openstackApi.action(sessionId, 'create_keypair', { name: `key-${Date.now() % 1000}` }), 'Keypair created')}>
            <Plus size={14} /> Create Key Pair
          </button>
        </div>
        <SimDataTable columns={[
          { key: 'name', label: 'Name' },
          { key: 'fingerprint', label: 'Fingerprint' },
          { key: 'type', label: 'Type' },
        ]} rows={st.keypairs || []} />
      </div>
    )
  }
  return null
}

export function renderAimlV2Page({ nav, st, sessionId, busy, run, ragQuery, setRagQuery }) {
  if (nav === 'experiments') {
    return (
      <div className="space-y-5 p-3">
        <div className="flex justify-between items-center">
          <h2 className="text-lg font-semibold text-[#E2E2F0]">Experiments</h2>
          <button type="button" className="px-3 py-1.5 rounded bg-[#7C3AED] text-white text-sm" disabled={busy}
            onClick={() => run(() => aimlApi.action(sessionId, 'create_experiment', { name: `exp-${Date.now() % 1000}` }), 'Experiment created')}>
            New experiment
          </button>
        </div>
        <SimDataTable variant="dark" columns={[
          { key: 'name', label: 'Name', sortable: true },
          { key: 'runs', label: 'Runs' },
          { key: 'tags', label: 'Tags', render: (r) => (r.tags || []).join(', ') },
          { key: 'created', label: 'Created' },
        ]} rows={st.experiments || []} />
        <h2 className="text-lg font-semibold text-[#E2E2F0]">Runs</h2>
        <SimDataTable variant="dark" columns={[
          { key: 'name', label: 'Run' },
          { key: 'status', label: 'Status' },
          { key: 'metrics', label: 'Metrics', render: (r) => Object.entries(r.metrics || {}).map(([k, v]) => `${k}=${v}`).join(' ') },
          { key: 'params', label: 'Params', render: (r) => Object.entries(r.params || {}).map(([k, v]) => `${k}=${v}`).join(' ') },
        ]} rows={st.ml_runs || []} />
      </div>
    )
  }
  if (nav === 'registry') {
    return (
      <div className="space-y-3 p-3">
        <h2 className="text-lg font-semibold text-[#E2E2F0]">Model Registry</h2>
        <SimDataTable variant="dark" columns={[
          { key: 'name', label: 'Model' },
          { key: 'latest_version', label: 'Version' },
          { key: 'stage', label: 'Stage', render: (r) => <SimStatusBadge status={r.stage === 'Production' ? 'success' : 'warning'} label={r.stage} /> },
          {
            key: 'actions', label: '',
            render: (r) => r.stage !== 'Production' ? (
              <button type="button" className="text-xs text-[#A78BFA]" disabled={busy}
                onClick={(e) => { e.stopPropagation(); run(() => aimlApi.action(sessionId, 'transition_model_stage', { name: r.name, stage: 'Production' }), 'Promoted') }}>
                Promote
              </button>
            ) : null,
          },
        ]} rows={st.model_registry || []} />
      </div>
    )
  }
  if (nav === 'rag') {
    return (
      <div className="space-y-3 p-3">
        <h2 className="text-lg font-semibold text-[#E2E2F0]">RAG Retrieval Test</h2>
        <div className="flex gap-2">
          <input className="flex-1 bg-[#1A1B26] border border-[#2A2B3D] rounded px-3 py-2 text-sm text-[#E2E2F0]"
            value={ragQuery || ''} onChange={(e) => setRagQuery(e.target.value)}
            placeholder="What is the refund policy for digital products?" />
          <button type="button" className="px-3 py-1.5 rounded bg-[#7C3AED] text-white text-sm" disabled={busy}
            onClick={() => run(() => aimlApi.action(sessionId, 'rag_retrieve', { query: ragQuery }), 'Retrieved')}>
            Retrieve
          </button>
        </div>
        <SimDataTable variant="dark" columns={[
          { key: 'score', label: 'Score' },
          { key: 'source', label: 'Source' },
          { key: 'text', label: 'Text' },
        ]} rows={st.rag_results || []} />
        <h2 className="text-lg font-semibold text-[#E2E2F0] pt-2">Knowledge Bases</h2>
        <SimDataTable variant="dark" columns={[
          { key: 'name', label: 'Name' },
          { key: 'vector_store', label: 'Store' },
          { key: 'documents', label: 'Docs' },
          { key: 'chunks', label: 'Chunks' },
          { key: 'embedding_model', label: 'Embedding' },
          { key: 'status', label: 'Status' },
        ]} rows={st.knowledge_bases || []} />
      </div>
    )
  }
  return null
}

export function renderMonitoringV2Extras({ nav, st, sessionId, busy, run }) {
  if (nav === 'silences') {
    const silences = (st.prometheus?.alertmanager?.silences) || []
    return (
      <div className="space-y-3 p-3">
        <div className="flex justify-between items-center">
          <h2 className="text-lg font-semibold">Alertmanager Silences</h2>
          <button type="button" className="px-3 py-1.5 rounded bg-[#E6522C] text-white text-sm" disabled={busy}
            onClick={() => run(() => monitoringApi.action(sessionId, 'create_silence', { alertname: 'NodeDown', comment: 'Lab silence' }), 'Silence created')}>
            Create silence
          </button>
        </div>
        <SimDataTable columns={[
          { key: 'id', label: 'ID' },
          { key: 'created_by', label: 'Created by' },
          { key: 'comment', label: 'Comment' },
          { key: 'state', label: 'State', render: (r) => <SimStatusBadge status={r.state === 'active' ? 'warning' : 'success'} label={r.state} /> },
          { key: 'ends_at', label: 'Ends' },
          {
            key: 'actions', label: '',
            render: (r) => r.state === 'active' ? (
              <button type="button" className="text-xs text-red-500" disabled={busy}
                onClick={(e) => { e.stopPropagation(); run(() => monitoringApi.action(sessionId, 'expire_silence', { id: r.id }), 'Expired') }}>
                Expire
              </button>
            ) : null,
          },
        ]} rows={silences} />
      </div>
    )
  }
  if (nav === 'exporters') {
    const ex = st.exporters || {}
    const probes = ex.blackbox?.probes || []
    return (
      <div className="space-y-5 p-3">
        <div className="flex justify-between items-center">
          <h2 className="text-lg font-semibold">Blackbox probes</h2>
          <button type="button" className="px-3 py-1.5 rounded bg-[#E6522C] text-white text-sm" disabled={busy}
            onClick={() => run(() => monitoringApi.action(sessionId, 'blackbox_probe', { target: 'https://example.com' }), 'Probed')}>
            Probe example.com
          </button>
        </div>
        <SimDataTable columns={[
          { key: 'target', label: 'Target' },
          { key: 'module', label: 'Module' },
          { key: 'success', label: 'Success', render: (r) => <SimStatusBadge status={r.success ? 'success' : 'error'} label={r.success ? 'OK' : 'FAIL'} /> },
          { key: 'duration_s', label: 'Duration (s)' },
        ]} rows={probes} />
      </div>
    )
  }
  return null
}
