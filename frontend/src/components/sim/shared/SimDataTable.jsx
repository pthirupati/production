import { useMemo, useState } from 'react'
import { ChevronDown, ChevronUp, ChevronsUpDown, Search } from 'lucide-react'

/**
 * Sortable, filterable, paginated table.
 * columns: [{ key, label, sortable?, render?(row) }]
 */
export default function SimDataTable({
  columns = [], rows = [], searchKeys = [], pageSize = 10,
  onRowClick, emptyMessage = 'No records found', className = '',
}) {
  const [sort, setSort] = useState({ key: null, dir: 'asc' })
  const [q, setQ] = useState('')
  const [page, setPage] = useState(0)

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase()
    let list = rows
    if (needle && searchKeys.length) {
      list = rows.filter((row) => searchKeys.some((k) => String(row[k] ?? '').toLowerCase().includes(needle)))
    }
    if (sort.key) {
      list = [...list].sort((a, b) => {
        const av = a[sort.key], bv = b[sort.key]
        const cmp = String(av ?? '').localeCompare(String(bv ?? ''), undefined, { numeric: true })
        return sort.dir === 'asc' ? cmp : -cmp
      })
    }
    return list
  }, [rows, q, searchKeys, sort])

  const pages = Math.max(1, Math.ceil(filtered.length / pageSize))
  const slice = filtered.slice(page * pageSize, page * pageSize + pageSize)

  const toggleSort = (key, sortable) => {
    if (!sortable) return
    setSort((prev) => prev.key === key
      ? { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
      : { key, dir: 'asc' })
  }

  const SortIcon = ({ col }) => {
    if (!col.sortable) return null
    if (sort.key !== col.key) return <ChevronsUpDown size={12} className="opacity-40" />
    return sort.dir === 'asc' ? <ChevronUp size={12} /> : <ChevronDown size={12} />
  }

  return (
    <div className={`sim-data-table ${className}`.trim()}>
      {searchKeys.length > 0 && (
        <div className="mb-3 relative max-w-xs">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500" />
          <input value={q} onChange={(e) => { setQ(e.target.value); setPage(0) }}
            placeholder="Filter…"
            className="w-full pl-8 pr-3 py-1.5 text-xs rounded border border-slate-600 bg-slate-900/80 text-slate-200 outline-none focus:border-violet-500" />
        </div>
      )}
      <div className="overflow-x-auto rounded border border-slate-700/80">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-slate-800/80 text-left text-slate-400">
              {columns.map((col) => (
                <th key={col.key} className="px-3 py-2 font-semibold whitespace-nowrap">
                  <button type="button" disabled={!col.sortable}
                    onClick={() => toggleSort(col.key, col.sortable)}
                    className={`inline-flex items-center gap-1 ${col.sortable ? 'hover:text-white cursor-pointer' : 'cursor-default'}`}>
                    {col.label} <SortIcon col={col} />
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {slice.length === 0 ? (
              <tr><td colSpan={columns.length} className="px-3 py-8 text-center text-slate-500">{emptyMessage}</td></tr>
            ) : slice.map((row, i) => (
              <tr key={row.id ?? i}
                onClick={() => onRowClick?.(row)}
                className={`border-t border-slate-700/60 ${onRowClick ? 'cursor-pointer hover:bg-white/5' : ''}`}>
                {columns.map((col) => (
                  <td key={col.key} className="px-3 py-2.5 text-slate-200 align-middle">
                    {col.render ? col.render(row) : row[col.key]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {pages > 1 && (
        <div className="flex items-center justify-between mt-2 text-[11px] text-slate-500">
          <span>{filtered.length} rows · page {page + 1} of {pages}</span>
          <div className="flex gap-1">
            <button type="button" disabled={page === 0} onClick={() => setPage((p) => p - 1)}
              className="px-2 py-1 rounded border border-slate-600 disabled:opacity-40">Prev</button>
            <button type="button" disabled={page >= pages - 1} onClick={() => setPage((p) => p + 1)}
              className="px-2 py-1 rounded border border-slate-600 disabled:opacity-40">Next</button>
          </div>
        </div>
      )}
    </div>
  )
}
