import { useMemo, useEffect, useRef, useState } from 'react'
import { Eye, RefreshCw, Monitor, Tablet, Smartphone, ZoomIn, ZoomOut, Crosshair } from 'lucide-react'
import {
  composeHtmlPreview,
  PREVIEW_LOG_TYPE,
  PREVIEW_NAV_TYPE,
  PREVIEW_INSPECT_TYPE,
} from '../../utils/ide/composeHtmlPreview'

const DEVICE_PRESETS = [
  { id: 'desktop', label: 'Desktop', icon: Monitor, width: null },
  { id: 'tablet', label: 'Tablet', icon: Tablet, width: 768 },
  { id: 'mobile', label: 'Mobile', icon: Smartphone, width: 390 },
]

export const PREVIEW_ZOOM_STEPS = [0.75, 1, 1.25, 1.5]

export function nextZoom(current, steps = PREVIEW_ZOOM_STEPS) {
  const i = steps.indexOf(current)
  if (i < 0) return steps[1] ?? 1
  return steps[Math.min(steps.length - 1, i + 1)]
}

export function prevZoom(current, steps = PREVIEW_ZOOM_STEPS) {
  const i = steps.indexOf(current)
  if (i < 0) return steps[1] ?? 1
  return steps[Math.max(0, i - 1)]
}

export function formatInspectHit(hit) {
  if (!hit) return ''
  const parts = [hit.tag || 'element']
  if (hit.id) parts.push(`#${hit.id}`)
  if (hit.className) {
    const cls = String(hit.className).trim().split(/\s+/).filter(Boolean).slice(0, 4)
    if (cls.length) parts.push(`.${cls.join('.')}`)
  }
  if (hit.w || hit.h) parts.push(`${hit.w}×${hit.h}`)
  return parts.join(' ')
}

/** Absolute box style for the inspect highlight overlay (iframe-local coords × zoom). */
export function inspectOverlayStyle(hit, zoom = 1) {
  if (!hit) return null
  const z = Number(zoom) || 1
  return {
    position: 'absolute',
    left: (Number(hit.left) || 0) * z,
    top: (Number(hit.top) || 0) * z,
    width: Math.max(2, (Number(hit.w) || 0) * z),
    height: Math.max(2, (Number(hit.h) || 0) * z),
    border: '1.5px solid #f97316',
    background: 'rgba(249, 115, 22, 0.12)',
    pointerEvents: 'none',
    boxSizing: 'border-box',
    zIndex: 2,
  }
}

/**
 * Live HTML preview for Coding IDE (sandboxed iframe srcDoc).
 *
 * Device presets + zoom + optional element inspector (click posts tag/id/class).
 */
