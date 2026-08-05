import { useCallback, useEffect, useRef, useState } from 'react'
import toast from 'react-hot-toast'
import CodeEditor from '../ide/CodeEditor'
import LabTerminal, { scheduleReadySend } from '../LabTerminal'
import VsCodeWorkbench, { VscFileItem, VscEditorTab, VscPanelTab, VscActivityButton } from '../ide/VsCodeWorkbench'
import { LabChromeControls } from '../lab/LabChromeBar'
import {
  FileCode, FolderOpen, Play, Plus, Trash2, RefreshCw, Terminal, Files, ExternalLink,
} from 'lucide-react'
import '../../styles/vscode-workbench.css'

const DEFAULT_MAIN = `# FixitLab GPU image factory — Packer HCL
# Validate → build → CVE gate → publish to MAAS boot-resources.

packer {
  required_plugins {
    qemu = {
      version = ">= 1.1.0"
      source  = "github.com/hashicorp/qemu"
    }
  }
}

variable "sku" {
  type    = string
  default = "h100"
}

source "qemu" "gpu" {
  iso_url      = "https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img"
  iso_checksum = "file:https://cloud-images.ubuntu.com/jammy/current/SHA256SUMS"
  disk_size    = "40G"
  memory       = 8192
  cpus         = 4
  accelerator  = "tcg"
  ssh_username = "ubuntu"
  ssh_password = "ubuntu"
  shutdown_command = "sudo shutdown -P now"
}

build {
  name    = "gpu-\${var.sku}"
  sources = ["source.qemu.gpu"]

  provisioner "shell" {
    script = "scripts/install-gpu-\${var.sku}.sh"
  }

  post-processor "shell-local" {
    inline = [
      "trivy image --exit-code 1 --severity HIGH,CRITICAL output-gpu-\${var.sku}/",
      "echo Publishing custom/\${var.sku}-jammy to MAAS boot-resources",
    ]
  }
}
`

const DEFAULT_VARS = `sku = "h100"
`

const DEFAULT_FILES = {
  'gpu-h100.pkr.hcl': DEFAULT_MAIN,
  'variables.pkr.hcl': DEFAULT_VARS,
}

function storageKey(sessionId) {
  return `fixitlab:packer-ide:${sessionId || 'local'}`
}

