/** Interactive DevOps / Networking simulation sidebar for LabRunner. */
export default function DevOpsNetworkingSimToolkit({ scenario, onRunCommand }) {
  const simType = (scenario?.simulation_type || 'generic').toLowerCase()
  const slug = (scenario?.slug || '').toLowerCase()
  const isDevops = simType === 'devops' || slug.includes('ci-pipeline') || slug.includes('helm')
  const isNetworking = simType === 'networking' || slug.includes('bgp') || slug.includes('ntp')

  if (!isDevops && !isNetworking) return null

  const run = (cmd) => onRunCommand?.(cmd)

  if (isDevops) {
    const pipelineFailed = slug.includes('ci-pipeline') || slug.includes('pipeline-failure')
    const helmStuck = slug.includes('helm')
    return (
      <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-lg p-3 space-y-3">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-emerald-400">DevOps Toolkit</p>
        <div className="grid grid-cols-2 gap-2 text-[11px]">
          <div className="bg-surface-900 rounded p-2 border border-surface-800">
            <p className="text-surface-500 mb-1">GitLab Pipeline</p>
            <p className={pipelineFailed ? 'text-accent-red font-medium' : 'text-accent-green'}>
              {pipelineFailed ? 'FAILED — deploy stage' : 'Healthy'}
            </p>
          </div>
          <div className="bg-surface-900 rounded p-2 border border-surface-800">
            <p className="text-surface-500 mb-1">Helm Release</p>
            <p className={helmStuck ? 'text-accent-amber font-medium' : 'text-accent-green'}>
              {helmStuck ? 'pending-upgrade' : 'deployed'}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <button type="button" onClick={() => run('gitlab-runner status')} className="px-2 py-1 rounded text-[10px] bg-surface-800 text-surface-300 hover:text-white border border-surface-700">
            Pipeline status
          </button>
          <button type="button" onClick={() => run('helm history webapp')} className="px-2 py-1 rounded text-[10px] bg-surface-800 text-surface-300 hover:text-white border border-surface-700">
            Helm history
          </button>
          <button type="button" onClick={() => run('export KUBECONFIG=/root/.kube/config')} className="px-2 py-1 rounded text-[10px] bg-surface-800 text-surface-300 hover:text-white border border-surface-700">
            Fix KUBECONFIG
          </button>
          <button type="button" onClick={() => run('helm rollback webapp 3')} className="px-2 py-1 rounded text-[10px] bg-surface-800 text-surface-300 hover:text-white border border-surface-700">
            Helm rollback
          </button>
        </div>
      </div>
    )
  }

  const bgpDown = slug.includes('bgp')
  const ntpDrift = slug.includes('ntp')
  return (
    <div className="bg-cyan-500/5 border border-cyan-500/20 rounded-lg p-3 space-y-3">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-cyan-400">Networking Toolkit</p>
      <div className="grid grid-cols-2 gap-2 text-[11px]">
        <div className="bg-surface-900 rounded p-2 border border-surface-800">
          <p className="text-surface-500 mb-1">BGP Peer 10.0.0.2</p>
          <p className={bgpDown ? 'text-accent-red font-medium' : 'text-accent-green'}>
            {bgpDown ? 'Idle' : 'Established'}
          </p>
        </div>
        <div className="bg-surface-900 rounded p-2 border border-surface-800">
          <p className="text-surface-500 mb-1">NTP</p>
          <p className={ntpDrift ? 'text-accent-amber font-medium' : 'text-accent-green'}>
            {ntpDrift ? 'Not synced' : 'Synced'}
          </p>
        </div>
      </div>
      <div className="flex flex-wrap gap-1.5">
        <button type="button" onClick={() => run('vtysh -c "show ip bgp summary"')} className="px-2 py-1 rounded text-[10px] bg-surface-800 text-surface-300 hover:text-white border border-surface-700">
          BGP summary
        </button>
        <button type="button" onClick={() => run('router bgp 65001\n neighbor 10.0.0.2 remote-as 65001')} className="px-2 py-1 rounded text-[10px] bg-surface-800 text-surface-300 hover:text-white border border-surface-700">
          Fix BGP AS
        </button>
        <button type="button" onClick={() => run('chronyc tracking')} className="px-2 py-1 rounded text-[10px] bg-surface-800 text-surface-300 hover:text-white border border-surface-700">
          NTP status
        </button>
        <button type="button" onClick={() => run('chronyc makestep')} className="px-2 py-1 rounded text-[10px] bg-surface-800 text-surface-300 hover:text-white border border-surface-700">
          Sync NTP
        </button>
      </div>
    </div>
  )
}
