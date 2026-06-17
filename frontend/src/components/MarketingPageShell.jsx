/**
 * Shared wrapper for public marketing pages — consistent spacing, typography, aurora bg.
 */
export default function MarketingPageShell({
  title,
  subtitle,
  eyebrow,
  children,
  className = '',
  narrow = false,
}) {
  return (
    <div className={`relative overflow-hidden ${className}`}>
      <div className="absolute inset-0 aurora-bg opacity-40 pointer-events-none" aria-hidden="true" />
      <div className="absolute inset-0 bg-dots-pattern opacity-[0.15] pointer-events-none" aria-hidden="true" />
      <div className={`relative ${narrow ? 'max-w-3xl' : 'max-w-7xl'} mx-auto px-4 sm:px-6 py-12 sm:py-16 lg:py-20`}>
        {(eyebrow || title) && (
          <header className="mb-10 sm:mb-12 text-center max-w-3xl mx-auto animate-fade-in">
            {eyebrow && (
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-accent-cyan mb-3">{eyebrow}</p>
            )}
            {title && (
              <h1 className="font-display text-3xl sm:text-4xl lg:text-5xl font-bold text-white tracking-tight text-balance">
                {title}
              </h1>
            )}
            {subtitle && (
              <p className="mt-4 text-base sm:text-lg text-surface-300 leading-relaxed text-balance">{subtitle}</p>
            )}
          </header>
        )}
        {children}
      </div>
    </div>
  )
}
