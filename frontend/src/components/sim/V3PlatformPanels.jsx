import { useState } from 'react'
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
          <button type="button" className="cicd-btn cicd-btn-approve text-xs flex items-center gap-1" disabled={busy}
            onClick={() => run(() => cicdApi.argoCreateApp(sessionId, {
              name: `app-${Date.now().toString(36).slice(-4)}`,
              namespace: 'default',
            }), 'Application created')}>
            <Plus size={14} /> New application
          </button>
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
                render: (r) => (
                  <div className="flex gap-1 flex-wrap">
                    {!r.ready && !r.suspended && (
                      <button type="button" className="cicd-btn cicd-btn-approve text-xs" disabled={busy}
                        onClick={(e) => { e.stopPropagation(); run(() => cicdApi.fluxReconcile(sessionId, r.name), 'Reconciled') }}>
                        Reconcile
                      </button>
                    )}
                    <button type="button" className="cicd-btn cicd-btn-approve text-xs" disabled={busy}
                      onClick={(e) => {
                        e.stopPropagation()
                        run(
                          () => cicdApi.fluxSuspend(sessionId, r.name, !r.suspended),
                          r.suspended ? 'Resumed' : 'Suspended',
                        )
                      }}>
                      {r.suspended ? 'Resume' : 'Suspend'}
                    </button>
                  </div>
                ),
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
            { key: 'suspended', label: 'Suspended', render: (r) => (r.suspended ? 'Yes' : 'No') },
            {
              key: 'actions', label: '',
              render: (r) => (
                <div className="flex gap-1 flex-wrap">
                  {!r.ready && !r.suspended && (
                    <button type="button" className="cicd-btn cicd-btn-approve text-xs" disabled={busy}
                      onClick={(e) => { e.stopPropagation(); run(() => cicdApi.fluxHelmReconcile(sessionId, r.name), 'Reconciled') }}>
                      Reconcile
                    </button>
                  )}
                  <button type="button" className="cicd-btn cicd-btn-approve text-xs" disabled={busy}
                    onClick={(e) => {
                      e.stopPropagation()
                      run(
                        () => cicdApi.fluxSuspend(sessionId, r.name, !r.suspended, 'helmrelease'),
                        r.suspended ? 'Resumed' : 'Suspended',
                      )
                    }}>
                    {r.suspended ? 'Resume' : 'Suspend'}
                  </button>
                </div>
              ),
            },
          ]} rows={flux.helm_releases || []} />
        </div>
      </div>
    )
  }
  if (nav === 'github') {
    const gh = st.github || {}
    const issues = gh.issues || []
    const prs = gh.pull_requests || []
    const runs = gh.actions_runs || []
    return (
      <div className="space-y-5 p-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <div>
            <h2 className="text-lg font-semibold text-[#e6edf3]">{gh.repo || 'fixitlab/app'}</h2>
            <p className="text-xs text-slate-400">{gh.open_issues ?? issues.filter((i) => i.state === 'open').length} open issues · {gh.open_prs ?? prs.filter((p) => p.state === 'open').length} open PRs · default {gh.default_branch || 'main'}</p>
          </div>
          <div className="flex gap-2">
            <button type="button" className="cicd-btn cicd-btn-approve text-xs" disabled={busy}
              onClick={() => run(() => cicdApi.githubCreateIssue(sessionId, { title: `Lab issue ${Date.now() % 1000}` }), 'Issue opened')}>
              <Plus size={12} /> New issue
            </button>
            <button type="button" className="cicd-btn cicd-btn-approve text-xs" disabled={busy}
              onClick={() => run(() => cicdApi.githubCreatePr(sessionId, { title: `lab: change ${Date.now() % 1000}` }), 'PR opened')}>
              <Plus size={12} /> New PR
            </button>
          </div>
        </div>
        <div>
          <h3 className="text-sm font-semibold text-[#e6edf3] mb-2">Issues</h3>
          <SimDataTable
            variant="dark"
            columns={[
              { key: 'number', label: '#', sortable: true },
              { key: 'title', label: 'Title' },
              { key: 'state', label: 'State', render: (r) => <SimStatusBadge status={r.state === 'open' ? 'warning' : 'success'} label={r.state} /> },
              { key: 'labels', label: 'Labels', render: (r) => (r.labels || []).join(', ') },
              { key: 'author', label: 'Author' },
              {
                key: 'actions', label: '',
                render: (r) => r.state === 'open' ? (
                  <button type="button" className="cicd-btn text-xs" disabled={busy}
                    onClick={(e) => { e.stopPropagation(); run(() => cicdApi.githubCloseIssue(sessionId, r.number), 'Closed') }}>
                    Close
                  </button>
                ) : null,
              },
            ]}
            rows={issues}
            searchKeys={['title', 'author']}
          />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-[#e6edf3] mb-2">Pull requests</h3>
          <SimDataTable
            variant="dark"
            columns={[
              { key: 'number', label: '#', sortable: true },
              { key: 'title', label: 'Title' },
              { key: 'state', label: 'State', render: (r) => <SimStatusBadge status={r.state === 'merged' ? 'success' : r.state === 'open' ? 'warning' : 'pending'} label={r.state} /> },
              { key: 'head', label: 'Branch', render: (r) => `${r.head} → ${r.base}` },
              { key: 'checks', label: 'Checks', render: (r) => <SimStatusBadge status={r.checks === 'success' ? 'success' : r.checks === 'failure' ? 'error' : 'pending'} label={r.checks} /> },
              { key: 'review', label: 'Review' },
              {
                key: 'actions', label: '',
                render: (r) => r.state === 'open' ? (
                  <div className="flex gap-1">
                    {r.review !== 'approved' && (
                      <button type="button" className="cicd-btn text-xs" disabled={busy}
                        onClick={(e) => { e.stopPropagation(); run(() => cicdApi.githubApprovePr(sessionId, r.number), 'Approved') }}>
                        Approve
                      </button>
                    )}
                    <button type="button" className="cicd-btn cicd-btn-approve text-xs" disabled={busy}
                      onClick={(e) => { e.stopPropagation(); run(() => cicdApi.githubMergePr(sessionId, r.number), 'Merged') }}>
                      Merge
                    </button>
                  </div>
                ) : null,
              },
            ]}
            rows={prs}
            searchKeys={['title', 'head']}
          />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-[#e6edf3] mb-2">Actions runs</h3>
          <SimDataTable
            variant="dark"
            columns={[
              { key: 'id', label: 'Run' },
              { key: 'workflow', label: 'Workflow' },
              { key: 'branch', label: 'Branch' },
              { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status={r.status === 'success' ? 'success' : 'error'} label={r.status} /> },
              { key: 'duration_s', label: 'Duration (s)' },
              {
                key: 'actions', label: '',
                render: (r) => r.status !== 'success' ? (
                  <button type="button" className="cicd-btn text-xs" disabled={busy}
                    onClick={(e) => { e.stopPropagation(); run(() => cicdApi.githubRerunWorkflow(sessionId, r.id), 'Re-ran') }}>
                    Re-run
                  </button>
                ) : null,
              },
            ]}
            rows={runs}
          />
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
          {
            key: 'actions', label: '',
            render: (r) => (
              <button type="button" className="text-xs text-[#cf2a27] underline" disabled={busy}
                onClick={(e) => { e.stopPropagation(); run(() => openstackApi.action(sessionId, 'add_router_interface', { name: r.name }), 'Interface added') }}>
                Add interface
              </button>
            ),
          },
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
          {
            key: 'actions', label: '',
            render: (r) => (
              <button type="button" className="text-xs text-red-600 underline" disabled={busy}
                onClick={(e) => { e.stopPropagation(); run(() => openstackApi.action(sessionId, 'delete_heat_stack', { name: r.name }), 'Stack deleted') }}>
                Delete
              </button>
            ),
          },
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
  if (nav === 'object-storage') {
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <h2 className="text-lg font-semibold">Object Storage (Swift)</h2>
          <button type="button" className="os-btn-primary flex items-center gap-1" disabled={busy}
            onClick={() => run(() => openstackApi.action(sessionId, 'create_object_container', { name: `container-${Date.now() % 1000}` }), 'Container created')}>
            <Plus size={14} /> Create Container
          </button>
        </div>
        <SimDataTable columns={[
          { key: 'name', label: 'Container' },
          { key: 'objects', label: 'Objects' },
          { key: 'bytes', label: 'Bytes', render: (r) => `${Math.round((r.bytes || 0) / 1024)} KiB` },
          { key: 'public', label: 'Public', render: (r) => (r.public ? 'Yes' : 'No') },
        ]} rows={st.object_containers || []} />
      </div>
    )
  }
  if (nav === 'hypervisors') {
    return (
      <div className="space-y-3">
        <h2 className="text-lg font-semibold">Hypervisors</h2>
        <SimDataTable columns={[
          { key: 'hostname', label: 'Hostname' },
          { key: 'type', label: 'Type' },
          { key: 'vcpus', label: 'vCPUs', render: (r) => `${r.vcpus_used}/${r.vcpus}` },
          { key: 'ram', label: 'RAM (GiB)', render: (r) => `${r.ram_used_gb}/${r.ram_gb}` },
          { key: 'vms', label: 'VMs' },
          { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status={r.status === 'up' ? 'success' : 'error'} label={r.status} /> },
        ]} rows={st.hypervisors || []} />
      </div>
    )
  }
  if (nav === 'snapshots') {
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <h2 className="text-lg font-semibold">Volume Snapshots</h2>
          <button type="button" className="os-btn-primary flex items-center gap-1" disabled={busy}
            onClick={() => run(() => openstackApi.action(sessionId, 'create_volume_snapshot', {
              volume: (st.volumes || [])[0]?.name || 'vol-db',
              snapshot_name: `snap-${Date.now() % 1000}`,
            }), 'Snapshot created')}>
            <Plus size={14} /> Create Snapshot
          </button>
        </div>
        <SimDataTable columns={[
          { key: 'name', label: 'Name' },
          { key: 'volume', label: 'Volume' },
          { key: 'size_gb', label: 'Size (GiB)' },
          { key: 'status', label: 'Status' },
          { key: 'created', label: 'Created' },
        ]} rows={st.volume_snapshots || []} />
      </div>
    )
  }
  if (nav === 'server-groups') {
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <h2 className="text-lg font-semibold">Server Groups</h2>
          <button type="button" className="os-btn-primary flex items-center gap-1" disabled={busy}
            onClick={() => run(() => openstackApi.action(sessionId, 'create_server_group', {
              name: `sg-${Date.now() % 1000}`, policy: 'anti-affinity',
            }), 'Server group created')}>
            <Plus size={14} /> Create Server Group
          </button>
        </div>
        <SimDataTable columns={[
          { key: 'name', label: 'Name' },
          { key: 'policy', label: 'Policy' },
          { key: 'members', label: 'Members' },
        ]} rows={st.server_groups || []} />
      </div>
    )
  }
  return null
}

