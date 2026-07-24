import { Plus } from 'lucide-react'
import { SimDataTable, SimStatusBadge, SimModal } from '../sim/shared'
import { gcpApi } from '../../api/gcp'

/** V2 GCP console blades: Cloud Run, Pub/Sub, GKE, Functions, SQL, Secrets, Armor, Spanner. */
export function renderGcpV2Page({
  nav, st, sessionId, busy, run,
  createRunOpen, setCreateRunOpen, runName, setRunName,
  createTopicOpen, setCreateTopicOpen, topicName, setTopicName,
  createGkeOpen, setCreateGkeOpen, gkeName, setGkeName,
  createFnOpen, setCreateFnOpen, fnName, setFnName,
  createSqlOpen, setCreateSqlOpen, sqlName, setSqlName,
  createSecOpen, setCreateSecOpen, secName, setSecName,
}) {
  if (nav === 'run') {
    const services = st.cloud_run_services || []
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold">Cloud Run</h2>
          <button type="button" className="gcp-btn-primary flex items-center gap-1" onClick={() => setCreateRunOpen(true)}>
            <Plus size={14} /> Create service
          </button>
        </div>
        <SimDataTable
          columns={[
            { key: 'name', label: 'Service', sortable: true },
            { key: 'region', label: 'Region' },
            { key: 'url', label: 'URL', render: (r) => <span className="gcp-link">{r.url}</span> },
            { key: 'cpu', label: 'CPU' },
            { key: 'memory', label: 'Memory' },
            {
              key: 'actions', label: 'Traffic',
              render: (r) => (
                <button type="button" className="gcp-btn-sm" disabled={busy}
                  onClick={(e) => { e.stopPropagation(); run(() => gcpApi.updateCloudRunTraffic(sessionId, r.name, 20), 'Traffic updated') }}>
                  Canary 20%
                </button>
              ),
            },
          ]} searchKeys={['name', 'region', 'url', 'cpu', 'memory']} rows={services}
          expandRow={(r) => (
            <div className="gcp-detail-panel text-sm p-3 space-y-2">
              <div>Image: <code>{r.image}</code> · Concurrency {r.concurrency} · Scale {r.min_instances}–{r.max_instances}</div>
              <SimDataTable columns={[
                { key: 'name', label: 'Revision' },
                { key: 'traffic_pct', label: 'Traffic %' },
                { key: 'active', label: 'Active', render: (x) => (x.active ? 'Yes' : 'No') },
              ]} searchKeys={['name', 'traffic_pct', 'active']} rows={r.revisions || []} />
            </div>
          )}
        />
        <SimModal open={createRunOpen} onClose={() => setCreateRunOpen(false)} title="Create Cloud Run service"
          footer={<>
            <button type="button" className="text-sm px-3" onClick={() => setCreateRunOpen(false)}>Cancel</button>
            <button type="button" className="gcp-btn-primary" disabled={busy} onClick={() => {
              run(() => gcpApi.createCloudRunService(sessionId, { name: runName }), 'Service deployed')
              setCreateRunOpen(false)
            }}>Deploy</button>
          </>}>
          <label className="block text-sm">Service name
            <input className="w-full mt-1 border rounded px-2 py-1.5" value={runName} onChange={(e) => setRunName(e.target.value)} />
          </label>
        </SimModal>
      </div>
    )
  }

  if (nav === 'pubsub') {
    const topics = st.pubsub_topics || []
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold">Pub/Sub</h2>
          <button type="button" className="gcp-btn-primary flex items-center gap-1" onClick={() => setCreateTopicOpen(true)}>
            <Plus size={14} /> Create topic
          </button>
        </div>
        <SimDataTable
          columns={[
            { key: 'name', label: 'Topic', sortable: true },
            { key: 'message_retention', label: 'Retention' },
            { key: 'subscriptions', label: 'Subscriptions', render: (r) => (r.subscriptions || []).length },
            {
              key: 'actions', label: '',
              render: (r) => (
                <div className="flex gap-1">
                  <button type="button" className="gcp-btn-sm" disabled={busy}
                    onClick={(e) => { e.stopPropagation(); run(() => gcpApi.publishPubsub(sessionId, r.name), 'Published') }}>Publish</button>
                  <button type="button" className="gcp-btn-sm" disabled={busy}
                    onClick={(e) => { e.stopPropagation(); run(() => gcpApi.createPubsubSubscription(sessionId, r.name, { name: `${r.name}-sub-${Date.now().toString(36).slice(-3)}` }), 'Subscription created') }}>
                    + Sub
                  </button>
                </div>
              ),
            },
          ]} searchKeys={['name', 'message_retention', 'subscriptions']} rows={topics}
          expandRow={(r) => (
            <SimDataTable columns={[
              { key: 'name', label: 'Subscription' },
              { key: 'type', label: 'Type' },
              { key: 'ack_deadline_s', label: 'Ack deadline (s)' },
              { key: 'undelivered', label: 'Undelivered' },
            ]} searchKeys={['name', 'type', 'ack_deadline_s', 'undelivered']} rows={r.subscriptions || []} />
          )}
        />
        <SimModal open={createTopicOpen} onClose={() => setCreateTopicOpen(false)} title="Create topic"
          footer={<>
            <button type="button" className="text-sm px-3" onClick={() => setCreateTopicOpen(false)}>Cancel</button>
            <button type="button" className="gcp-btn-primary" disabled={busy} onClick={() => {
              run(() => gcpApi.createPubsubTopic(sessionId, topicName), 'Topic created')
              setCreateTopicOpen(false)
            }}>Create</button>
          </>}>
          <label className="block text-sm">Topic ID
            <input className="w-full mt-1 border rounded px-2 py-1.5" value={topicName} onChange={(e) => setTopicName(e.target.value)} />
          </label>
        </SimModal>
      </div>
    )
  }

  if (nav === 'gke') {
    const clusters = st.gke_clusters || []
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold">Kubernetes Engine</h2>
          <button type="button" className="gcp-btn-primary flex items-center gap-1" onClick={() => setCreateGkeOpen(true)}>
            <Plus size={14} /> Create
          </button>
        </div>
        <SimDataTable
          columns={[
            { key: 'name', label: 'Name', sortable: true },
            { key: 'location', label: 'Location' },
            { key: 'mode', label: 'Mode' },
            { key: 'version', label: 'Version' },
            { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status="success" label={r.status} /> },
            { key: 'endpoint', label: 'Endpoint' },
          ]} searchKeys={['name', 'location', 'mode', 'version', 'status', 'endpoint']} rows={clusters}
          
          expandRow={(r) => (
            <div className="gcp-detail-panel text-sm p-3 space-y-2">
              <SimDataTable
                columns={[
                  { key: 'name', label: 'Node pool' },
                  { key: 'machine_type', label: 'Machine type' },
                  { key: 'node_count', label: 'Nodes' },
                  {
                    key: 'actions', label: '',
                    render: (p) => (
                      <div className="flex gap-1">
                        <button type="button" className="gcp-btn-sm" disabled={busy}
                          onClick={() => run(() => gcpApi.resizeGkeNodePool(sessionId, r.name, p.name, Math.max(0, p.node_count - 1)), 'Scaled in')}>−</button>
                        <button type="button" className="gcp-btn-sm" disabled={busy}
                          onClick={() => run(() => gcpApi.resizeGkeNodePool(sessionId, r.name, p.name, p.node_count + 1), 'Scaled out')}>+</button>
                      </div>
                    ),
                  },
                ]} searchKeys={['name', 'machine_type', 'node_count']} rows={r.node_pools || []}
              />
            </div>
          )}
        />
        <SimModal open={createGkeOpen} onClose={() => setCreateGkeOpen(false)} title="Create GKE cluster"
          footer={<>
            <button type="button" className="text-sm px-3" onClick={() => setCreateGkeOpen(false)}>Cancel</button>
            <button type="button" className="gcp-btn-primary" disabled={busy} onClick={() => {
              run(() => gcpApi.createGkeCluster(sessionId, { name: gkeName }), 'Cluster created')
              setCreateGkeOpen(false)
            }}>Create</button>
          </>}>
          <label className="block text-sm">Name
            <input className="w-full mt-1 border rounded px-2 py-1.5" value={gkeName} onChange={(e) => setGkeName(e.target.value)} />
          </label>
        </SimModal>
      </div>
    )
  }

  if (nav === 'functions') {
    const fns = st.cloud_functions || []
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold">Cloud Functions</h2>
          <button type="button" className="gcp-btn-primary flex items-center gap-1" onClick={() => setCreateFnOpen(true)}>
            <Plus size={14} /> Create function
          </button>
        </div>
        <SimDataTable columns={[
          { key: 'name', label: 'Name', sortable: true },
          { key: 'gen', label: 'Generation' },
          { key: 'runtime', label: 'Runtime' },
          { key: 'trigger', label: 'Trigger' },
          { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status="success" label={r.status} /> },
          { key: 'invocations_24h', label: 'Invocations (24h)' },
        ]} searchKeys={['name', 'gen', 'runtime', 'trigger', 'status', 'invocations_24h']} rows={fns} />
        <SimModal open={createFnOpen} onClose={() => setCreateFnOpen(false)} title="Create function"
          footer={<>
            <button type="button" className="text-sm px-3" onClick={() => setCreateFnOpen(false)}>Cancel</button>
            <button type="button" className="gcp-btn-primary" disabled={busy} onClick={() => {
              run(() => gcpApi.createCloudFunction(sessionId, { name: fnName }), 'Function deployed')
              setCreateFnOpen(false)
            }}>Deploy</button>
          </>}>
          <label className="block text-sm">Name
            <input className="w-full mt-1 border rounded px-2 py-1.5" value={fnName} onChange={(e) => setFnName(e.target.value)} />
          </label>
        </SimModal>
      </div>
    )
  }

  if (nav === 'sql') {
    const instances = st.cloud_sql_instances || []
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold">Cloud SQL</h2>
          <button type="button" className="gcp-btn-primary flex items-center gap-1" onClick={() => setCreateSqlOpen(true)}>
            <Plus size={14} /> Create instance
          </button>
        </div>
        <SimDataTable
          columns={[
            { key: 'name', label: 'Instance', sortable: true },
            { key: 'database_version', label: 'Version' },
            { key: 'tier', label: 'Tier' },
            { key: 'state', label: 'Status', render: (r) => <SimStatusBadge status="success" label={r.state} /> },
            { key: 'ip', label: 'Public IP' },
          ]} searchKeys={['name', 'database_version', 'tier', 'state', 'ip']} rows={instances}
          
          expandRow={(r) => (
            <div className="gcp-detail-panel text-sm p-3 space-y-2">
              <div className="flex justify-between">
                <strong>Databases</strong>
                <button type="button" className="gcp-btn-sm" disabled={busy}
                  onClick={() => run(() => gcpApi.createSqlDatabase(sessionId, r.name, `db-${Date.now().toString(36).slice(-4)}`), 'Database created')}>
                  <Plus size={11} /> Create database
                </button>
              </div>
              <SimDataTable columns={[
                { key: 'name', label: 'Name' },
                { key: 'charset', label: 'Charset' },
              ]} searchKeys={['name', 'charset']} rows={r.databases || []} />
            </div>
          )}
        />
        <SimModal open={createSqlOpen} onClose={() => setCreateSqlOpen(false)} title="Create Cloud SQL instance"
          footer={<>
            <button type="button" className="text-sm px-3" onClick={() => setCreateSqlOpen(false)}>Cancel</button>
            <button type="button" className="gcp-btn-primary" disabled={busy} onClick={() => {
              run(() => gcpApi.createSqlInstance(sessionId, { name: sqlName }), 'Instance created')
              setCreateSqlOpen(false)
            }}>Create</button>
          </>}>
          <label className="block text-sm">Instance ID
            <input className="w-full mt-1 border rounded px-2 py-1.5" value={sqlName} onChange={(e) => setSqlName(e.target.value)} />
          </label>
        </SimModal>
      </div>
    )
  }

  if (nav === 'secrets') {
    const secrets = st.secrets || []
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold">Secret Manager</h2>
          <button type="button" className="gcp-btn-primary flex items-center gap-1" onClick={() => setCreateSecOpen(true)}>
            <Plus size={14} /> Create secret
          </button>
        </div>
        <SimDataTable
          columns={[
            { key: 'name', label: 'Secret', sortable: true },
            { key: 'versions', label: 'Versions', render: (r) => (r.versions || []).length },
            {
              key: 'actions', label: '',
              render: (r) => (
                <button type="button" className="gcp-btn-sm" disabled={busy}
                  onClick={(e) => { e.stopPropagation(); run(() => gcpApi.addSecretVersion(sessionId, r.name), 'Version added') }}>
                  New version
                </button>
              ),
            },
          ]} searchKeys={['name', 'versions']} rows={secrets}
          expandRow={(r) => (
            <SimDataTable columns={[
              { key: 'version', label: 'Version' },
              { key: 'state', label: 'State' },
              { key: 'created', label: 'Created' },
            ]} searchKeys={['version', 'state', 'created']} rows={r.versions || []} />
          )}
        />
        <SimModal open={createSecOpen} onClose={() => setCreateSecOpen(false)} title="Create secret"
          footer={<>
            <button type="button" className="text-sm px-3" onClick={() => setCreateSecOpen(false)}>Cancel</button>
            <button type="button" className="gcp-btn-primary" disabled={busy} onClick={() => {
              run(() => gcpApi.createSecret(sessionId, secName), 'Secret created')
              setCreateSecOpen(false)
            }}>Create</button>
          </>}>
          <label className="block text-sm">Name
            <input className="w-full mt-1 border rounded px-2 py-1.5" value={secName} onChange={(e) => setSecName(e.target.value)} />
          </label>
        </SimModal>
      </div>
    )
  }

  if (nav === 'armor') {
    const policies = st.armor_policies || []
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold">Cloud Armor</h2>
          <button type="button" className="gcp-btn-primary flex items-center gap-1" disabled={busy}
            onClick={() => run(() => gcpApi.createArmorPolicy(sessionId, `armor-${Date.now().toString(36).slice(-4)}`), 'Policy created')}>
            <Plus size={14} /> Create policy
          </button>
        </div>
        <SimDataTable
          columns={[
            { key: 'name', label: 'Policy', sortable: true },
            { key: 'rules', label: 'Rules', render: (r) => (r.rules || []).length },
          ]} searchKeys={['name', 'rules']} rows={policies}
          expandRow={(r) => (
            <div className="gcp-detail-panel text-sm p-3 space-y-2">
              <button type="button" className="gcp-btn-sm" disabled={busy}
                onClick={() => run(() => gcpApi.addArmorRule(sessionId, r.name, {
                  priority: 50, action: 'deny(403)', match: 'srcIpRanges=203.0.113.0/24', description: 'blocklist',
                }), 'Rule added')}>
                <Plus size={11} /> Add deny rule
              </button>
              <SimDataTable columns={[
                { key: 'priority', label: 'Priority' },
                { key: 'action', label: 'Action' },
                { key: 'match', label: 'Match' },
                { key: 'description', label: 'Description' },
              ]} searchKeys={['priority', 'match', 'description']} rows={r.rules || []} />
            </div>
          )}
        />
      </div>
    )
  }

  if (nav === 'spanner') {
    const instances = st.spanner_instances || []
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold">Cloud Spanner</h2>
          <button type="button" className="gcp-btn-primary flex items-center gap-1" disabled={busy}
            onClick={() => run(() => gcpApi.createSpannerInstance(sessionId, { name: `spanner-${Date.now().toString(36).slice(-4)}` }), 'Instance created')}>
            <Plus size={14} /> Create instance
          </button>
        </div>
        <SimDataTable
          columns={[
            { key: 'name', label: 'Instance', sortable: true },
            { key: 'config', label: 'Config' },
            { key: 'processing_units', label: 'Processing units' },
            { key: 'state', label: 'State', render: (r) => <SimStatusBadge status="success" label={r.state} /> },
            { key: 'databases', label: 'Databases', render: (r) => (r.databases || []).length },
          ]} searchKeys={['name', 'config', 'processing_units', 'state', 'databases']} rows={instances}
          expandRow={(r) => (
            <div className="space-y-2 p-2">
              <div className="flex justify-end">
                <button type="button" className="gcp-btn-sm" disabled={busy}
                  onClick={() => run(() => gcpApi.createSpannerDatabase(sessionId, r.name, `db_${Date.now().toString(36).slice(-4)}`), 'Database created')}>
                  Create database
                </button>
              </div>
              <SimDataTable columns={[
                { key: 'name', label: 'Database' },
                { key: 'tables', label: 'Tables' },
                { key: 'size_gb', label: 'Size (GB)' },
              ]} searchKeys={['name', 'tables', 'size_gb']} rows={r.databases || []} />
            </div>
          )}
        />
      </div>
    )
  }

  if (nav === 'bigquery') {
    const datasets = st.bigquery_datasets || []
    const jobs = st.bigquery_jobs || []
    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold">BigQuery</h2>
          <div className="flex gap-2">
            <button type="button" className="gcp-btn-sm" disabled={busy}
              onClick={() => run(() => gcpApi.runBigQuery(sessionId, 'SELECT COUNT(*) FROM analytics.events'), 'Query finished')}>
              Run sample query
            </button>
            <button type="button" className="gcp-btn-primary flex items-center gap-1" disabled={busy}
              onClick={() => run(() => gcpApi.createBigQueryDataset(sessionId, `dataset_${Date.now().toString(36).slice(-4)}`), 'Dataset created')}>
              <Plus size={14} /> Create dataset
            </button>
          </div>
        </div>
        <SimDataTable
          columns={[
            { key: 'dataset_id', label: 'Dataset', sortable: true },
            { key: 'location', label: 'Location' },
            { key: 'tables', label: 'Tables', render: (r) => (r.tables || []).length },
          ]} searchKeys={['dataset_id', 'location', 'tables']} rows={datasets}
          expandRow={(r) => (
            <div className="gcp-detail-panel text-sm p-3 space-y-2">
              <button type="button" className="gcp-btn-sm" disabled={busy}
                onClick={() => run(() => gcpApi.createBigQueryTable(sessionId, r.dataset_id, `tbl_${Date.now().toString(36).slice(-3)}`), 'Table created')}>
                <Plus size={11} /> Create table
              </button>
              <SimDataTable columns={[
                { key: 'name', label: 'Table' },
                { key: 'type', label: 'Type' },
                { key: 'rows', label: 'Rows' },
                { key: 'size_gb', label: 'Size (GB)' },
              ]} searchKeys={['name', 'type', 'rows', 'size_gb']} rows={r.tables || []} />
            </div>
          )}
        />
        {jobs.length > 0 && (
          <>
            <h3 className="text-sm font-semibold text-slate-600">Query jobs</h3>
            <SimDataTable columns={[
              { key: 'id', label: 'Job' },
              { key: 'state', label: 'State', render: (r) => <SimStatusBadge status="success" label={r.state} /> },
              { key: 'rows_returned', label: 'Rows' },
              { key: 'bytes_processed', label: 'Bytes' },
              { key: 'sql', label: 'SQL' },
            ]} searchKeys={['id', 'state', 'rows_returned', 'bytes_processed', 'sql']} rows={jobs} />
          </>
        )}
      </div>
    )
  }

  if (nav === 'lb') {
    const lbs = st.http_load_balancers || []
    const igs = st.instance_groups || []
    return (
      <div className="space-y-5">
        <div className="space-y-3">
          <div className="flex justify-between items-center flex-wrap gap-2">
            <h2 className="text-lg font-semibold">Load balancing</h2>
            <button type="button" className="gcp-btn-primary flex items-center gap-1" disabled={busy}
              onClick={() => run(() => gcpApi.createHttpLoadBalancer(sessionId, {
                name: `https-lb-${Date.now().toString(36).slice(-4)}`,
              }), 'Load balancer created')}>
              <Plus size={14} /> Create HTTP(S) LB
            </button>
          </div>
          <SimDataTable
            columns={[
              { key: 'name', label: 'Name', sortable: true },
              { key: 'protocol', label: 'Protocol' },
              { key: 'ip', label: 'Frontend IP' },
              { key: 'port', label: 'Port' },
              { key: 'backend_service', label: 'Backend service' },
              { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status="success" label={r.status} /> },
            ]} searchKeys={['name', 'protocol', 'ip', 'port', 'backend_service', 'status']} rows={lbs}
            
            expandRow={(r) => (
              <div className="gcp-detail-panel text-sm p-3 space-y-1">
                <div>Health check: <code>{r.health_check}</code> · SSL: <code>{r.ssl_cert}</code></div>
                <SimDataTable columns={[
                  { key: 'instance_group', label: 'Backend' },
                  { key: 'zone', label: 'Zone' },
                  { key: 'capacity', label: 'Capacity %' },
                ]} searchKeys={['instance_group', 'zone', 'capacity']} rows={r.backends || []} />
              </div>
            )}
          />
        </div>
        <div className="space-y-3">
          <div className="flex justify-between items-center flex-wrap gap-2">
            <h2 className="text-lg font-semibold">Instance groups</h2>
            <button type="button" className="gcp-btn-sm flex items-center gap-1" disabled={busy}
              onClick={() => run(() => gcpApi.createInstanceGroup(sessionId, {
                name: `ig-${Date.now().toString(36).slice(-4)}`,
                size: 1,
              }), 'Instance group created')}>
              <Plus size={11} /> Create MIG
            </button>
          </div>
          <SimDataTable
            columns={[
              { key: 'name', label: 'Name', sortable: true },
              { key: 'zone', label: 'Zone' },
              { key: 'network', label: 'Network' },
              { key: 'size', label: 'Size', sortable: true },
              { key: 'template', label: 'Template' },
              {
                key: 'actions', label: '',
                render: (r) => (
                  <button type="button" className="gcp-btn-sm" disabled={busy}
                    onClick={(e) => {
                      e.stopPropagation()
                      run(() => gcpApi.resizeInstanceGroup(sessionId, r.name, (r.size || 1) + 1), 'Resized')
                    }}>
                    + Size
                  </button>
                ),
              },
            ]} searchKeys={['name', 'zone', 'network', 'size', 'template']} rows={igs}
          />
        </div>
      </div>
    )
  }

  return null
}
