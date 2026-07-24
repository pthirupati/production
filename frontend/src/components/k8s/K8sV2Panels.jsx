import { Plus } from 'lucide-react'
import { SimDataTable, SimStatusBadge } from '../sim/shared'
import { k8sApi } from '../../api/k8s'

/** Ingress, ConfigMaps, Secrets, NetworkPolicy, Helm, HPA, OpenShift blades. */
export function renderK8sV2Page({ nav, cluster, sessionId, busy, run, isOpenShift = false }) {
  if (nav === 'ingress') {
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold">Ingresses</h2>
          <button type="button" className="k8s-btn-primary flex items-center gap-1" disabled={busy}
            onClick={() => run(() => k8sApi.createIngress(sessionId, {
              name: `ing-${Date.now().toString(36).slice(-4)}`, host: 'app.fixitlab.io', service: 'frontend',
            }), 'Ingress created')}>
            <Plus size={14} /> Create Ingress
          </button>
        </div>
        <SimDataTable columns={[
          { key: 'name', label: 'Name', sortable: true },
          { key: 'namespace', label: 'Namespace' },
          { key: 'className', label: 'Class' },
          { key: 'rules', label: 'Hosts', render: (r) => (r.rules || []).map((x) => x.host).join(', ') },
        ]} searchKeys={['name', 'namespace', 'className', 'rules']} rows={cluster.ingresses || []} searchKeys={['name', 'namespace']} />
      </div>
    )
  }

  if (nav === 'configmaps') {
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold">ConfigMaps</h2>
          <button type="button" className="k8s-btn-primary flex items-center gap-1" disabled={busy}
            onClick={() => run(() => k8sApi.applyConfigMap(sessionId, `cm-${Date.now().toString(36).slice(-4)}`, { KEY: 'value' }), 'ConfigMap applied')}>
            <Plus size={14} /> Apply ConfigMap
          </button>
        </div>
        <SimDataTable columns={[
          { key: 'name', label: 'Name', sortable: true },
          { key: 'namespace', label: 'Namespace' },
          { key: 'data', label: 'Keys', render: (r) => Object.keys(r.data || {}).join(', ') },
          {
            key: 'actions', label: 'Actions', render: (r) => (
              <button type="button" className="k8s-btn-ghost" disabled={busy}
                onClick={(e) => {
                  e.stopPropagation()
                  run(() => k8sApi.patchResource(sessionId, 'configmap', r.name, {
                    data: { ...(r.data || {}), 'lab.patched': 'true' },
                  }, r.namespace), 'ConfigMap patched')
                }}>
                Patch
              </button>
            ),
          },
        ]} searchKeys={['name', 'namespace', 'data']} rows={cluster.configmaps || []} searchKeys={['name']}
          expandRow={(r) => (
            <pre className="text-xs p-2 bg-slate-50 overflow-auto">{JSON.stringify(r.data || {}, null, 2)}</pre>
          )}
        />
      </div>
    )
  }

  if (nav === 'secrets') {
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold">Secrets</h2>
          <button type="button" className="k8s-btn-primary flex items-center gap-1" disabled={busy}
            onClick={() => run(() => k8sApi.applySecret(sessionId, `sec-${Date.now().toString(36).slice(-4)}`, ['password']), 'Secret applied')}>
            <Plus size={14} /> Apply Secret
          </button>
        </div>
        <SimDataTable columns={[
          { key: 'name', label: 'Name', sortable: true },
          { key: 'namespace', label: 'Namespace' },
          { key: 'type', label: 'Type' },
          { key: 'keys', label: 'Keys', render: (r) => (r.keys || Object.keys(r.data || {})).join(', ') },
        ]} searchKeys={['name', 'namespace', 'type', 'keys']} rows={cluster.secrets || []} searchKeys={['name']} />
      </div>
    )
  }

  if (nav === 'netpol') {
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold">NetworkPolicies</h2>
          <button type="button" className="k8s-btn-primary flex items-center gap-1" disabled={busy}
            onClick={() => run(() => k8sApi.createNetworkPolicy(sessionId, {
              name: `allow-${Date.now().toString(36).slice(-3)}`, app: 'api',
            }), 'NetworkPolicy created')}>
            <Plus size={14} /> Create
          </button>
        </div>
        <SimDataTable columns={[
          { key: 'name', label: 'Name', sortable: true },
          { key: 'namespace', label: 'Namespace' },
          { key: 'policy_types', label: 'Types', render: (r) => (r.policy_types || []).join(', ') },
          { key: 'pod_selector', label: 'Selector', render: (r) => JSON.stringify(r.pod_selector || {}) },
        ]} searchKeys={['name', 'namespace', 'policy_types', 'pod_selector']} rows={cluster.network_policies || []} searchKeys={['name']} />
      </div>
    )
  }

  if (nav === 'helm') {
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold">Helm Releases</h2>
          <button type="button" className="k8s-btn-primary flex items-center gap-1" disabled={busy}
            onClick={() => run(() => k8sApi.helmInstall(sessionId, {
              name: `chart-${Date.now().toString(36).slice(-4)}`,
            }), 'Helm install complete')}>
            <Plus size={14} /> Install chart
          </button>
        </div>
        <SimDataTable columns={[
          { key: 'name', label: 'Name', sortable: true },
          { key: 'namespace', label: 'Namespace' },
          { key: 'chart', label: 'Chart' },
          { key: 'version', label: 'Version' },
          { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status="success" label={r.status} /> },
          { key: 'revision', label: 'Rev' },
          {
            key: 'actions', label: 'Actions',
            render: (r) => (
              <div className="flex gap-1 flex-wrap">
                <button type="button" className="k8s-btn-ghost" disabled={busy}
                  onClick={(e) => { e.stopPropagation(); run(() => k8sApi.helmUpgrade(sessionId, r.name), 'Helm upgrade complete') }}>
                  Upgrade
                </button>
                <button type="button" className="k8s-btn-ghost" disabled={busy || (r.revision || 1) <= 1}
                  onClick={(e) => { e.stopPropagation(); run(() => k8sApi.helmRollback(sessionId, r.name), 'Helm rollback complete') }}>
                  Rollback
                </button>
                <button type="button" className="k8s-btn-ghost" disabled={busy}
                  onClick={(e) => { e.stopPropagation(); run(() => k8sApi.helmUninstall(sessionId, r.name), 'Helm uninstall complete') }}>
                  Uninstall
                </button>
              </div>
            ),
          },
        ]} searchKeys={['name', 'namespace', 'chart', 'version', 'status', 'revision']} rows={cluster.helm_releases || []} searchKeys={['name', 'chart']} />
      </div>
    )
  }

  if (nav === 'hpa') {
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold">Horizontal Pod Autoscalers</h2>
          <button type="button" className="k8s-btn-primary flex items-center gap-1" disabled={busy}
            onClick={() => run(() => k8sApi.createHpa(sessionId, { name: `hpa-${Date.now().toString(36).slice(-3)}` }), 'HPA created')}>
            <Plus size={14} /> Create HPA
          </button>
        </div>
        <SimDataTable columns={[
          { key: 'name', label: 'Name', sortable: true },
          { key: 'namespace', label: 'Namespace' },
          { key: 'target_ref', label: 'Target' },
          { key: 'min_replicas', label: 'Min' },
          { key: 'max_replicas', label: 'Max' },
          { key: 'current_replicas', label: 'Current' },
          { key: 'cpu_target', label: 'CPU %' },
        ]} searchKeys={['name', 'namespace', 'target_ref', 'min_replicas', 'max_replicas', 'current_replicas']} rows={cluster.hpas || []} searchKeys={['name']} />
      </div>
    )
  }

  if (nav === 'rbac') {
    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold">RBAC</h2>
          <button type="button" className="k8s-btn-primary flex items-center gap-1" disabled={busy}
            onClick={() => run(() => k8sApi.createRoleBinding(sessionId, {
              name: `rb-${Date.now().toString(36).slice(-4)}`, role: 'secret-reader', subject: 'deploy-bot',
            }), 'RoleBinding created')}>
            <Plus size={14} /> Bind role
          </button>
        </div>
        <h3 className="text-sm font-semibold text-slate-600">Roles</h3>
        <SimDataTable columns={[
          { key: 'name', label: 'Name' },
          { key: 'namespace', label: 'Namespace' },
          { key: 'rules', label: 'Rules', render: (r) => (r.rules || []).length },
        ]} searchKeys={['name', 'namespace', 'rules']} rows={cluster.roles || []} />
        <h3 className="text-sm font-semibold text-slate-600">RoleBindings</h3>
        <SimDataTable columns={[
          { key: 'name', label: 'Name' },
          { key: 'namespace', label: 'Namespace' },
          { key: 'roleRef', label: 'Role', render: (r) => r.roleRef?.name },
          { key: 'subjects', label: 'Subjects', render: (r) => (r.subjects || []).map((s) => s.name).join(', ') },
        ]} searchKeys={['name', 'namespace', 'roleRef', 'subjects']} rows={cluster.role_bindings || []} />
      </div>
    )
  }

  if (nav === 'projects' || (isOpenShift && nav === 'projects')) {
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold">Projects</h2>
          <button type="button" className="k8s-btn-primary flex items-center gap-1" disabled={busy}
            onClick={() => run(() => k8sApi.createOpenShiftProject(sessionId, {
              name: `proj-${Date.now().toString(36).slice(-4)}`,
            }), 'Project created')}>
            <Plus size={14} /> Create Project
          </button>
        </div>
        <SimDataTable columns={[
          { key: 'name', label: 'Name', sortable: true },
          { key: 'display_name', label: 'Display name' },
          { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status="success" label={r.status} /> },
        ]} searchKeys={['name', 'display_name', 'status']} rows={cluster.openshift_projects || []} searchKeys={['name']} />
      </div>
    )
  }

  if (nav === 'routes') {
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold">Routes</h2>
          <button type="button" className="k8s-btn-primary flex items-center gap-1" disabled={busy}
            onClick={() => run(() => k8sApi.createOpenShiftRoute(sessionId, {
              name: `route-${Date.now().toString(36).slice(-4)}`, service: 'api',
            }), 'Route created')}>
            <Plus size={14} /> Create Route
          </button>
        </div>
        <SimDataTable columns={[
          { key: 'name', label: 'Name', sortable: true },
          { key: 'namespace', label: 'Namespace' },
          { key: 'host', label: 'Hostname' },
          { key: 'to', label: 'Service' },
          { key: 'tls', label: 'TLS' },
          { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status="success" label={r.status} /> },
        ]} searchKeys={['name', 'namespace', 'host', 'to', 'tls', 'status']} rows={cluster.openshift_routes || []} searchKeys={['name', 'host']} />
      </div>
    )
  }

  if (nav === 'builds') {
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold">Builds</h2>
          <button type="button" className="k8s-btn-primary flex items-center gap-1" disabled={busy}
            onClick={() => run(() => k8sApi.startOpenShiftBuild(sessionId, { name: 'api' }), 'Build started')}>
            <Plus size={14} /> Start Build
          </button>
        </div>
        <SimDataTable columns={[
          { key: 'name', label: 'Build', sortable: true },
          { key: 'namespace', label: 'Namespace' },
          { key: 'from', label: 'From' },
          { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status="success" label={r.status} /> },
          { key: 'duration_s', label: 'Duration (s)' },
        ]} searchKeys={['name', 'namespace', 'from', 'status', 'duration_s']} rows={cluster.openshift_builds || []} searchKeys={['name']} />
        <h3 className="text-sm font-semibold text-slate-600 pt-2">Security Context Constraints</h3>
        <SimDataTable columns={[
          { key: 'name', label: 'SCC' },
          { key: 'priority', label: 'Priority' },
          { key: 'users', label: 'Users', render: (r) => (r.users || []).join(', ') },
        ]} searchKeys={['name', 'priority', 'users']} rows={cluster.sccs || []} />
      </div>
    )
  }

  return null
}
