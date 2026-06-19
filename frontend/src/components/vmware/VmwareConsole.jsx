import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createLinuxShell, BOOT_SEQUENCE, GRUB_ENTRIES } from './linuxShell'
import { createWindowsShell, WIN_BOOT_SEQUENCE, WIN_LOGIN_HINT } from './windowsShell'

const LOGIN_HINT = 'Hint: username root, password root13'

function isWindowsGuest(vm) {
  return (vm?.guest_os || '').includes('Windows') || (vm?.guest_os_version || '').includes('Windows')
}

function guestUser(vm) {
  return isWindowsGuest(vm) ? 'Administrator' : 'root'
}

export default function VmwareConsole({ vm, onClose, onGuestAction }) {
  const isWin = isWindowsGuest(vm)
  const shell = useMemo(() => (
    isWin ? createWindowsShell(vm) : createLinuxShell(vm)
  ), [isWin, vm?.id, vm?.hostname, vm?.ip, vm?.disk_gb, vm?.memory_mb, vm?.cpu, vm?.guest_disk_hidden, vm?.kernel_module_missing])
  const [lines, setLines] = useState([])
  const [cmd, setCmd] = useState('')
  const [histIdx, setHistIdx] = useState(-1)
  const [phase, setPhase] = useState(() => {
    if (vm?.guest_hung) return 'hung'
    if (vm?.boot_failure) return 'initramfs'
    if (vm?.power === 'poweredOn') return isWindowsGuest(vm) ? 'winboot' : 'login'
    return 'post'
  })
  const [grubSel, setGrubSel] = useState(0)
  const [grubCount, setGrubCount] = useState(8)
  const [bootIdx, setBootIdx] = useState(0)
  const [loginUser, setLoginUser] = useState('')
  const [loginPass, setLoginPass] = useState('')
  const [loginStep, setLoginStep] = useState('user') // user | pass
  const scrollRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    if (vm?.power !== 'poweredOn') {
      setPhase('post')
      setLines([`${vm?.name} — power on to boot guest OS`])
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
    if (phase === 'post') {
      setLines(['SeaBIOS (version fixitlab-1.0)', 'Booting from Hard Disk...'])
      setBootIdx(0)
    }
  }, [vm?.id, vm?.power, vm?.name, vm?.guest_hung])

  useEffect(() => {
    if (phase === 'winboot') {
      setLines(WIN_BOOT_SEQUENCE)
      const t = setTimeout(() => setPhase('login'), 2500)
      return () => clearTimeout(t)
    }
    if (phase === 'initramfs' && vm?.boot_failure) {
      setLines([
        'Give root password for maintenance',
        '(or type Control-D to continue):',
        'Entering recovery mode — run fsck or exit to continue boot.',
      ])
      setPhase('shell')
    }
    return undefined
  }, [phase, vm?.boot_failure])

  useEffect(() => {
    if (phase !== 'post') return undefined
    const t = setInterval(() => {
      setBootIdx(i => {
        if (i >= BOOT_SEQUENCE.length - 1) {
          setPhase('grub')
          return i
        }
        setLines(prev => [...prev, BOOT_SEQUENCE[i + 1]])
        return i + 1
      })
    }, 450)
    return () => clearInterval(t)
  }, [phase])

  useEffect(() => {
    if (phase !== 'grub') return undefined
    const t = setInterval(() => {
      setGrubCount(c => {
        if (c <= 1) {
          setPhase('initramfs')
          setLines(prev => [...prev, `Loading ${GRUB_ENTRIES[grubSel]}…`, '[    3.445000] Loading initial ramdisk ...'])
          setTimeout(() => setPhase('login'), 1800)
          return 0
        }
        return c - 1
      })
    }, 1000)
    return () => clearInterval(t)
  }, [phase, grubSel])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight })
  }, [lines, phase, grubSel, grubCount, loginStep])

  const append = useCallback((text) => {
    setLines(prev => [...prev, ...(Array.isArray(text) ? text : [text])])
  }, [])

  const runCmd = useCallback((raw) => {
    const result = shell.run(raw)
    if (result.clear) { setLines([]); return }
    if (result.exit) { onClose(); return }
    append(result.lines)
    if (result.sideEffect && onGuestAction) onGuestAction(result.sideEffect)
    if (vm?.boot_failure && (raw.includes('fsck') || raw.includes('exit') || raw.includes('reboot'))) {
      onGuestAction?.({ action: 'guest_fix_boot', vm_id: vm.id })
      setPhase('login')
      append('System boot resumed.')
    }
  }, [append, onClose, onGuestAction, shell, vm?.boot_failure, vm?.id])

  const tryLogin = useCallback(() => {
    if (loginStep === 'user') {
      append(`${loginUser || guestUser(vm)} login: ${loginUser}`)
      setLoginStep('pass')
      setLoginPass('')
      return
    }
    append('Password:')
    if (loginUser === 'root' && loginPass === 'root13') {
      append([
        `Last login: ${new Date().toUTCString()} on tty1`,
        LOGIN_HINT,
        `Welcome to FixitLab simulated ${vm?.guest_os_version || 'Linux'}.`,
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
  }, [append, loginPass, loginStep, loginUser, vm])

  const onKeyDown = (e) => {
    if (phase === 'hung') {
      e.preventDefault()
      append('(no response — guest OS is hung)')
      return
    }
    if (phase === 'grub') {
      if (e.key === 'ArrowUp') { e.preventDefault(); setGrubSel(s => Math.max(0, s - 1)) }
      else if (e.key === 'ArrowDown') { e.preventDefault(); setGrubSel(s => Math.min(GRUB_ENTRIES.length - 1, s + 1)) }
      else if (e.key === 'Enter') {
        e.preventDefault()
        setPhase('initramfs')
        append(`Loading ${GRUB_ENTRIES[grubSel]}…`)
        setTimeout(() => setPhase('login'), 1500)
      }
      return
    }
    if (phase === 'login') {
      if (e.key === 'Enter') {
        e.preventDefault()
        tryLogin()
      }
      return
    }
    if (phase === 'shell') {
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

  return (
    <div className="vm-modal-overlay" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="vm-modal w-full max-w-[900px] h-[580px] max-h-[90vh] flex flex-col p-0 overflow-hidden" onMouseDown={e => e.stopPropagation()}>
        <div className="flex items-center gap-2.5 px-3.5 py-2.5 bg-[#1B2A3B] border-b border-[#2D3A4A] shrink-0">
          <div className="flex gap-1.5">
            <span className="w-[11px] h-[11px] rounded-full bg-[#D9534F]" />
            <span className="w-[11px] h-[11px] rounded-full bg-[#F5A623]" />
            <span className="w-[11px] h-[11px] rounded-full bg-[#5DB85D]" />
          </div>
          <span className="font-mono text-xs text-[#8FA5B8]">{vm.name} — Web Console</span>
          <span className="text-[10px] text-[#8FA5B8] ml-2">{LOGIN_HINT}</span>
          <div className="flex-1" />
          <button type="button" onClick={onClose} className="text-[#8FA5B8] hover:text-white">✕</button>
        </div>
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 font-mono text-[12.5px] leading-relaxed bg-[#05090f] cursor-text" onClick={() => inputRef.current?.focus()}>
          {lines.map((l, i) => (
            <div key={i} className={l.startsWith('[') ? 'text-[#8FA5B8]' : l.includes('$') || l.includes('login:') ? 'text-[#E8EDF2]' : 'text-[#5DB85D]'}>{l || '\u00A0'}</div>
          ))}
          {phase === 'post' && bootIdx < BOOT_SEQUENCE.length && <div className="text-[#8FA5B8] animate-pulse">POST …</div>}
          {phase === 'hung' && <div className="text-[#D9534F] mt-2">Guest not responding — use Reset after customer approval.</div>}
          {phase === 'grub' && (
            <div className="my-2 border border-[#5b9bf5] rounded overflow-hidden">
              <div className="bg-[#0a1a3a] px-2.5 py-1.5 text-[#9bb8ff] text-[11px]">GNU GRUB 2.06 — ↑/↓ select, Enter boot, Esc for menu</div>
              {GRUB_ENTRIES.map((entry, i) => (
                <div key={entry} className={`px-3 py-1 text-[12.5px] ${i === grubSel ? 'bg-[#2D7CFF] text-white' : 'text-[#cdd7e1]'}`}>{entry}</div>
              ))}
              <div className="bg-[#0a1a3a] px-2.5 py-1.5 text-[#9bb8ff] text-[11px]">Auto-boot in {grubCount}s</div>
            </div>
          )}
          {phase === 'login' && (
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
          {phase === 'shell' && (
            <div className="flex items-center mt-1">
              <span className="text-[#5DB85D] whitespace-nowrap">{shell.prompt()}</span>
              <input ref={inputRef} autoFocus value={cmd} onChange={e => setCmd(e.target.value)} onKeyDown={onKeyDown} spellCheck={false} autoComplete="off" className="flex-1 bg-transparent border-none outline-none text-[#E8EDF2] font-mono text-[12.5px] caret-[#5DB85D] ml-1" />
            </div>
          )}
          {(phase === 'grub' || phase === 'post') && <input ref={inputRef} className="sr-only" onKeyDown={onKeyDown} autoFocus readOnly tabIndex={0} />}
        </div>
        <div className="shrink-0 px-3.5 py-2 bg-[#1B2A3B] border-t border-[#2D3A4A] text-[10.5px] text-[#8FA5B8] font-mono">
          {phase === 'shell' ? 'Type help for 150+ simulated commands · ↑/↓ history' : phase === 'login' ? LOGIN_HINT : phase === 'grub' ? 'GRUB menu — arrow keys work' : 'Booting guest OS…'}
        </div>
      </div>
    </div>
  )
}