/** VS Code–style Packer workspace — edit .pkr.hcl, validate/fmt/build via lab terminal. */
export default function PackerWorkspaceIde({
  sessionId,
  scenario,
  terminalSession,
  terminalHost = 'primary',
  blockedCommands = [],
  isMobile = false,
  onExit,
  onHints,
  onCheck,
  onExtend,
  onStop,
  hintsLabel,
  checkDisabled,
  extendDisabled,
  showLabControls = false,
}) {
  const [files, setFiles] = useState(() => {
    try {
      const raw = sessionStorage.getItem(storageKey(sessionId))
      if (raw) {
        const parsed = JSON.parse(raw)
        if (parsed?.files && typeof parsed.files === 'object') return parsed.files
      }
    } catch { /* ignore */ }
    return { ...DEFAULT_FILES }
  })
  const [activeFile, setActiveFile] = useState('gpu-h100.pkr.hcl')
  const [bottomTab, setBottomTab] = useState('output')
  const [output, setOutput] = useState('')
  const [dirty, setDirty] = useState(false)
  const [showTerminal, setShowTerminal] = useState(true)
  const [terminalReady, setTerminalReady] = useState({})
  const filesRef = useRef(files)
  const terminalRef = useRef(null)
  const pendingSendRef = useRef(null)
  const sendCancelRef = useRef(null)

  useEffect(() => () => { sendCancelRef.current?.() }, [])

  useEffect(() => {
    filesRef.current = files
    try {
      sessionStorage.setItem(storageKey(sessionId), JSON.stringify({ files, activeFile }))
    } catch { /* ignore */ }
  }, [files, activeFile, sessionId])

  const handleTerminalReady = useCallback((hostKey) => {
    setTerminalReady((prev) => (prev[hostKey] ? prev : { ...prev, [hostKey]: true }))
    const pending = pendingSendRef.current
    if (pending) {
      sendCancelRef.current?.()
      sendCancelRef.current = null
      pendingSendRef.current = null
      if (terminalRef.current?.sendCommand(pending.line)) {
        toast.success(`Terminal: ${pending.cmd}`, { duration: 1500 })
      }
    }
  }, [])

  const sendToTerminal = useCallback((cmd) => {
    const line = cmd.trim()
    if (!line) return
    setBottomTab('terminal')
    setShowTerminal(true)
    setOutput((prev) => `${prev ? `${prev}\n` : ''}$ ${line}`)
    if (terminalRef.current?.sendCommand(line)) {
      toast.success(`Terminal: ${line.split(/\s+/)[0]}`, { duration: 1200 })
      return
    }
    pendingSendRef.current = { line, cmd: line.split(/\s+/)[0] }
    sendCancelRef.current?.()
    sendCancelRef.current = scheduleReadySend(line, {
      getTerminal: () => (pendingSendRef.current?.line === line ? terminalRef.current : null),
      onSuccess: () => {
        pendingSendRef.current = null
        sendCancelRef.current = null
        toast.success(`Terminal: ${line.split(/\s+/)[0]}`, { duration: 1500 })
      },
      onError: () => {
        pendingSendRef.current = null
        sendCancelRef.current = null
        toast.error('Terminal not ready — use Output panel buttons')
      },
      timeoutMs: 5000,
      intervalMs: 150,
      initialDelayMs: 150,
    })
  }, [])

  const canTerminal = terminalSession?.status === 'RUNNING'
  const fileList = Object.keys(files)
  const mainFile = fileList.find((f) => f.endsWith('.pkr.hcl') && !f.startsWith('variables')) || 'gpu-h100.pkr.hcl'

  const bottomContent = () => {
    if (bottomTab === 'terminal' && showTerminal && canTerminal) {
      return (
        <LabTerminal
          ref={terminalRef}
          sessionId={sessionId}
          session={terminalSession}
          hostKey={terminalHost}
          isMobile={isMobile}
          blockedCommands={blockedCommands}
          className="h-full min-h-[180px]"
          welcomeHint="packer validate / fmt / build — CVE gate publishes to MAAS on success"
          onReady={() => handleTerminalReady(terminalHost)}
        />
      )
    }
    return (
      <div className="space-y-2 h-full flex flex-col min-h-0">
        <div className="flex flex-wrap gap-1.5 shrink-0">
          <button type="button" onClick={() => sendToTerminal(`packer validate ${mainFile}`)} className="vsc-btn vsc-btn-primary">
            packer validate
          </button>
          <button type="button" onClick={() => sendToTerminal(`packer fmt ${mainFile}`)} className="vsc-btn">
            packer fmt
          </button>
          <button
            type="button"
            onClick={() => sendToTerminal(`packer build ${mainFile}`)}
            className="vsc-btn vsc-btn-primary"
            style={{ background: '#02A8EF', borderColor: '#02A8EF' }}
          >
            <Play size={11} /> packer build
          </button>
          <button
            type="button"
            onClick={() => {
              setFiles({ ...DEFAULT_FILES })
              setActiveFile('gpu-h100.pkr.hcl')
              setDirty(false)
              setOutput('Reset template to GPU H100 defaults.')
            }}
            className="vsc-btn"
          >
            <RefreshCw size={11} /> Reset
          </button>
          {canTerminal && (
            <button type="button" onClick={() => sendToTerminal(`packer build ${mainFile}`)} className="vsc-btn" title="Run build in terminal">
              <Terminal size={11} /> Shell{terminalReady[terminalHost] ? '' : ' ▸'}
            </button>
          )}
        </div>
        <pre className="text-xs whitespace-pre-wrap break-words flex-1 overflow-auto font-mono leading-relaxed text-[var(--vsc-text)]">
          {output || 'Edit the Packer template, then validate and build. Successful builds pass the CVE gate and publish to MAAS boot-resources.'}
        </pre>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-[60] flex flex-col bg-[var(--vsc-bg,#1e1e1e)]">
      <div className="flex items-center gap-2 px-3 py-1.5 border-b border-[var(--vsc-border,#333)] shrink-0">
        <span className="text-xs font-semibold text-[#02A8EF]">Packer Image Factory</span>
        <span className="text-[10px] text-[var(--vsc-muted)] truncate">{scenario?.title || scenario?.slug || 'GPU image build'}</span>
        <div className="ml-auto flex items-center gap-1.5">
          {showLabControls && (onHints || onCheck || onExtend || onStop) && (
            <LabChromeControls
              onHints={onHints}
              onCheck={onCheck}
              onExtend={onExtend}
              onStop={onStop}
              hintsLabel={hintsLabel}
              checkDisabled={checkDisabled}
              extendDisabled={extendDisabled}
            />
          )}
          {onExit && (
            <button type="button" onClick={onExit} className="vsc-btn text-[10px] inline-flex items-center gap-1">
              <ExternalLink size={11} /> Close
            </button>
          )}
        </div>
      </div>
      <VsCodeWorkbench
        accent="#02A8EF"
        className="flex-1 min-h-0"
        sidebarMobile="horizontal"
        title="Packer Workspace"
        subtitle={scenario?.title || 'Image factory IDE'}
        activityBar={(
          <div className="vsc-activity-bar hidden sm:flex">
            <VscActivityButton active title="Explorer"><Files size={22} /></VscActivityButton>
            {canTerminal && (
              <VscActivityButton
                active={bottomTab === 'terminal'}
                onClick={() => { setBottomTab('terminal'); setShowTerminal(true) }}
                title="Terminal"
              >
                <Terminal size={22} />
              </VscActivityButton>
            )}
          </div>
        )}
        sidebarHeader={(
          <>
            <span className="flex items-center gap-1"><FolderOpen size={11} /> packer</span>
            <button
              type="button"
              onClick={() => {
                const name = window.prompt('New .pkr.hcl file:', 'custom.pkr.hcl')
                if (!name?.endsWith('.pkr.hcl') && !name?.endsWith('.pkrvars.hcl')) return
                const next = { ...filesRef.current, [name]: '# New Packer configuration\n' }
                filesRef.current = next
                setFiles(next)
                setActiveFile(name)
                setDirty(true)
              }}
              className="text-[var(--vsc-accent)]"
              title="New file"
            >
              <Plus size={12} />
            </button>
          </>
        )}
        sidebar={fileList.map((f) => (
          <div key={f} className="flex items-center gap-0.5 w-full group">
            <VscFileItem
              active={activeFile === f}
              onClick={() => setActiveFile(f)}
              className="flex-1 min-w-0"
            >
              <FileCode size={13} className="shrink-0 opacity-70" />
              <span className="truncate">{f}</span>
              {dirty && activeFile === f && <span className="ml-auto text-[10px] text-amber-400">●</span>}
            </VscFileItem>
            {!Object.keys(DEFAULT_FILES).includes(f) && (
              <button
                type="button"
                onClick={() => {
                  const next = { ...filesRef.current }
                  delete next[f]
                  filesRef.current = next
                  setFiles(next)
                  if (activeFile === f) setActiveFile(Object.keys(next)[0] || 'gpu-h100.pkr.hcl')
                }}
                className="opacity-0 group-hover:opacity-100 p-1 text-red-400 hover:text-red-300"
                title="Delete"
              >
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
            {['packer validate', 'packer fmt', `packer build ${mainFile}`].map((cmd) => (
              <button
                key={cmd}
                type="button"
                onClick={() => sendToTerminal(cmd.includes(mainFile) ? cmd : `${cmd} ${mainFile}`)}
                className="vsc-btn"
                title={terminalReady[terminalHost] ? `Run: ${cmd}` : 'Opens the terminal and runs once connected'}
              >
                <Terminal size={11} /> {cmd}
              </button>
            ))}
          </>
        )}
        editor={(
          <CodeEditor
            language="hcl"
            value={files[activeFile] || ''}
            onChange={(v) => {
              const next = { ...filesRef.current, [activeFile]: v }
              filesRef.current = next
              setFiles(next)
              setDirty(true)
            }}
          />
        )}
        bottomTabs={(
          <>
            <VscPanelTab active={bottomTab === 'output'} onClick={() => setBottomTab('output')}>Output</VscPanelTab>
            {canTerminal && (
              <VscPanelTab active={bottomTab === 'terminal'} onClick={() => { setBottomTab('terminal'); setShowTerminal(true) }}>
                Terminal
              </VscPanelTab>
            )}
          </>
        )}
        bottom={bottomContent()}
      />
    </div>
  )
}
