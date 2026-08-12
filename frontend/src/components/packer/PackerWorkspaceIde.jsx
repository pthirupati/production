import { useCallback, useEffect, useRef, useState } from 'react'
import toast from 'react-hot-toast'
import CodeEditor from '../ide/CodeEditor'
import IdeExplorer from '../ide/IdeExplorer'
import LabTerminal, { scheduleReadySend } from '../LabTerminal'
import VsCodeWorkbench, { VscEditorTab, VscPanelTab, VscActivityButton } from '../ide/VsCodeWorkbench'
import { LabChromeControls } from '../lab/LabChromeBar'
import { baremetalApi } from '../../api/baremetal'
import { packerApi } from '../../api/packer'
import PackerCiPipelinePanel from './PackerCiPipelinePanel'
import {
  FileCode, FolderOpen, Play, RefreshCw, Terminal, Files, ExternalLink, Upload,
  GitBranch, Workflow,
} from 'lucide-react'
import { parentDirs } from '../../utils/ide/fileTree'
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

  provisioner "file" {
    content = <<-EOF
      #cloud-config
      datasource:
        MAAS: {}
      package_update: true
      runcmd:
        - systemctl enable --now nvidia-persistenced
        - gpu-sanity || true
        - cloud-init status --wait
      final_message: "ImageDev GPU image cloud-init finished in $UPTIME seconds"
    EOF
    destination = "/tmp/gpu-cloud-init.cfg"
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

function bootResourceForSku(sku) {
  if (sku === 'rhel-gpu' || sku === 'rhel') return 'custom/rhel-gpu'
  return `custom/${sku}-jammy`
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
  const [expandedDirs, setExpandedDirs] = useState(() => new Set())
  const [bottomTab, setBottomTab] = useState('output')
  const [output, setOutput] = useState('')
  const [dirty, setDirty] = useState(false)
  const [showTerminal, setShowTerminal] = useState(true)
  const [terminalReady, setTerminalReady] = useState({})
  const [buildSucceeded, setBuildSucceeded] = useState(false)
  const [artifactReady, setArtifactReady] = useState(false)
  const [suggestPublish, setSuggestPublish] = useState(false)
  const [bootResourceName, setBootResourceName] = useState('custom/h100-jammy')
  const [showCiPanel, setShowCiPanel] = useState(true)
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

  const detectSku = useCallback(() => {
    const blob = `${activeFile}\n${Object.keys(files).join('\n')}\n${files[activeFile] || ''}\n${scenario?.slug || ''}`.toLowerCase()
    if (blob.includes('rhel')) return 'rhel-gpu'
    for (const key of ['b300', 'h200', 'h100', 'a100', 'mi300']) {
      if (blob.includes(key)) return key
    }
    return 'h100'
  }, [files, activeFile, scenario?.slug])

  const sku = detectSku()
  const mainFile = Object.keys(files).find((f) => f.endsWith('.pkr.hcl') && !f.startsWith('variables')) || 'gpu-h100.pkr.hcl'

  useEffect(() => {
    setBootResourceName(bootResourceForSku(sku))
  }, [sku])

  // Ensure baremetal session is signed in so factory actions work.
  useEffect(() => {
    if (!sessionId) return undefined
    let cancelled = false
    ;(async () => {
      try {
        await baremetalApi.getState(sessionId, scenario?.slug || '')
        await baremetalApi.login(sessionId)
        if (!cancelled) {
          const st = await packerApi.getFactoryState(sessionId)
          if (st?.build_succeeded) setBuildSucceeded(true)
          if (st?.artifact_ready) {
            setArtifactReady(true)
            setSuggestPublish(true)
          }
          if (st?.suggested_boot_resource) setBootResourceName(st.suggested_boot_resource)
        }
      } catch { /* companion may not be ready */ }
    })()
    return () => { cancelled = true }
  }, [sessionId, scenario?.slug])

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

  const noteBuildSuccess = useCallback(async () => {
    setBuildSucceeded(true)
    setOutput((prev) => `${prev ? `${prev}\n` : ''}Packer build succeeded — Image Factory pipeline is available.`)
    toast.success('Build artifact ready — run Image Factory pipeline', { duration: 2500 })
    setBottomTab('ci')
    setShowCiPanel(true)
    if (sessionId) {
      try {
        await packerApi.markBuild(sessionId, { sku: detectSku(), success: true })
      } catch { /* ignore */ }
    }
  }, [sessionId, detectSku])

  const sendToTerminal = useCallback((cmd) => {
    const line = cmd.trim()
    if (!line) return
    setBottomTab('terminal')
    setShowTerminal(true)
    setOutput((prev) => `${prev ? `${prev}\n` : ''}$ ${line}`)
    const isBuild = /\bpacker\s+build\b/.test(line)
    if (terminalRef.current?.sendCommand(line)) {
      toast.success(`Terminal: ${line.split(/\s+/)[0]}`, { duration: 1200 })
      if (isBuild) {
        // Lab shell streams build success; enable pipeline after typical stream window.
        window.setTimeout(() => { noteBuildSuccess() }, 3200)
      }
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
        if (isBuild) window.setTimeout(() => { noteBuildSuccess() }, 3200)
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
  }, [noteBuildSuccess])

  const canTerminal = terminalSession?.status === 'RUNNING'
  const fileList = Object.keys(files)
  const dirtyPaths = dirty ? new Set([activeFile]) : new Set()

  const toggleDir = useCallback((path) => {
    setExpandedDirs((prev) => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }, [])

  const createFileAt = useCallback((rawPath) => {
    let name = String(rawPath || '').trim().replace(/^\/+/, '')
    if (!name) return
    if (!name.includes('.')) name = `${name}.pkr.hcl`
    if (filesRef.current[name] !== undefined) {
      toast.error('File already exists')
      return
    }
    const next = { ...filesRef.current, [name]: '# New Packer configuration\n\n' }
    filesRef.current = next
    setFiles(next)
    setActiveFile(name)
    setDirty(true)
    setExpandedDirs((prev) => {
      const n = new Set(prev)
      parentDirs(name).forEach((d) => n.add(d))
      return n
    })
    toast.success(`Created ${name}`)
  }, [])

  const createFolderAt = useCallback((rawDir) => {
    const dir = String(rawDir || '').trim().replace(/^\/+|\/+$/g, '')
    if (!dir) return
    const keep = `${dir}/.keep`
    if (filesRef.current[keep] !== undefined) return
    const next = { ...filesRef.current, [keep]: '' }
    filesRef.current = next
    setFiles(next)
    setDirty(true)
    setExpandedDirs((prev) => new Set([...prev, dir, ...parentDirs(keep)]))
    toast.success(`Created folder ${dir}/`)
  }, [])

  const deletePackerFile = useCallback((f) => {
    if (Object.keys(DEFAULT_FILES).includes(f)) {
      toast.error('Cannot delete starter templates')
      return
    }
    const next = { ...filesRef.current }
    delete next[f]
    filesRef.current = next
    setFiles(next)
    setDirty(true)
    if (activeFile === f) setActiveFile(Object.keys(next).find((p) => !p.endsWith('/.keep')) || 'gpu-h100.pkr.hcl')
  }, [activeFile])

  const renamePackerFile = useCallback((path) => {
    if (Object.keys(DEFAULT_FILES).includes(path)) {
      toast.error('Cannot rename starter templates')
      return
    }
    const input = window.prompt('Rename file', path)
    if (!input) return
    const nextName = input.trim().replace(/^\/+/, '')
    if (!nextName || nextName === path) return
    if (filesRef.current[nextName] !== undefined) {
      toast.error('File already exists')
      return
    }
    const next = { ...filesRef.current }
    next[nextName] = next[path]
    delete next[path]
    filesRef.current = next
    setFiles(next)
    setActiveFile(nextName)
    setDirty(true)
  }, [])

  const syncFilesToShell = useCallback(() => {
    const entries = Object.entries(filesRef.current || {})
    if (!entries.length) return
    const script = entries.map(([name, content]) => {
      const body = String(content ?? '').replace(/\r\n/g, '\n')
      return `cat > ${name} <<'FIXITLAB_EOF'\n${body}\nFIXITLAB_EOF`
    }).join('\n')
    sendToTerminal(script)
    setOutput((prev) => `${prev ? `${prev}\n` : ''}Synced ${entries.length} file(s) to lab workspace.`)
  }, [sendToTerminal])

  const openCompanion = useCallback((kind, label) => {
    try {
      window.dispatchEvent(new CustomEvent('fixitlab:open-companion', { detail: { kind } }))
      toast.success(`Opening ${label}`, { duration: 1500 })
    } catch {
      toast.error(`Could not open ${label}`)
    }
  }, [])

  const openMaasImages = useCallback(() => {
    openCompanion('baremetal', 'MAAS Images')
  }, [openCompanion])

  const publishToMaas = useCallback(async () => {
    const currentSku = detectSku()
    const bootResource = bootResourceForSku(currentSku)
    try {
      const res = await baremetalApi.publishBootResource(sessionId, {
        sku: currentSku,
        name: bootResource,
        source: `packer output-gpu-${currentSku}/`,
      })
      const name = res?.boot_resource?.name || bootResource
      setBootResourceName(name)
      setArtifactReady(true)
      setSuggestPublish(false)
      setOutput((prev) => `${prev ? `${prev}\n` : ''}Published ${name} → MAAS Images (boot-resources). Open MAAS → Images to deploy.`)
      toast.success(`Published ${name} to MAAS`)
      openMaasImages()
    } catch (err) {
      toast.error(err?.response?.data?.error || err?.message || 'MAAS publish failed')
    }
  }, [detectSku, sessionId, openMaasImages])

  /** Publish then Deploy the first Ready machine with this custom boot resource. */
  const publishAndDeploy = useCallback(async () => {
    const currentSku = detectSku()
    const bootResource = bootResourceForSku(currentSku)
    try {
      await baremetalApi.login(sessionId)
      const pub = await baremetalApi.publishBootResource(sessionId, {
        sku: currentSku,
        name: bootResource,
        source: `packer output-gpu-${currentSku}/`,
      })
      const name = pub?.boot_resource?.name || bootResource
      setBootResourceName(name)
      setArtifactReady(true)
      setSuggestPublish(false)
      const st = await baremetalApi.getState(sessionId)
      const machines = st?.state?.maas?.machines || []
      const ready = machines.find((m) => m.status === 'Ready') || machines.find((m) => m.status === 'Allocated')
      if (!ready) {
        setOutput((prev) => `${prev ? `${prev}\n` : ''}Published ${name}. No Ready machine — open MAAS and Commission a node, then Deploy with ${name}.`)
        toast.success(`Published ${name} — Commission a node before Deploy`)
        openMaasImages()
        return
      }
      const dep = await baremetalApi.deploy(sessionId, ready.id, { boot_resource: name })
      if (dep?.ok === false) {
        toast.error(dep.error || 'Deploy failed')
        openMaasImages()
        return
      }
      setOutput((prev) => `${prev ? `${prev}\n` : ''}Published ${name} and started Deploy on ${ready.hostname || ready.id} with that image.`)
      toast.success(`Deploying ${ready.hostname || 'node'} with ${name}`)
      openMaasImages()
    } catch (err) {
      toast.error(err?.response?.data?.error || err?.message || 'Publish/Deploy failed')
    }
  }, [detectSku, sessionId, openMaasImages])

  const onFactoryUpdate = useCallback((st) => {
    if (st?.artifact_ready) {
      setArtifactReady(true)
      setSuggestPublish(true)
    }
    if (st?.suggested_boot_resource) setBootResourceName(st.suggested_boot_resource)
    if (st?.build_succeeded) setBuildSucceeded(true)
  }, [])

  const bottomContent = () => {
    if (bottomTab === 'ci') {
      return (
        <PackerCiPipelinePanel
          sessionId={sessionId}
          sku={sku}
          files={files}
          buildSucceeded={buildSucceeded}
          onFactoryUpdate={onFactoryUpdate}
          onPublishSuggest={(name) => {
            if (name) setBootResourceName(name)
            setSuggestPublish(true)
            setArtifactReady(true)
            toast.success(`Artifact ready — publish ${name || bootResourceName}`, { duration: 2200 })
          }}
        />
      )
    }
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
            onClick={() => {
              syncFilesToShell()
              sendToTerminal(`packer build ${mainFile}`)
            }}
            className="vsc-btn vsc-btn-primary"
            style={{ background: '#02A8EF', borderColor: '#02A8EF' }}
          >
            <Play size={11} /> packer build
          </button>
          <button
            type="button"
            disabled={!buildSucceeded}
            onClick={() => { setBottomTab('ci'); setShowCiPanel(true) }}
            className="vsc-btn disabled:opacity-40"
            title={buildSucceeded ? 'Open Image Factory CI pipeline' : 'Complete packer build first'}
          >
            <Workflow size={11} /> Run Image Factory pipeline
          </button>
          <button
            type="button"
            onClick={() => { syncFilesToShell(); publishToMaas() }}
            className={`vsc-btn inline-flex items-center gap-1 ${suggestPublish || artifactReady ? 'vsc-btn-primary' : ''}`}
            style={suggestPublish || artifactReady ? { background: '#02A8EF', borderColor: '#02A8EF' } : undefined}
            title={`Register Packer artifact as ${bootResourceName}`}
          >
            <Upload size={11} /> {suggestPublish ? 'Publish to MAAS (suggested)' : 'Publish to MAAS'}
          </button>
          <button type="button" onClick={openMaasImages} className="vsc-btn" title="Open MAAS Images">
            <ExternalLink size={11} /> Open MAAS Images
          </button>
          <button
            type="button"
            onClick={publishAndDeploy}
            className="vsc-btn inline-flex items-center gap-1"
            style={artifactReady ? { background: '#0e8420', borderColor: '#0e8420', color: '#fff' } : undefined}
            title={`Publish ${bootResourceName} then Deploy a Ready node with that image`}
          >
            <Upload size={11} /> Publish + Deploy in MAAS
          </button>
          <button type="button" onClick={syncFilesToShell} className="vsc-btn" title="Write IDE files into the lab shell">
            Sync files
          </button>
          <button
            type="button"
            onClick={() => {
              setFiles({ ...DEFAULT_FILES })
              setActiveFile('gpu-h100.pkr.hcl')
              setDirty(false)
              setBuildSucceeded(false)
              setArtifactReady(false)
              setSuggestPublish(false)
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
        <div className="text-[10px] text-[var(--vsc-muted)] shrink-0 flex flex-wrap gap-x-3 gap-y-0.5">
          <span>MAAS boot resource: <span className="text-[#02A8EF] font-mono">{bootResourceName}</span></span>
          {buildSucceeded && <span className="text-emerald-400">Build OK — pipeline enabled</span>}
          {artifactReady && <span className="text-emerald-400">Artifact ready to publish</span>}
        </div>
        <pre className="text-xs whitespace-pre-wrap break-words flex-1 overflow-auto font-mono leading-relaxed text-[var(--vsc-text)]">
          {output || 'Edit the Packer template, then validate and build. Successful builds pass the CVE gate and publish to MAAS boot-resources.'}
        </pre>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-[80] flex flex-col bg-[var(--vsc-bg,#1e1e1e)]">
      <div className="flex items-center gap-2 px-3 py-1.5 border-b border-[var(--vsc-border,#333)] shrink-0">
        <span className="text-xs font-semibold text-[#02A8EF]">Packer Image Factory</span>
        <span className="text-[10px] text-[var(--vsc-muted)] truncate">{scenario?.title || scenario?.slug || 'GPU image build'}</span>
        <span className="text-[10px] font-mono text-[#02A8EF]/opacity-80 hidden sm:inline">{bootResourceName}</span>
        <div className="ml-auto flex items-center gap-1.5 flex-wrap justify-end">
          <button type="button" onClick={openMaasImages} className="vsc-btn text-[10px] inline-flex items-center gap-1" title="Open MAAS">
            <ExternalLink size={11} /> MAAS
          </button>
          <button type="button" onClick={() => openCompanion('awx', 'AWX')} className="vsc-btn text-[10px] inline-flex items-center gap-1" title="Open AWX">
            <ExternalLink size={11} /> AWX
          </button>
          <button type="button" onClick={() => openCompanion('lxd', 'LXD')} className="vsc-btn text-[10px] inline-flex items-center gap-1" title="Open LXD">
            <ExternalLink size={11} /> LXD
          </button>
          <button type="button" onClick={() => openCompanion('vyos', 'VyOS')} className="vsc-btn text-[10px] inline-flex items-center gap-1" title="Open VyOS">
            <ExternalLink size={11} /> VyOS
          </button>
          <button type="button" onClick={() => openCompanion('datacenter', 'Datacenter')} className="vsc-btn text-[10px] inline-flex items-center gap-1" title="Open Datacenter">
            <ExternalLink size={11} /> Datacenter
          </button>
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
            <VscActivityButton active={!showCiPanel || bottomTab !== 'ci'} title="Explorer"><Files size={22} /></VscActivityButton>
            <VscActivityButton
              active={bottomTab === 'ci'}
              onClick={() => { setBottomTab('ci'); setShowCiPanel(true) }}
              title="Image Factory CI"
            >
              <GitBranch size={22} />
            </VscActivityButton>
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
          </>
        )}
        sidebar={(
          <IdeExplorer
            files={files}
            activePath={activeFile}
            dirtyPaths={dirtyPaths}
            expandedDirs={expandedDirs}
            language="hcl"
            onToggleDir={toggleDir}
            onOpenFile={setActiveFile}
            onDeleteFile={deletePackerFile}
            onRenameFile={renamePackerFile}
            onCreateFileAt={createFileAt}
            onCreateFolderAt={createFolderAt}
            protectedPaths={new Set(Object.keys(DEFAULT_FILES))}
            emptyHint="No Packer files — create a .pkr.hcl template to begin."
          />
        )}
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
            <button
              type="button"
              disabled={!buildSucceeded}
              onClick={() => { setBottomTab('ci'); setShowCiPanel(true) }}
              className="vsc-btn disabled:opacity-40"
              title="Image Factory CI"
            >
              <Workflow size={11} /> Pipeline
            </button>
            <button type="button" onClick={openMaasImages} className="vsc-btn" title="Open MAAS Images">
              <ExternalLink size={11} /> MAAS Images
            </button>
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
        bottomPanel={{
          height: bottomTab === 'ci' ? 300 : 240,
          tabs: (
            <>
              <VscPanelTab active={bottomTab === 'output'} onClick={() => setBottomTab('output')}>Output</VscPanelTab>
              <VscPanelTab active={bottomTab === 'ci'} onClick={() => { setBottomTab('ci'); setShowCiPanel(true) }}>
                <GitBranch size={11} /> CI Pipeline
              </VscPanelTab>
              {canTerminal && (
                <VscPanelTab active={bottomTab === 'terminal'} onClick={() => { setBottomTab('terminal'); setShowTerminal(true) }}>
                  Terminal
                </VscPanelTab>
              )}
            </>
          ),
          content: bottomContent(),
        }}
        statusBar={{
          left: activeFile,
          center: `Packer · ${sku.toUpperCase()} · ${bootResourceName}`,
          right: (
            <>
              {dirty ? <span>Modified</span> : <span>Saved</span>}
              {buildSucceeded && <span className="text-emerald-400">Build OK</span>}
              {artifactReady && <span className="text-[#02A8EF]">Artifact ready</span>}
            </>
          ),
        }}
      />
    </div>
  )
}
