import { useState } from 'react'
import { Plus, Trash2, KeyRound } from 'lucide-react'
import { SimDataTable, SimStatusBadge, SimModal } from '../sim/shared'
import { dockerApi } from '../../api/docker'

/** Secrets are mounted as tmpfs files, so "who mounts this" lives on the
 *  containers, not on the secret. Invert that relation for display. */
function mountsOfSecret(containers, secretName) {
  return containers.flatMap((c) =>
    (c.secretMounts || [])
      .filter((m) => m.secret === secretName)
      .map((m) => ({ container: c.shortName, target: m.target, mode: m.mode })),
  )
}

function SecretsPanel({ daemon, sessionId, busy, run }) {
  const containers = daemon.containers || []
  const secrets = daemon.secrets || []
  const [createOpen, setCreateOpen] = useState(false)
  const [form, setForm] = useState({ name: '', value: '' })
  const [mountFor, setMountFor] = useState(null)
  const [mountForm, setMountForm] = useState({ container: '', target: '' })

  const openMount = (secret) => {
    setMountFor(secret)
    setMountForm({
      container: containers[0]?.shortName || '',
      target: `/run/secrets/${secret.name}`,
    })
  }

  const rows = secrets.map((s) => ({ ...s, mounts: mountsOfSecret(containers, s.name) }))

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center flex-wrap gap-2">
        <div>
          <h2 className="text-lg font-semibold">Secrets</h2>
          <p className="text-xs text-slate-500">
            A secret&apos;s value is readable only from inside a container that mounts it — never from
            this list, and never from <code>docker inspect</code>.
          </p>
        </div>
        <button type="button" className="docker-btn-primary flex items-center gap-1" disabled={busy}
          onClick={() => { setForm({ name: '', value: '' }); setCreateOpen(true) }}>
          <Plus size={14} /> Create secret
        </button>
      </div>
      <SimDataTable columns={[
        { key: 'name', label: 'Name', sortable: true },
        { key: 'id', label: 'ID' },
        { key: 'created', label: 'Created' },
        {
          key: 'mounts', label: 'Mounted in',
          render: (r) => (r.mounts.length === 0 ? <span className="text-slate-400">—</span> : (
            <div className="flex flex-col gap-1">
              {r.mounts.map((m) => (
                <div key={`${m.container}:${m.target}`} className="flex items-center gap-1.5">
                  <span className="inline-flex items-center gap-1 rounded bg-slate-100 border border-slate-200 px-1.5 py-0.5 text-[11px]">
                    <span className="font-medium">{m.container}</span>
                    <span className="text-slate-500 font-mono">{m.target}</span>
                  </span>
                  <button type="button" className="docker-btn-ghost text-[11px]" disabled={busy}
                    onClick={(e) => {
                      e.stopPropagation()
                      run(() => dockerApi.unmountSecret(sessionId, m.container, r.name), 'Unmounted')
                    }}>Unmount</button>
                </div>
              ))}
            </div>
          )),
        },
        {
          key: 'actions', label: '',
          render: (r) => (
            <div className="flex gap-1">
              <button type="button" className="docker-btn-ghost" disabled={busy || containers.length === 0}
                onClick={(e) => { e.stopPropagation(); openMount(r) }}>
                <KeyRound size={12} className="inline mr-0.5" />Mount into container
              </button>
              <button type="button" className="docker-btn-ghost" disabled={busy}
                onClick={(e) => {
                  e.stopPropagation()
                  run(() => dockerApi.removeSecret(sessionId, r.name), 'Secret removed')
                }}>
                <Trash2 size={12} className="inline mr-0.5" />Remove
              </button>
            </div>
          ),
        },
      ]} searchKeys={['name', 'id', 'created']} rows={rows} />

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
      ]} searchKeys={['name', 'id', 'created']} rows={daemon.configs || []} />

      <SimModal open={createOpen} onClose={() => setCreateOpen(false)} title="Create secret"
        footer={<>
          <button type="button" className="text-sm px-3 text-slate-300" onClick={() => setCreateOpen(false)}>Cancel</button>
          <button type="button" className="docker-btn-primary px-3 py-1.5 text-sm"
            disabled={busy || !form.name.trim() || !form.value}
            onClick={() => {
              run(() => dockerApi.createSecret(sessionId, form.name.trim(), form.value), 'Secret created')
              setCreateOpen(false)
            }}>Create</button>
        </>}>
        <div className="space-y-3 text-sm text-slate-200">
          <label className="block">Name
            <input className="mt-1 w-full border rounded px-2 py-1.5 text-slate-900"
              value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="api_db_password" />
          </label>
          <label className="block">Value
            <input className="mt-1 w-full border rounded px-2 py-1.5 text-slate-900 font-mono"
              value={form.value} onChange={(e) => setForm((f) => ({ ...f, value: e.target.value }))}
              placeholder="read from stdin or a file in real docker" />
          </label>
          <p className="text-xs text-slate-400">
            The value is stored on the daemon and never returned to this console. Mount the secret into a
            container to make it readable at <code>/run/secrets/&lt;name&gt;</code>.
          </p>
        </div>
      </SimModal>

      <SimModal open={!!mountFor} onClose={() => setMountFor(null)}
        title={`Mount ${mountFor?.name || ''}`}
        footer={<>
          <button type="button" className="text-sm px-3 text-slate-300" onClick={() => setMountFor(null)}>Cancel</button>
          <button type="button" className="docker-btn-primary px-3 py-1.5 text-sm"
            disabled={busy || !mountForm.container}
            onClick={() => {
              run(() => dockerApi.mountSecret(
                sessionId, mountForm.container, mountFor.name, mountForm.target.trim(),
              ), 'Secret mounted')
              setMountFor(null)
            }}>Mount</button>
        </>}>
        <div className="space-y-3 text-sm text-slate-200">
          <label className="block">Container
            <select className="mt-1 w-full border rounded px-2 py-1.5 text-slate-900"
              value={mountForm.container}
              onChange={(e) => setMountForm((f) => ({ ...f, container: e.target.value }))}>
              {containers.map((c) => (
                <option key={c.id} value={c.shortName}>{c.shortName} ({c.state})</option>
              ))}
            </select>
          </label>
          <label className="block">Target path
            <input className="mt-1 w-full border rounded px-2 py-1.5 text-slate-900 font-mono"
              value={mountForm.target}
              onChange={(e) => setMountForm((f) => ({ ...f, target: e.target.value }))}
              placeholder={`/run/secrets/${mountFor?.name || ''}`} />
          </label>
          <p className="text-xs text-slate-400">
            The secret lands as a read-only tmpfs file at this path. It is never exposed as an
            environment variable.
          </p>
        </div>
      </SimModal>
    </div>
  )
}

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
        ]} searchKeys={['name', 'image', 'replicas', 'ports', 'status']} rows={services} />
      </div>
    )
  }

  if (nav === 'secrets') {
    return <SecretsPanel daemon={daemon} sessionId={sessionId} busy={busy} run={run} />
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
        ]} searchKeys={['name', 'tag', 'size_mb', 'pushed']} rows={reg.images || []} />
      </div>
    )
  }

  return null
}
