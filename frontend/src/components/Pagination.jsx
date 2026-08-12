import { ChevronLeft, ChevronRight } from 'lucide-react'

export default function Pagination({ currentPage, totalPages, onPageChange }) {
  if (totalPages <= 1) return null

  const pages = []
  const maxVisible = 5
  let start = Math.max(1, currentPage - Math.floor(maxVisible / 2))
  let end = Math.min(totalPages, start + maxVisible - 1)
  if (end - start + 1 < maxVisible) start = Math.max(1, end - maxVisible + 1)

  if (start > 1) {
    pages.push(1)
    if (start > 2) pages.push('...')
  }
  for (let i = start; i <= end; i++) pages.push(i)
  if (end < totalPages) {
    if (end < totalPages - 1) pages.push('...')
    pages.push(totalPages)
  }

  return (
    <div className="flex items-center justify-center gap-1.5 mt-8">
      <button
        type="button"
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage <= 1}
        className="p-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded-lg text-surface-400 hover:text-white hover:bg-surface-800 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
        aria-label="Previous page"
      >
        <ChevronLeft size={16} />
      </button>
      {pages.map((p, i) =>
        p === '...' ? (
          <span key={`dots-${i}`} className="px-2 text-surface-600 text-sm">...</span>
        ) : (
          <button
            key={p}
            onClick={() => onPageChange(p)}
            className={`min-w-[36px] h-9 rounded-lg text-sm font-medium transition-all ${
              currentPage === p
                ? 'bg-gradient-to-r from-accent-cyan to-accent-blue text-white shadow-lg shadow-accent-cyan/20'
                : 'text-surface-400 hover:text-white hover:bg-surface-800'
            }`}
          >
            {p}
          </button>
        )
      )}
      <button
        type="button"
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage >= totalPages}
        className="p-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded-lg text-surface-400 hover:text-white hover:bg-surface-800 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
        aria-label="Next page"
      >
        <ChevronRight size={16} />
      </button>
    </div>
  )
}
