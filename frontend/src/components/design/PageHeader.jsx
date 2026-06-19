/** Page hero header — matches Claude mockup eyebrow + title pattern. */
export default function PageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
  className = '',
}) {
  return (
    <div className={`fx-page-header animate-fx-rise ${className}`}>
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          {eyebrow && (
            <p className="fx-page-eyebrow m-0 mb-2">{eyebrow}</p>
          )}
          {title && (
            <h1 className="font-display font-extrabold text-2xl sm:text-3xl text-white m-0 tracking-tight">{title}</h1>
          )}
          {subtitle && (
            <p className="text-surface-400 text-sm mt-2 m-0 max-w-2xl">{subtitle}</p>
          )}
        </div>
        {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
      </div>
    </div>
  )
}
