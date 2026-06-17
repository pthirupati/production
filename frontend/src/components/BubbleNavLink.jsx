import { Link } from 'react-router-dom'

/**
 * Glass / water-bubble navigation pill with hover glow.
 */
export default function BubbleNavLink({
  to,
  children,
  active = false,
  onClick,
  className = '',
  size = 'sm',
}) {
  const sizeCls = size === 'md'
    ? 'px-4 py-2 text-sm'
    : 'px-3 py-1.5 text-xs sm:text-sm'

  const base = `relative inline-flex items-center justify-center gap-1.5 rounded-full font-medium whitespace-nowrap transition-all duration-300 ${sizeCls}`

  const state = active
    ? 'bubble-nav-active text-white shadow-lg shadow-accent-cyan/20'
    : 'bubble-nav-idle text-surface-300 hover:text-white'

  const Tag = to ? Link : 'button'
  const props = to
    ? { to, onClick }
    : { type: 'button', onClick }

  return (
    <Tag {...props} className={`${base} ${state} ${className}`}>
      <span className="relative z-[1]">{children}</span>
    </Tag>
  )
}
