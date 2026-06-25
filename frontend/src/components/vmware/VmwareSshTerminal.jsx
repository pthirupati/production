import { useCallback, useEffect, useRef, useState } from 'react'
import { LinuxTerminalTabs, LinuxTerminalStatusBar } from '../linux/LinuxTerminalChrome'
import { useLinuxTerminalTabs } from '../linux/useLinuxTerminalTabs'
import { ViNanoEditor } from './VmwareConsole'

/**
 * Interactive SSH terminal. The SSH button opens this; it logs into the guest
 * (root / root13) over a simulated SSH session and runs the SAME shell as the
 * web console — including vi/nano editing, yum/apt y/N prompts, and reboot
 * (which closes the session like a real `ssh` does when the host reboots).
 *
 * It renders as a full console-style window (matching VmwareConsole): a modal
 * overlay that can be minimized to a taskbar pill or maximized to fill the
 * viewport — not a cramped inline box.
 */
export default function VmwareSshTerminal({ vm, sshOk = true, onClose }) {
  const linuxTabs = useLinuxTerminalTabs(vm, { enabled: true })
  const shell = linuxTabs.activeShell || linuxTabs.getShell(linuxTabs.activeId)
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
  const [loginUser, setLoginUser] = useState('root')
  const [password, setPassword] = useState('')
  const [cmd, setCmd] = useState('')
  const [histIdx, setHistIdx] = useState(-1)
  const [editor, setEditor] = useState(null)
  const [confirm, setConfirm] = useState(null)
  const [confirmInput, setConfirmInput] = useState('')
  const [busy, setBusy] = useState(false)
  // Window chrome: a full console-style terminal that can be minimized to a
  // taskbar pill or maximized to (nearly) fill the viewport — same UX as the VM
  // web console, not a tiny inline box.
  const [minimized, setMinimized] = useState(false)
  const [maximized, setMaximized] = useState(false)

  const inputRef = useRef(null)
  const scrollRef = useRef(null)
  const timersRef = useRef([])
  const prevTabRef = useRef(null)

  useEffect(() => {
    if (phase !== 'shell' || !linuxTabs.activeId) return
    const prev = prevTabRef.current
    if (prev && prev !== linuxTabs.activeId) {
      linuxTabs.persistTabUi(prev, { lines, cmd, histIdx })
      const loaded = linuxTabs.getTabUi(linuxTabs.activeId)
      if (loaded) {
        setLines(loaded.lines)
        setCmd(loaded.cmd)
        setHistIdx(loaded.histIdx)
      } else {
        const idx = Math.max(0, linuxTabs.tabs.findIndex((t) => t.id === linuxTabs.activeId))
        const seed = [`Last login: ${new Date().toUTCString()} on pts/${idx}`, '']
        linuxTabs.persistTabUi(linuxTabs.activeId, { lines: seed, cmd: '', histIdx: -1 })
        setLines(seed)
        setCmd('')
        setHistIdx(-1)
      }
    } else if (!prev) {
      linuxTabs.persistTabUi(linuxTabs.activeId, { lines, cmd, histIdx })
    }
    prevTabRef.current = linuxTabs.activeId
  }, [linuxTabs.activeId, phase]) // eslint-disable-line react-hooks/exhaustive-deps

  const clearTimers = useCallback(() => { timersRef.current.forEach(clearTimeout); timersRef.current = [] }, [])
  const later = useCallback((fn, ms) => { const id = setTimeout(fn, ms); timersRef.current.push(id); return id }, [])
  useEffect(() => () => clearTimers(), [clearTimers])

  const append = useCallback((text) => {
    setLines(prev => [...prev, ...(Array.isArray(text) ? text : [text])])
  }, [])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight })
  }, [lines, phase, confirm, minimized, maximized])

  useEffect(() => {
    if (!minimized && !editor && (phase === 'shell' || phase === 'password')) inputRef.current?.focus()
  }, [phase, editor, confirm, busy, minimized])

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
    if (yes) { c.onYesStream.commit?.(); streamChunks(c.onYesStream.chunks, c.onYesStream.doneLines) }
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
    if (result.stream) {
      append(result.lines)
      // Commit the package transaction now (implied by -y) so a later rpm -q /
      // dnf list installed reflects the install/removal.
      result.stream.commit?.()
      streamChunks(result.stream.chunks, result.stream.doneLines)
      return
    }
    append(result.lines)
  }, [append, ip, streamChunks])

  const onKeyDown = (e) => {
    // Own the keyboard while focused (esp. Escape) so the simulator's document
    // listener doesn't close this terminal mid-session.
    e.stopPropagation()
    if (phase === 'failed' || phase === 'closed') return
    if (phase === 'password') {
      if (e.key === 'Enter') {
        e.preventDefault()
        const okRoot = loginUser === 'root' && password === 'root13'
        const okLab = loginUser === 'labuser' && password === 'labuser@123'
        if (okRoot || okLab) {
          if (okLab) shell?.switchUser?.('labuser')
          const welcome = ['', `Last login: ${new Date().toUTCString()} from 10.20.30.1`, `Welcome to ${vm?.guest_os_version || 'Linux'} (SSH session).`, '']
          append(welcome)
          if (linuxTabs.activeId) {
            linuxTabs.persistTabUi(linuxTabs.activeId, { lines: [...lines, ...welcome], cmd: '', histIdx: -1 })
          }
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
      const raw = cmd
      append(`${shell.prompt()} ${cmd}`)
      const result = shell.run(cmd)
      if (result?.editor && linuxTabs.activeId) {
        const tool = result.editor.tool === 'nano' ? 'nano' : 'vim'
        linuxTabs.renameTab(linuxTabs.activeId, tool)
      }
      if (raw.trim().startsWith('htop') && linuxTabs.activeId) {
        linuxTabs.renameTab(linuxTabs.activeId, 'htop')
      }
      handleResult(result)
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

  // Minimized -> a small taskbar pill at the bottom of the screen (like a window
  // you've collapsed); click to restore. Lives in a fixed overlay so it is not
  // clipped by the SSH drawer that mounts it.
  if (minimized) {
    return (
      <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[120]">
        <button
          type="button"
          onClick={() => setMinimized(false)}
          className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-[#1b2a3b] border border-[#2d3a4a] shadow-xl text-[#8fa5b8] hover:text-white font-mono text-xs"
        >
          <span className="text-[#5DB85D]">{'▣'}</span>
          SSH - root@{vm?.hostname || vm?.name}
          <span className="text-[10px] text-[#5b9bf5]">(restore)</span>
        </button>
      </div>
    )
  }

  const footerHint = editor
    ? (editor.tool === 'nano' ? 'nano - ^O save / ^X exit / ^C cancel' : 'vi - i/a/o insert / Esc command mode / :wq save / :q! quit')
    : confirm ? 'Type y to proceed or n to abort, then Enter'
    : phase === 'password' ? 'Hint: root/root13 or labuser/labuser@123'
    : phase === 'shell' ? 'Connected over SSH / same shell as the console / vi & nano edit & save / arrow keys for history'
    : phase === 'closed' ? 'Session closed - close this window or reconnect from the SSH panel'
    : phase === 'failed' ? 'Connection failed - verify the guest is up and the IP/VLAN is correct'
    : 'Establishing SSH session...'

  // Same full-screen modal chrome as the VM web console.
  const shellSize = maximized
    ? 'w-[98vw] h-[94vh] max-w-none'
    : 'w-full max-w-[900px] h-[580px] max-h-[90vh]'

  return (
    <div className="vm-modal-overlay" onMouseDown={e => e.target === e.currentTarget && onClose?.()}>
      <div
        className={`vm-modal relative ${shellSize} flex flex-col p-0 overflow-hidden`}
        onMouseDown={e => e.stopPropagation()}
      >
        <div className="flex items-center gap-2.5 px-3.5 py-2.5 bg-[#1B2A3B] border-b border-[#2D3A4A] shrink-0">
          <div className="flex gap-1.5">
            <span className="w-[11px] h-[11px] rounded-full bg-[#D9534F]" />
            <span className="w-[11px] h-[11px] rounded-full bg-[#F5A623]" />
            <span className="w-[11px] h-[11px] rounded-full bg-[#5DB85D]" />
          </div>
          <span className="font-mono text-xs text-[#8FA5B8]">SSH - root@{vm?.hostname || vm?.name} ({ip})</span>
          <span className="text-[10px] text-[#8FA5B8] ml-2 hidden sm:inline">Hint: root/root13 or labuser/labuser@123</span>
          <div className="flex-1" />
          <button
            type="button"
            onClick={() => setMinimized(true)}
            title="Minimize"
            aria-label="Minimize SSH window"
            className="flex items-center justify-center w-7 h-6 rounded text-[#8FA5B8] hover:text-white hover:bg-[#2D3A4A] text-sm leading-none"
          >
            {'–'}
          </button>
          <button
            type="button"
            onClick={() => setMaximized(m => !m)}
            title={maximized ? 'Restore' : 'Maximize'}
            aria-label={maximized ? 'Restore SSH window' : 'Maximize SSH window'}
            className="flex items-center justify-center w-7 h-6 rounded text-[#8FA5B8] hover:text-white hover:bg-[#2D3A4A] text-[11px] leading-none"
          >
            {maximized ? '❐' : '▢'}
          </button>
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              title="Close SSH window"
              aria-label="Close SSH window"
              className="flex items-center gap-1 px-2 py-0.5 rounded text-[#8FA5B8] hover:text-white hover:bg-[#2D3A4A] text-xs"
            >
              <span className="text-[13px] leading-none">{'✕'}</span>
              <span className="hidden sm:inline">Close</span>
            </button>
          )}
        </div>

        {phase === 'shell' && (
          <LinuxTerminalTabs
            tabs={linuxTabs.tabs}
            activeId={linuxTabs.activeId}
            onSelect={linuxTabs.setActiveId}
            onClose={linuxTabs.closeTab}
            onNew={() => linuxTabs.addTab('shell')}
          />
        )}

        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto p-4 font-mono text-[12.5px] leading-relaxed bg-[#05090f] cursor-text"
          onClick={() => !editor && inputRef.current?.focus()}
        >
          {lines.map((l, i) => (
            <div key={i} className={l.startsWith('$') || l.includes('password') || l.startsWith('[  OK  ]') ? 'text-[#5DB85D]' : l.startsWith('[') ? 'text-[#8fa5b8]' : 'text-[#E8EDF2]'}>{l || ' '}</div>
          ))}

          {phase === 'password' && (
            <>
              <div className="flex items-center gap-1 text-[#5DB85D] mt-1">
                <span>{loginUser || 'root'}@{ip}&apos;s password:</span>
                <input ref={inputRef} autoFocus type="password" value={password} onChange={e => setPassword(e.target.value)} onKeyDown={onKeyDown} className="flex-1 bg-transparent border-none outline-none text-[#E8EDF2] font-mono caret-[#5DB85D]" />
              </div>
              <div className="flex items-center gap-1 text-[#8FA5B8] mt-2 text-[11px]">
                <span>login as:</span>
                <input value={loginUser} onChange={e => setLoginUser(e.target.value)} onKeyDown={onKeyDown} className="w-32 bg-transparent border-b border-[#2D3A4A] outline-none text-[#E8EDF2] font-mono" spellCheck={false} />
              </div>
            </>
          )}

          {phase === 'shell' && confirm && !busy && (
            <div className="flex items-center mt-1 text-[#E8EDF2]">
              <span className="whitespace-nowrap">{confirm.promptText}</span>
              <input ref={inputRef} autoFocus value={confirmInput} onChange={e => setConfirmInput(e.target.value)} onKeyDown={onKeyDown} maxLength={3} spellCheck={false} className="w-16 bg-transparent border-none outline-none text-[#E8EDF2] font-mono caret-[#5DB85D] ml-1" />
            </div>
          )}

          {phase === 'shell' && !editor && !confirm && !busy && (
            <div className="flex items-center mt-1">
              <span className="text-[#5DB85D] whitespace-nowrap">{shell.prompt()}</span>
              <input ref={inputRef} autoFocus value={cmd} onChange={e => setCmd(e.target.value)} onKeyDown={onKeyDown} className="flex-1 bg-transparent border-none outline-none text-[#E8EDF2] font-mono text-[12.5px] caret-[#5DB85D] ml-1" spellCheck={false} autoComplete="off" />
            </div>
          )}

          {busy && phase === 'shell' && <div className="text-[#8fa5b8] animate-pulse mt-1">...</div>}

          {phase === 'closed' && (
            <p className="text-[#8fa5b8] mt-2">Session closed. Re-open the SSH panel to reconnect.</p>
          )}
          {phase === 'failed' && (
            <p className="text-[#8fa5b8] mt-2">Guest may be hung or network misconfigured. Use the web console and verify IP/VLAN assignment.</p>
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

        {phase === 'shell' ? (
          <LinuxTerminalStatusBar status={linuxTabs.status} hint={footerHint} />
        ) : (
          <div className="shrink-0 px-3.5 py-2 bg-[#1B2A3B] border-t border-[#2D3A4A] text-[10.5px] text-[#8FA5B8] font-mono">
            {footerHint}
          </div>
        )}
      </div>
    </div>
  )
}
