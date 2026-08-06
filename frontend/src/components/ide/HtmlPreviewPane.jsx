import { useMemo, useEffect, useRef } from 'react'
import { Eye, RefreshCw } from 'lucide-react'
import { composeHtmlPreview, PREVIEW_LOG_TYPE } from '../../utils/ide/composeHtmlPreview'

/**
 * Live HTML preview for Coding IDE (sandboxed iframe srcDoc).
 *
 * The composed document carries a console/error shim that posts back here, so
 * console.log and uncaught exceptions from the previewed page reach the IDE's
 * Logs pane instead of vanishing. onLog is optional — without it the preview
 * behaves exactly as before.
 *
 * sandbox="allow-scripts" without allow-same-origin makes this an OPAQUE origin,
 * which is why composeHtmlPreview has to resolve every relative <link href> and
 * <script src> into an inline block before we get here: there is no origin for
 * a relative URL to resolve against, so an un-rewritten ref just 404s silently.
 * Do not add allow-same-origin to "fix" that — it would give previewed learner
 * code same-origin access to the app.
 */
export default function HtmlPreviewPane({ files, htmlPath, onRefresh, onLog }) {
  const iframeRef = useRef(null)
  const onLogRef = useRef(onLog)
  useEffect(() => { onLogRef.current = onLog }, [onLog])

  const srcDoc = useMemo(
    () => composeHtmlPreview(files || {}, { htmlPath }),
    [files, htmlPath],
  )

  useEffect(() => {
    const handler = (event) => {
      // srcDoc iframes are opaque-origin, so we cannot match event.origin.
      // Identify the sender by window reference instead: this rejects messages
      // from every other frame, extension, or embedded widget on the page.
      if (event.source !== iframeRef.current?.contentWindow) return
      const data = event.data
      if (!data || data.type !== PREVIEW_LOG_TYPE) return
      onLogRef.current?.({
        level: typeof data.level === 'string' ? data.level : 'log',
        text: typeof data.text === 'string' ? data.text : String(data.text ?? ''),
      })
    }
    window.addEventListener('message', handler)
    return () => window.removeEventListener('message', handler)
  }, [])

  return (
    <div className="flex flex-col h-full min-h-0 bg-[var(--vsc-editor-bg,#1e1e1e)]">
      <div className="flex items-center justify-between gap-2 px-2 py-1.5 border-b border-[var(--vsc-border,#333)] text-[10px] uppercase tracking-wider text-[var(--vsc-muted)]">
        <span className="inline-flex items-center gap-1"><Eye size={11} /> Preview</span>
        {onRefresh && (
          <button type="button" onClick={onRefresh} className="vsc-btn" title="Refresh preview">
            <RefreshCw size={11} /> Refresh
          </button>
        )}
      </div>
      <iframe
        ref={iframeRef}
        title="HTML preview"
        sandbox="allow-scripts"
        srcDoc={srcDoc}
        className="flex-1 w-full min-h-[180px] border-0 bg-white"
      />
    </div>
  )
}
