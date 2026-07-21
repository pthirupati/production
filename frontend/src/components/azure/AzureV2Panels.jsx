import { Plus } from 'lucide-react'
import { SimDataTable, SimStatusBadge, SimModal } from '../sim/shared'
import { azureApi } from '../../api/azure'

/** V2 Azure portal blades: VMSS, App Service, Functions, Container Apps, Firewall, Cosmos, Sentinel, Entra. */
export function AzureV2NavExtras() {
  return [
    { key: 'vmss', label: 'Virtual machine scale sets' },
    { key: 'appservice', label: 'App Services' },
    { key: 'functions', label: 'Function apps' },
    { key: 'containerapps', label: 'Container apps' },
    { key: 'aks', label: 'Kubernetes services' },
    { key: 'firewall', label: 'Firewalls & VPN' },
    { key: 'cosmos', label: 'Azure Cosmos DB' },
    { key: 'sentinel', label: 'Microsoft Sentinel' },
    { key: 'entra', label: 'Microsoft Entra ID' },
  ]
}

export function renderAzureV2Page({
  nav, st, sessionId, busy, run,
  createVmssOpen, setCreateVmssOpen, vmssName, setVmssName, vmssCap, setVmssCap,
  createAppOpen, setCreateAppOpen, appName, setAppName,
  createFuncOpen, setCreateFuncOpen, funcName, setFuncName,
  createCaOpen, setCreateCaOpen, caName, setCaName,
  createAksOpen, setCreateAksOpen, aksName, setAksName,
  inviteOpen, setInviteOpen, inviteUpn, setInviteUpn,
}) {
  const vmss = st.vmss || []
  const webApps = st.web_apps || []
  const plans = st.app_service_plans || []
  const funcs = st.function_apps || []
  const aksClusters = st.aks_clusters || []
  const cas = st.container_apps || []
  const envs = st.container_apps_envs || []
  const firewalls = st.firewalls || []
  const vpnGateways = st.vpn_gateways || []
  const cosmos = st.cosmos_accounts || []
  const sentinel = st.sentinel || {}
  const entra = st.entra || {}

  if (nav === 'vmss') {
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold">Virtual machine scale sets</h2>
          <button type="button" className="az-btn-primary flex items-center gap-1" onClick={() => setCreateVmssOpen(true)}>
            <Plus size={14} /> Create
          </button>
        </div>
        <SimDataTable
          columns={[
            { key: 'name', label: 'Name', sortable: true },
            { key: 'sku', label: 'Size', sortable: true },
            { key: 'capacity', label: 'Instances', sortable: true },
            { key: 'orchestration', label: 'Orchestration' },
            { key: 'upgrade_policy', label: 'Upgrade policy' },
            {
              key: 'actions', label: 'Scale',
              render: (r) => (
                <div className="flex gap-1">
                  <button type="button" className="az-btn-sm" disabled={busy}
                    onClick={(e) => { e.stopPropagation(); run(() => azureApi.scaleVmss(sessionId, r.name, Math.max(0, (r.capacity || 1) - 1)), 'Scaled in') }}>−</button>
                  <button type="button" className="az-btn-sm" disabled={busy}
                    onClick={(e) => { e.stopPropagation(); run(() => azureApi.scaleVmss(sessionId, r.name, (r.capacity || 0) + 1), 'Scaled out') }}>+</button>
                </div>
              ),
            },
          ]}
          rows={vmss}
          searchKeys={['name']}
          expandRow={(r) => (
            <div className="az-detail-panel text-sm space-y-2 p-3">
              <div><strong>Autoscale:</strong> min {r.autoscale?.min} / max {r.autoscale?.max} · CPU out {r.autoscale?.cpu_out}%</div>
              <SimDataTable
                columns={[
                  { key: 'name', label: 'Instance' },
                  { key: 'power_state', label: 'Power', render: (i) => <SimStatusBadge status={i.power_state === 'running' ? 'success' : 'pending'} label={i.power_state} /> },
                  { key: 'private_ip', label: 'Private IP' },
                ]}
                rows={r.instances || []}
              />
            </div>
          )}
        />
        <SimModal open={createVmssOpen} onClose={() => setCreateVmssOpen(false)} title="Create a virtual machine scale set"
          footer={<>
            <button type="button" className="text-sm px-3" onClick={() => setCreateVmssOpen(false)}>Cancel</button>
            <button type="button" className="az-btn-primary" disabled={busy} onClick={() => {
              run(() => azureApi.createVmss(sessionId, { name: vmssName, capacity: Number(vmssCap) || 2 }), 'Scale set created')
              setCreateVmssOpen(false)
            }}>Create</button>
          </>}>
          <label className="block text-sm">Name
            <input className="w-full mt-1 border rounded px-2 py-1.5" value={vmssName} onChange={(e) => setVmssName(e.target.value)} />
          </label>
          <label className="block text-sm mt-3">Instance count
            <input type="number" min={0} max={20} className="w-full mt-1 border rounded px-2 py-1.5" value={vmssCap} onChange={(e) => setVmssCap(e.target.value)} />
          </label>
        </SimModal>
      </div>
    )
  }

  if (nav === 'appservice') {
    return (
      <div className="space-y-5">
        <div>
          <h2 className="text-lg font-semibold mb-2">App Service plans</h2>
          <SimDataTable columns={[
            { key: 'name', label: 'Name', sortable: true },
            { key: 'sku', label: 'SKU', sortable: true },
            { key: 'os', label: 'OS' },
            { key: 'apps', label: 'Apps' },
            { key: 'location', label: 'Region' },
          ]} rows={plans} searchKeys={['name']} />
        </div>
        <div>
          <div className="flex justify-between items-center mb-2 flex-wrap gap-2">
            <h2 className="text-lg font-semibold">Web apps</h2>
            <button type="button" className="az-btn-primary flex items-center gap-1" onClick={() => setCreateAppOpen(true)}>
              <Plus size={14} /> Create
            </button>
          </div>
          <SimDataTable
            columns={[
              { key: 'name', label: 'Name', sortable: true },
              { key: 'state', label: 'Status', render: (r) => <SimStatusBadge status={r.state === 'Running' ? 'success' : 'pending'} label={r.state} /> },
              { key: 'runtime', label: 'Runtime' },
              { key: 'plan', label: 'Plan' },
              { key: 'url', label: 'URL', render: (r) => <a className="az-link" href={r.url} onClick={(e) => e.preventDefault()}>{r.url}</a> },
              {
                key: 'actions', label: 'Slots',
                render: (r) => (
                  <button type="button" className="az-btn-sm" disabled={busy}
                    onClick={(e) => { e.stopPropagation(); run(() => azureApi.swapWebSlots(sessionId, r.name), 'Slots swapped') }}>
                    Swap staging
                  </button>
                ),
              },
            ]}
            rows={webApps}
            searchKeys={['name']}
            expandRow={(r) => (
              <div className="az-detail-panel text-sm p-3 space-y-2">
                <div>HTTPS only: {r.https_only ? 'On' : 'Off'} · Always On: {r.always_on ? 'On' : 'Off'}</div>
                <div><strong>Deployment slots</strong></div>
                <SimDataTable columns={[
                  { key: 'name', label: 'Slot' },
                  { key: 'traffic_pct', label: 'Traffic %' },
                ]} rows={r.slots || []} />
                <div><strong>Application settings</strong></div>
                <SimDataTable columns={[
                  { key: 'name', label: 'Name' },
                  { key: 'value', label: 'Value' },
                ]} rows={r.app_settings || []} />
              </div>
            )}
          />
        </div>
        <SimModal open={createAppOpen} onClose={() => setCreateAppOpen(false)} title="Create Web App"
          footer={<>
            <button type="button" className="text-sm px-3" onClick={() => setCreateAppOpen(false)}>Cancel</button>
            <button type="button" className="az-btn-primary" disabled={busy} onClick={() => {
              run(() => azureApi.createWebApp(sessionId, { name: appName }), 'Web app created')
              setCreateAppOpen(false)
            }}>Create</button>
          </>}>
          <label className="block text-sm">Name
            <input className="w-full mt-1 border rounded px-2 py-1.5" value={appName} onChange={(e) => setAppName(e.target.value)} />
          </label>
          <p className="text-xs text-slate-600 mt-2">*.azurewebsites.net · Linux · plan asp-prod</p>
        </SimModal>
      </div>
    )
  }

  if (nav === 'functions') {
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold">Function apps</h2>
          <button type="button" className="az-btn-primary flex items-center gap-1" onClick={() => setCreateFuncOpen(true)}>
            <Plus size={14} /> Create
          </button>
        </div>
        <SimDataTable
          columns={[
            { key: 'name', label: 'Name', sortable: true },
            { key: 'state', label: 'Status', render: (r) => <SimStatusBadge status="success" label={r.state} /> },
            { key: 'runtime', label: 'Runtime', render: (r) => `${r.runtime} ${r.version || ''}`.trim() },
            { key: 'plan', label: 'Plan' },
            { key: 'functions', label: 'Functions', render: (r) => (r.functions || []).length },
          ]}
          rows={funcs}
          searchKeys={['name']}
          expandRow={(r) => (
            <div className="az-detail-panel text-sm p-3 space-y-2">
              <div className="flex justify-between items-center">
                <strong>Functions</strong>
                <button type="button" className="az-btn-sm" disabled={busy}
                  onClick={() => run(() => azureApi.createFunction(sessionId, r.name, { function_name: `HttpTrigger${(r.functions || []).length + 1}`, trigger: 'http' }), 'Function created')}>
                  <Plus size={11} /> Add HTTP trigger
                </button>
              </div>
              <SimDataTable columns={[
                { key: 'name', label: 'Name' },
                { key: 'trigger', label: 'Trigger' },
                { key: 'auth_level', label: 'Auth level' },
                { key: 'invocations_24h', label: 'Invocations (24h)' },
              ]} rows={r.functions || []} />
            </div>
          )}
        />
        <SimModal open={createFuncOpen} onClose={() => setCreateFuncOpen(false)} title="Create Function App"
          footer={<>
            <button type="button" className="text-sm px-3" onClick={() => setCreateFuncOpen(false)}>Cancel</button>
            <button type="button" className="az-btn-primary" disabled={busy} onClick={() => {
              run(() => azureApi.createFunctionApp(sessionId, { name: funcName }), 'Function app created')
              setCreateFuncOpen(false)
            }}>Create</button>
          </>}>
          <label className="block text-sm">Name
            <input className="w-full mt-1 border rounded px-2 py-1.5" value={funcName} onChange={(e) => setFuncName(e.target.value)} />
          </label>
        </SimModal>
      </div>
    )
  }

  if (nav === 'containerapps') {
    return (
      <div className="space-y-5">
        <div>
          <h2 className="text-lg font-semibold mb-2">Environments</h2>
          <SimDataTable columns={[
            { key: 'name', label: 'Name' },
            { key: 'plan', label: 'Plan' },
            { key: 'log_analytics', label: 'Log Analytics' },
            { key: 'location', label: 'Region' },
          ]} rows={envs} />
        </div>
        <div>
          <div className="flex justify-between items-center mb-2 flex-wrap gap-2">
            <h2 className="text-lg font-semibold">Container apps</h2>
            <button type="button" className="az-btn-primary flex items-center gap-1" onClick={() => setCreateCaOpen(true)}>
              <Plus size={14} /> Create
            </button>
          </div>
          <SimDataTable
            columns={[
              { key: 'name', label: 'Name', sortable: true },
              { key: 'environment', label: 'Environment' },
              { key: 'replicas', label: 'Replicas' },
              { key: 'cpu', label: 'CPU' },
              { key: 'memory', label: 'Memory' },
              { key: 'ingress', label: 'Ingress' },
            ]}
            rows={cas}
            searchKeys={['name']}
            expandRow={(r) => (
              <div className="az-detail-panel text-sm p-3 space-y-1">
                <div>Image: <code>{r.image}</code></div>
                <div>URL: {r.url}</div>
                <SimDataTable columns={[
                  { key: 'name', label: 'Revision' },
                  { key: 'active', label: 'Active', render: (x) => (x.active ? 'Yes' : 'No') },
                  { key: 'traffic_pct', label: 'Traffic %' },
                ]} rows={r.revisions || []} />
              </div>
            )}
          />
        </div>
        <SimModal open={createCaOpen} onClose={() => setCreateCaOpen(false)} title="Create Container App"
          footer={<>
            <button type="button" className="text-sm px-3" onClick={() => setCreateCaOpen(false)}>Cancel</button>
            <button type="button" className="az-btn-primary" disabled={busy} onClick={() => {
              run(() => azureApi.createContainerApp(sessionId, { name: caName }), 'Container app created')
              setCreateCaOpen(false)
            }}>Create</button>
          </>}>
          <label className="block text-sm">Name
            <input className="w-full mt-1 border rounded px-2 py-1.5" value={caName} onChange={(e) => setCaName(e.target.value)} />
          </label>
        </SimModal>
      </div>
    )
  }

  if (nav === 'aks') {
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold">Kubernetes services</h2>
          <button type="button" className="az-btn-primary flex items-center gap-1" onClick={() => setCreateAksOpen(true)}>
            <Plus size={14} /> Create
          </button>
        </div>
        <SimDataTable
          columns={[
            { key: 'name', label: 'Name', sortable: true },
            { key: 'kubernetes_version', label: 'Version' },
            { key: 'sku', label: 'SKU' },
            { key: 'network_plugin', label: 'Network' },
            {
              key: 'nodes', label: 'Nodes',
              render: (r) => (r.node_pools || []).reduce((n, p) => n + (p.count || 0), 0),
            },
            {
              key: 'provisioning_state', label: 'Status',
              render: (r) => <SimStatusBadge status="success" label={r.provisioning_state || 'Succeeded'} />,
            },
            {
              key: 'actions', label: '',
              render: (r) => (
                <button
                  type="button"
                  className="az-btn-outline text-xs"
                  disabled={busy}
                  onClick={(e) => {
                    e.stopPropagation()
                    const pool = (r.node_pools || [])[0]
                    if (!pool) return
                    run(
                      () => azureApi.scaleAksNodePool(sessionId, r.name, pool.name, (pool.count || 1) + 1),
                      'Node pool scaled',
                    )
                  }}
                >
                  Scale +1
                </button>
              ),
            },
          ]}
          rows={aksClusters}
          searchKeys={['name']}
          expandRow={(r) => (
            <div className="az-detail-panel text-sm p-3 space-y-2">
              <div>FQDN: <code>{r.fqdn}</code></div>
              <SimDataTable
                columns={[
                  { key: 'name', label: 'Node pool' },
                  { key: 'mode', label: 'Mode' },
                  { key: 'count', label: 'Count' },
                  { key: 'vm_size', label: 'Size' },
                  { key: 'autoscaling', label: 'Autoscale', render: (p) => (p.autoscaling ? 'On' : 'Off') },
                ]}
                rows={r.node_pools || []}
              />
            </div>
          )}
        />
        <SimModal open={createAksOpen} onClose={() => setCreateAksOpen(false)} title="Create AKS cluster"
          footer={<>
            <button type="button" className="text-sm px-3" onClick={() => setCreateAksOpen(false)}>Cancel</button>
            <button type="button" className="az-btn-primary" disabled={busy} onClick={() => {
              run(() => azureApi.createAksCluster(sessionId, { name: aksName }), 'AKS cluster created')
              setCreateAksOpen(false)
            }}>Create</button>
          </>}>
          <label className="block text-sm">Cluster name
            <input className="w-full mt-1 border rounded px-2 py-1.5" value={aksName} onChange={(e) => setAksName(e.target.value)} />
          </label>
        </SimModal>
      </div>
    )
  }

  if (nav === 'firewall') {
    return (
      <div className="space-y-5">
        <div>
          <h2 className="text-lg font-semibold mb-2">Azure Firewall</h2>
          <SimDataTable
            columns={[
              { key: 'name', label: 'Name' },
              { key: 'sku', label: 'SKU' },
              { key: 'public_ip', label: 'Public IP' },
              { key: 'threat_intel', label: 'Threat intel' },
            ]}
            rows={firewalls}
            expandRow={(r) => (
              <div className="az-detail-panel text-sm p-3 space-y-2">
                <div className="flex justify-between">
                  <strong>Network rules</strong>
                  <button type="button" className="az-btn-sm" disabled={busy}
                    onClick={() => run(() => azureApi.createFirewallRule(sessionId, r.name, {
                      kind: 'network', rule_name: `allow-${Date.now().toString(36).slice(-4)}`,
                      source: '10.10.0.0/16', dest: '*', ports: '443',
                    }), 'Rule added')}>
                    <Plus size={11} /> Add network rule
                  </button>
                </div>
                <SimDataTable columns={[
                  { key: 'name', label: 'Name' },
                  { key: 'source', label: 'Source' },
                  { key: 'dest', label: 'Destination' },
                  { key: 'ports', label: 'Ports' },
                  { key: 'action', label: 'Action' },
                ]} rows={r.network_rules || []} />
                <strong>Application rules</strong>
                <SimDataTable columns={[
                  { key: 'name', label: 'Name' },
                  { key: 'source', label: 'Source' },
                  { key: 'fqdns', label: 'FQDNs' },
                  { key: 'action', label: 'Action' },
                ]} rows={r.app_rules || []} />
              </div>
            )}
          />
        </div>
        <div>
          <h2 className="text-lg font-semibold mb-2">VPN gateways</h2>
          <SimDataTable
            columns={[
              { key: 'name', label: 'Name' },
              { key: 'sku', label: 'SKU' },
              { key: 'generation', label: 'Generation' },
              { key: 'bgp_asn', label: 'BGP ASN' },
              { key: 'connections', label: 'Connections', render: (r) => (r.connections || []).length },
            ]}
            rows={vpnGateways}
            expandRow={(r) => (
              <SimDataTable columns={[
                { key: 'name', label: 'Connection' },
                { key: 'type', label: 'Type' },
                { key: 'status', label: 'Status', render: (c) => <SimStatusBadge status={c.status === 'Connected' ? 'success' : 'pending'} label={c.status} /> },
                { key: 'local_network', label: 'Local network gateway' },
              ]} rows={r.connections || []} />
            )}
          />
        </div>
      </div>
    )
  }

  if (nav === 'cosmos') {
    return (
      <div className="space-y-3">
        <h2 className="text-lg font-semibold">Azure Cosmos DB</h2>
        <SimDataTable
          columns={[
            { key: 'name', label: 'Account', sortable: true },
            { key: 'api', label: 'API' },
            { key: 'consistency', label: 'Consistency' },
            { key: 'location', label: 'Region' },
            { key: 'databases', label: 'Databases', render: (r) => (r.databases || []).length },
          ]}
          rows={cosmos}
          searchKeys={['name']}
          expandRow={(r) => (
            <div className="az-detail-panel text-sm p-3 space-y-2">
              {(r.databases || []).map((db) => (
                <div key={db.name}>
                  <div className="font-medium mb-1">{db.name}</div>
                  <SimDataTable
                    columns={[
                      { key: 'name', label: 'Container' },
                      { key: 'partition_key', label: 'Partition key' },
                      { key: 'throughput', label: 'RU/s' },
                      { key: 'items', label: 'Items' },
                      {
                        key: 'actions', label: '',
                        render: (c) => (
                          <button type="button" className="az-btn-sm" disabled={busy}
                            onClick={() => run(() => azureApi.createCosmosItem(sessionId, r.name, db.name, c.name), 'Item inserted')}>
                            Insert item
                          </button>
                        ),
                      },
                    ]}
                    rows={db.containers || []}
                  />
                </div>
              ))}
            </div>
          )}
        />
      </div>
    )
  }

  if (nav === 'sentinel') {
    return (
      <div className="space-y-5">
        <div className="az-tile" style={{ maxWidth: 320 }}>
          <div className="az-tile-label">Log Analytics workspace</div>
          <div className="az-tile-num" style={{ fontSize: 16 }}>{sentinel.workspace || '—'}</div>
        </div>
        <div>
          <h2 className="text-lg font-semibold mb-2">Incidents</h2>
          <SimDataTable
            columns={[
              { key: 'id', label: 'ID' },
              { key: 'title', label: 'Title', sortable: true },
              { key: 'severity', label: 'Severity' },
              { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status={r.status === 'Closed' ? 'success' : 'warning'} label={r.status} /> },
              { key: 'tactics', label: 'Tactics', render: (r) => (r.tactics || []).join(', ') },
              {
                key: 'actions', label: '',
                render: (r) => r.status !== 'Closed' ? (
                  <button type="button" className="az-btn-sm" disabled={busy}
                    onClick={(e) => { e.stopPropagation(); run(() => azureApi.sentinelUpdateIncident(sessionId, r.id, 'Closed'), 'Incident closed') }}>
                    Close
                  </button>
                ) : null,
              },
            ]}
            rows={sentinel.incidents || []}
          />
        </div>
        <div>
          <h2 className="text-lg font-semibold mb-2">Analytics rules</h2>
          <SimDataTable columns={[
            { key: 'name', label: 'Name' },
            { key: 'kind', label: 'Kind' },
            { key: 'enabled', label: 'Enabled', render: (r) => (r.enabled ? 'Yes' : 'No') },
            { key: 'firings_30d', label: 'Firings (30d)' },
          ]} rows={sentinel.analytics_rules || []} />
        </div>
        <div>
          <h2 className="text-lg font-semibold mb-2">Data connectors</h2>
          <SimDataTable columns={[
            { key: 'name', label: 'Connector' },
            { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status="success" label={r.status} /> },
          ]} rows={sentinel.connectors || []} />
        </div>
      </div>
    )
  }

  if (nav === 'entra') {
    return (
      <div className="space-y-5">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="az-tile"><div className="az-tile-label">Tenant</div><div className="az-tile-num" style={{ fontSize: 14 }}>{entra.tenant}</div></div>
          <div className="az-tile"><div className="az-tile-label">Tenant ID</div><div className="az-tile-num" style={{ fontSize: 12 }}>{entra.tenant_id}</div></div>
          <div className="az-tile"><div className="az-tile-label">Users</div><div className="az-tile-num">{(entra.users || []).length}</div></div>
        </div>
        <div>
          <div className="flex justify-between items-center mb-2 flex-wrap gap-2">
            <h2 className="text-lg font-semibold">Users</h2>
            <button type="button" className="az-btn-primary flex items-center gap-1" onClick={() => setInviteOpen(true)}>
              <Plus size={14} /> Invite user
            </button>
          </div>
          <SimDataTable columns={[
            { key: 'display', label: 'Name', sortable: true },
            { key: 'upn', label: 'User principal name', sortable: true },
            { key: 'type', label: 'User type' },
            { key: 'mfa', label: 'MFA', render: (r) => (r.mfa ? 'Registered' : 'Not registered') },
          ]} rows={entra.users || []} searchKeys={['upn', 'display']} />
        </div>
        <div>
          <h2 className="text-lg font-semibold mb-2">Groups</h2>
          <SimDataTable columns={[
            { key: 'name', label: 'Name' },
            { key: 'type', label: 'Type' },
            { key: 'members', label: 'Members' },
          ]} rows={entra.groups || []} />
        </div>
        <div>
          <h2 className="text-lg font-semibold mb-2">App registrations</h2>
          <SimDataTable columns={[
            { key: 'name', label: 'Name' },
            { key: 'app_id', label: 'Application (client) ID' },
            { key: 'secrets', label: 'Secrets' },
          ]} rows={entra.app_registrations || []} />
        </div>
        <div>
          <h2 className="text-lg font-semibold mb-2">Conditional Access</h2>
          <SimDataTable columns={[
            { key: 'name', label: 'Policy' },
            { key: 'state', label: 'State' },
            { key: 'users', label: 'Users' },
            { key: 'grant', label: 'Grant' },
          ]} rows={entra.conditional_access || []} />
        </div>
        <SimModal open={inviteOpen} onClose={() => setInviteOpen(false)} title="Invite external user"
          footer={<>
            <button type="button" className="text-sm px-3" onClick={() => setInviteOpen(false)}>Cancel</button>
            <button type="button" className="az-btn-primary" disabled={busy} onClick={() => {
              run(() => azureApi.entraInviteUser(sessionId, inviteUpn), 'Invitation sent')
              setInviteOpen(false)
            }}>Invite</button>
          </>}>
          <label className="block text-sm">Email / UPN
            <input className="w-full mt-1 border rounded px-2 py-1.5" value={inviteUpn} onChange={(e) => setInviteUpn(e.target.value)} placeholder="partner@fabrikam.com" />
          </label>
        </SimModal>
      </div>
    )
  }

  return null
}
