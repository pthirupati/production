import { Link } from 'react-router-dom'
import { X, Sparkles, ChevronRight, Wrench } from 'lucide-react'
import { useState } from 'react'
import { resolveMediaUrl } from '../utils/mediaUrl'

const DISMISS_KEY = 'fixitlab_banners_dismissed'

function getDismissed() {
  try {
    return JSON.parse(sessionStorage.getItem(DISMISS_KEY) || '{}')
  } catch {
    return {}
  }
}

function setDismissed(key) {
  const d = getDismissed()
  d[key] = true
  sessionStorage.setItem(DISMISS_KEY, JSON.stringify(d))
}

export function MaintenanceBanner({ config, className = '', enabled = true }) {
  const dismissId = `maint-${config?.maintenance_message?.slice(0, 24) || 'default'}`
  const [dismissed, setLocalDismissed] = useState(() => getDismissed()[dismissId])

  if (!enabled || !config?.maintenance_mode || dismissed) return null
  if (config.maintenance_banner_enabled === false) return null

  const imageUrl = resolveMediaUrl(config.maintenance_banner?.image_url)
  const scheduledEnd = config.maintenance_scheduled_end || config.maintenance_banner?.scheduled_end

  return (
    <div
      className={`relative overflow-hidden border-b border-amber-500/25 bg-gradient-to-r from-amber-950/90 via-amber-900/40 to-surface-950 ${className}`}
      role="alert"
    >
      {imageUrl && (
        <>
          <img
            src={imageUrl}
            alt=""
            className="absolute inset-0 w-full h-full object-cover object-center opacity-25"
            onError={(e) => { e.currentTarget.style.display = 'none' }}
          />
          <div className="absolute inset-0 bg-gradient-to-r from-amber-950/95 via-amber-900/75 to-surface-950/90" />
        </>
      )}
      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 py-3 sm:py-3.5 flex items-center gap-3 sm:gap-4">
        <div className="flex h-9 w-9 sm:h-10 sm:w-10 shrink-0 items-center justify-center rounded-xl bg-amber-500/20 border border-amber-400/30">
          <Wrench size={18} className="text-amber-300" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wider text-amber-400/90 mb-0.5">Scheduled maintenance</p>
          <p className="text-sm sm:text-[15px] font-medium text-amber-50 leading-snug">
            {config.maintenance_message || 'The platform is under maintenance.'}
          </p>
          {scheduledEnd && (
            <p className="text-[11px] sm:text-xs text-amber-200/60 mt-1">
              Expected until {new Date(scheduledEnd).toLocaleString()}
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={() => { setDismissed(dismissId); setLocalDismissed(true) }}
          className="shrink-0 rounded-lg p-2 text-amber-200/50 hover:text-white hover:bg-white/10 transition-colors"
          aria-label="Dismiss maintenance notice"
        >
          <X size={16} />
        </button>
      </div>
    </div>
  )
}

export function PromoBannerCarousel({ banners = [], className = '', enabled = true }) {
  const [index, setIndex] = useState(0)
  const active = banners.filter(b => b.active !== false)
  const banner = active[index % Math.max(active.length, 1)]
  const dismissId = `promo-${banner?.id || banner?.title || index}`
  const [dismissed, setLocalDismissed] = useState(() => getDismissed()[dismissId])

  if (!enabled || dismissed || !active.length || !banner) return null

  const imageUrl = resolveMediaUrl(banner.image_url)
  const bgStyle = !imageUrl && banner.bg_color ? { background: banner.bg_color } : undefined

  return (
    <div
      className={`relative overflow-hidden border-b border-accent-cyan/20 ${className}`}
      style={bgStyle}
    >
      {!imageUrl && !banner.bg_color && (
        <div className="absolute inset-0 bg-gradient-to-r from-indigo-950 via-teal-900/80 to-surface-950" />
      )}
      {imageUrl && (
        <>
          <img
            src={imageUrl}
            alt=""
            className="absolute inset-0 w-full h-full object-cover object-center"
            onError={(e) => { e.currentTarget.style.display = 'none' }}
          />
          <div className="absolute inset-0 bg-gradient-to-r from-surface-950/92 via-surface-950/75 to-surface-950/50" />
        </>
      )}
      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 py-3 sm:py-4 flex items-center gap-3 sm:gap-5 min-h-[56px] sm:min-h-[64px]">
        <div className="hidden sm:flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent-cyan/15 border border-accent-cyan/25">
          <Sparkles size={18} className="text-accent-cyan" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[10px] sm:text-xs font-bold uppercase tracking-widest text-accent-cyan/80 mb-0.5">Limited offer</p>
          <p className="font-semibold text-white text-sm sm:text-base leading-tight truncate">{banner.title}</p>
          {banner.text && (
            <p className="text-xs sm:text-sm text-surface-300 mt-0.5 line-clamp-1 sm:line-clamp-2">{banner.text}</p>
          )}
        </div>
        {banner.link && (
          <Link
            to={banner.link}
            className="inline-flex items-center gap-1 shrink-0 rounded-lg bg-accent-cyan px-3 sm:px-4 py-2 text-xs sm:text-sm font-semibold text-surface-950 hover:bg-accent-cyan/90 transition-colors shadow-lg shadow-accent-cyan/20"
          >
            {banner.cta || 'View offer'}
            <ChevronRight size={14} />
          </Link>
        )}
        <button
          type="button"
          onClick={() => { setDismissed(dismissId); setLocalDismissed(true) }}
          className="shrink-0 rounded-lg p-2 text-surface-400 hover:text-white hover:bg-white/10 transition-colors"
          aria-label="Dismiss offer"
        >
          <X size={16} />
        </button>
      </div>
      {active.length > 1 && (
        <div className="absolute bottom-1.5 left-1/2 -translate-x-1/2 flex gap-1.5">
          {active.map((_, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setIndex(i)}
              className={`h-1.5 rounded-full transition-all ${i === index % active.length ? 'w-4 bg-accent-cyan' : 'w-1.5 bg-white/30'}`}
              aria-label={`Offer ${i + 1}`}
            />
          ))}
        </div>
      )}
    </div>
  )
}

/** Maintenance app-wide (except lab); promos on marketing/pricing pages only. */
export function PlatformBanners({ config, className = '', showMaintenance = true, showPromo = false }) {
  if (!config) return null
  const promoOn = showPromo && config.promo_banners_enabled !== false
  const maintOn = showMaintenance && config.maintenance_banner_enabled !== false && config.maintenance_mode
  const hasPromo = promoOn && (config.promo_banners || []).some(b => b.active !== false)

  if (!hasPromo && !maintOn) return null

  return (
    <div className={`w-full ${className}`}>
      {hasPromo && <PromoBannerCarousel banners={config.promo_banners || []} enabled={promoOn} />}
      {maintOn && <MaintenanceBanner config={config} enabled={maintOn} />}
    </div>
  )
}
