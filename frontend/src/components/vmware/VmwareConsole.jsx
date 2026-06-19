import { useCallback, useEffect, useRef, useState } from 'react'

const BOOT_LINES = [
  '[    0.000000] Linux version 5.15.0-generic',
  '[    1.234567] systemd[1]: Started FixitLab simulated guest.',
  '[    2.100000] cloud-init: Cloud-init v. 23.1 running.',
]

const GRUB_ENTRIES = [
  'Ubuntu, with Linux 5.15.0-91-generic',
  'Ubuntu, with Linux 5.15.0-91-generic (recovery mode)',
  'Ubuntu, with Linux 5.15.0-88-generic',
  'Advanced options for Ubuntu',
  'UEFI Firmware Settings',
]

const HELP = `Available commands:
  help          Show this message
  clear         Clear screen
  uptime        System uptime
  whoami        Current user
  hostname      Guest hostname
  ip addr       Network interfaces
  df -h         Disk usage
  free -m       Memory usage
  systemctl     Service status (try: systemctl status nginx)
  exit          Close console`

function promptFor(vm) {
  const user = vm?.guest_os?.includes('Windows') ? 'Administrator' : 'root'
  const host = vm?.hostname || vm?.name || 'guest'
  return `${user}@${host}`
}

export default function VmwareConsole({ vm, onClose }) {
  const [lines, setLines] = useState([`${promptFor(vm)} — VMware Web Console`, 'Type "help" for available commands.', ''])
  const [cmd, setCmd] = useState('')
  const [history, setHistory] = useState([])
  const [histIdx, setHistIdx] = useState(-1)
  const [phase, setPhase] = useState(vm?.power === 'poweredOn' ? 'ready' : 'booting') // booting | grub | ready
  const [grubSel, setGrubSel] = useState(0)
  const [grubCount, setGrubCount] = useState(5)
  const scrollRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    if (vm?.power !== 'poweredOn') {
      setPhase('booting')
      setLines([`Powering on ${vm?.name}…`, ...BOOT_LINES, ''])
      const t = setTimeout(() => setPhase('grub'), 1200)
      return () => clearTimeout(t)
    }
    if (vm?.guest_hung) {
      setPhase('hung')
      setLines([
        `${promptFor(vm)} — VMware Web Console`,
        'Guest OS appears hung — keyboard input not accepted.',
        'Last visible output:',
        '[  892.441] INFO: task sshd:1234 blocked for more than 120 seconds.',
        '[  892.442] "echo 0 > /proc/sys/kernel/hung_task_timeout_secs" disables this message.',
        '',
      ])
      return undefined
    }
    setPhase('ready')
  }, [vm?.id, vm?.power, vm?.name, vm?.guest_hung])

  useEffect(() => {
    if (phase !== 'grub') return undefined
    const t = setInterval(() => {
      setGrubCount(c => {
        if (c <= 1) {
          setPhase('ready')
          setLines(prev => [...prev, 'Booting kernel…', ''])
          return 0
        }
        return c - 1
      })
    }, 1000)
    return () => clearInterval(t)
  }, [phase])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight })
  }, [lines, phase, grubSel, grubCount])

  const append = useCallback((text) => {
    setLines(prev => [...prev, ...(Array.isArray(text) ? text : [text])])
  }, [])

  const runCmd = useCallback((raw) => {
    const c = raw.trim()
    if (!c) return
    append([`${promptFor(vm)}$ ${c}`])
    const parts = c.split(/\s+/)
    const base = parts[0].toLowerCase()

    if (base === 'help') append(HELP.split('\n'))
    else if (base === 'clear') setLines([])
    else if (base === 'exit') onClose()
    else if (base === 'uptime') append('up 14 days,  3:22,  1 user,  load average: 0.08, 0.12, 0.09')
    else if (base === 'whoami') append('root')
    else if (base === 'hostname') append(vm?.hostname || vm?.name || 'localhost')
    else if (c === 'ip addr' || c === 'ip a') {
      append([
        '2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500',
        `    inet ${vm?.ip || '10.20.30.41'}/24 brd 10.20.30.255 scope global eth0`,
      ])
    } else if (c === 'df -h') append(`Filesystem      Size  Used Avail Use% Mounted on\n/dev/sda1        ${vm?.disk_gb || 40}G   12G   ${(vm?.disk_gb || 40) - 12}G  30% /`)
    else if (c === 'free -m') append(`              total        used        free\nMem:           ${Math.round((vm?.memory_mb || 4096) / 1024 * 10) / 10}G        ${Math.round((vm?.mem_pct || 40) * (vm?.memory_mb || 4096) / 102400)}M        …`)
    else if (c.startsWith('systemctl')) {
      const svc = parts[2] || 'nginx'
      append([
        `● ${svc}.service - Simulated service`,
        `   Active: failed (Result: exit-code) since ${new Date().toUTCString()}`,
        '   Hint: This is a training lab — fix the service in the scenario!',
      ])
    } else append(`bash: ${base}: command not found`)
    append('')
  }, [append, onClose, vm])

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
        setPhase('ready')
        setLines(prev => [...prev, `Loading ${GRUB_ENTRIES[grubSel]}…`, ''])
      }
      return
    }
    if (e.key === 'Enter') {
      e.preventDefault()
      runCmd(cmd)
      setHistory(h => [...h, cmd])
      setHistIdx(-1)
      setCmd('')
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      if (!history.length) return
      const next = histIdx < 0 ? history.length - 1 : Math.max(0, histIdx - 1)
      setHistIdx(next)
      setCmd(history[next])
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      if (histIdx < 0) return
      const next = histIdx + 1
      if (next >= history.length) { setHistIdx(-1); setCmd('') }
      else { setHistIdx(next); setCmd(history[next]) }
    }
  }

  if (!vm) return null

  return (
    <div className="vm-modal-overlay" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="vm-modal w-full max-w-[820px] h-[560px] max-h-[88vh] flex flex-col p-0 overflow-hidden" onMouseDown={e => e.stopPropagation()}>
        <div className="flex items-center gap-2.5 px-3.5 py-2.5 bg-[#1B2A3B] border-b border-[#2D3A4A] shrink-0">
          <div className="flex gap-1.5">
            <span className="w-[11px] h-[11px] rounded-full bg-[#D9534F]" />
            <span className="w-[11px] h-[11px] rounded-full bg-[#F5A623]" />
            <span className="w-[11px] h-[11px] rounded-full bg-[#5DB85D]" />
          </div>
          <span className="font-mono text-xs text-[#8FA5B8]">{vm.name} — Web Console</span>
          <span className="inline-flex items-center gap-1.5 ml-1.5 text-[10.5px] font-semibold text-[#5DB85D]">
            <span className={`w-1.5 h-1.5 rounded-full ${vm.guest_hung ? 'bg-[#D9534F]' : 'bg-[#5DB85D]'} ${vm.guest_hung ? '' : 'animate-pulse'}`} />
            {vm.guest_hung ? 'Guest hung' : 'Connected'}
          </span>
          <div className="flex-1" />
          <button type="button" onClick={() => setLines([])} className="text-[11px] font-semibold px-2.5 py-1 rounded-md border border-[#2D3A4A] bg-[#243447] text-[#8FA5B8]">Clear</button>
          <button type="button" onClick={onClose} className="text-[#8FA5B8] hover:text-white text-base">✕</button>
        </div>
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 font-mono text-[13px] leading-relaxed bg-[#05090f] cursor-text" onClick={() => inputRef.current?.focus()}>
          {lines.map((l, i) => (
            <div key={i} className={l.startsWith('[') || l.includes('Active:') ? 'text-[#8FA5B8]' : l.includes('$') ? 'text-[#E8EDF2]' : 'text-[#5DB85D]'}>{l || '\u00A0'}</div>
          ))}
          {phase === 'booting' && <div className="text-[#8FA5B8] animate-pulse">Booting guest OS…</div>}
          {phase === 'hung' && <div className="text-[#D9534F] mt-2">Guest not responding — use Reset after customer approval.</div>}
          {phase === 'grub' && (
            <div className="my-2 border border-[#5b9bf5] rounded overflow-hidden">
              <div className="bg-[#0a1a3a] px-2.5 py-1.5 text-[#9bb8ff] text-[11px] border-b border-[#2b4a7f]">
                GNU GRUB version 2.06 — use ↑/↓ to select, Enter to boot
              </div>
              {GRUB_ENTRIES.map((entry, i) => (
                <div key={entry} className={`px-3 py-1 text-[12.5px] ${i === grubSel ? 'bg-[#2D7CFF] text-white' : 'text-[#cdd7e1]'}`}>
                  {entry}
                </div>
              ))}
              <div className="bg-[#0a1a3a] px-2.5 py-1.5 text-[#9bb8ff] text-[11px] border-t border-[#2b4a7f]">
                The highlighted entry will be executed automatically in {grubCount}s.
              </div>
            </div>
          )}
          {phase === 'ready' && (
            <div className="flex items-center mt-1">
              <span className="text-[#5DB85D] whitespace-nowrap">{promptFor(vm)}</span>
              <span className="text-[#8FA5B8] mx-1">$</span>
              <input
                ref={inputRef}
                value={cmd}
                onChange={e => setCmd(e.target.value)}
                onKeyDown={onKeyDown}
                spellCheck={false}
                autoComplete="off"
                className="flex-1 bg-transparent border-none outline-none text-[#E8EDF2] font-mono text-[13px] caret-[#5DB85D]"
              />
            </div>
          )}
          {phase === 'grub' && (
            <input ref={inputRef} className="sr-only" onKeyDown={onKeyDown} autoFocus readOnly tabIndex={0} />
          )}
        </div>
        <div className="shrink-0 px-3.5 py-2 bg-[#1B2A3B] border-t border-[#2D3A4A] text-[10.5px] text-[#8FA5B8] font-mono">
          Type <span className="text-[#E8EDF2]">help</span> for commands · ↑/↓ history
          {phase === 'grub' && <span> · GRUB menu active</span>}
        </div>
      </div>
    </div>
  )
}
