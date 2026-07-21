import { Plus } from 'lucide-react'
import { SimDataTable, SimStatusBadge } from '../sim/shared'
import { dockerApi } from '../../api/docker'

export function renderDockerV2Page({ nav, daemon, sessionId, busy, run }) {
  if (nav === 'swarm') {
    const swarm = daemon.swarm || {}
    const services = daemon.swarm_services || []
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <div>
            <h2 className="text-lg font-semibold">Swarm services</h2>
            <p className="text-xs text-slate-500">
              {swarm.active ? `Active · managers ${swarm.managers} · workers ${swarm.workers}` : 'Not initialized'}
            </p>
          </div>
          <div className="flex gap-2">
            {!swarm.active && (
              <button type="button" className="docker-btn-primary flex items-center gap-1" disabled={busy}
                onClick={() => run(() => dockerApi.swarmInit(sessionId), 'Swarm initialized')}>
                Init swarm
              </button>
            )}
            <button type="button" className="docker-btn-primary flex items-center gap-1" disabled={busy}
              onClick={() => run(() => dockerApi.createSwarmService(sessionId, {
                name: `svc-${Date.now().toString(36).slice(-4)}`, replicas: 2,
              }), 'Service created')}>
              <Plus size={14} /> Create service
            </button>
          </div>
        </div>
        <SimDataTable columns={[
          { key: 'name', label: 'Name', sortable: true },
          { key: 'image', label: 'Image' },
          { key: 'replicas', label: 'Replicas' },
          { key: 'ports', label: 'Ports' },
          { key: 'status', label: 'Status', render: (r) => <SimStatusBadge status="success" label={r.status} /> },
          {
            key: 'actions', label: '',
            render: (r) => (
              <div className="flex gap-1">
                <button type="button" className="docker-btn-ghost" disabled={busy}
                  onClick={(e) => { e.stopPropagation(); run(() => dockerApi.scaleSwarmService(sessionId, r.name, Math.max(0, (r.replicas || 1) - 1)), 'Scaled') }}>−</button>
                <button type="button" className="docker-btn-ghost" disabled={busy}
                  onClick={(e) => { e.stopPropagation(); run(() => dockerApi.scaleSwarmService(sessionId, r.name, (r.replicas || 0) + 1), 'Scaled') }}>+</button>
              </div>
            ),
          },
        ]} rows={services} searchKeys={['name', 'image']} />
      </div>
    )
  }

  if (nav === 'secrets') {
    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold">Secrets</h2>
          <button type="button" className="docker-btn-primary flex items-center gap-1" disabled={busy}
            onClick={() => run(() => dockerApi.createSecret(sessionId, `secret_${Date.now().toString(36).slice(-4)}`), 'Secret created')}>
            <Plus size={14} /> Create secret
          </button>
        </div>
        <SimDataTable columns={[
          { key: 'name', label: 'Name', sortable: true },
          { key: 'id', label: 'ID' },
          { key: 'created', label: 'Created' },
        ]} rows={daemon.secrets || []} searchKeys={['name']} />
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-lg font-semibold">Configs</h2>
          <button type="button" className="docker-btn-primary flex items-center gap-1" disabled={busy}
            onClick={() => run(() => dockerApi.createConfig(sessionId, `cfg_${Date.now().toString(36).slice(-4)}`), 'Config created')}>
            <Plus size={14} /> Create config
          </button>
        </div>
        <SimDataTable columns={[
          { key: 'name', label: 'Name', sortable: true },
          { key: 'id', label: 'ID' },
          { key: 'created', label: 'Created' },
        ]} rows={daemon.configs || []} searchKeys={['name']} />
      </div>
    )
  }

  if (nav === 'registry') {
    const reg = daemon.registry || {}
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <div>
            <h2 className="text-lg font-semibold">Local registry</h2>
            <p className="text-xs text-slate-500">{reg.url || 'localhost:5000'}</p>
          </div>
          <button type="button" className="docker-btn-primary flex items-center gap-1" disabled={busy}
            onClick={() => run(() => dockerApi.registryPush(sessionId, {
              name: `localhost:5000/fixitlab/app`, tag: Date.now().toString(36).slice(-4),
            }), 'Pushed')}>
            <Plus size={14} /> Push image
          </button>
        </div>
        <SimDataTable columns={[
          { key: 'name', label: 'Repository', sortable: true },
          { key: 'tag', label: 'Tag' },
          { key: 'size_mb', label: 'Size (MB)' },
          { key: 'pushed', label: 'Pushed' },
          {
            key: 'actions', label: '',
            render: (r) => (
              <button type="button" className="docker-btn-ghost" disabled={busy}
                onClick={(e) => { e.stopPropagation(); run(() => dockerApi.registryPull(sessionId, r.name, r.tag), 'Pulled') }}>
                Pull
              </button>
            ),
          },
        ]} rows={reg.images || []} searchKeys={['name', 'tag']} />
      </div>
    )
  }

  return null
}