export function renderAimlV2Page({ nav, st, sessionId, busy, run, ragQuery, setRagQuery }) {
  if (nav === 'experiments') {
    return (
      <div className="space-y-5 p-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold text-[#E2E2F0]">Experiments</h2>
          <div className="flex gap-2">
            <button type="button" className="px-3 py-1.5 rounded bg-[#7C3AED] text-white text-sm" disabled={busy}
              onClick={() => run(() => aimlApi.createExperiment(sessionId, { name: `exp-${Date.now() % 1000}` }), 'Experiment created')}>
              New experiment
            </button>
            <button type="button" className="px-3 py-1.5 rounded border border-[#7C3AED] text-[#A78BFA] text-sm" disabled={busy}
              onClick={() => run(() => aimlApi.logRun(sessionId, {
                name: `run-${Date.now().toString(36).slice(-4)}`,
              }), 'Run logged')}>
              Log run
            </button>
          </div>
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
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold text-[#E2E2F0]">Model Registry</h2>
          <button type="button" className="px-3 py-1.5 rounded bg-[#7C3AED] text-white text-sm" disabled={busy}
            onClick={() => run(() => aimlApi.registerModel(sessionId, {
              name: `model-${Date.now().toString(36).slice(-4)}`,
              stage: 'Staging',
            }), 'Model registered')}>
            Register model
          </button>
        </div>
        <SimDataTable variant="dark" columns={[
          { key: 'name', label: 'Model' },
          { key: 'latest_version', label: 'Version' },
          { key: 'stage', label: 'Stage', render: (r) => <SimStatusBadge status={r.stage === 'Production' ? 'success' : 'warning'} label={r.stage} /> },
          {
            key: 'actions', label: '',
            render: (r) => r.stage !== 'Production' ? (
              <button type="button" className="text-xs text-[#A78BFA]" disabled={busy}
                onClick={(e) => { e.stopPropagation(); run(() => aimlApi.transitionModelStage(sessionId, r.name, 'Production'), 'Promoted') }}>
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
            onClick={() => run(() => aimlApi.ragRetrieve(sessionId, ragQuery), 'Retrieved')}>
            Retrieve
          </button>
        </div>
        <SimDataTable variant="dark" columns={[
          { key: 'score', label: 'Score' },
          { key: 'source', label: 'Source' },
          { key: 'text', label: 'Text' },
        ]} rows={st.rag_results || []} />
        <div className="flex justify-between items-center flex-wrap gap-2 pt-2">
          <h2 className="text-lg font-semibold text-[#E2E2F0]">Knowledge Bases</h2>
          <button type="button" className="px-3 py-1.5 rounded bg-[#7C3AED] text-white text-sm" disabled={busy}
            onClick={() => run(() => aimlApi.createKnowledgeBase(sessionId, {
              name: `kb-${Date.now().toString(36).slice(-4)}`,
              documents: 12,
              chunks: 180,
            }), 'Knowledge base created')}>
            Create knowledge base
          </button>
        </div>
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
  if (nav === 'playground') {
    return <AimlPlaygroundPanel st={st} sessionId={sessionId} busy={busy} run={run} />
  }
  return null
}

function AimlPlaygroundPanel({ st, sessionId, busy, run }) {
  const playground = st.llm_playground || {}
  const models = playground.models || ['GPT-4o']
  const [model, setModel] = useState(playground.last_model || models[0])
  const [prompt, setPrompt] = useState(playground.last_prompt || '')
  const usage = playground.token_usage || {}
  return (
    <div className="space-y-3 p-3 max-w-3xl">
      <h2 className="text-lg font-semibold text-[#E2E2F0]">LLM Playground</h2>
      <p className="text-xs text-[#9CA3AF]">Lab Environment chat — grounded responses for training (not a live model API).</p>
      <label className="block text-xs text-[#9CA3AF]">
        Model
        <select className="mt-1 w-full bg-[#1A1B26] border border-[#2A2B3D] rounded px-3 py-2 text-sm text-[#E2E2F0]"
          value={model} onChange={(e) => setModel(e.target.value)}>
          {models.map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
      </label>
      <textarea
        className="w-full h-28 bg-[#1A1B26] border border-[#2A2B3D] rounded px-3 py-2 text-sm text-[#E2E2F0]"
        placeholder="Ask a question…"
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
      />
      <button type="button" className="px-3 py-1.5 rounded bg-[#7C3AED] text-white text-sm" disabled={busy || !prompt.trim()}
        onClick={() => run(() => aimlApi.action(sessionId, 'llm_chat', { prompt, model }), 'Response generated')}>
        Generate
      </button>
      {playground.last_response && (
        <div className="rounded border border-[#2A2B3D] bg-[#12131C] p-3 text-sm text-[#E2E2F0] whitespace-pre-wrap">
          {playground.last_response}
          <div className="text-[10px] text-[#9CA3AF] mt-2">
            Tokens · in {usage.input || 0} · out {usage.output || 0}
            {playground.last_model ? ` · ${playground.last_model}` : ''}
          </div>
        </div>
      )}
    </div>
  )
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
    const groups = ex.pushgateway?.groups || []
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
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold">Pushgateway</h2>
          <button type="button" className="px-3 py-1.5 rounded bg-[#E6522C] text-white text-sm" disabled={busy}
            onClick={() => run(() => monitoringApi.pushgatewayPush(sessionId, {
              job: 'batch-export',
              instance: `cron-${Date.now().toString(36).slice(-3)}`,
              metrics: 3,
            }), 'Metrics pushed')}>
            Push metrics
          </button>
        </div>
        <SimDataTable columns={[
          { key: 'job', label: 'Job' },
          { key: 'instance', label: 'Instance' },
          { key: 'metrics', label: 'Metrics' },
          { key: 'last_push', label: 'Last push' },
        ]} rows={groups} />
      </div>
    )
  }
  return null
}
