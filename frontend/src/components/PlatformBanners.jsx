import { Link } from 'react-router-dom'
import { AlertTriangle, X, Tag } from 'lucide-react'
import { useState } from 'react'

export function MaintenanceBanner({ config, className = '' }) {
  const [dismissed, setDismissed] = useState(false)
  if (!config?.maintenance_mode || dismissed) return null

  const style = config.maintenance_banner?.style || {}
  const bg = style.bg || 'bg-amber-500/15'
  const border = style.border || 'border-amber-500/30'
  const text = style.text || 'text-amber-300'

  return (
    <div className={`${bg} ${border} border-b px-4 py-3 ${className}`}>
      <div className="max-w-7xl mx-auto flex items-start gap-3">
        {config.maintenance_banner?.image_url ? (
          <img src={config.maintenance_banner.image_url} alt="" className="h-10 w-10 rounded object-cover shrink-0" />
        ) : (
          <AlertTriangle size={20} className={`${text} shrink-0 mt-0.5`} />
        )}
        <div className="flex-1 min-w-0">
          <p className={`text-sm font-medium ${text}`}>{config.maintenance_message}</p>
          {config.maintenance_banner?.scheduled_end && (
            <p className="text-xs text-surface-400 mt-1">
              Until {new Date(config.maintenance_banner.scheduled_end).toLocaleString()}
            </p>
          )}
        </div>
        <button type="button" onClick={() => setDismissed(true)} className="text-surface-500 hover:text-white p-1">
          <X size={16} />
        </button>
      </div>
    </div>
  )
}

export function PromoBannerCarousel({ banners = [], className = '' }) {
  const [index, setIndex] = useState(0)
  if (!banners.length) return null

  const banner = banners[index % banners.length]
  const bgStyle = banner.bg_color ? { background: banner.bg_color } : undefined

  return (
    <div className={`relative overflow-hidden ${className}`} style={bgStyle}>
      <div className="max-w-7xl mx-auto px-4 py-3 flex items-center gap-4">
        {banner.image_url && (
          <img src={banner.image_url} alt="" className="h-12 w-12 rounded-lg object-cover shrink-0 hidden sm:block" />
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <Tag size={14} className="text-accent-amber shrink-0" />
            <p className="font-semibold text-white text-sm sm:text-base truncate">{banner.title}</p>
          </div>
          {banner.text && <p className="text-xs sm:text-sm text-surface-300 mt-0.5 line-clamp-2">{banner.text}</p>}
        </div>
        {banner.link && (
          <Link to={banner.link} className="btn-primary text-xs sm:text-sm py-1.5 px-3 shrink-0 whitespace-nowrap">
            {banner.cta || 'View offer'}
          </Link>
        )}
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

export function PlatformBanners({ config, className = '' }) {
  if (!config) return null
  return (
    <div className={className}>
      <MaintenanceBanner config={config} />
      <PromoBannerCarousel banners={config.promo_banners || []} />
    </div>
  )
}
