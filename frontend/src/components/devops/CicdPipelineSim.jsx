import { useMemo, useState } from 'react'
import { Play, RotateCcw, CheckCircle2, XCircle, Loader2, GitBranch, Package, Shield } from 'lucide-react'

const DEFAULT_STAGES = [
  { id: 'checkout', name: 'Checkout', tool: 'git', status: 'success', log: ['Cloning repository…', 'Checked out main @ a1b2c3d'] },
  { id: 'build', name: 'Build', tool: 'maven', status: 'failed', log: ['mvn clean package -DskipTests', 'ERROR: cannot find symbol HttpClient'] },
  { id: 'test', name: 'Unit tests', tool: 'maven', status: 'pending', log: [] },
  { id: 'scan', name: 'SonarQube', tool: 'sonar', status: 'pending', log: [] },
  { id: 'deploy', name: 'Deploy', tool: 'argocd', status: 'pending', log: [] },
]

/**
 * Visual CI/CD pipeline simulator for DevOps labs — Jenkins / GitHub Actions /
 * Argo CD style stages with editable env vars and simulated logs.
 */
export default function CicdPipelineSim({ scenario, onExit, onFixed }) {
  const [stages, setStages] = useState(() => DEFAULT_STAGES.map((s) => ({ ...s })))
  const [kubeconfig, setKubeconfig] = useState('')
  const [imageTag, setImageTag] = useState('broken-tag')
  const [running, setRunning] = useState(false)
  const [fixed, setFixed] = useState(false)

  const allGreen = useMemo(() => stages.every((s) => s.status === 'success'), [stages])

  const rerun = async () => {
    setRunning(true)
    setFixed(false)
    const next = stages.map((s) => ({ ...s, status: s.id === 'checkout' ? 'success' : 'pending', log: s.id === 'checkout' ? s.log : [] }))
    setStages(next)
    await delay(400)
    const buildOk = imageTag && imageTag !== 'broken-tag'
    setStages((prev) => prev.map((s) => {
      if (s.id === 'build') {
        return {
          ...s,
          status: buildOk ? 'success' : 'failed',
          log: buildOk
            ? ['mvn clean package -DskipTests', 'BUILD SUCCESS', `artifact: app-${imageTag}.jar`]
            : ['mvn clean package', `ERROR: image tag ${imageTag} not found in registry`],
        }
      }
      return s
    }))
    if (!buildOk) { setRunning(false); return }
    await delay(500)
    const deployOk = kubeconfig.trim().length > 10
    setStages((prev) => prev.map((s) => {
      if (s.id === 'test') return { ...s, status: 'success', log: ['Tests run: 42, Failures: 0'] }
      if (s.id === 'scan') return { ...s, status: 'success', log: ['SonarQube: Quality Gate PASSED', 'Coverage: 78%'] }
      if (s.id === 'deploy') {
        return {
          ...s,
          status: deployOk ? 'success' : 'failed',
          log: deployOk
            ? ['argocd app sync webapp', 'Sync status: Synced', 'Health: Healthy']
            : ['kubectl apply failed: invalid kubeconfig', 'error: unable to load config'],
        }
      }
      return s
    }))
    if (deployOk) {
      setFixed(true)
      onFixed?.()
    }
    setRunning(false)
  }

  return (
    <div className="fixed inset-0 z-[100] bg-[#0d1117] flex flex-col text-sm text-surface-200">
      <header className="flex items-center justify-between px-4 py-2 border-b border-surface-700 bg-surface-900/95">
        <div className="flex items-center gap-2">
          <GitBranch size={16} className="text-accent-cyan" />
          <span className="font-semibold text-white">CI/CD Pipeline</span>
          <span className="text-xs text-surface-500">{scenario?.title || 'DevOps lab'}</span>
        </div>
        <button type="button" onClick={onExit} className="btn-secondary text-xs px-3 py-1">Close</button>
      </header>

      <div className="flex-1 overflow-auto p-4 space-y-4 max-w-4xl mx-auto w-full">
        <p className="text-surface-400 text-xs">
          Fix pipeline variables below, then re-run. Set a valid <code className="text-accent-cyan">IMAGE_TAG</code> and paste a
          kubeconfig to unblock deploy (simulates Jenkins / GitHub Actions → SonarQube → Argo CD).
        </p>

        <div className="grid sm:grid-cols-2 gap-3">
          <label className="block">
            <span className="text-xs text-surface-500">IMAGE_TAG</span>
            <input
              className="input w-full mt-1 font-mono text-xs"
              value={imageTag}
              onChange={(e) => setImageTag(e.target.value)}
              placeholder="v1.2.3"
            />
          </label>
          <label className="block sm:col-span-1">
            <span className="text-xs text-surface-500">KUBECONFIG (paste)</span>
            <textarea
              className="input w-full mt-1 font-mono text-[10px] h-16"
              value={kubeconfig}
              onChange={(e) => setKubeconfig(e.target.value)}
              placeholder="apiVersion: v1..."
            />
          </label>
        </div>

        <div className="flex gap-2">
          <button type="button" disabled={running} onClick={rerun} className="btn-primary text-xs flex items-center gap-1.5">
            {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            Re-run pipeline
          </button>
          <button type="button" onClick={() => { setImageTag('v1.2.3'); setKubeconfig('apiVersion: v1\nkind: Config\nclusters:\n- name: lab\n'); }} className="btn-secondary text-xs flex items-center gap-1">
            <RotateCcw size={12} /> Reset vars
          </button>
        </div>

        <ol className="space-y-2">
          {stages.map((stage, i) => (
            <li key={stage.id} className="rounded-lg border border-surface-700 bg-surface-900/60 overflow-hidden">
              <div className="flex items-center gap-2 px-3 py-2 border-b border-surface-800">
                <StageIcon status={stage.status} />
                <span className="font-medium text-white">{i + 1}. {stage.name}</span>
                <span className="text-[10px] text-surface-500 ml-auto flex items-center gap-1">
                  {stage.tool === 'sonar' && <Shield size={10} />}
                  {stage.tool === 'maven' && <Package size={10} />}
                  {stage.tool}
                </span>
              </div>
              {stage.log?.length > 0 && (
                <pre className="p-3 text-[11px] font-mono text-surface-400 whitespace-pre-wrap">{stage.log.join('\n')}</pre>
              )}
            </li>
          ))}
        </ol>

        {allGreen && fixed && (
          <div className="p-3 rounded-lg bg-accent-green/10 border border-accent-green/30 text-accent-green text-xs flex items-center gap-2">
            <CheckCircle2 size={16} /> Pipeline green — return to the terminal and run Check Solution.
          </div>
        )}
      </div>
    </div>
  )
}

function StageIcon({ status }) {
  if (status === 'success') return <CheckCircle2 size={16} className="text-accent-green" />
  if (status === 'failed') return <XCircle size={16} className="text-red-400" />
  return <span className="w-4 h-4 rounded-full border-2 border-surface-600" />
}

function delay(ms) {
  return new Promise((r) => setTimeout(r, ms))
}
