import { useCallback, useMemo, useRef, useState } from 'react'
import { createLinuxShell } from './linuxShell'

export default function VmwareSshTerminal({ vm, sshOk = true, onClose }) {
  const shell = useMemo(() => createLinuxShell(vm), [vm])
  const [lines, setLines] = useState([
    `$ ssh root@${vm?.hostname || vm?.name || 'guest'}`,
    sshOk ? `${vm?.hostname || vm?.name}'s password:` : `ssh: connect to host port 22: Connection timed out`,
  ])
  const [phase, setPhase] = useState(sshOk ? 'password' : 'failed')
  const [password, setPassword] = useState('')
  const [cmd, setCmd] = useState('')
  const [histIdx, setHistIdx] = useState(-1)
  const inputRef = useRef(null)

  const append = useCallback((text) => {
    setLines(prev => [...prev, ...(Array.isArray(text) ? text : [text])])
  }, [])

  const onKeyDown = (e) => {
    if (phase === 'failed') return
    if (phase === 'password') {
      if (e.key === 'Enter') {
        e.preventDefault()
        if (password === 'root13') {
          append(['', `Welcome to ${vm?.guest_os_version || 'Linux'}`, ''])
          setPhase('shell')
          setPassword('')
        } else {
          append('Permission denied, please try again.')
          setPassword('')
        }
      }
      return
    }
    if (e.key === 'Enter') {
      e.preventDefault()
      append(`${shell.prompt()} ${cmd}`)
      const result = shell.run(cmd)
      if (result.clear) setLines([])
      else append(result.lines)
      setCmd('')
      setHistIdx(-1)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      const h = shell.history
      if (!h.length) return
      const next = histIdx < 0 ? h.length - 1 : Math.max(0, histIdx - 1)
      setHistIdx(next)
      setCmd(h[next])
    }
  }

  return (
    <div className="rounded-lg border border-[#2d3a4a] bg-[#05090f] font-mono text-[11px] leading-relaxed min-h-[280px] flex flex-col">
      <div className="flex items-center justify-between px-3 py-2 border-b border-[#2d3a4a] bg-[#1b2a3b]">
        <span className="text-[#8fa5b8]">SSH — root@{vm?.hostname || vm?.name}</span>
        {onClose && <button type="button" onClick={onClose} className="text-[#8fa5b8] hover:text-white text-xs">Close</button>}
      </div>
      <div className="flex-1 overflow-y-auto p-3" onClick={() => inputRef.current?.focus()}>
        {lines.map((l, i) => (
          <div key={i} className={l.startsWith('$') || l.includes('password') ? 'text-[#5DB85D]' : 'text-[#E8EDF2]'}>{l}</div>
        ))}
        {phase === 'password' && (
          <div className="flex items-center gap-1 text-[#5DB85D] mt-1">
            <span>Password:</span>
            <input ref={inputRef} autoFocus type="password" value={password} onChange={e => setPassword(e.target.value)} onKeyDown={onKeyDown} className="flex-1 bg-transparent border-none outline-none text-[#E8EDF2] font-mono" />
          </div>
        )}
        {phase === 'shell' && (
          <div className="flex items-center mt-1">
            <span className="text-[#5DB85D]">{shell.prompt()}</span>
            <input ref={inputRef} autoFocus value={cmd} onChange={e => setCmd(e.target.value)} onKeyDown={onKeyDown} className="flex-1 bg-transparent border-none outline-none text-[#E8EDF2] font-mono ml-1" spellCheck={false} />
          </div>
        )}
        {phase === 'failed' && (
          <p className="text-[#8fa5b8] mt-2 text-[10px]">Guest may be hung or network misconfigured. Use web console and verify IP/VLAN assignment.</p>
        )}
      </div>
      <div className="px-3 py-1.5 border-t border-[#2d3a4a] text-[10px] text-[#8fa5b8]">Hint: password root13</div>
    </div>
  )
}
