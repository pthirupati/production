import { Link } from 'react-router-dom'
import { AlertTriangle, X, Tag } from 'lucide-react'
import { useState } from 'react'

export function MaintenanceBanner({ config, className = '', enabled = true }) {
  const [dismissed, setDismissed] = useState(false)
  if (!enabled || !config?.maintenance_mode || dismissed) return null
  if (config.maintenance_banner_enabled === false) return null

  const style = config.maintenance_banner?.style || {}
  const bg = style.bg || 'bg-amber-500/15'
  const border = style.border || 'border-amber-500/30'
  const text = style.text || 'text-amber-300'

  return (
    <div className={`${bg} ${border} border-b px-3 sm:px-4 py-2 sm:py-3 ${className}`}>
      <div className="max-w-7xl mx-auto flex items-start gap-3">
        {config.maintenance_banner?.image_url ? (
          <img src={config.maintenance_banner.image_url} alt="" className="h-8 w-8 sm:h-10 sm:w-10 rounded object-cover shrink-0" />
        ) : (
          <AlertTriangle size={20} className={`${text} shrink-0 mt-0.5`} />
        )}
        <div className="flex-1 min-w-0">
          <p className={`text-xs sm:text-sm font-medium ${text}`}>{config.maintenance_message}</p>
          {config.maintenance_banner?.scheduled_end && (
            <p className="text-[10px] sm:text-xs text-surface-400 mt-1">
              Until {new Date(config.maintenance_banner.scheduled_end).toLocaleString()}
            </p>
          )}
        </div>
        <button type="button" onClick={() => setDismissed(true)} className="text-surface-500 hover:text-white p-1 shrink-0">
          <X size={16} />
        </button>
      </div>
    </div>
  )
}

export function PromoBannerCarousel({ banners = [], className = '', enabled = true }) {
  const [index, setIndex] = useState(0)
  const [dismissed, setDismissed] = useState(false)
  if (!enabled || dismissed || !banners.length) return null

  const banner = banners[index % banners.length]
  const bgStyle = banner.bg_color ? { background: banner.bg_color } : undefined

  return (
    <div className={`relative overflow-hidden ${className}`} style={bgStyle}>
      <div className="max-w-7xl mx-auto px-3 sm:px-4 py-2 sm:py-3 flex items-center gap-3 sm:gap-4">
        {banner.image_url && (
          <img src={banner.image_url} alt="" className="h-10 w-10 sm:h-12 sm:w-12 rounded-lg object-cover shrink-0" />
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <Tag size={14} className="text-accent-amber shrink-0" />
            <p className="font-semibold text-white text-xs sm:text-base truncate">{banner.title}</p>
          </div>
          {banner.text && <p className="text-[11px] sm:text-sm text-surface-300 mt-0.5 line-clamp-2">{banner.text}</p>}
        </div>
        {banner.link && (
          <Link to={banner.link} className="btn-primary text-[10px] sm:text-sm py-1 px-2 sm:px-3 shrink-0 whitespace-nowrap">
            {banner.cta || 'View offer'}
          </Link>
        )}
        <button type="button" onClick={() => setDismissed(true)} className="text-surface-400 hover:text-white p-1 shrink-0" aria-label="Dismiss offer">
          <X size={14} />
        </button>
      </div>
      {banners.length > 1 && (
        <div className="absolute bottom-1 left-1/2 -translate-x-1/2 flex gap-1">
          {banners.map((_, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setIndex(i)}
              className={`w-1.5 h-1.5 rounded-full ${i === index ? 'bg-white' : 'bg-white/40'}`}
              aria-label={`Promo ${i + 1}`}
            />
          ))}
        </div>
      )}
    </div>
  )
}

/** showMaintenance / showPromo control where banners appear (home, pricing, subscription only for promos). */
export function PlatformBanners({ config, className = '', showMaintenance = true, showPromo = false }) {
  if (!config) return null
  const promoOn = showPromo && config.promo_banners_enabled !== false
  const maintOn = showMaintenance && config.maintenance_banner_enabled !== false
  if (!promoOn && !(maintOn && config.maintenance_mode)) return null
  return (
    <div className={className}>
      {maintOn && <MaintenanceBanner config={config} enabled={maintOn} />}
      {promoOn && <PromoBannerCarousel banners={config.promo_banners || []} enabled={promoOn} />}
    </div>
  )
}
