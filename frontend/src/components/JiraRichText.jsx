/**
 * Lightweight markdown-ish renderer for Jira ticket descriptions.
 * Supports fenced code blocks, inline `code`, headings, and lists.
 */
export function JiraRichText({ text, className = '' }) {
  if (!text) return null

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
            <div key={i} className="rounded-md overflow-hidden border border-[#C1C7D0] bg-[#F4F5F7]">
              {lang && (
                <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-[#6B778C] bg-[#EBECF0] border-b border-[#DFE1E6]">
                  {lang}
                </div>
              )}
              <pre className="p-3 text-[13px] leading-relaxed overflow-x-auto font-mono text-[#172B4D]">
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
              <h4 key={key} className="text-sm font-semibold text-[#172B4D] mt-2">
                {renderInline(line.slice(4))}
              </h4>
            )
          }
          if (line.startsWith('## ')) {
            return (
              <h3 key={key} className="text-base font-semibold text-[#172B4D] mt-2">
                {renderInline(line.slice(3))}
              </h3>
            )
          }
          if (line.startsWith('- ') || line.startsWith('* ')) {
            return (
              <p key={key} className="text-sm text-[#172B4D] pl-4 relative before:content-['•'] before:absolute before:left-0 before:text-[#0052CC]">
                {renderInline(line.slice(2))}
              </p>
            )
          }
          if (/^\d+\.\s/.test(line)) {
            const body = line.replace(/^\d+\.\s/, '')
            return (
              <p key={key} className="text-sm text-[#172B4D] pl-5">
                {renderInline(body)}
              </p>
            )
          }

          return (
            <p key={key} className="text-sm text-[#172B4D] leading-relaxed">
              {renderInline(line)}
            </p>
          )
        })
      })}
    </div>
  )
}

function renderInline(text) {
  const parts = text.split(/(`[^`]+`)/g)
  return parts.map((part, i) => {
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code
          key={i}
          className="px-1.5 py-0.5 rounded text-[12px] font-mono bg-[#F4F5F7] border border-[#DFE1E6] text-[#0747A6]"
        >
          {part.slice(1, -1)}
        </code>
      )
    }
    return part
  })
}
