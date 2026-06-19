/** Reference-style surface panel — rgba fill + subtle border. */
export default function FxPanel({ children, className = '', padding = 'p-6', as: Tag = 'div', ...props }) {
  return (
    <Tag
      className={`rounded-[18px] bg-white/[0.025] border border-white/[0.08] ${padding} ${className}`}
      {...props}
    >
      {children}
    </Tag>
  )
}
