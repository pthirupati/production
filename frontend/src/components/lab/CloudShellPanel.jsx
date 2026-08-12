/**
 * Shared Cloud Shell drawer for Azure / GCP lab consoles.
 * Parses a small subset of az / gcloud commands and calls the tech API action.
 * Learner-facing label: Cloud Shell (never Simulation).
 */
import { useCallback, useRef, useState } from 'react'
import { X, Maximize2, Minimize2, Terminal } from 'lucide-react'

function parseAzureLine(line) {
  const parts = line.trim().split(/\s+/).filter(Boolean)
  if (!parts.length || parts[0] !== 'az') return null
  // az vm start --name X
  if (parts[1] === 'vm' && parts[2] === 'start') {
    const i = parts.indexOf('--name')
    return { action: 'start_vm', payload: { name: parts[i + 1] || parts[3] } }
  }
  if (parts[1] === 'vm' && parts[2] === 'stop') {
    const i = parts.indexOf('--name')
    return { action: 'stop_vm', payload: { name: parts[i + 1] || parts[3] } }
  }
  if (parts[1] === 'vm' && parts[2] === 'restart') {
    const i = parts.indexOf('--name')
    return { action: 'restart_vm', payload: { name: parts[i + 1] || parts[3] } }
  }
  if (parts[1] === 'vm' && parts[2] === 'resize') {
    const ni = parts.indexOf('--name')
    const si = parts.indexOf('--size')
    return { action: 'resize_vm', payload: { name: parts[ni + 1], size: parts[si + 1] } }
  }
  if (parts[1] === 'group' && parts[2] === 'create') {
    const i = parts.indexOf('--name')
    return { action: 'create_resource_group', payload: { name: parts[i + 1] } }
  }
  if (parts[1] === 'storage' && parts[2] === 'account' && parts[3] === 'create') {
    const i = parts.indexOf('--name')
    return { action: 'create_storage_account', payload: { name: parts[i + 1] } }
  }
  if (parts[1] === 'role' && parts[2] === 'assignment' && parts[3] === 'create') {
    const ai = parts.indexOf('--assignee')
    const ri = parts.indexOf('--role')
    return { action: 'assign_role', payload: { principal: parts[ai + 1], role: parts[ri + 1] } }
  }
  return { help: true }
}

