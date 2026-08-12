import { useState, useEffect } from 'react'
import { X, Sparkles, ArrowRight } from '../ui/eagerIcons'
import api from '../api/client'
import { resolveMediaUrl } from '../utils/mediaUrl'
import { currentUserScopedKey, migrateUnscopedKey } from '../utils/userScopedStorage'

// Scoped per user: an unscoped key hid campaigns from every account that shared
// the browser once any one of them dismissed them.
const DISMISS_KEY_BASE = 'fixitlab_campaigns_dismissed'

function getDismissed() {
  try {
    return JSON.parse(localStorage.getItem(migrateUnscopedKey(DISMISS_KEY_BASE)) || '{}')
  } catch {
    return {}
  }
}

function markDismissed(id) {
  const d = getDismissed()
  d[id] = true
  try {
    localStorage.setItem(currentUserScopedKey(DISMISS_KEY_BASE), JSON.stringify(d))
  } catch {
    /* ignore quota / private-mode errors */
  }
}

/**
 * Shared renderer used by BOTH the admin live-preview pane and the public
 * banner so "what you preview is what ships". Honors bg/text colors and the
 * text_style overrides. Works in light + dark mode (defaults adapt to theme
 * via CSS vars when no explicit color is set).
 */
export function CampaignRender({ campaign, onDismiss, preview = false }) {
  if (!campaign) return null

  const {
    title,
    body,
    media_type,
    media_url,
    bg_color,
    text_color,
    text_style = {},
    cta_label,
    cta_url,
    dismissible = true,
    placement = 'banner_top',
  } = campaign

  const imageUrl = media_type === 'image' ? resolveMediaUrl(media_url) : ''
  const videoUrl = media_type === 'video' ? resolveMediaUrl(media_url) : ''

  const wrapStyle = {
    background: bg_color || undefined,
    color: text_color || undefined,
  }
  const textStyle = {
    fontSize: text_style.font_size || undefined,
    fontWeight: text_style.font_weight || undefined,
    textAlign: text_style.text_align || undefined,
  }

  // Fallback styling when admin left colors blank — themed, not hardcoded.
  // `text-white` is remapped to a dark ink under [data-theme="light"], so this
  // reads correctly in both light and dark mode.
  const usingCustomBg = Boolean(bg_color)
  const baseClasses = usingCustomBg
    ? ''
    : 'bg-gradient-to-r from-accent-cyan/15 via-accent-purple/10 to-transparent border-accent-cyan/20 text-white'

  const isCard = placement === 'dashboard' || placement === 'modal'

  return (
    <div
      className={`relative overflow-hidden ${isCard ? 'rounded-2xl border' : 'border-b'} ${baseClasses}`}
      style={wrapStyle}
      role="region"
      aria-label="Promotion"
    >
      {imageUrl && (
        <>
          <img
            src={imageUrl}
            alt=""
            className="absolute inset-0 w-full h-full object-cover opacity-25"
            onError={(e) => { e.currentTarget.style.display = 'none' }}
          />
          <div className="absolute inset-0 bg-black/30" />
        </>
      )}
      <div className={`relative flex items-center gap-3 sm:gap-4 ${isCard ? 'p-5' : 'max-w-7xl mx-auto px-4 sm:px-6 py-3'}`}>
        {videoUrl ? (
          <video
            src={videoUrl}
            className={`shrink-0 rounded-lg object-cover ${isCard ? 'w-28 h-16' : 'w-16 h-10'}`}
            autoPlay
            muted
            loop
            playsInline
          />
        ) : !imageUrl ? (
          <span className="hidden sm:flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white/15 border border-white/20">
            <Sparkles size={17} className="opacity-90" />
          </span>
        ) : null}

        <div className="flex-1 min-w-0" style={textStyle}>
          {title && <p className="font-semibold leading-snug m-0 truncate sm:whitespace-normal">{title}</p>}
          {body && <p className="text-[13px] opacity-90 leading-snug m-0 mt-0.5 line-clamp-2">{body}</p>}
        </div>

        {cta_label && (
          <a
            href={cta_url || '#'}
            target={cta_url?.startsWith('http') ? '_blank' : undefined}
            rel="noopener noreferrer"
            onClick={(e) => { if (preview) e.preventDefault() }}
            className="shrink-0 inline-flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-sm font-semibold bg-white/20 hover:bg-white/30 border border-white/25 transition-colors no-underline"
          >
            {cta_label}
            <ArrowRight size={14} />
          </a>
        )}

        {dismissible && (
          <button
            type="button"
            onClick={onDismiss}
            className="shrink-0 rounded-lg p-2 opacity-60 hover:opacity-100 hover:bg-white/15 transition-all"
            aria-label="Dismiss"
          >
            <X size={16} />
          </button>
        )}
      </div>
    </div>
  )
}

/**
 * Public banner — fetches enabled campaigns for the top-banner placement and
 * renders them, with per-campaign dismissal persisted in localStorage.
 * Safe: a failed fetch renders nothing.
 */
export default function CampaignBanner({ placement = 'banner_top' }) {
  const [campaigns, setCampaigns] = useState([])
  const [dismissed, setLocalDismissed] = useState(() => getDismissed())

  useEffect(() => {
    let cancelled = false
    api
      .get(`/campaigns/active/?placement=${encodeURIComponent(placement)}`, { silentError: true })
      .then((res) => { if (!cancelled) setCampaigns(Array.isArray(res.data) ? res.data : []) })
      .catch(() => { if (!cancelled) setCampaigns([]) })
    return () => { cancelled = true }
  }, [placement])

  const visible = campaigns.filter((c) => !dismissed[c.id])
  if (!visible.length) return null

  const dismiss = (id) => {
    markDismissed(id)
    setLocalDismissed((prev) => ({ ...prev, [id]: true }))
  }

  return (
    <>
      {visible.map((c) => (
        <CampaignRender key={c.id} campaign={c} onDismiss={() => dismiss(c.id)} />
      ))}
    </>
  )
}
