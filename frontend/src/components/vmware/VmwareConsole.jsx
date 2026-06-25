import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createLinuxShell, POST_LINES, buildGrubEntries, buildBootStages } from './linuxShell'
import { createWindowsShell, WIN_BOOT_SEQUENCE, WIN_LOGIN_HINT } from './windowsShell'
import { LinuxTerminalTabs, LinuxTerminalStatusBar } from '../linux/LinuxTerminalChrome'
import { useLinuxTerminalTabs } from '../linux/useLinuxTerminalTabs'

const LOGIN_HINT = 'Hint: root/root13 or labuser/labuser@123'
const GRUB_TIMEOUT = 8 // seconds the GRUB menu counts down before auto-booting

function isWindowsGuest(vm) {
  return (vm?.guest_os || '').includes('Windows') || (vm?.guest_os_version || '').includes('Windows')
}

function guestUser(vm) {
  return isWindowsGuest(vm) ? 'Administrator' : 'root'
}

// The pre-login banner a real Linux getty prints above the `login:` prompt
// (the /etc/issue contents) when you attach a console to an already-running box.
function loginBanner(vm) {
  const ver = vm?.guest_os_version || vm?.guest_os || 'Linux'
  const isUbuntu = /ubuntu|debian/i.test(`${vm?.guest_os || ''} ${vm?.guest_os_version || ''}`)
  const kernel = isUbuntu ? '5.15.0-91-generic' : '5.14.0-362.el9.x86_64'
  const tty = isUbuntu ? 'tty1' : 'tty1'
  return [
    `${ver}`,
    `Kernel ${kernel} on an x86_64 (${tty})`,
    '',
  ]
}

