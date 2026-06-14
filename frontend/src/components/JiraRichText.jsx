/**
 * Lightweight markdown-ish renderer for Jira ticket descriptions.
 * variant="dark" matches Initial State styling on scenario/lab pages.
 */
export function JiraRichText({ text, className = '', variant = 'light' }) {
  if (!text) return null

  const isDark = variant === 'dark'
  const textMain = isDark ? 'text-surface-400' : 'text-[#172B4D]'
  const heading = isDark ? 'text-surface-300' : 'text-[#172B4D]'
  const codeBlock = isDark
    ? 'rounded-md overflow-hidden border border-surface-800 bg-surface-950'
    : 'rounded-md overflow-hidden border border-[#C1C7D0] bg-[#F4F5F7]'
  const codeHeader = isDark
    ? 'px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-surface-500 bg-surface-900 border-b border-surface-800'
    : 'px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-[#6B778C] bg-[#EBECF0] border-b border-[#DFE1E6]'
  const codePre = isDark
    ? 'p-3 text-xs leading-relaxed overflow-x-auto font-mono text-surface-400'
    : 'p-3 text-[13px] leading-relaxed overflow-x-auto font-mono text-[#172B4D]'
  const inlineCode = isDark
    ? 'px-1.5 py-0.5 rounded text-[11px] font-mono bg-surface-900 border border-surface-800 text-surface-300'
    : 'px-1.5 py-0.5 rounded text-[12px] font-mono bg-[#F4F5F7] border border-[#DFE1E6] text-[#0747A6]'

  const blocks = text.split(/(```[\s\S]*?```)/g)

  return (
    <div className={`space-y-3 ${className}`}>
      {blocks.map((block, i) => {
        if (block.startsWith('```') && block.endsWith('```')) {
          const inner = block.slice(3, -3)
          const firstLineBreak = inner.indexOf('\n')
          const lang = firstLineBreak > 0 ? inner.slice(0, firstLineBreak).trim() : ''
          const code = firstLineBreak > 0 ? inner.slice(firstLineBreak + 1) : inner
          return (
            <div key={i} className={codeBlock}>
              {lang && (
                <div className={codeHeader}>{lang}</div>
              )}
              <pre className={codePre}>
                <code>{code.replace(/\n$/, '')}</code>
              </pre>
            </div>
          )
        }

        return block.split('\n').map((line, j) => {
          const key = `${i}-${j}`
          if (!line.trim()) return <div key={key} className="h-1" />

          if (line.startsWith('### ')) {
            return (
              <h4 key={key} className={`text-sm font-semibold ${heading} mt-2`}>
                {renderInline(line.slice(4), inlineCode)}
              </h4>
            )
          }
          if (line.startsWith('## ')) {
            return (
              <h3 key={key} className={`text-base font-semibold ${heading} mt-2`}>
                {renderInline(line.slice(3), inlineCode)}
              </h3>
            )
          }
          if (line.startsWith('- ') || line.startsWith('* ')) {
            return (
              <p key={key} className={`text-sm ${textMain} pl-4 relative before:content-['•'] before:absolute before:left-0 ${isDark ? 'before:text-surface-500' : 'before:text-[#0052CC]'}`}>
                {renderInline(line.slice(2), inlineCode)}
              </p>
            )
          }
          if (/^\d+\.\s/.test(line)) {
            const body = line.replace(/^\d+\.\s/, '')
            return (
              <p key={key} className={`text-sm ${textMain} pl-5`}>
                {renderInline(body, inlineCode)}
              </p>
            )
          }

          return (
            <p key={key} className={`text-sm ${textMain} leading-relaxed`}>
              {renderInline(line, inlineCode)}
            </p>
          )
        })
      })}
    </div>
  )
}

function renderInline(text, inlineCodeClass) {
  const parts = text.split(/(`[^`]+`)/g)
  return parts.map((part, i) => {
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code key={i} className={inlineCodeClass}>
          {part.slice(1, -1)}
        </code>
      )
    }
    return part
  })
}
