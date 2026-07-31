import { useMemo } from 'react'
import { Eye, RefreshCw } from 'lucide-react'
import { composeHtmlPreview } from '../../utils/ide/composeHtmlPreview'

/**
 * Live HTML preview for Coding IDE (sandboxed iframe srcDoc).
 */
export default function HtmlPreviewPane({ files, htmlPath, onRefresh }) {
  const srcDoc = useMemo(
    () => composeHtmlPreview(files || {}, { htmlPath }),
    [files, htmlPath],
  )

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
        title="HTML preview"
        sandbox="allow-scripts"
        srcDoc={srcDoc}
        className="flex-1 w-full min-h-[180px] border-0 bg-white"
      />
    </div>
  )
}
