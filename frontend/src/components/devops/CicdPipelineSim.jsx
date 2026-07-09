import { useMemo, useState } from 'react'
import {
  Play, RotateCcw, CheckCircle2, XCircle, Loader2, GitBranch, Package, Shield,
  Workflow, FileCode, Settings, History, Terminal, ExternalLink,
} from 'lucide-react'
import LabChromeBar from '../lab/LabChromeBar'
import { simPanelRoot } from '../../utils/simLayout'
import '../../styles/lab-chrome.css'
import '../../styles/sim-products.css'

const BROKEN_GITLAB_CI = `stages:
  - build
  - test
  - deploy

build:
  stage: build
  image: node:18-alpinee
  script:
    - npm ci
    - npm run build
  artifacts:
    paths:
      - dist/

test:
  stage: test
  image: node:18-alpine
  script:
    - npm test

deploy:
  stage: deploy
  image: alpine/k8s:1.28.0
  script:
    - kubectl apply -f k8s/
  only:
    - main
`

const FIXED_GITLAB_CI = BROKEN_GITLAB_CI.replace('node:18-alpinee', 'node:18-alpine')

const DEFAULT_STAGES = [
  { id: 'checkout', name: 'Checkout', tool: 'git', status: 'success', duration: '12s', log: ['Cloning repository…', 'Checked out main @ a1b2c3d'] },
  { id: 'build', name: 'Build', tool: 'maven', status: 'failed', duration: '48s', log: ['mvn clean package -DskipTests', 'ERROR: Docker image node:18-alpinee not found'] },
  { id: 'test', name: 'Unit tests', tool: 'maven', status: 'pending', duration: '—', log: [] },
  { id: 'scan', name: 'SonarQube', tool: 'sonar', status: 'pending', duration: '—', log: [] },
  { id: 'deploy', name: 'Deploy', tool: 'argocd', status: 'pending', duration: '—', log: [] },
]

/**
 * CI/CD pipeline simulator — GitLab CI / Jenkins / GitHub Actions / Argo CD.
 * Wired with standard lab chrome (Hints, Check, timer, Stop) like AWX/Terraform.
 */