export default function HtmlPreviewPane({ files, htmlPath, onRefresh, onLog, onNavigate }) {
  const iframeRef = useRef(null)
  const onLogRef = useRef(onLog)
  const onNavigateRef = useRef(onNavigate)
  const [device, setDevice] = useState('desktop')
  const [zoom, setZoom] = useState(1)
  const [inspect, setInspect] = useState(false)
  const [inspectHit, setInspectHit] = useState(null)
  useEffect(() => { onLogRef.current = onLog }, [onLog])
  useEffect(() => { onNavigateRef.current = onNavigate }, [onNavigate])

  const srcDoc = useMemo(
    () => composeHtmlPreview(files || {}, { htmlPath, inspect }),
    [files, htmlPath, inspect],
  )

  const frameWidth = DEVICE_PRESETS.find((d) => d.id === device)?.width

  useEffect(() => {
    const handler = (event) => {
      if (event.source !== iframeRef.current?.contentWindow) return
      const data = event.data
      if (!data) return
      if (data.type === PREVIEW_LOG_TYPE) {
        onLogRef.current?.({
          level: typeof data.level === 'string' ? data.level : 'log',
          text: typeof data.text === 'string' ? data.text : String(data.text ?? ''),
        })
        return
      }
      if (data.type === PREVIEW_NAV_TYPE && typeof data.href === 'string') {
        onNavigateRef.current?.(data.href)
        return
      }
      if (data.type === PREVIEW_INSPECT_TYPE) {
        setInspectHit({
          tag: data.tag,
          id: data.id,
          className: data.className,
          text: data.text,
          w: data.w,
          h: data.h,
          left: data.left,
          top: data.top,
        })
      }
    }
    window.addEventListener('message', handler)
    return () => window.removeEventListener('message', handler)
  }, [])

  return (
    <div className="flex flex-col h-full min-h-0 bg-[var(--vsc-editor-bg,#1e1e1e)]">
      <div className="flex items-center justify-between gap-2 px-2 py-1.5 border-b border-[var(--vsc-border,#333)] text-[10px] uppercase tracking-wider text-[var(--vsc-muted)]">
        <span className="inline-flex items-center gap-1"><Eye size={11} /> Preview</span>
        <div className="flex items-center gap-1">
          {DEVICE_PRESETS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              title={label}
              aria-pressed={device === id}
              onClick={() => setDevice(id)}
              className={`vsc-btn ${device === id ? 'opacity-100' : 'opacity-50'}`}
            >
              <Icon size={11} />
            </button>
          ))}
          <button
            type="button"
            title="Inspect element"
            aria-label="Inspect element"
            aria-pressed={inspect}
            className={`vsc-btn ${inspect ? 'opacity-100' : 'opacity-50'}`}
            onClick={() => {
              setInspect((v) => !v)
              setInspectHit(null)
            }}
          >
            <Crosshair size={11} />
          </button>
          <button
            type="button"
            title="Zoom out"
            aria-label="Zoom out"
            className="vsc-btn"
            onClick={() => setZoom((z) => prevZoom(z))}
            disabled={zoom <= PREVIEW_ZOOM_STEPS[0]}
          >
            <ZoomOut size={11} />
          </button>
          <span className="tabular-nums min-w-[2.5rem] text-center" data-testid="preview-zoom">
            {Math.round(zoom * 100)}%
          </span>
          <button
            type="button"
            title="Zoom in"
            aria-label="Zoom in"
            className="vsc-btn"
            onClick={() => setZoom((z) => nextZoom(z))}
            disabled={zoom >= PREVIEW_ZOOM_STEPS[PREVIEW_ZOOM_STEPS.length - 1]}
          >
            <ZoomIn size={11} />
          </button>
          {onRefresh && (
            <button type="button" onClick={onRefresh} className="vsc-btn" title="Refresh preview">
              <RefreshCw size={11} /> Refresh
            </button>
          )}
        </div>
      </div>
      {inspect && (
        <div
          data-testid="preview-inspect"
          className="px-2 py-1 text-[10px] font-mono border-b border-[var(--vsc-border,#333)] text-[var(--vsc-muted)]"
        >
          {inspectHit
            ? `${formatInspectHit(inspectHit)}${inspectHit.text ? ` · “${inspectHit.text}”` : ''}`
            : 'Inspect on — click an element in the preview'}
        </div>
      )}
      <div className="flex-1 min-h-0 overflow-auto flex justify-center bg-[var(--vsc-sidebar-bg,#252526)]">
        <div
          style={{
            position: 'relative',
            width: frameWidth || '100%',
            maxWidth: '100%',
            transform: zoom !== 1 ? `scale(${zoom})` : undefined,
            transformOrigin: 'top center',
          }}
          className={frameWidth ? 'my-2' : 'flex-1 w-full h-full'}
        >
          <iframe
            ref={iframeRef}
            title="HTML preview"
            sandbox="allow-scripts"
            srcDoc={srcDoc}
            className={`min-h-[180px] border-0 bg-white w-full ${frameWidth ? 'h-full shadow-lg' : 'h-full'}`}
          />
          {inspect && inspectHit && (
            <div
              data-testid="preview-inspect-overlay"
              aria-hidden
              style={inspectOverlayStyle(inspectHit, 1)}
            />
          )}
        </div>
      </div>
    </div>
  )
}