export default function VmwareConsole({ vm, onClose, onGuestAction }) {
  const isWin = isWindowsGuest(vm)
  const winShell = useMemo(() => (
    isWin ? createWindowsShell(vm) : null
  ), [isWin, vm?.id, vm?.hostname, vm?.ip, vm?.disk_gb, vm?.memory_mb, vm?.cpu, vm?.guest_disk_hidden, vm?.kernel_module_missing])
  const linuxTabs = useLinuxTerminalTabs(vm, { enabled: !isWin })
  const shell = isWin ? winShell : (linuxTabs.activeShell || linuxTabs.getShell(linuxTabs.activeId))
  const grubEntries = useMemo(() => buildGrubEntries(vm), [vm?.id, vm?.guest_os, vm?.guest_os_version])

  const [lines, setLines] = useState([])
  const [cmd, setCmd] = useState('')
  const [histIdx, setHistIdx] = useState(-1)
  // phases: post | grub | booting | login | shell | hung | rescue | off
  // A running guest shows the LOGIN prompt by default — exactly like reconnecting
  // to a server that's been up for days. The full POST/GRUB/boot sequence only
  // replays when the VM was actually powered on / reset this session, which the
  // backend signals via `boot_pending`.
  const [phase, setPhase] = useState(() => {
    if (vm?.guest_hung) return 'hung'
    if (vm?.boot_failure) return 'rescue'
    if (vm?.power === 'poweredOn') {
      if (isWindowsGuest(vm)) return vm?.boot_pending ? 'winboot' : 'login'
      return vm?.boot_pending ? 'post' : 'login'
    }
    return 'off'
  })
  const [grubSel, setGrubSel] = useState(0)
  const [grubCount, setGrubCount] = useState(GRUB_TIMEOUT)
  const [grubPaused, setGrubPaused] = useState(false)
  const [loginUser, setLoginUser] = useState('')
  const [loginPass, setLoginPass] = useState('')
  const [loginStep, setLoginStep] = useState('user') // user | pass
  const [editor, setEditor] = useState(null) // { tool, path, content }
  const [confirm, setConfirm] = useState(null) // { promptText, defaultYes, onYesStream, onNoLines }
  const [confirmInput, setConfirmInput] = useState('')
  const [busy, setBusy] = useState(false) // true while streaming install / boot — input disabled

  const scrollRef = useRef(null)
  const inputRef = useRef(null)
  const overlayRef = useRef(null)
  const timersRef = useRef([]) // all pending setTimeouts, cleared on unmount / phase change
  const prevTabRef = useRef(null)

  // Persist / restore per-tab terminal output when switching tabs (shared VFS, independent sessions).
  useEffect(() => {
    if (isWin || (phase !== 'shell' && phase !== 'rescue') || !linuxTabs.activeId) return
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
  }, [linuxTabs.activeId, phase, isWin]) // eslint-disable-line react-hooks/exhaustive-deps

  // --- timer bookkeeping (interruptible, no leaks) ---
  const clearTimers = useCallback(() => {
    timersRef.current.forEach(clearTimeout)
    timersRef.current = []
  }, [])
  const later = useCallback((fn, ms) => {
    const id = setTimeout(fn, ms)
    timersRef.current.push(id)
    return id
  }, [])
  useEffect(() => () => clearTimers(), [clearTimers])

  const append = useCallback((text) => {
    setLines(prev => [...prev, ...(Array.isArray(text) ? text : [text])])
  }, [])

  // ------------------------------------------------------------------ *
  // Boot / reboot orchestration
  // ------------------------------------------------------------------ *
  const startPost = useCallback(() => {
    clearTimers()
    setBusy(true)
    setLines([])
    setGrubSel(0)
    setGrubCount(GRUB_TIMEOUT)
    setGrubPaused(false)
    setPhase('post')
    // stream the POST/BIOS lines (paced so it reads like real firmware), then GRUB
    POST_LINES.forEach((l, i) => later(() => append(l), 360 * (i + 1)))
    later(() => setPhase('grub'), 360 * (POST_LINES.length + 1) + 300)
  }, [append, clearTimers, later])

  // Run the kernel→systemd→login stage list with real pacing.
  const runBootStages = useCallback((single) => {
    clearTimers()
    setBusy(true)
    setPhase('booting')
    const stages = buildBootStages(vm, { single })
    let acc = 0
    stages.forEach((st) => {
      acc += st.delay
      later(() => append(st.text), acc)
    })
    later(() => {
      setBusy(false)
      if (single) {
        setPhase('rescue')
      } else {
        setLoginStep('user')
        setLoginUser('')
        setLoginPass('')
        setPhase('login')
        // Boot finished — tell the backend so a later console open on this still-
        // running guest goes straight to login instead of replaying the boot.
        if (vm?.boot_pending && vm?.id && onGuestAction) {
          onGuestAction({ action: 'console_booted', vm_id: vm.id, silent: true })
        }
      }
    }, acc + 400)
  }, [append, clearTimers, later, onGuestAction, vm])

  // Power state changes from the parent (power on/off, reset) restart the console state.
  useEffect(() => {
    clearTimers()
    if (vm?.power !== 'poweredOn') {
      setPhase('off')
      setLines([`${vm?.name || 'Guest'} — power on to boot guest OS`])
      return
    }
    if (vm?.guest_hung) {
      setPhase('hung')
      setLines([
        `${vm?.name} — VMware Web Console`,
        'Guest OS appears hung — keyboard input not accepted.',
        '[  892.441] INFO: task sshd:1234 blocked for more than 120 seconds.',
        '[  892.442] "echo 0 > /proc/sys/kernel/hung_task_timeout_secs" disables this message.',
      ])
      return
    }
    if (vm?.boot_failure) {
      setPhase('rescue')
      setLines([
        'Generating "/run/initramfs/rdsosreport.txt"',
        '',
        'Entering emergency mode. Exit the shell to continue.',
        'Give root password for maintenance',
        '(or press Control-D to continue): ',
      ])
      return
    }
    // A guest that was just powered on / reset this session replays the full
    // BIOS→GRUB→boot run (Windows: its own boot splash). An already-running guest
    // goes straight to the login prompt, exactly like reconnecting over the
    // console to a server that has been up for days.
    if (!vm?.boot_pending) {
      if (isWin) { setLoginStep('user'); setPhase('login'); setLines([]) }
      else { setLoginStep('user'); setPhase('login'); setLines(loginBanner(vm)) }
      return
    }
    if (isWin) {
      setPhase('winboot')
      return
    }
    startPost()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vm?.id, vm?.power, vm?.guest_hung, vm?.boot_failure, vm?.boot_pending, isWin])

  // Windows boot (unchanged simple path)
  useEffect(() => {
    if (phase !== 'winboot') return undefined
    setLines(WIN_BOOT_SEQUENCE)
    const t = setTimeout(() => {
      setLoginStep('user')
      setPhase('login')
      if (vm?.boot_pending && vm?.id && onGuestAction) {
        onGuestAction({ action: 'console_booted', vm_id: vm.id, silent: true })
      }
    }, 2500)
    return () => clearTimeout(t)
  }, [phase, onGuestAction, vm?.boot_pending, vm?.id])

  // GRUB auto-boot countdown
  useEffect(() => {
    if (phase !== 'grub' || grubPaused) return undefined
    if (grubCount <= 0) {
      // selecting the rescue/recovery entry (index 1) boots single-user
      runBootStages(grubSel === 1)
      return undefined
    }
    const t = setTimeout(() => setGrubCount(c => c - 1), 1000)
    return () => clearTimeout(t)
  }, [phase, grubCount, grubPaused, grubSel, runBootStages])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight })
  }, [lines, phase, grubSel, grubCount, loginStep, confirm])

  // keep the hidden capture input / command input focused while console owns the keyboard
  useEffect(() => {
    if (!editor && phase !== 'off') inputRef.current?.focus()
  }, [phase, editor, confirm, busy])

  // return focus to the page when the console closes
  const handleClose = useCallback(() => {
    clearTimers()
    onClose?.()
  }, [clearTimers, onClose])

  // ------------------------------------------------------------------ *
  // Escape guard (Defect #1 & #4)
  // ------------------------------------------------------------------ *
  // The parent VMwareSimulator has a document-level (bubble-phase) keydown
  // listener that closes the console on ANY Escape. React 18 delegates events
  // at #root, which is INSIDE document, so calling stopPropagation() on our
  // React keydown handlers stops the native event before it bubbles up to that
  // document listener — the console stays open and we own Escape ourselves.
  // Every phase keeps a focused input wired to one of these handlers, so a
  // single helper applied at the top of each handler is enough.
  const stopBubble = (e) => { e.stopPropagation() }

  // ------------------------------------------------------------------ *
  // Command execution + result handling (reboot / confirm / stream / editor)
  // ------------------------------------------------------------------ *
  const streamChunks = useCallback((chunks, doneLines, onDone) => {
    setBusy(true)
    let acc = 0
    chunks.forEach((chunk) => {
      acc += 380
      later(() => append(chunk), acc)
    })
    later(() => {
      if (doneLines && doneLines.length) append(doneLines)
      setBusy(false)
      onDone?.()
    }, acc + 300)
  }, [append, later])

  const handleResult = useCallback((result) => {
    if (!result) return
    if (result.clear) { setLines([]); return }
    if (result.exit) { handleClose(); return }
    if (result.editor) { setEditor(result.editor); return }
    if (result.reboot) {
      append(result.lines)
      append(['', 'Broadcast message: The system is going down for reboot NOW!', ''])
      later(() => startPost(), 1200)
      return
    }
    if (result.poweroff) {
      append(result.lines)
      append(['', 'The system is powering off.', ''])
      later(() => { setPhase('off'); setLines([`${vm?.name || 'Guest'} — guest OS powered off. Power on the VM to boot again.`]) }, 1400)
      return
    }
    // package-manager confirmation: print resolution, then wait for y/N
    if (result.confirm) {
      append(result.lines)
      setConfirm(result.confirm)
      setConfirmInput('')
      return
    }
    // -y install / non-interactive: print head then stream progress
    if (result.stream) {
      append(result.lines)
      // Commit the package transaction now (the "y" was implied by -y) so a later
      // rpm -q / dnf list installed reflects the install/removal.
      result.stream.commit?.()
      streamChunks(result.stream.chunks, result.stream.doneLines, undefined)
      return
    }
    append(result.lines)
    if (result.sideEffect && onGuestAction) onGuestAction(result.sideEffect)
  }, [append, handleClose, later, onGuestAction, startPost, streamChunks, vm?.name])

  const runCmd = useCallback((raw) => {
    if (!shell) return
    const result = shell.run(raw)
    handleResult(result)
    if (result?.editor && linuxTabs.activeId) {
      const tool = result.editor.tool === 'nano' ? 'nano' : 'vim'
      linuxTabs.renameTab(linuxTabs.activeId, tool)
    }
    if (raw.trim().startsWith('htop') && linuxTabs.activeId) {
      linuxTabs.renameTab(linuxTabs.activeId, 'htop')
    }
    // legacy boot_failure repair path (fsck / exit / reboot from rescue)
    if (vm?.boot_failure && (raw.includes('fsck') || raw.includes('exit') || raw.includes('reboot'))) {
      onGuestAction?.({ action: 'guest_fix_boot', vm_id: vm.id })
    }
  }, [handleResult, linuxTabs, onGuestAction, shell, vm?.boot_failure, vm?.id])

  // ------------------------------------------------------------------ *
  // Login
  // ------------------------------------------------------------------ *
  const tryLogin = useCallback(() => {
    if (loginStep === 'user') {
      setLoginStep('pass')
      setLoginPass('')
      return
    }
    if (loginUser === 'root' && loginPass === 'root13') {
      append([
        `Last login: ${new Date().toUTCString()} on tty1`,
        LOGIN_HINT,
        `Welcome to FixitLab simulated ${vm?.guest_os_version || 'Linux'}.`,
        '',
      ])
      setPhase('shell')
      setCmd('')
    } else if (!isWin && loginUser === 'labuser' && loginPass === 'labuser@123') {
      shell?.switchUser?.('labuser')
      append([
        `Last login: ${new Date().toUTCString()} on pts/0 from 192.168.10.1`,
        `Welcome to Ubuntu 22.04 LTS — GNU/Linux`,
        '',
      ])
      setPhase('shell')
      setCmd('')
    } else if (isWin && loginUser === 'Administrator' && loginPass === 'P@ssw0rd123') {
      append([WIN_LOGIN_HINT, `Welcome to ${vm?.guest_os_version || 'Windows Server'}.`, ''])
      setPhase('shell')
      setCmd('')
    } else {
      append('Login incorrect')
      setLoginStep('user')
      setLoginUser('')
      setLoginPass('')
    }
  }, [append, isWin, loginPass, loginStep, loginUser, shell, vm])

  // ------------------------------------------------------------------ *
  // Editor (vi / nano) — real save back into the VFS
  // ------------------------------------------------------------------ *
  const finishEditor = useCallback((save, content) => {
    if (editor && save) {
      shell.saveFile(editor.path || '/root/scratch.txt', content ?? editor.content)
      append(editor.tool === 'nano'
        ? `[ Wrote ${(content ?? '').split('\n').length} lines ]`
        : `"${editor.path || 'scratch.txt'}" ${(content ?? '').split('\n').length}L written`)
    }
    setEditor(null)
  }, [append, editor, shell])

  // ------------------------------------------------------------------ *
  // y/N confirmation prompt for yum/dnf/apt
  // ------------------------------------------------------------------ *
  const resolveConfirm = useCallback((answerRaw) => {
    const c = confirm
    if (!c) return
    const answer = (answerRaw || '').trim().toLowerCase()
    const yes = answer === '' ? c.defaultYes : (answer === 'y' || answer === 'yes')
    append(`${c.promptText}${answerRaw}`)
    setConfirm(null)
    setConfirmInput('')
    if (yes) {
      // User confirmed — commit the package DB change so rpm/dnf/dpkg queries
      // reflect the install or removal afterwards.
      c.onYesStream.commit?.()
      streamChunks(c.onYesStream.chunks, c.onYesStream.doneLines, undefined)
    } else {
      append(c.onNoLines)
    }
  }, [append, confirm, streamChunks])

  // ------------------------------------------------------------------ *
  // Keyboard for the terminal (login / grub / shell / confirm)
  // ------------------------------------------------------------------ *
  const onKeyDown = (e) => {
    // Keep every keystroke (especially Escape) from bubbling to the parent's
    // document listener, which would otherwise close the console.
    stopBubble(e)
    if (phase === 'hung') {
      e.preventDefault()
      append('(no response — guest OS is hung)')
      return
    }
    // Esc during BIOS/POST or boot opens the GRUB menu (pauses countdown).
    if ((phase === 'post' || phase === 'booting') && e.key === 'Escape') {
      e.preventDefault()
      clearTimers()
      setBusy(false)
      setGrubSel(0)
      setGrubCount(GRUB_TIMEOUT)
      setGrubPaused(true)
      setPhase('grub')
      return
    }
    if (phase === 'grub') {
      if (e.key === 'ArrowUp') { e.preventDefault(); setGrubPaused(true); setGrubSel(s => Math.max(0, s - 1)) }
      else if (e.key === 'ArrowDown') { e.preventDefault(); setGrubPaused(true); setGrubSel(s => Math.min(grubEntries.length - 1, s + 1)) }
      else if (e.key === 'e' || e.key === 'c') { e.preventDefault(); setGrubPaused(true); append(`grub> (edit mode — append "single" to the linux line and press Enter to boot ${grubEntries[grubSel]} into single-user mode)`) }
      else if (e.key === 'Enter') {
        e.preventDefault()
        clearTimers()
        // last entry = firmware settings; index 1 = rescue/recovery -> single-user
        if (grubSel === grubEntries.length - 1) { append('Entering UEFI Firmware Settings… (no settings in simulation) — rebooting'); later(() => startPost(), 1200); return }
        runBootStages(grubSel === 1)
      } else if (e.key !== 'Escape') {
        // any other key pauses the countdown (real GRUB behaviour)
        setGrubPaused(true)
      } else {
        e.preventDefault()
        setGrubPaused(true)
      }
      return
    }
    if (phase === 'login') {
      if (e.key === 'Enter') {
        e.preventDefault()
        if (loginStep === 'user') append(`${vm?.hostname || vm?.name} login: ${loginUser}`)
        else append('Password: ')
        tryLogin()
      }
      return
    }
    if (busy) { e.preventDefault(); return } // ignore typing while streaming
    // y/N confirmation
    if (confirm) {
      if (e.key === 'Enter') { e.preventDefault(); resolveConfirm(confirmInput) }
      return
    }
    if (phase === 'rescue' || phase === 'shell') {
      if (e.key === 'Enter') {
        e.preventDefault()
        append(`${shell.prompt()} ${cmd}`)
        runCmd(cmd)
        setHistIdx(-1)
        setCmd('')
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
  }

  if (!vm) return null

  const footerHint = editor
    ? (editor.tool === 'nano' ? 'nano — ^O save · ^X exit · ^C cancel' : 'vi — i/a/o insert · Esc command mode · :wq save · :q! quit')
    : confirm ? 'Type y to proceed or n to abort, then Enter'
    : phase === 'shell' || phase === 'rescue' ? 'Type help · real filesystem · vi/nano edit & save · reboot replays boot · ↑/↓ history'
    : phase === 'login' ? LOGIN_HINT
    : phase === 'grub' ? 'GRUB — ↑/↓ select · e edit · Enter boot · any key pauses countdown'
    : phase === 'off' ? 'Guest is powered off'
    : 'Booting guest OS… — press Esc for the GRUB menu'

  return (
    <div className="vm-modal-overlay" onMouseDown={e => e.target === e.currentTarget && handleClose()}>
      <div ref={overlayRef} className="vm-modal relative w-full max-w-[900px] h-[580px] max-h-[90vh] flex flex-col p-0 overflow-hidden" onMouseDown={e => e.stopPropagation()}>
        <div className="flex items-center gap-2.5 px-3.5 py-2.5 bg-[#1B2A3B] border-b border-[#2D3A4A] shrink-0">
          <div className="flex gap-1.5">
            <span className="w-[11px] h-[11px] rounded-full bg-[#D9534F]" />
            <span className="w-[11px] h-[11px] rounded-full bg-[#F5A623]" />
            <span className="w-[11px] h-[11px] rounded-full bg-[#5DB85D]" />
          </div>
          <span className="font-mono text-xs text-[#8FA5B8]">{vm.name} — Web Console</span>
          <span className="text-[10px] text-[#8FA5B8] ml-2 hidden sm:inline">{LOGIN_HINT}</span>
          <div className="flex-1" />
          <button
            type="button"
            onClick={handleClose}
            title="Close console (Esc returns focus to the page)"
            aria-label="Close console"
            className="flex items-center gap-1 px-2 py-0.5 rounded text-[#8FA5B8] hover:text-white hover:bg-[#2D3A4A] text-xs"
          >
            <span className="text-[13px] leading-none">✕</span>
            <span className="hidden sm:inline">Close</span>
          </button>
        </div>

        {!isWin && (phase === 'shell' || phase === 'rescue') && (
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
            <div key={i} className={lineClass(l)}>{l || ' '}</div>
          ))}

          {phase === 'post' && <div className="text-[#8FA5B8] animate-pulse">_</div>}
          {phase === 'booting' && busy && <div className="text-[#8FA5B8] animate-pulse">_</div>}
          {phase === 'hung' && <div className="text-[#D9534F] mt-2">Guest not responding — use Reset after customer approval.</div>}
          {phase === 'off' && <div className="text-[#8FA5B8] mt-2">No signal — VM is powered off.</div>}

          {phase === 'grub' && (
            <div className="my-2 border border-[#5b9bf5] rounded overflow-hidden max-w-[640px]">
              <div className="bg-[#0a1a3a] px-2.5 py-1.5 text-[#9bb8ff] text-[11px]">GNU GRUB version 2.06 — ↑/↓ select · Enter boot · e edit</div>
              {grubEntries.map((entry, i) => (
                <div key={entry} className={`px-3 py-1 text-[12.5px] ${i === grubSel ? 'bg-[#2D7CFF] text-white' : 'text-[#cdd7e1]'}`}>
                  {i === grubSel ? '▶ ' : '  '}{entry}
                </div>
              ))}
              <div className="bg-[#0a1a3a] px-2.5 py-1.5 text-[#9bb8ff] text-[11px]">
                {grubPaused
                  ? 'Countdown paused — press Enter to boot the highlighted entry.'
                  : `The highlighted entry will be executed automatically in ${grubCount}s.`}
              </div>
            </div>
          )}

          {phase === 'login' && !editor && (
            <div className="mt-2 text-[#E8EDF2]">
              {loginStep === 'user' ? (
                <div className="flex items-center gap-1">
                  <span>{vm.hostname || vm.name} login:</span>
                  <input ref={inputRef} autoFocus value={loginUser} onChange={e => setLoginUser(e.target.value)} onKeyDown={onKeyDown} className="flex-1 bg-transparent border-none outline-none text-[#E8EDF2] font-mono caret-[#5DB85D]" spellCheck={false} />
                </div>
              ) : (
                <div className="flex items-center gap-1">
                  <span>Password:</span>
                  <input ref={inputRef} autoFocus type="password" value={loginPass} onChange={e => setLoginPass(e.target.value)} onKeyDown={onKeyDown} className="flex-1 bg-transparent border-none outline-none text-[#E8EDF2] font-mono caret-[#5DB85D]" spellCheck={false} />
                </div>
              )}
            </div>
          )}

          {/* y/N confirmation line (yum/dnf/apt) */}
          {(phase === 'shell' || phase === 'rescue') && confirm && !busy && (
            <div className="flex items-center mt-1 text-[#E8EDF2]">
              <span className="whitespace-nowrap">{confirm.promptText}</span>
              <input ref={inputRef} autoFocus value={confirmInput} onChange={e => setConfirmInput(e.target.value)} onKeyDown={onKeyDown} maxLength={3} spellCheck={false} autoComplete="off" className="w-16 bg-transparent border-none outline-none text-[#E8EDF2] font-mono caret-[#5DB85D] ml-1" />
            </div>
          )}

          {/* normal shell prompt */}
          {(phase === 'shell' || phase === 'rescue') && !editor && !confirm && !busy && (
            <div className="flex items-center mt-1">
              <span className="text-[#5DB85D] whitespace-nowrap">{shell.prompt()}</span>
              <input ref={inputRef} autoFocus value={cmd} onChange={e => setCmd(e.target.value)} onKeyDown={onKeyDown} spellCheck={false} autoComplete="off" className="flex-1 bg-transparent border-none outline-none text-[#E8EDF2] font-mono text-[12.5px] caret-[#5DB85D] ml-1" />
            </div>
          )}

          {busy && (phase === 'shell' || phase === 'rescue') && <div className="text-[#8FA5B8] animate-pulse mt-1">…</div>}

          {/* hidden capture input keeps the keyboard with the console during boot/grub */}
          {(phase === 'grub' || phase === 'post' || phase === 'booting') && (
            <input ref={inputRef} className="sr-only" onKeyDown={onKeyDown} autoFocus tabIndex={0} aria-hidden />
          )}
        </div>

        {/* vi / nano editor overlay (real modes, real save) */}
        {editor && (
          <ViNanoEditor
            tool={editor.tool}
            path={editor.path}
            initialContent={editor.content}
            onFinish={finishEditor}
          />
        )}

        <div className="shrink-0">
          {!isWin && (phase === 'shell' || phase === 'rescue') ? (
            <LinuxTerminalStatusBar status={linuxTabs.status} hint={footerHint} />
          ) : (
            <div className="px-3.5 py-2 bg-[#1B2A3B] border-t border-[#2D3A4A] text-[10.5px] text-[#8FA5B8] font-mono">
              {footerHint}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function lineClass(l) {
  if (typeof l !== 'string') return 'text-[#5DB85D]'
  if (l.startsWith('[  OK  ]')) return 'text-[#5DB85D]'
  if (l.startsWith('[FAILED]')) return 'text-[#D9534F]'
  if (l.startsWith('[')) return 'text-[#8FA5B8]'
  if (l.includes('login:') || l.includes('Password') || l.includes('#') || l.includes('$')) return 'text-[#E8EDF2]'
  return 'text-[#9fb3c6]'
}

/* ------------------------------------------------------------------ *
 * In-console vi / vim / nano editor with REAL modes.
 *
 * vi/vim:  starts in COMMAND mode.  i/a/I/A/o/O -> INSERT mode.  Esc -> COMMAND.
 *          In COMMAND mode `:` opens the ex line; :w :wq :wq! :x save, :q :q! quit.
 *          Esc NEVER closes the console while the editor is open — it only returns
 *          to command mode (or clears the ex line).
 * nano:    always editable; ^O write, ^X exit (save), ^C cancel.
 * ------------------------------------------------------------------ */
export function ViNanoEditor({ tool, path, initialContent, onFinish }) {
  const isNano = tool === 'nano'
  const [text, setText] = useState(initialContent || '')
  const [mode, setMode] = useState(isNano ? 'insert' : 'command') // command | insert
  const [exline, setExline] = useState(null) // null = no ex prompt; string = current ":..." buffer
  const [status, setStatus] = useState(isNano ? '' : '"' + (path || '[No Name]') + '"')
  const taRef = useRef(null)

  useEffect(() => { taRef.current?.focus() }, [])

  const lineCount = (text.match(/\n/g) || []).length + 1

  const runEx = (cmd) => {
    const c = cmd.replace(/^:/, '').trim()
    // accept :w :wq :wq! :x :x! :q :q!  (and write-to-file :w name -> still saves current buffer)
    if (c === 'w' || /^w\s+\S+/.test(c)) { onFinish(true, taRef.current?.value ?? text); setStatus('written'); setExline(null); setMode('command'); return }
    if (c === 'wq' || c === 'wq!' || c === 'x' || c === 'x!' || /^wq?\s+\S+/.test(c)) { onFinish(true, taRef.current?.value ?? text); return }
    if (c === 'q') { onFinish(false); return }
    if (c === 'q!') { onFinish(false); return }
    // unknown ex command — show an error like vim does, stay in command mode
    setStatus(`E492: Not an editor command: ${c}`)
    setExline(null)
    setMode('command')
  }

  const onKeyDown = (e) => {
    // Never let editor keystrokes (Esc especially) reach the parent's document
    // listener — Esc must only toggle vi command mode, not close the console.
    e.stopPropagation()
    // ---- nano ----
    if (isNano) {
      if (e.ctrlKey && (e.key === 'o' || e.key === 'O')) { e.preventDefault(); onFinish(true, taRef.current?.value ?? text); return }
      if (e.ctrlKey && (e.key === 'x' || e.key === 'X')) { e.preventDefault(); onFinish(true, taRef.current?.value ?? text); return }
      if (e.ctrlKey && (e.key === 'c' || e.key === 'C')) { e.preventDefault(); onFinish(false); return }
      return // otherwise let textarea edit freely
    }

    // ---- vi / vim ----
    // The ex command line (after pressing ':') captures everything until Enter/Esc.
    if (exline !== null) {
      if (e.key === 'Enter') { e.preventDefault(); runEx(exline); return }
      if (e.key === 'Escape') { e.preventDefault(); setExline(null); setMode('command'); setStatus(''); return }
      if (e.key === 'Backspace') { e.preventDefault(); setExline(ex => ex.length <= 1 ? '' : ex.slice(0, -1)); return }
      if (e.key.length === 1) { e.preventDefault(); setExline(ex => ex + e.key); return }
      e.preventDefault()
      return
    }

    if (mode === 'insert') {
      // Esc -> back to COMMAND mode. ALWAYS swallow Esc so it can't close the console.
      if (e.key === 'Escape') { e.preventDefault(); setMode('command'); setStatus(''); return }
      return // textarea edits normally in insert mode
    }

    // ---- COMMAND mode ----
    if (e.key === 'Escape') { e.preventDefault(); setStatus(''); return } // stay in command mode, never close
    // entering insert mode
    if (e.key === 'i') { e.preventDefault(); setMode('insert'); setStatus('-- INSERT --'); return }
    if (e.key === 'a') { e.preventDefault(); moveCaret(taRef.current, +1); setMode('insert'); setStatus('-- INSERT --'); return }
    if (e.key === 'I') { e.preventDefault(); caretToLineStart(taRef.current); setMode('insert'); setStatus('-- INSERT --'); return }
    if (e.key === 'A') { e.preventDefault(); caretToLineEnd(taRef.current); setMode('insert'); setStatus('-- INSERT --'); return }
    if (e.key === 'o') { e.preventDefault(); openLineBelow(taRef.current, setText); setMode('insert'); setStatus('-- INSERT --'); return }
    if (e.key === 'O') { e.preventDefault(); openLineAbove(taRef.current, setText); setMode('insert'); setStatus('-- INSERT --'); return }
    // ex command line
    if (e.key === ':') { e.preventDefault(); setExline(':'); setStatus(''); return }
    // a few common command-mode keys for realism
    if (e.key === 'x') { e.preventDefault(); deleteCharAtCaret(taRef.current, setText); return }
    if (e.key === 'd') { e.preventDefault(); setStatus('(use :wq to save, dd to delete a line — partial vi)'); return }
    // motions / arrows pass through to move the caret, but block text insertion
    if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Home', 'End', 'PageUp', 'PageDown'].includes(e.key)) return
    // any other printable key in command mode is swallowed (vi ignores it / beeps)
    if (e.key.length === 1 && !e.ctrlKey && !e.metaKey) { e.preventDefault() }
  }

  return (
    <div className="absolute left-0 right-0 top-[42px] bottom-0 z-20 flex items-stretch bg-[#05090f]" onMouseDown={e => e.stopPropagation()}>
      <div className="flex flex-col w-full h-full">
        <div className="shrink-0 px-3 py-1.5 bg-[#1B2A3B] text-[#8FA5B8] text-[11px] font-mono flex items-center gap-2">
          <span className="text-[#5DB85D]">{isNano ? 'GNU nano 6.2' : 'VIM - Vi IMproved 8.2'}</span>
          <span>{path || '[No Name]'}</span>
          {!isNano && <span className={mode === 'insert' ? 'text-[#5DB85D]' : 'text-[#F5A623]'}>· {mode === 'insert' ? 'INSERT' : 'NORMAL'}</span>}
        </div>
        <textarea
          ref={taRef}
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={onKeyDown}
          spellCheck={false}
          autoComplete="off"
          autoFocus
          // In vi COMMAND mode every printable key is preventDefault'd in onKeyDown,
          // so the textarea never inserts stray characters; arrows still move the caret.
          className="flex-1 w-full resize-none bg-[#05090f] text-[#E8EDF2] font-mono text-[12.5px] leading-relaxed p-3 border-none outline-none caret-[#5DB85D]"
        />
        {isNano ? (
          <div className="shrink-0 px-3 py-1.5 bg-[#1B2A3B] text-[#8FA5B8] text-[11px] font-mono flex justify-between">
            <span><span className="text-[#E8EDF2]">^O</span> Write Out   <span className="text-[#E8EDF2]">^X</span> Exit   <span className="text-[#E8EDF2]">^C</span> Cancel</span>
            <span>{lineCount} lines</span>
          </div>
        ) : (
          <div className="shrink-0 px-3 py-1.5 bg-[#1B2A3B] text-[11px] font-mono flex items-center min-h-[28px]">
            {exline !== null ? (
              <span className="text-[#E8EDF2]">{exline}<span className="animate-pulse">▏</span></span>
            ) : (
              <span className={status.startsWith('E') ? 'text-[#D9534F]' : status === '-- INSERT --' ? 'text-[#5DB85D]' : 'text-[#8FA5B8]'}>
                {status || (mode === 'command' ? 'press i to insert · :wq to save · :q! to quit' : '')}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// --- tiny caret/text helpers for vi command-mode operations ---
function moveCaret(ta, delta) {
  if (!ta) return
  const p = Math.min(ta.value.length, Math.max(0, ta.selectionStart + delta))
  ta.setSelectionRange(p, p)
}
function caretToLineStart(ta) {
  if (!ta) return
  const before = ta.value.lastIndexOf('\n', ta.selectionStart - 1)
  const p = before + 1
  ta.setSelectionRange(p, p)
}
function caretToLineEnd(ta) {
  if (!ta) return
  let end = ta.value.indexOf('\n', ta.selectionStart)
  if (end === -1) end = ta.value.length
  ta.setSelectionRange(end, end)
}
function openLineBelow(ta, setText) {
  if (!ta) return
  let end = ta.value.indexOf('\n', ta.selectionStart)
  if (end === -1) end = ta.value.length
  const next = ta.value.slice(0, end) + '\n' + ta.value.slice(end)
  setText(next)
  requestAnimationFrame(() => { ta.setSelectionRange(end + 1, end + 1) })
}
function openLineAbove(ta, setText) {
  if (!ta) return
  const start = ta.value.lastIndexOf('\n', ta.selectionStart - 1) + 1
  const next = ta.value.slice(0, start) + '\n' + ta.value.slice(start)
  setText(next)
  requestAnimationFrame(() => { ta.setSelectionRange(start, start) })
}
function deleteCharAtCaret(ta, setText) {
  if (!ta) return
  const p = ta.selectionStart
  if (p >= ta.value.length || ta.value[p] === '\n') return
  setText(ta.value.slice(0, p) + ta.value.slice(p + 1))
  requestAnimationFrame(() => { ta.setSelectionRange(p, p) })
}