export default function CicdPipelineSim({
  scenario,
  onExit,
  onHints,
  onCheck,
  onExtend,
  onStop,
  hintsLabel,
  checkDisabled,
  extendDisabled,
  embedded = true,
  vmwareHref = null,
}) {
  const [tab, setTab] = useState('pipeline')
  const [stages, setStages] = useState(() => DEFAULT_STAGES.map((s) => ({ ...s })))
  const [gitlabCi, setGitlabCi] = useState(BROKEN_GITLAB_CI)
  const [branch, setBranch] = useState('main')
  const [imageTag, setImageTag] = useState('broken-tag')
  const [kubeconfig, setKubeconfig] = useState('')
  const [ciRegistry, setCiRegistry] = useState('registry.fixitlab.local')
  const [dockerImage, setDockerImage] = useState('fixitlab/webapp')
  const [running, setRunning] = useState(false)
  const [runHistory, setRunHistory] = useState([])
  const [fixed, setFixed] = useState(false)

  const yamlOk = !/alpinee|node:18-alpinee/.test(gitlabCi) && gitlabCi.includes('node:18-alpine')
  const buildOk = yamlOk && imageTag && imageTag !== 'broken-tag'
  const deployOk = kubeconfig.trim().length > 10
  const allGreen = useMemo(() => stages.every((s) => s.status === 'success'), [stages])

  const rerun = async () => {
    setRunning(true)
    setFixed(false)
    const runId = `#${1024 + runHistory.length}`
    const started = new Date().toISOString()
    setStages(DEFAULT_STAGES.map((s) => ({
      ...s,
      status: s.id === 'checkout' ? 'success' : 'pending',
      log: s.id === 'checkout' ? s.log : [],
      duration: s.id === 'checkout' ? '11s' : '—',
    })))
    await delay(350)

    const buildPass = buildOk
    setStages((prev) => prev.map((s) => {
      if (s.id === 'build') {
        return {
          ...s,
          status: buildPass ? 'success' : 'failed',
          duration: buildPass ? '1m 04s' : '48s',
          log: buildPass
            ? [
              `Using CI_REGISTRY=${ciRegistry}`,
              `docker pull ${ciRegistry}/${dockerImage}:${imageTag}`,
              'mvn clean package -DskipTests',
              'BUILD SUCCESS',
              `artifact: app-${imageTag}.jar`,
            ]
            : [
              'Checking .gitlab-ci.yml image…',
              yamlOk ? `ERROR: image tag ${imageTag} not found in registry` : 'ERROR: invalid image node:18-alpinee in .gitlab-ci.yml',
              'Job failed: exit code 1',
            ],
        }
      }
      return s
    }))
    if (!buildPass) {
      setRunning(false)
      setRunHistory((h) => [{ id: runId, branch, status: 'failed', started, reason: yamlOk ? 'bad image tag' : 'bad CI image' }, ...h].slice(0, 8))
      return
    }

    await delay(450)
    setStages((prev) => prev.map((s) => {
      if (s.id === 'test') return { ...s, status: 'success', duration: '22s', log: ['npm test', 'Tests run: 42, Failures: 0', 'Coverage: 78%'] }
      if (s.id === 'scan') return { ...s, status: 'success', duration: '31s', log: ['sonar-scanner', 'Quality Gate PASSED', 'Bugs: 0, Vulnerabilities: 0'] }
      if (s.id === 'deploy') {
        return {
          ...s,
          status: deployOk ? 'success' : 'failed',
          duration: deployOk ? '18s' : '5s',
          log: deployOk
            ? [`argocd app sync webapp --revision ${imageTag}`, 'Sync status: Synced', 'Health: Healthy', `Deployed branch ${branch}`]
            : ['kubectl apply failed: invalid kubeconfig', 'error: unable to load config file'],
        }
      }
      return s
    }))

    const ok = deployOk
    if (ok) setFixed(true)
    setRunHistory((h) => [{ id: runId, branch, status: ok ? 'success' : 'failed', started, reason: ok ? 'all stages green' : 'deploy failed' }, ...h].slice(0, 8))
    setRunning(false)
  }

  const tabs = [
    { id: 'pipeline', label: 'Pipeline', icon: Workflow },
    { id: 'gitlab', label: '.gitlab-ci.yml', icon: FileCode },
    { id: 'variables', label: 'Variables', icon: Settings },
    { id: 'history', label: 'Run history', icon: History },
  ]

  return (
    <div className={simPanelRoot(embedded, 'cicd-sim bg-[#0d1117] text-sm text-surface-200')}>
      <LabChromeBar
        icon={GitBranch}
        title="CI/CD Pipeline"
        subtitle={scenario?.title || 'DevOps lab'}
        accent="#38bdf8"
        className="lab-chrome-bar !bg-[#161b22] !border-b-surface-700"
        onExit={onExit}
        onHints={onHints}
        onCheck={onCheck}
        onExtend={onExtend}
        onStop={onStop}
        hintsLabel={hintsLabel}
        checkDisabled={checkDisabled}
        extendDisabled={extendDisabled}
        backLabel="Terminal"
        vmwareHref={vmwareHref}
      >
        <div className="hidden sm:flex items-center gap-1 mr-2">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={`text-[10px] px-2 py-1 rounded border transition-colors ${
                tab === t.id
                  ? 'border-sky-500/50 bg-sky-500/15 text-sky-300'
                  : 'border-surface-700 text-surface-500 hover:text-surface-300'
              }`}
            >
              <t.icon size={11} className="inline mr-1" />
              {t.label}
            </button>
          ))}
        </div>
      </LabChromeBar>

      <div className="flex sm:hidden items-center gap-1 px-4 py-2 border-b border-surface-800 overflow-x-auto shrink-0">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`text-[10px] px-2 py-1 rounded border whitespace-nowrap ${
              tab === t.id ? 'border-sky-500/50 bg-sky-500/15 text-sky-300' : 'border-surface-700 text-surface-500'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="flex-1 min-h-0 overflow-auto p-4 space-y-4 max-w-5xl mx-auto w-full">
        <p className="text-surface-400 text-xs flex items-start gap-2">
          <Terminal size={14} className="text-accent-cyan shrink-0 mt-0.5" />
          Fix the pipeline in this simulator <strong className="text-surface-300">and</strong> in the lab terminal
          (<code className="text-accent-cyan">/opt/app/.gitlab-ci.yml</code>). Correct the Docker image typo, set a valid
          <code className="text-accent-cyan mx-1">IMAGE_TAG</code>, then re-run. Use Check Solution in the lab chrome when green.
        </p>

        {tab === 'pipeline' && (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <label className="text-xs text-surface-500 flex items-center gap-1">
                Branch
                <select value={branch} onChange={(e) => setBranch(e.target.value)} className="input text-xs py-1">
                  <option value="main">main</option>
                  <option value="develop">develop</option>
                  <option value="feature/fix-pipeline">feature/fix-pipeline</option>
                </select>
              </label>
              <button type="button" disabled={running} onClick={rerun} className="btn-primary text-xs flex items-center gap-1.5">
                {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                Run pipeline
              </button>
              <button
                type="button"
                onClick={() => {
                  setGitlabCi(FIXED_GITLAB_CI)
                  setImageTag('v1.2.3')
                  setKubeconfig('apiVersion: v1\nkind: Config\nclusters:\n- name: lab\n  cluster:\n    server: https://k8s.lab\n')
                }}
                className="btn-secondary text-xs flex items-center gap-1"
              >
                <RotateCcw size={12} /> Apply known-good fix
              </button>
            </div>

            <div className="grid gap-2">
              {stages.map((stage, i) => (
                <div key={stage.id} className="rounded-lg border border-surface-700 bg-surface-900/60 overflow-hidden">
                  <div className="flex items-center gap-2 px-3 py-2 border-b border-surface-800">
                    <StageIcon status={stage.status} />
                    <span className="font-medium text-white">{i + 1}. {stage.name}</span>
                    <span className="text-[10px] text-surface-500">{stage.duration}</span>
                    <span className="text-[10px] text-surface-500 ml-auto flex items-center gap-1">
                      {stage.tool === 'sonar' && <Shield size={10} />}
                      {stage.tool === 'maven' && <Package size={10} />}
                      {stage.tool}
                    </span>
                  </div>
                  {stage.log?.length > 0 && (
                    <pre className="p-3 text-[11px] font-mono text-surface-400 whitespace-pre-wrap max-h-32 overflow-auto">{stage.log.join('\n')}</pre>
                  )}
                </div>
              ))}
            </div>

            {allGreen && fixed && (
              <div className="p-3 rounded-lg bg-accent-green/10 border border-accent-green/30 text-accent-green text-xs flex items-center gap-2">
                <CheckCircle2 size={16} />
                Pipeline green — return to the terminal and click <strong>Check</strong> in the lab bar to validate.
              </div>
            )}
          </>
        )}

        {tab === 'gitlab' && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-surface-500">Edit pipeline definition (mirrors terminal file)</span>
              {!yamlOk && (
                <span className="text-[10px] text-red-400 flex items-center gap-1">
                  <XCircle size={12} /> Fix image typo: node:18-alpinee → node:18-alpine
                </span>
              )}
            </div>
            <textarea
              className="input w-full font-mono text-[11px] min-h-[280px]"
              value={gitlabCi}
              onChange={(e) => setGitlabCi(e.target.value)}
              spellCheck={false}
            />
          </div>
        )}

        {tab === 'variables' && (
          <div className="grid sm:grid-cols-2 gap-3">
            <label className="block">
              <span className="text-xs text-surface-500">IMAGE_TAG</span>
              <input className="input w-full mt-1 font-mono text-xs" value={imageTag} onChange={(e) => setImageTag(e.target.value)} />
            </label>
            <label className="block">
              <span className="text-xs text-surface-500">CI_REGISTRY</span>
              <input className="input w-full mt-1 font-mono text-xs" value={ciRegistry} onChange={(e) => setCiRegistry(e.target.value)} />
            </label>
            <label className="block">
              <span className="text-xs text-surface-500">DOCKER_IMAGE</span>
              <input className="input w-full mt-1 font-mono text-xs" value={dockerImage} onChange={(e) => setDockerImage(e.target.value)} />
            </label>
            <label className="block sm:col-span-2">
              <span className="text-xs text-surface-500">KUBECONFIG (paste for deploy stage)</span>
              <textarea className="input w-full mt-1 font-mono text-[10px] h-24" value={kubeconfig} onChange={(e) => setKubeconfig(e.target.value)} />
            </label>
          </div>
        )}

        {tab === 'history' && (
          <div className="rounded-lg border border-surface-700 overflow-hidden">
            <table className="w-full text-xs">
              <thead className="bg-surface-900 text-surface-500">
                <tr>
                  <th className="text-left p-2">Run</th>
                  <th className="text-left p-2">Branch</th>
                  <th className="text-left p-2">Status</th>
                  <th className="text-left p-2">Started</th>
                </tr>
              </thead>
              <tbody>
                {runHistory.length === 0 ? (
                  <tr><td colSpan={4} className="p-4 text-surface-500">No runs yet — click Run pipeline.</td></tr>
                ) : runHistory.map((r) => (
                  <tr key={r.id} className="border-t border-surface-800">
                    <td className="p-2 font-mono">{r.id}</td>
                    <td className="p-2">{r.branch}</td>
                    <td className={`p-2 ${r.status === 'success' ? 'text-accent-green' : 'text-red-400'}`}>{r.status}</td>
                    <td className="p-2 text-surface-500">{new Date(r.started).toLocaleTimeString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <p className="text-[10px] text-surface-600 flex items-center gap-1">
          <ExternalLink size={10} />
          Tip: open the lab terminal and edit <code>/opt/app/.gitlab-ci.yml</code> — the checker validates the real file there.
        </p>
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
