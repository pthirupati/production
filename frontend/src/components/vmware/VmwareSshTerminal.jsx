import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createLinuxShell } from './linuxShell'
import { ViNanoEditor } from './VmwareConsole'

/**
 * Interactive SSH terminal. The SSH button opens this; it logs into the guest
 * (root / root13) over a simulated SSH session and runs the SAME shell as the
 * web console — including vi/nano editing, yum/apt y/N prompts, and reboot
 * (which closes the session like a real `ssh` does when the host reboots).
 */
export default function VmwareSshTerminal({ vm, sshOk = true, onClose }) {
  const shell = useMemo(() => createLinuxShell(vm), [vm?.id, vm?.hostname, vm?.ip, vm?.disk_gb, vm?.memory_mb, vm?.cpu])
  const ip = vm?.ip || vm?.hostname || vm?.name || 'guest'
  const [lines, setLines] = useState([
    `$ ssh root@${ip}`,
    sshOk
      ? `The authenticity of host '${ip}' can't be established.`
      : `ssh: connect to host ${ip} port 22: Connection timed out`,
    ...(sshOk ? [
      `ED25519 key fingerprint is SHA256:Hk7Q9f2mF3sZ1vY8nQwErTyUiOpAsDfGhJkLzXcVbNm.`,
      `Warning: Permanently added '${ip}' (ED25519) to the list of known hosts.`,
      `root@${ip}'s password:`,
    ] : []),
  ])
  const [phase, setPhase] = useState(sshOk ? 'password' : 'failed') // password | shell | editor | closed
  const [password, setPassword] = useState('')
  const [cmd, setCmd] = useState('')
  const [histIdx, setHistIdx] = useState(-1)
  const [editor, setEditor] = useState(null)
  const [confirm, setConfirm] = useState(null)
  const [confirmInput, setConfirmInput] = useState('')
  const [busy, setBusy] = useState(false)

  const inputRef = useRef(null)
  const scrollRef = useRef(null)
  const timersRef = useRef([])

  const clearTimers = useCallback(() => { timersRef.current.forEach(clearTimeout); timersRef.current = [] }, [])
  const later = useCallback((fn, ms) => { const id = setTimeout(fn, ms); timersRef.current.push(id); return id }, [])
  useEffect(() => () => clearTimers(), [clearTimers])

  const append = useCallback((text) => {
    setLines(prev => [...prev, ...(Array.isArray(text) ? text : [text])])
  }, [])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight })
  }, [lines, phase, confirm])

  useEffect(() => {
    if (!editor && (phase === 'shell' || phase === 'password')) inputRef.current?.focus()
  }, [phase, editor, confirm, busy])

  const streamChunks = useCallback((chunks, doneLines) => {
    setBusy(true)
    let acc = 0
    chunks.forEach((chunk) => { acc += 360; later(() => append(chunk), acc) })
    later(() => { if (doneLines?.length) append(doneLines); setBusy(false) }, acc + 280)
  }, [append, later])

  const finishEditor = useCallback((save, content) => {
    if (editor) {
      if (save) {
        shell.saveFile(editor.path || '/root/scratch.txt', content ?? editor.content)
        append(editor.tool === 'nano'
          ? `[ Wrote ${(content ?? '').split('\n').length} lines ]`
          : `"${editor.path || 'scratch.txt'}" written`)
      }
    }
    setEditor(null)
    later(() => inputRef.current?.focus(), 0)
  }, [append, editor, later, shell])

  const resolveConfirm = useCallback((answerRaw) => {
    const c = confirm
    if (!c) return
    const answer = (answerRaw || '').trim().toLowerCase()
    const yes = answer === '' ? c.defaultYes : (answer === 'y' || answer === 'yes')
    append(`${c.promptText}${answerRaw}`)
    setConfirm(null)
    setConfirmInput('')
    if (yes) streamChunks(c.onYesStream.chunks, c.onYesStream.doneLines)
    else append(c.onNoLines)
  }, [append, confirm, streamChunks])

  const handleResult = useCallback((result) => {
    if (!result) return
    if (result.clear) { setLines([]); return }
    if (result.exit) { append('logout'); append(`Connection to ${ip} closed.`); setPhase('closed'); return }
    if (result.editor) { setEditor(result.editor); return }
    if (result.reboot || result.poweroff) {
      append(result.lines)
      append(`Connection to ${ip} closed by remote host.`)
      append(`Connection to ${ip} closed.`)
      setPhase('closed')
      return
    }
    if (result.confirm) { append(result.lines); setConfirm(result.confirm); setConfirmInput(''); return }
    if (result.stream) { append(result.lines); streamChunks(result.stream.chunks, result.stream.doneLines); return }
    append(result.lines)
  }, [append, ip, streamChunks])

  const onKeyDown = (e) => {
    if (phase === 'failed' || phase === 'closed') return
    if (phase === 'password') {
      if (e.key === 'Enter') {
        e.preventDefault()
        if (password === 'root13') {
          append(['', `Last login: ${new Date().toUTCString()} from 10.20.30.1`, `Welcome to ${vm?.guest_os_version || 'Linux'} (SSH session).`, ''])
          setPhase('shell')
          setPassword('')
        } else {
          append('Permission denied, please try again.')
          setPassword('')
        }
      }
      return
    }
    if (busy) { e.preventDefault(); return }
    if (confirm) {
      if (e.key === 'Enter') { e.preventDefault(); resolveConfirm(confirmInput) }
      return
    }
    if (e.key === 'Enter') {
      e.preventDefault()
      append(`${shell.prompt()} ${cmd}`)
      handleResult(shell.run(cmd))
      setCmd('')
      setHistIdx(-1)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      const h = shell.history
      if (!h.length) return
      const next = histIdx < 0 ? h.length - 1 : Math.max(0, histIdx - 1)
      setHistIdx(next)
      setCmd(h[next])
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      if (histIdx < 0) return
      const next = histIdx + 1
      if (next >= shell.history.length) { setHistIdx(-1); setCmd('') }
      else { setHistIdx(next); setCmd(shell.history[next]) }
    }
  }

  return (
    <div className="relative rounded-lg border border-[#2d3a4a] bg-[#05090f] font-mono text-[11px] leading-relaxed min-h-[280px] flex flex-col">
      <div className="flex items-center justify-between px-3 py-2 border-b border-[#2d3a4a] bg-[#1b2a3b]">
        <span className="text-[#8fa5b8]">SSH — root@{vm?.hostname || vm?.name} ({ip})</span>
        {onClose && <button type="button" onClick={onClose} className="text-[#8fa5b8] hover:text-white text-xs px-1.5 py-0.5 rounded hover:bg-[#2d3a4a]">Close</button>}
      </div>
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 max-h-[420px]" onClick={() => !editor && inputRef.current?.focus()}>
        {lines.map((l, i) => (
          <div key={i} className={l.startsWith('$') || l.includes('password') || l.startsWith('[  OK  ]') ? 'text-[#5DB85D]' : l.startsWith('[') ? 'text-[#8fa5b8]' : 'text-[#E8EDF2]'}>{l || ' '}</div>
        ))}

        {phase === 'password' && (
          <div className="flex items-center gap-1 text-[#5DB85D] mt-1">
            <span>Password:</span>
            <input ref={inputRef} autoFocus type="password" value={password} onChange={e => setPassword(e.target.value)} onKeyDown={onKeyDown} className="flex-1 bg-transparent border-none outline-none text-[#E8EDF2] font-mono" />
          </div>
        )}

        {phase === 'shell' && confirm && !busy && (
          <div className="flex items-center mt-1 text-[#E8EDF2]">
            <span className="whitespace-nowrap">{confirm.promptText}</span>
            <input ref={inputRef} autoFocus value={confirmInput} onChange={e => setConfirmInput(e.target.value)} onKeyDown={onKeyDown} maxLength={3} spellCheck={false} className="w-16 bg-transparent border-none outline-none text-[#E8EDF2] font-mono caret-[#5DB85D] ml-1" />
          </div>
        )}

        {phase === 'shell' && !editor && !confirm && !busy && (
          <div className="flex items-center mt-1">
            <span className="text-[#5DB85D]">{shell.prompt()}</span>
            <input ref={inputRef} autoFocus value={cmd} onChange={e => setCmd(e.target.value)} onKeyDown={onKeyDown} className="flex-1 bg-transparent border-none outline-none text-[#E8EDF2] font-mono ml-1" spellCheck={false} autoComplete="off" />
          </div>
        )}

        {busy && phase === 'shell' && <div className="text-[#8fa5b8] animate-pulse mt-1">…</div>}

        {phase === 'closed' && (
          <p className="text-[#8fa5b8] mt-2 text-[10px]">Session closed. Re-open the SSH panel to reconnect.</p>
        )}
        {phase === 'failed' && (
          <p className="text-[#8fa5b8] mt-2 text-[10px]">Guest may be hung or network misconfigured. Use web console and verify IP/VLAN assignment.</p>
        )}
      </div>

      {editor && (
        <ViNanoEditor
          tool={editor.tool}
          path={editor.path}
          initialContent={editor.content}
          onFinish={finishEditor}
        />
      )}

      <div className="px-3 py-1.5 border-t border-[#2d3a4a] text-[10px] text-[#8fa5b8]">
        {editor ? (editor.tool === 'nano' ? 'nano — ^O save · ^X exit · ^C cancel' : 'vi — i insert · Esc normal · :wq save · :q! quit') : 'Hint: password root13 · same shell as the console'}
      </div>
    </div>
  )
}
