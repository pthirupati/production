import { Link } from 'react-router-dom'

/**
 * Primary navigation link — minimal editorial style with active underline.
 * Works in dark and light mode via nav-link-* CSS utilities.
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
    ? 'px-3 py-2 text-sm'
    : 'px-2.5 py-1.5 text-xs sm:text-sm'

  const Tag = to ? Link : 'button'
  const props = to
    ? { to, onClick }
    : { type: 'button', onClick }

  return (
    <Tag
      {...props}
      className={`nav-link ${active ? 'nav-link-active' : 'nav-link-idle'} ${sizeCls} ${className}`}
    >
      {children}
    </Tag>
  )
}
