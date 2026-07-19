import { Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { lazyWithRetry } from '../../utils/lazyWithRetry'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { terraformApi } from '../../api/terraform'
import toast from 'react-hot-toast'
import { useConfirm } from '../../hooks/useConfirm'
import CodeEditor from '../ide/CodeEditor'
import LabTerminal, { scheduleReadySend } from '../LabTerminal'
import TerraformAwsTerminal from './TerraformAwsTerminal'
import VsCodeWorkbench, { VscFileItem, VscEditorTab, VscPanelTab, VscActivityButton } from '../ide/VsCodeWorkbench'
import { getIacProfile } from '../../utils/iacFlavor'
import { LabChromeControls } from '../lab/LabChromeBar'
import { syncTerraformApplyToAwsConsole } from '../../utils/terraformAwsBridge'
import {
  FileCode, FolderOpen, Play, Plus, Trash2, AlertTriangle, RefreshCw, Terminal, CloudCog, Files, CheckCircle2, History, ExternalLink, LayoutDashboard,
} from 'lucide-react'
import '../../styles/vscode-workbench.css'

// Full AWS console, embedded read-only-router style so the terraform lab can show
// exactly the resources `terraform apply` created without leaving the IDE.
const AwsConsole = lazyWithRetry(() => import('../aws/AwsConsole'))
const AzureConsole = lazyWithRetry(() => import('../azure/AzureConsole'))
const GcpConsole = lazyWithRetry(() => import('../gcp/GcpConsole'))

const DEFAULT_FILES = ['main.tf', 'variables.tf', 'outputs.tf']

/** VS Code–style Terraform workspace — files, init/plan/apply, scenario-driven output. */
export default function TerraformWorkspaceIde({
  sessionId, scenario, terminalSession, terminalHost = 'primary',
  blockedCommands = [], isMobile = false, state, setState, onRefresh,
  standalone = false,
  // Lab chrome controls — rendered inline in the IDE toolbar so the standard
  // Hints / Check / +30m / Stop buttons are always reachable in a terraform lab,
  // even when the IDE is the standalone surface inside the Cloud shell.
  onHints, onCheck, onExtend, onStop,
  hintsLabel, checkDisabled, extendDisabled, showLabControls = false,
}) {
  const { confirm, ConfirmPortal } = useConfirm()
  const profile = getIacProfile()
  const cli = 'terraform'
  const [files, setFiles] = useState({})
  const [activeFile, setActiveFile] = useState('main.tf')
  const [bottomTab, setBottomTab] = useState('output')
  const [output, setOutput] = useState('')
  const [busy, setBusy] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [showTerminal, setShowTerminal] = useState(!standalone)
  const [terminalReady, setTerminalReady] = useState({})
  const saveTimer = useRef(null)
  const filesRef = useRef({})
  const terminalRef = useRef(null)
  const pendingSendRef = useRef(null)
  const sendCancelRef = useRef(null)

  useEffect(() => () => { sendCancelRef.current?.() }, [])

  // Fired by <LabTerminal> once its shell is ready (backend shell_ready or the
  // sim/cloud fallback timer). Flush any command queued while the pane was
  // still mounting its xterm + WebSocket.
  const handleTerminalReady = useCallback((hostKey) => {
    setTerminalReady((prev) => (prev[hostKey] ? prev : { ...prev, [hostKey]: true }))
    const pending = pendingSendRef.current
    if (pending) {
      // Stop the polling loop first so it can't also fire a (spurious) error.
      sendCancelRef.current?.()
      sendCancelRef.current = null
      pendingSendRef.current = null
      if (terminalRef.current?.sendCommand(pending.line)) {
        toast.success(`Terminal: ${pending.cmd}`, { duration: 1500 })
      }
    }
  }, [])

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
          syncTerraformApplyToAwsConsole(res?.state ? { state: res.state } : state, { sessionId })
          toast.success('Resources mirrored to cloud consoles — open AWS / Azure / GCP tabs to verify.', { duration: 3500 })
        }
      }
      if (res?.state) setState(res.state)
      else onRefresh?.()
    } finally { setBusy(false) }
  }

  const deleteFile = async (name) => {
    if (!await confirm({ message: `Delete ${name}?`, danger: true, confirmLabel: 'Delete' })) return
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

  // Readiness-driven send. The <LabTerminal> only mounts when
  // bottomTab === 'terminal' && showTerminal, so we FIRST reveal it, then wait
  // for its xterm dynamic-import + WebSocket handshake before flushing. The
  // command is queued so onReady can flush it the instant the shell connects,
  // and we only toast an error after a bounded timeout.
  const sendToTerminal = (cmd) => {
    const line = cmd.startsWith('cd ') ? cmd : `cd /root/terraform && ${cmd}`
    // Mount the terminal pane if it is not already visible.
    setShowTerminal(true)
    setBottomTab('terminal')
    sendCancelRef.current?.()
    pendingSendRef.current = { cmd, line }

    sendCancelRef.current = scheduleReadySend(line, {
      // Skip if handleTerminalReady already flushed this queued command.
      getTerminal: () => (pendingSendRef.current?.line === line ? terminalRef.current : null),
      onSuccess: () => {
        pendingSendRef.current = null
        sendCancelRef.current = null
        toast.success(`Terminal: ${cmd}`, { duration: 1500 })
      },
      onError: () => {
        pendingSendRef.current = null
        sendCancelRef.current = null
        toast.error('Terminal not ready — use Output panel buttons')
      },
      timeoutMs: 5000,
      intervalMs: 150,
      // Defer the first attempt so the terminal pane actually mounts first.
      initialDelayMs: 150,
    })
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
          welcomeHint={`cd /root/terraform — ${cli} init / plan / apply`}
          onReady={() => handleTerminalReady(terminalHost)} />
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
              AWS CloudShell — <code className="text-violet-300">terraform apply</code> the files in this editor, then verify with <code className="text-orange-300">aws ec2 describe-instances</code>. Same store as the AWS Console.
            </p>
            <button
              type="button"
              onClick={() => setBottomTab('console')}
              className="vsc-btn text-[10px] inline-flex items-center gap-1"
              style={{ borderColor: '#ff9900', color: '#ff9900' }}
            >
              <ExternalLink size={11} /> Open AWS Console
            </button>
          </div>
          <div className="flex-1 min-h-[180px] rounded border border-[var(--vsc-border)] overflow-hidden">
            <TerraformAwsTerminal filesRef={filesRef} />
          </div>
        </div>
      )
    }
    if (bottomTab === 'console') {
      return (
        <div className="h-full min-h-[220px] rounded border border-[var(--vsc-border)] overflow-hidden aws-embedded-host">
          <Suspense fallback={<div className="p-4 text-xs text-[var(--vsc-muted)]">Loading AWS Console…</div>}>
            <MemoryRouter initialEntries={['/aws-sim/ec2/instances']}>
              <Routes>
                <Route path="/aws-sim/*" element={<AwsConsole embedded />} />
              </Routes>
            </MemoryRouter>
          </Suspense>
        </div>
      )
    }
    if (bottomTab === 'azure') {
      return (
        <div className="h-full min-h-[220px] rounded border border-[var(--vsc-border)] overflow-hidden">
          <Suspense fallback={<div className="p-4 text-xs text-[var(--vsc-muted)]">Loading Azure Portal…</div>}>
            <AzureConsole embedded sessionId={sessionId} scenario={scenario} />
          </Suspense>
        </div>
      )
    }
    if (bottomTab === 'gcp') {
      return (
        <div className="h-full min-h-[220px] rounded border border-[var(--vsc-border)] overflow-hidden">
          <Suspense fallback={<div className="p-4 text-xs text-[var(--vsc-muted)]">Loading Google Cloud Console…</div>}>
            <GcpConsole embedded sessionId={sessionId} scenario={scenario} />
          </Suspense>
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
            <button type="button" onClick={() => sendToTerminal(`${cli} plan`)} className="vsc-btn"
              title={terminalReady[terminalHost] ? `Run ${cli} plan in terminal` : 'Opens the terminal and runs once connected'}>
              <Terminal size={11} /> Shell{terminalReady[terminalHost] ? '' : ' ▸'}</button>
          )}
        </div>
        <pre className="text-xs whitespace-pre-wrap break-words flex-1 overflow-auto font-mono leading-relaxed text-[var(--vsc-text)]">{output || `Run ${cli} init, then plan and apply. Output reflects this lab scenario.`}</pre>
      </div>
    )
  }

  return (
    <>
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
          <VscActivityButton active={bottomTab === 'console'} onClick={() => setBottomTab('console')} title="AWS Console"><LayoutDashboard size={22} /></VscActivityButton>
          <VscActivityButton active={bottomTab === 'azure'} onClick={() => setBottomTab('azure')} title="Azure Portal"><CloudCog size={22} /></VscActivityButton>
          <VscActivityButton active={bottomTab === 'gcp'} onClick={() => setBottomTab('gcp')} title="Google Cloud Console"><CloudCog size={22} /></VscActivityButton>
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
      editorToolbar={(
        <>
          {!standalone && [`${cli} init`, `${cli} plan`, `${cli} apply -auto-approve`].map((cmd) => (
            <button key={cmd} type="button" onClick={() => sendToTerminal(cmd)} className="vsc-btn"
              title={terminalReady[terminalHost] ? `Run: ${cmd}` : 'Opens the terminal and runs once connected'}>
              <Terminal size={11} /> {cmd}
            </button>
          ))}
          {showLabControls && (onHints || onCheck || onExtend || onStop) && (
            <div className="ml-auto flex items-center gap-1.5 lab-chrome-actions">
              <LabChromeControls
                onHints={onHints}
                onCheck={onCheck}
                onExtend={onExtend}
                onStop={onStop}
                hintsLabel={hintsLabel}
                checkDisabled={checkDisabled}
                extendDisabled={extendDisabled}
                showTimer={false}
              />
            </div>
          )}
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
            <VscPanelTab active={bottomTab === 'console'} onClick={() => setBottomTab('console')}><LayoutDashboard size={11} /> AWS Console</VscPanelTab>
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
    <ConfirmPortal />
    </>
  )
}
