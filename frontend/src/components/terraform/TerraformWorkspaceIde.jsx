import { useCallback, useEffect, useRef, useState } from 'react'
import { terraformApi } from '../../api/terraform'
import toast from 'react-hot-toast'
import CodeEditor from '../ide/CodeEditor'
import LabTerminal from '../LabTerminal'
import AwsTerminal from '../aws/terminal/AwsTerminal'
import VsCodeWorkbench, { VscFileItem, VscEditorTab, VscPanelTab, VscActivityButton } from '../ide/VsCodeWorkbench'
import { getIacProfile } from '../../utils/iacFlavor'
import { syncTerraformApplyToAwsConsole, awsConsoleUrlForResource } from '../../utils/terraformAwsBridge'
import {
  FileCode, FolderOpen, Play, Plus, Trash2, AlertTriangle, RefreshCw, Terminal, CloudCog, Files, CheckCircle2, History, ExternalLink,
} from 'lucide-react'
import '../../styles/vscode-workbench.css'

const DEFAULT_FILES = ['main.tf', 'variables.tf', 'outputs.tf']

/** VS Code–style Terraform workspace — files, init/plan/apply, scenario-driven output. */
export default function TerraformWorkspaceIde({
  sessionId, scenario, terminalSession, terminalHost = 'primary',
  blockedCommands = [], isMobile = false, state, setState, onRefresh,
  standalone = false,
}) {
  const profile = getIacProfile()
  const cli = 'terraform'
  const [files, setFiles] = useState({})
  const [activeFile, setActiveFile] = useState('main.tf')
  const [bottomTab, setBottomTab] = useState('output')
  const [lastAwsResource, setLastAwsResource] = useState(null)
  const [output, setOutput] = useState('')
  const [busy, setBusy] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [showTerminal, setShowTerminal] = useState(!standalone)
  const saveTimer = useRef(null)
  const filesRef = useRef({})
  const terminalRef = useRef(null)

  const actionPrefix = 'terraform'

  useEffect(() => {
    const remoteFiles = state?.state?.files || {}
    setFiles((prev) => {
      const next = Object.keys(prev).length && dirty ? prev : remoteFiles
      filesRef.current = next
      return next
    })
    if (state?.state?.active_file && !dirty) setActiveFile(state.state.active_file)
  }, [state, dirty])

  const persistFiles = useCallback(async (nextFiles, nextActive = activeFile) => {
    setBusy(true)
    try {
      const res = await terraformApi.action(sessionId, 'save_files', { files: nextFiles, active_file: nextActive })
      setDirty(false)
      if (res?.state) setState(res.state)
      toast.success('Saved', { id: 'tf-save', duration: 1200 })
    } catch {
      toast.error('Save failed')
    } finally { setBusy(false) }
  }, [sessionId, activeFile, setState])

  const fileList = Object.keys(files).length ? Object.keys(files).sort() : DEFAULT_FILES

  const handleFileChange = (content) => {
    const next = { ...filesRef.current, [activeFile]: content }
    filesRef.current = next
    setFiles(next)
    setDirty(true)
    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => persistFiles(next, activeFile), 1500)
  }

  const run = async (action, payload = {}, okMsg) => {
    if (busy) return
    setBusy(true)
    setBottomTab('output')
    try {
      const res = await terraformApi.action(sessionId, action, payload)
      if (res?.ok === false) {
        toast.error(res.error || 'Failed')
        setOutput(res.output || res.error || 'Command failed')
      } else {
        if (okMsg) toast.success(res?.message || okMsg, { duration: 2000 })
        setOutput(res?.output || res?.plan?.summary || JSON.stringify(res?.plan || res, null, 2) || '')
        if (action === `${actionPrefix}_apply` || action === 'terraform_apply') {
          syncTerraformApplyToAwsConsole(res?.state ? { state: res.state } : state)
          setLastAwsResource({ type: 'instance', id: null })
        }
      }
      if (res?.state) setState(res.state)
      else onRefresh?.()
    } finally { setBusy(false) }
  }

  const deleteFile = async (name) => {
    if (!window.confirm(`Delete ${name}?`)) return
    const res = await terraformApi.action(sessionId, 'delete_file', { path: name })
    if (res?.ok === false) { toast.error(res.error || 'Delete failed'); return }
    const next = { ...filesRef.current }
    delete next[name]
    filesRef.current = next
    setFiles(next)
    if (activeFile === name) setActiveFile('main.tf')
    if (res?.state) setState(res.state)
    else onRefresh?.()
    toast.success(`Deleted ${name}`)
  }

  const sendToTerminal = (cmd) => {
    const line = cmd.startsWith('cd ') ? cmd : `cd /root/terraform && ${cmd}`
    if (terminalRef.current?.sendCommand(line)) {
      setShowTerminal(true)
      setBottomTab('terminal')
      toast.success(`Terminal: ${cmd}`, { duration: 1500 })
    } else toast.error('Terminal not ready — use Output panel buttons')
  }

  const tf = state?.state?.terraform || {}
  const broken = state?.state?.broken || {}
  const events = state?.state?.events || []
  const goal = state?.state?.goal || {}
  const editorLang = 'hcl'
  const canTerminal = terminalSession?.status === 'RUNNING'

  const bottomContent = () => {
    if (bottomTab === 'terminal' && showTerminal && canTerminal) {
      return (
        <LabTerminal ref={terminalRef} sessionId={sessionId} session={terminalSession} hostKey={terminalHost}
          isMobile={isMobile} blockedCommands={blockedCommands} className="h-full min-h-[180px]"
          welcomeHint={`cd /root/terraform — ${cli} init / plan / apply`} />
      )
    }
    if (bottomTab === 'events') {
      return (
        <div className="space-y-1 max-h-[220px] overflow-y-auto text-xs">
          {events.length === 0 ? (
            <p className="text-[var(--vsc-muted)]">No events yet — run init, plan, or apply.</p>
          ) : events.map((ev, i) => (
            <div key={i} className="flex gap-2 py-0.5 border-b border-[var(--vsc-border)]/40">
              <span className="text-[var(--vsc-muted)] shrink-0">{ev.time?.replace('T', ' ').replace('Z', '')}</span>
              <span className={ev.severity === 'success' ? 'text-emerald-400' : ''}>{ev.message}</span>
            </div>
          ))}
        </div>
      )
    }
    if (bottomTab === 'aws') {
      return (
        <div className="h-full min-h-[200px] flex flex-col gap-2">
          <div className="flex items-center justify-between gap-2 shrink-0 px-1">
            <p className="text-[10px] text-[var(--vsc-muted)]">
              AWS CloudShell — run <code className="text-orange-300">aws</code> and <code className="text-violet-300">terraform</code> commands in a real terminal. Resources appear in the AWS Console.
            </p>
            <a
              href={awsConsoleUrlForResource(lastAwsResource?.type, lastAwsResource?.id)}
              target="_blank"
              rel="noopener noreferrer"
              className="vsc-btn text-[10px] inline-flex items-center gap-1"
              style={{ borderColor: '#ff9900', color: '#ff9900' }}
            >
              <ExternalLink size={11} /> Open AWS Console
            </a>
          </div>
          <div className="flex-1 min-h-[180px] rounded border border-[var(--vsc-border)] overflow-hidden">
            <AwsTerminal cloudShell />
          </div>
        </div>
      )
    }
    return (
      <div className="space-y-2 h-full flex flex-col min-h-0">
        <div className="flex flex-wrap gap-1.5 shrink-0">
          <button type="button" onClick={() => run(`${actionPrefix}_init`, {}, 'Initialized')} disabled={busy || tf.initialized} className="vsc-btn vsc-btn-primary">{cli} init</button>
          <button type="button" onClick={() => run(`${actionPrefix}_validate`)} disabled={busy} className="vsc-btn">{cli} validate</button>
          <button type="button" onClick={() => run(`${actionPrefix}_plan`)} disabled={busy || !tf.initialized} className="vsc-btn">{cli} plan</button>
          <button type="button" onClick={() => run(`${actionPrefix}_apply`)} disabled={busy || !tf.last_plan} className="vsc-btn vsc-btn-primary" style={{ background: '#107c10', borderColor: '#107c10' }}>
            <Play size={11} /> {cli} apply
          </button>
          {broken.stale_lock && (
            <button type="button" onClick={() => run('force_unlock', {}, 'Unlocked')} className="vsc-btn" style={{ color: '#fbbf24' }}>force-unlock</button>
          )}
          <button type="button" onClick={onRefresh} className="vsc-btn"><RefreshCw size={11} /></button>
          {canTerminal && (
            <button type="button" onClick={() => sendToTerminal(`${cli} plan`)} className="vsc-btn"><Terminal size={11} /> Shell</button>
          )}
        </div>
        <pre className="text-xs whitespace-pre-wrap break-words flex-1 overflow-auto font-mono leading-relaxed text-[var(--vsc-text)]">{output || `Run ${cli} init, then plan and apply. Output reflects this lab scenario.`}</pre>
      </div>
    )
  }

  return (
    <VsCodeWorkbench
      accent={profile.accent}
      className="flex-1 min-h-0"
      sidebarMobile={standalone ? 'horizontal' : 'hidden'}
      title={`${profile.label} Workspace`}
      subtitle={scenario?.title || goal.title || 'IaC IDE'}
      activityBar={(
        <div className="vsc-activity-bar hidden sm:flex">
          <VscActivityButton active title="Explorer"><Files size={22} /></VscActivityButton>
          <VscActivityButton active={bottomTab === 'aws'} onClick={() => setBottomTab('aws')} title="AWS CLI"><CloudCog size={22} /></VscActivityButton>
          {canTerminal && (
            <VscActivityButton active={bottomTab === 'terminal'} onClick={() => { setBottomTab('terminal'); setShowTerminal(true) }} title="Terminal"><Terminal size={22} /></VscActivityButton>
          )}
        </div>
      )}
      sidebarHeader={(
        <>
          <span className="flex items-center gap-1"><FolderOpen size={11} /> {profile.explorerLabel}</span>
          <button type="button" onClick={() => {
            const name = window.prompt('New .tf file:', 'custom.tf')
            if (!name?.endsWith('.tf')) return
            const next = { ...filesRef.current, [name]: '# New configuration\nresource "null_resource" "example" {}\n' }
            filesRef.current = next
            setFiles(next)
            setActiveFile(name)
            setDirty(true)
            persistFiles(next, name)
          }} className="text-[var(--vsc-accent)]" title="New file"><Plus size={12} /></button>
        </>
      )}
      sidebar={fileList.map((f) => (
        <div key={f} className="flex items-center gap-0.5 w-full group">
          <VscFileItem active={activeFile === f} onClick={() => setActiveFile(f)} className="flex-1 min-w-0">
            <FileCode size={13} className="shrink-0 opacity-70" />
            <span className="truncate">{f}</span>
            {dirty && activeFile === f && <span className="ml-auto text-[10px] text-amber-400">●</span>}
          </VscFileItem>
          {standalone && !DEFAULT_FILES.includes(f) && (
            <button type="button" onClick={() => deleteFile(f)} className="opacity-0 group-hover:opacity-100 p-1 text-red-400 hover:text-red-300" title="Delete">
              <Trash2 size={11} />
            </button>
          )}
        </div>
      ))}
      editorTabs={fileList.map((f) => (
        <VscEditorTab key={f} active={activeFile === f} onClick={() => setActiveFile(f)}>
          <FileCode size={12} /> {f}{dirty && activeFile === f ? ' ●' : ''}
        </VscEditorTab>
      ))}
      editorToolbar={!standalone && (
        <>
          {[`${cli} init`, `${cli} plan`, `${cli} apply -auto-approve`].map((cmd) => (
            <button key={cmd} type="button" onClick={() => sendToTerminal(cmd)} className="vsc-btn">
              <Terminal size={11} /> {cmd}
            </button>
          ))}
        </>
      )}
      editor={(
        <CodeEditor key={activeFile} value={files[activeFile] || ''} onChange={handleFileChange}
          language={editorLang} fontSize={13} formatOnSave />
      )}
      bottomPanel={{
        height: standalone ? 280 : (showTerminal ? 240 : 200),
        tabs: (
          <>
            <VscPanelTab active={bottomTab === 'output'} onClick={() => setBottomTab('output')}>{profile.label} Output</VscPanelTab>
            <VscPanelTab active={bottomTab === 'events'} onClick={() => setBottomTab('events')}><History size={11} /> Events</VscPanelTab>
            <VscPanelTab active={bottomTab === 'aws'} onClick={() => setBottomTab('aws')}>AWS CLI</VscPanelTab>
            {canTerminal && showTerminal && (
              <VscPanelTab active={bottomTab === 'terminal'} onClick={() => setBottomTab('terminal')}>Terminal</VscPanelTab>
            )}
          </>
        ),
        content: bottomContent(),
      }}
      statusBar={{
        left: activeFile,
        center: `${profile.label} · HCL · ${tf.initialized ? 'initialized' : 'not initialized'}`,
        right: (
          <>
            <span>{dirty ? '● Modified' : 'Saved'}</span>
            {tf.last_apply && <span className="text-emerald-400 flex items-center gap-1"><CheckCircle2 size={10} /> Applied</span>}
            {broken.drift && !tf.last_apply && <span className="text-amber-400">Drift</span>}
            {broken.stale_lock && <span className="text-red-400">Locked</span>}
          </>
        ),
      }}
      footer={goal.objective && (
        <div className="px-3 py-1.5 text-[11px] bg-amber-900/30 border-t border-amber-700/40 flex items-center gap-2 shrink-0">
          <AlertTriangle size={12} className="text-amber-400 shrink-0" />
          <span><strong>{goal.title}:</strong> {goal.objective}</span>
        </div>
      )}
    />
  )
}
