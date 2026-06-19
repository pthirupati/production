import { Link } from 'react-router-dom'
import { Terminal } from 'lucide-react'

/** Shared FixitLab logo — matches Claude design system (ac → ac2 gradient). */
export default function FixitLogo({ to = '/', size = 'md', showText = true, className = '' }) {
  const box = size === 'sm' ? 'w-8 h-8 rounded-[10px]' : size === 'lg' ? 'w-10 h-10 rounded-xl' : 'w-9 h-9 rounded-[11px]'
  const icon = size === 'sm' ? 16 : size === 'lg' ? 20 : 18
  const text = size === 'sm' ? 'text-lg' : size === 'lg' ? 'text-xl' : 'text-lg'

  const inner = (
    <>
      <span
        className={`${box} flex items-center justify-center shrink-0 fixit-logo-mark`}
        aria-hidden="true"
      >
        <Terminal size={icon} className="text-white" strokeWidth={2} />
      </span>
      {showText && (
        <span className={`font-display font-extrabold ${text} tracking-tight text-white`}>FixitLab</span>
      )}
    </>
  )

  if (to) {
    return (
      <Link to={to} className={`flex items-center gap-2.5 group ${className}`}>
        {inner}
      </Link>
    )
  }
  return <div className={`flex items-center gap-2.5 ${className}`}>{inner}</div>
}
