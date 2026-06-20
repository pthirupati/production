import { useEffect } from 'react'

/** vSphere-style action toast — matches Claude VMware Lab mockup. */
export default function VmwareToast({ message, kind = 'success', onDone }) {
  useEffect(() => {
    const t = setTimeout(() => onDone?.(), 3000)
    return () => clearTimeout(t)
  }, [message, onDone])

  if (!message) return null

  const dot = kind === 'error' ? '#D9534F' : kind === 'warn' ? '#F5A623' : kind === 'info' ? '#2D7CFF' : '#5DB85D'
  const border = kind === 'error' ? 'rgba(217,83,79,.45)' : kind === 'warn' ? 'rgba(245,166,35,.45)' : kind === 'info' ? 'rgba(45,124,255,.45)' : 'rgba(93,184,93,.45)'

  return (
    <div
      className="fixed bottom-5 right-5 z-[95] flex items-center gap-2.5 px-4 py-3 rounded-lg bg-[#243447] shadow-2xl animate-[vmScale_0.2s_both]"
      style={{ border: `1px solid ${border}` }}
    >
      <span className="w-2 h-2 rounded-full shrink-0" style={{ background: dot }} />
      <span className="text-[13px] text-[#E8EDF2] font-medium">{message}</span>
    </div>
  )
}
