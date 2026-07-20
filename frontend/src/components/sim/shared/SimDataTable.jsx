import { useMemo, useState } from 'react'
import { ChevronDown, ChevronUp, ChevronsUpDown, Search } from 'lucide-react'

/**
 * Sortable, filterable, paginated table.
 * Theme follows parent shell via CSS (.az-shell light, .soc-shell dark, etc.).
 * columns: [{ key, label, sortable?, render?(row) }]
 */
export default function SimDataTable({
  columns = [], rows = [], searchKeys = [], pageSize = 10,
  onRowClick, emptyMessage = 'No records found', className = '',
  variant = 'auto',
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
    if (sort.key !== col.key) return <ChevronsUpDown size={12} className="sdt-sort-idle" />
    return sort.dir === 'asc' ? <ChevronUp size={12} /> : <ChevronDown size={12} />
  }

  const themeClass = variant === 'dark' ? 'sim-data-table-dark' : variant === 'light' ? 'sim-data-table-light' : ''

  return (
    <div className={`sim-data-table ${themeClass} ${className}`.trim()}>
      {searchKeys.length > 0 && (
        <div className="sdt-search-wrap">
          <Search size={14} className="sdt-search-icon" />
          <input value={q} onChange={(e) => { setQ(e.target.value); setPage(0) }}
            placeholder="Filter…"
            className="sdt-search" />
        </div>
      )}
      <div className="sdt-scroll">
        <table className="sdt-table">
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col.key}>
                  <button type="button" disabled={!col.sortable}
                    onClick={() => toggleSort(col.key, col.sortable)}
                    className={`sdt-th-btn ${col.sortable ? 'sdt-th-sortable' : ''}`}>
                    {col.label} <SortIcon col={col} />
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {slice.length === 0 ? (
              <tr><td colSpan={columns.length} className="sdt-empty">{emptyMessage}</td></tr>
            ) : slice.map((row, i) => (
              <tr key={row.id ?? i}
                onClick={() => onRowClick?.(row)}
                className={onRowClick ? 'sdt-row-click' : ''}>
                {columns.map((col) => (
                  <td key={col.key}>
                    {col.render ? col.render(row) : row[col.key]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {pages > 1 && (
        <div className="sdt-pager">
          <span>{filtered.length} rows · page {page + 1} of {pages}</span>
          <div className="sdt-pager-btns">
            <button type="button" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Prev</button>
            <button type="button" disabled={page >= pages - 1} onClick={() => setPage((p) => p + 1)}>Next</button>
          </div>
        </div>
      )}
    </div>
  )
}
