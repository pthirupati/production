import { useState, useEffect } from 'react'
import { adminApi } from '../../api/admin'
import { FileText, Download, Search, RefreshCw, IndianRupee } from 'lucide-react'
import toast from 'react-hot-toast'

export default function AdminInvoices() {
  const [invoices, setInvoices] = useState([])
  const [stats, setStats] = useState({ total_count: 0, total_revenue_inr: 0 })
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  const loadData = async () => {
    setLoading(true)
    try {
      const data = await adminApi.getInvoices(search ? { user: search } : {})
      setInvoices(data.invoices || [])
      setStats({ total_count: data.total_count || 0, total_revenue_inr: data.total_revenue_inr || 0 })
    } catch {
      toast.error('Failed to load invoices')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadData() }, [])

  const handleSearch = (e) => {
    e.preventDefault()
    loadData()
  }

  const download = async (inv) => {
    try {
      const res = await adminApi.downloadInvoice(inv.id)
      const blob = new Blob([res.data], { type: 'text/html' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${inv.invoice_number}.html`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      toast.error('Download failed')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <FileText size={22} className="text-accent-cyan" /> Payment Invoices
          </h1>
          <p className="text-surface-400 mt-1">Invoices for verified payments (technology & interview)</p>
        </div>
        <button onClick={loadData} className="btn-secondary text-sm flex items-center gap-2">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      <div className="grid sm:grid-cols-2 gap-4">
        <div className="glass-card p-4">
          <p className="text-xs text-surface-500 uppercase">Total Invoices</p>
          <p className="text-2xl font-bold text-white mt-1">{stats.total_count}</p>
        </div>
        <div className="glass-card p-4">
          <p className="text-xs text-surface-500 uppercase flex items-center gap-1"><IndianRupee size={12} /> Revenue (shown)</p>
          <p className="text-2xl font-bold text-accent-green mt-1">₹{Math.round(stats.total_revenue_inr)}</p>
        </div>
      </div>

      <form onSubmit={handleSearch} className="flex gap-2 max-w-md">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-500" />
          <input
            type="text"
            placeholder="Search user email or invoice #..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="input-field pl-9 text-sm"
          />
        </div>
        <button type="submit" className="btn-primary text-sm px-4">Search</button>
      </form>

      <div className="glass-card overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-surface-400">Loading...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-700">
                  <th className="text-left p-3 text-surface-400 font-medium">Invoice #</th>
                  <th className="text-left p-3 text-surface-400 font-medium">User</th>
                  <th className="text-left p-3 text-surface-400 font-medium">Type</th>
                  <th className="text-left p-3 text-surface-400 font-medium">Product</th>
                  <th className="text-left p-3 text-surface-400 font-medium">Amount</th>
                  <th className="text-left p-3 text-surface-400 font-medium">Date</th>
                  <th className="text-right p-3 text-surface-400 font-medium">Download</th>
                </tr>
              </thead>
              <tbody>
                {invoices.map(inv => (
                  <tr key={inv.id} className="border-b border-surface-800 hover:bg-surface-800/30">
                    <td className="p-3 font-mono text-xs text-cyan-400">{inv.invoice_number}</td>
                    <td className="p-3">
                      <p className="text-white">{inv.user?.username}</p>
                      <p className="text-xs text-surface-500">{inv.user?.email}</p>
                    </td>
                    <td className="p-3">
                      <span className={`text-[10px] uppercase px-1.5 py-0.5 rounded ${inv.product_type === 'interview' ? 'text-indigo-400 bg-indigo-500/10' : 'text-cyan-400 bg-cyan-500/10'}`}>
                        {inv.product_type || 'technology'}
                      </span>
                    </td>
                    <td className="p-3">{inv.technology}</td>
                    <td className="p-3 font-semibold">₹{inv.amount}</td>
                    <td className="p-3 text-xs text-surface-400">
                      {new Date(inv.created_at).toLocaleDateString()}
                    </td>
                    <td className="p-3 text-right">
                      <button onClick={() => download(inv)} className="btn-secondary text-xs px-2 py-1 inline-flex items-center gap-1">
                        <Download size={12} /> HTML
                      </button>
                    </td>
                  </tr>
                ))}
                {invoices.length === 0 && (
                  <tr><td colSpan={7} className="p-8 text-center text-surface-400">No invoices found</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
