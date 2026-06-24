import { useCallback, useEffect, useRef, useState } from 'react'
import { terraformApi } from '../../api/terraform'
import toast from 'react-hot-toast'
import CodeEditor from '../ide/CodeEditor'
import LabTerminal from '../LabTerminal'
import LabChromeBar from '../lab/LabChromeBar'
import {
  Cloud, FileCode, FolderOpen, Play, Plus, Trash2,
  AlertTriangle, RefreshCw, Save, Terminal, CloudCog,
} from 'lucide-react'
import '../../styles/lab-chrome.css'

const DEFAULT_FILES = ['main.tf', 'variables.tf', 'outputs.tf']

export default function TerraformSimulator({
  sessionId,
  scenario,
  terminalSession,
  terminalHost = 'primary',
  blockedCommands = [],
  isMobile = false,
  onExit,
  onStop,
  onHints,
  onCheck,
  onExtend,
  hintsLabel,
  checkDisabled,
  extendDisabled,
}) {
  const [state, setState] = useState(null)
  const [files, setFiles] = useState({})
  const [activeFile, setActiveFile] = useState('main.tf')
  const [panel, setPanel] = useState('editor')
  const [awsCmd, setAwsCmd] = useState('aws sts get-caller-identity')
  const [output, setOutput] = useState('')
  const [busy, setBusy] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [showTerminal, setShowTerminal] = useState(true)
  const saveTimer = useRef(null)
  const filesRef = useRef({})
  const terminalRef = useRef(null)
  const slug = scenario?.slug || ''

  const refresh = useCallback(async () => {
    const data = await terraformApi.getState(sessionId, slug)
    setState(data)
    const remoteFiles = data?.state?.files || {}
    setFiles((prev) => {
      const next = Object.keys(prev).length && dirty ? prev : remoteFiles
      filesRef.current = next
      return next
    })
    if (data?.state?.active_file && !dirty) {
      setActiveFile(data.state.active_file)
    }
  }, [sessionId, slug, dirty])

  useEffect(() => { refresh() }, [refresh])

  const persistFiles = useCallback(async (nextFiles, nextActive = activeFile) => {
    setBusy(true)
    try {
      await terraformApi.action(sessionId, 'save_files', { files: nextFiles, active_file: nextActive })
      setDirty(false)
      toast.success('Saved', { id: 'tf-save', duration: 1200 })
    } catch {
      toast.error('Save failed')
    } finally {
      setBusy(false)
    }
  }, [sessionId, activeFile])

  const fileList = Object.keys(files).length ? Object.keys(files).sort() : DEFAULT_FILES

  const handleFileChange = (content) => {
    const next = { ...filesRef.current, [activeFile]: content }
    filesRef.current = next
    setFiles(next)
    setDirty(true)
    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => persistFiles(next, activeFile), 1500)
  }

  const handleSave = () => {
    if (saveTimer.current) clearTimeout(saveTimer.current)
    persistFiles(filesRef.current, activeFile)
  }

  const run = async (action, payload = {}, okMsg) => {
    if (busy) return
    setBusy(true)
    try {
      const res = await terraformApi.action(sessionId, action, payload)
      if (res?.ok === false) toast.error(res.error || 'Failed')
      else if (okMsg) toast.success(res?.message || okMsg)
      setOutput(res?.output || res?.plan?.summary || JSON.stringify(res?.plan || res, null, 2) || '')
      if (res?.state) setState(res.state)
      else await refresh()
    } finally { setBusy(false) }
  }

  const sendToTerminal = (cmd) => {
    const line = cmd.startsWith('cd ') ? cmd : `cd /root/terraform && ${cmd}`
    if (terminalRef.current?.sendCommand(line)) {
      setShowTerminal(true)
      toast.success(`Terminal: ${cmd}`, { duration: 1500 })
    } else {
      toast.error('Terminal not ready — wait for shell connection')
    }
  }

  const addFile = () => {
    const name = window.prompt('New Terraform file name (must end with .tf):', 'custom.tf')
    if (!name || !name.endsWith('.tf')) return
    const next = { ...filesRef.current, [name]: '# New Terraform configuration\n' }
    filesRef.current = next
    setFiles(next)
    setActiveFile(name)
    setDirty(true)
    persistFiles(next, name)
  }

  const deleteFile = () => {
    if (DEFAULT_FILES.includes(activeFile)) {
      toast.error('Cannot delete default project files')
      return
    }
    if (!window.confirm(`Delete ${activeFile}?`)) return
    const next = { ...filesRef.current }
    delete next[activeFile]
    filesRef.current = next
    setFiles(next)
    const fallback = Object.keys(next)[0] || 'main.tf'
    setActiveFile(fallback)
    persistFiles(next, fallback)
  }

  const tf = state?.state?.terraform || {}
  const goal = state?.state?.goal || {}
  const broken = state?.state?.broken || {}

  return (
    <div className="fixed inset-0 z-[60] flex flex-col bg-[#1e1e1e] text-slate-200">
      <LabChromeBar
        icon={Cloud}
        title="Terraform + AWS IDE"
        subtitle={scenario?.title || slug}
        accent="#a78bfa"
        className="lab-chrome-bar"
        onHints={onHints}
        onCheck={onCheck}
        onExtend={onExtend}
        onStop={onStop}
        onBackToTerminal={onExit}
        backLabel="Hide IDE"
        hintsLabel={hintsLabel}
        checkDisabled={checkDisabled}
        extendDisabled={extendDisabled}
      >
        <button type="button" className="lab-chrome-btn" onClick={handleSave} disabled={busy || !dirty}>
          <Save size={12} /> Save
        </button>
        <button type="button" className="lab-chrome-btn" onClick={() => setShowTerminal((v) => !v)}>
          <Terminal size={12} /> {showTerminal ? 'Hide shell' : 'Show shell'}
        </button>
      </LabChromeBar>

      {goal.objective && (
        <div className="px-3 py-1.5 text-[11px] bg-amber-900/30 border-b border-amber-700/40 flex items-center gap-2 shrink-0">
          <AlertTriangle size={12} className="shrink-0 text-amber-400" />
          <span className="text-amber-100/90">{goal.objective}</span>
        </div>
      )}

      <div className="flex flex-1 min-h-0 flex-col">
        <div className={`flex min-h-0 ${showTerminal ? 'flex-[3]' : 'flex-1'}`}>
          <aside className="w-44 shrink-0 bg-[#252526] border-r border-slate-700 flex flex-col">
            <div className="px-2 py-1.5 text-[10px] uppercase tracking-wide text-slate-500 flex items-center justify-between">
              <span className="flex items-center gap-1"><FolderOpen size={11} /> Explorer</span>
              <button type="button" onClick={addFile} className="text-violet-400 hover:text-violet-300" title="New file"><Plus size={12} /></button>
            </div>
            {fileList.map((f) => (
              <button key={f} type="button" onClick={() => setActiveFile(f)}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs text-left ${
                  activeFile === f ? 'bg-violet-600/25 text-violet-200' : 'text-slate-400 hover:bg-slate-800'
                }`}>
                <FileCode size={12} /> {f}
              </button>
            ))}
          </aside>

          <div className="flex-1 flex flex-col min-w-0 min-h-0">
            <div className="flex border-b border-slate-700 bg-[#2d2d2d] shrink-0">
              {['editor', 'output', 'aws'].map((t) => (
                <button key={t} type="button" onClick={() => setPanel(t)}
                  className={`px-3 py-1.5 text-xs capitalize ${panel === t ? 'border-b-2 border-violet-400 text-white bg-[#1e1e1e]' : 'text-slate-400'}`}>
                  {t === 'aws' ? 'AWS CLI' : t}
                </button>
              ))}
              <div className="flex-1" />
              {!DEFAULT_FILES.includes(activeFile) && panel === 'editor' && (
                <button type="button" onClick={deleteFile} className="px-2 text-red-400 hover:text-red-300" title="Delete file"><Trash2 size={14} /></button>
              )}
            </div>

            {panel === 'editor' && (
              <div className="flex-1 min-h-0 flex flex-col">
                <div className="px-3 py-1 text-[10px] text-slate-500 border-b border-slate-800 shrink-0 flex justify-between">
                  <span>/root/terraform/{activeFile}</span>
                </div>
                <div className="flex-1 min-h-0">
                  <CodeEditor key={activeFile} value={files[activeFile] || ''} onChange={handleFileChange} language="hcl" fontSize={12} formatOnSave />
                </div>
                <div className="shrink-0 px-3 py-2 border-t border-slate-700 bg-[#252526] flex flex-wrap gap-1.5">
                  <span className="text-[10px] text-slate-500 self-center mr-1">Run in terminal:</span>
                  {['terraform init', 'terraform plan', 'terraform apply -auto-approve'].map((cmd) => (
                    <button key={cmd} type="button" onClick={() => sendToTerminal(cmd)}
                      className="px-2 py-1 rounded text-[10px] bg-slate-700 hover:bg-violet-700 flex items-center gap-1">
                      <Terminal size={10} /> {cmd}
                    </button>
                  ))}
                  {broken.stale_lock && (
                    <button type="button" onClick={() => sendToTerminal('terraform force-unlock fixitlab-lock')}
                      className="px-2 py-1 rounded text-[10px] bg-amber-800 hover:bg-amber-700">force-unlock</button>
                  )}
                </div>
              </div>
            )}

            {panel === 'output' && (
              <div className="flex-1 min-h-0 flex flex-col p-3 gap-2 overflow-auto">
                <div className="flex flex-wrap gap-2">
                  <button onClick={() => run('terraform_init', {}, 'Initialized')} disabled={busy || tf.initialized}
                    className="px-3 py-1.5 rounded bg-violet-600 text-xs disabled:opacity-50">init (sim)</button>
                  <button onClick={() => run('terraform_plan')} disabled={busy || !tf.initialized}
                    className="px-3 py-1.5 rounded bg-slate-700 text-xs disabled:opacity-50">plan (sim)</button>
                  <button onClick={() => run('terraform_apply')} disabled={busy || !tf.last_plan}
                    className="px-3 py-1.5 rounded bg-green-700 text-xs disabled:opacity-50 flex items-center gap-1"><Play size={12} /> apply (sim)</button>
                  {broken.stale_lock && (
                    <button onClick={() => run('force_unlock', {}, 'Lock released')} disabled={busy}
                      className="px-3 py-1.5 rounded bg-amber-700 text-xs">force-unlock (sim)</button>
                  )}
                  <button onClick={refresh} className="px-3 py-1.5 rounded border border-slate-600 text-xs flex items-center gap-1">
                    <RefreshCw size={12} /> refresh
                  </button>
                </div>
                <div className="text-[10px] text-slate-500">
                  Workspace: {tf.workspace || 'default'} · Drift: {tf.drift_detected ? 'yes' : 'no'} · Init: {tf.initialized ? 'yes' : 'no'}
                </div>
                <pre className="flex-1 min-h-[120px] bg-black/50 rounded p-3 text-xs font-mono overflow-auto border border-slate-700">
                  {output || <span className="text-slate-500 flex items-center gap-2"><CloudCog size={14} /> Use terminal below for CLI workflow, or sim buttons above…</span>}
                </pre>
              </div>
            )}

            {panel === 'aws' && (
              <div className="flex-1 min-h-0 flex flex-col p-3 gap-2">
                <div className="flex gap-2 flex-wrap">
                  <input value={awsCmd} onChange={(e) => setAwsCmd(e.target.value)}
                    className="flex-1 min-w-[200px] bg-[#252526] border border-slate-600 rounded px-3 py-2 text-xs font-mono" />
                  <button onClick={() => run('aws_cli', { command: awsCmd })} disabled={busy}
                    className="px-4 py-2 rounded bg-[#ff9900] text-black text-xs font-medium">Run (sim)</button>
                  <button type="button" onClick={() => sendToTerminal(awsCmd)}
                    className="px-3 py-2 rounded border border-slate-600 text-xs flex items-center gap-1">
                    <Terminal size={12} /> Terminal
                  </button>
                </div>
                <div className="flex flex-wrap gap-1">
                  {['aws sts get-caller-identity', 'aws s3 ls', 'aws ec2 describe-instances', 'aws iam list-users'].map((c) => (
                    <button key={c} type="button" onClick={() => setAwsCmd(c)} className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-400 hover:text-white">{c}</button>
                  ))}
                </div>
                <pre className="flex-1 min-h-[120px] bg-black/50 rounded p-3 text-xs font-mono overflow-auto border border-slate-700">{output}</pre>
              </div>
            )}
          </div>
        </div>

        {showTerminal && terminalSession?.status === 'RUNNING' && (
          <div className="flex-[2] min-h-[180px] border-t border-violet-500/40 flex flex-col bg-surface-950">
            <div className="px-2 py-1 text-[10px] text-violet-300 border-b border-slate-800 bg-[#252526]">
              Lab terminal · /root/terraform
            </div>
            <LabTerminal
              ref={terminalRef}
              sessionId={sessionId}
              session={terminalSession}
              hostKey={terminalHost}
              isMobile={isMobile}
              blockedCommands={blockedCommands}
              className="flex-1 min-h-0"
              welcomeHint="cd /root/terraform — edit .tf files above, run terraform init/plan/apply here"
            />
          </div>
        )}
      </div>
    </div>
  )
}