function parseGcpLine(line) {
  const parts = line.trim().split(/\s+/).filter(Boolean)
  if (!parts.length || parts[0] !== 'gcloud') return null
  if (parts[1] === 'compute' && parts[2] === 'instances' && parts[3] === 'start') {
    return { action: 'start_instance', payload: { name: parts[4] } }
  }
  if (parts[1] === 'compute' && parts[2] === 'instances' && parts[3] === 'stop') {
    return { action: 'stop_instance', payload: { name: parts[4] } }
  }
  if (parts[1] === 'compute' && parts[2] === 'instances' && parts[3] === 'reset') {
    return { action: 'reset_instance', payload: { name: parts[4] } }
  }
  if (parts[1] === 'compute' && parts[2] === 'disks' && parts[3] === 'create') {
    return { action: 'create_disk', payload: { name: parts[4], size_gb: 100 } }
  }
  if (parts[1] === 'storage' && parts[2] === 'buckets' && parts[3] === 'create') {
    const name = (parts[4] || '').replace(/^gs:\/\//, '')
    return { action: 'create_bucket', payload: { name } }
  }
  if (parts[1] === 'projects' && parts[2] === 'add-iam-policy-binding') {
    const mi = parts.indexOf('--member')
    const ri = parts.indexOf('--role')
    return { action: 'add_iam_binding', payload: { member: parts[mi + 1], role: parts[ri + 1] } }
  }
  return { help: true }
}

const HELP = {
  azure: [
    'Azure Cloud Shell — supported commands:',
    '  az vm start --name <vm>',
    '  az vm stop --name <vm>',
    '  az vm restart --name <vm>',
    '  az vm resize --name <vm> --size Standard_B2s',
    '  az group create --name <rg>',
    '  az storage account create --name <name>',
    '  az role assignment create --assignee <user> --role Reader',
  ].join('\n'),
  gcp: [
    'Google Cloud Shell — supported commands:',
    '  gcloud compute instances start <name>',
    '  gcloud compute instances stop <name>',
    '  gcloud compute instances reset <name>',
    '  gcloud compute disks create <name>',
    '  gcloud storage buckets create gs://<name>',
    '  gcloud projects add-iam-policy-binding --member user:x@y.com --role roles/viewer',
  ].join('\n'),
}

export default function CloudShellPanel({
  provider = 'azure',
  accent = '#0078d4',
  onClose,
  onCommand,
  title,
}) {
  const [maximized, setMaximized] = useState(false)
  const [lines, setLines] = useState([HELP[provider] || ''])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const endRef = useRef(null)
  const height = maximized ? '70vh' : 280
  const prompt = provider === 'gcp' ? 'cloudshell:~$' : 'azureuser@cloudshell:~$'

  const append = useCallback((text) => {
    setLines((prev) => [...prev, text])
    setTimeout(() => endRef.current?.scrollIntoView({ behavior: 'smooth' }), 30)
  }, [])

  const runLine = async (e) => {
    e?.preventDefault()
    const line = input.trim()
    if (!line || busy) return
    setInput('')
    append(`${prompt} ${line}`)
    if (line === 'help' || line === 'clear') {
      if (line === 'clear') setLines([])
      else append(HELP[provider])
      return
    }
    const parsed = provider === 'gcp' ? parseGcpLine(line) : parseAzureLine(line)
    if (!parsed) {
      append(`bash: ${line.split(/\s+/)[0]}: command not found`)
      return
    }
    if (parsed.help) {
      append(HELP[provider])
      return
    }
    setBusy(true)
    try {
      const res = await onCommand?.(parsed.action, parsed.payload || {})
      if (res?.ok === false) append(`ERROR: ${res.error || 'command failed'}`)
      else append(res?.message || 'OK')
    } catch (err) {
      append(`ERROR: ${err?.message || 'request failed'}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      className="fixitlab-cloudshell"
      style={{
        height,
        display: 'flex',
        flexDirection: 'column',
        background: '#0c0c0c',
        borderTop: `2px solid ${accent}`,
        color: '#d4d4d4',
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
        fontSize: 12,
      }}
    >
      <div style={{
        height: 32, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 10px', borderBottom: '1px solid #222', background: '#141414',
      }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Terminal size={13} style={{ color: accent }} />
          <strong style={{ color: accent }}>{title || (provider === 'gcp' ? 'Cloud Shell' : 'Azure Cloud Shell')}</strong>
          <span style={{ opacity: 0.5 }}>/home/cloudshell</span>
        </span>
        <span style={{ display: 'flex', gap: 8 }}>
          <button type="button" onClick={() => setMaximized((m) => !m)} style={{ background: 'none', border: 0, color: '#aaa', cursor: 'pointer' }} aria-label={maximized ? 'Restore cloud shell' : 'Maximize cloud shell'}>
            {maximized ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
          </button>
          <button type="button" onClick={onClose} style={{ background: 'none', border: 0, color: '#aaa', cursor: 'pointer' }} aria-label="Close cloud shell">
            <X size={15} />
          </button>
        </span>
      </div>
      <div style={{ flex: 1, overflow: 'auto', padding: 10, whiteSpace: 'pre-wrap' }}>
        {lines.map((l, i) => <div key={`${i}-${l.slice(0, 12)}`}>{l}</div>)}
        <div ref={endRef} />
      </div>
      <form onSubmit={runLine} style={{ display: 'flex', gap: 8, padding: '6px 10px', borderTop: '1px solid #222' }}>
        <span style={{ color: accent, whiteSpace: 'nowrap' }}>{prompt}</span>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={busy}
          autoFocus
          spellCheck={false}
          style={{
            flex: 1, background: 'transparent', border: 0, outline: 'none', color: '#eaeaea',
            fontFamily: 'inherit', fontSize: 12,
          }}
          placeholder="Type a command — help for list"
        />
      </form>
    </div>
  )
}
