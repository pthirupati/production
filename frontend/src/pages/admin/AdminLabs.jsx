import { useState, useEffect, useMemo } from 'react'
import { adminApi } from '../../api/admin'
import { MonitorPlay, StopCircle, Trash2, Clock, CheckSquare, Square, MinusSquare } from 'lucide-react'
import toast from 'react-hot-toast'
import ConfirmModal, { ConfirmDialog } from '../../components/ConfirmModal'

export default function AdminLabs() {
  const [labs, setLabs] = useState([])
  const [loading, setLoading] = useState(true)
  const [includeExpired, setIncludeExpired] = useState(true)
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [bulkConfirm, setBulkConfirm] = useState(null)
  const [processing, setProcessing] = useState(false)

  useEffect(() => { loadData() }, [includeExpired])

  const loadData = async () => {
    setLoading(true)
    try {
      const data = await adminApi.getActiveLabs({ include_expired: includeExpired ? '1' : '0' })
      setLabs(data)
      setSelectedIds(new Set())
    } catch { console.error } finally { setLoading(false) }
  }

  const visibleLabs = useMemo(() => labs, [labs])
  const allSelected = visibleLabs.length > 0 && visibleLabs.every(l => selectedIds.has(l.id))
  const someSelected = visibleLabs.some(l => selectedIds.has(l.id))

  const toggleSelect = (id) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const toggleSelectAll = () => {
    if (allSelected) setSelectedIds(new Set())
    else setSelectedIds(new Set(visibleLabs.map(l => l.id)))
  }

  const handleTerminate = async (sessionId) => {
    try {
      await adminApi.terminateLab(sessionId)
      toast.success('Lab terminated')
      loadData()
    } catch {
      toast.error('Terminate failed')
    }
  }

  const handleBulk = async () => {
    if (!bulkConfirm) return
    setProcessing(true)
    try {
      let result
      if (bulkConfirm.action === 'terminate_expired') {
        result = await adminApi.bulkTerminateLabs({ action: 'terminate_expired' })
      } else {
        result = await adminApi.bulkTerminateLabs({
          session_ids: [...selectedIds],
          terminate_expired_only: bulkConfirm.expiredOnly || false,
        })
      }
      toast.success(result.message || `${result.terminated} terminated`)
      loadData()
    } catch (err) {
      toast.error(err.response?.data?.error || 'Bulk terminate failed')
    } finally {
      setProcessing(false)
      setBulkConfirm(null)
    }
  }

  const formatTime = (seconds) => {
    if (!seconds) return '—'
    const m = Math.floor(seconds / 60)
    const s = seconds % 60
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  return (
    <div className="space-y-4 sm:space-y-6 animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-white">Active Labs</h1>
          <p className="text-surface-400 mt-1 text-sm">{labs.length} lab(s) shown</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-sm text-surface-400">
            <input type="checkbox" checked={includeExpired} onChange={e => setIncludeExpired(e.target.checked)} />
            Show expired
          </label>
          <button
            type="button"
            onClick={() => setBulkConfirm({ action: 'terminate_expired' })}
            className="btn-danger flex items-center gap-2 text-sm"
          >
            <Trash2 size={16} /> Terminate expired
          </button>
        </div>
      </div>

      {someSelected && (
        <div className="glass-card p-3 flex flex-wrap items-center gap-2 border border-accent-purple/30">
          <span className="text-sm text-surface-300">{selectedIds.size} selected</span>
          <button
            type="button"
            onClick={() => setBulkConfirm({ action: 'terminate_selected' })}
            className="btn-danger text-sm flex items-center gap-1"
          >
            <StopCircle size={14} /> Terminate selected
          </button>
          <button type="button" onClick={() => setSelectedIds(new Set())} className="text-sm text-surface-500">Clear</button>
        </div>
      )}

      <div className="glass-card overflow-x-auto">
        {loading ? (
          <div className="flex items-center justify-center h-40">
            <div className="w-8 h-8 border-2 border-accent-purple border-t-transparent rounded-full animate-spin" />
          </div>
        ) : labs.length === 0 ? (
          <div className="text-center py-16 text-surface-500">
            <MonitorPlay size={48} className="mx-auto mb-4 opacity-30" />
            No active labs
          </div>
        ) : (
          <table className="w-full min-w-[720px]">
            <thead>
              <tr className="border-b border-surface-700/50 text-left">
                <th className="px-3 py-3 w-10">
                  <button type="button" onClick={toggleSelectAll} className="text-surface-400 hover:text-white">
                    {allSelected ? <CheckSquare size={16} /> : someSelected ? <MinusSquare size={16} /> : <Square size={16} />}
                  </button>
                </th>
                <th className="px-3 py-3 text-xs font-medium text-surface-400 uppercase">User</th>
                <th className="px-3 py-3 text-xs font-medium text-surface-400 uppercase">Scenario</th>
                <th className="px-3 py-3 text-xs font-medium text-surface-400 uppercase hidden sm:table-cell">Infra</th>
                <th className="px-3 py-3 text-xs font-medium text-surface-400 uppercase hidden md:table-cell">Resource</th>
                <th className="px-3 py-3 text-xs font-medium text-surface-400 uppercase">Time</th>
                <th className="px-3 py-3 text-xs font-medium text-surface-400 uppercase text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {visibleLabs.map((lab) => (
                <tr key={lab.id} className={`border-b border-surface-800/50 hover:bg-surface-800/30 ${lab.is_expired ? 'bg-accent-red/5' : ''}`}>
                  <td className="px-3 py-3">
                    <button type="button" onClick={() => toggleSelect(lab.id)} className="text-surface-400 hover:text-white">
                      {selectedIds.has(lab.id) ? <CheckSquare size={16} className="text-accent-cyan" /> : <Square size={16} />}
                    </button>
                  </td>
                  <td className="px-3 py-3 text-sm text-white">{lab.user}</td>
                  <td className="px-3 py-3 text-sm text-surface-300 max-w-[140px] truncate">{lab.scenario}</td>
                  <td className="px-3 py-3 hidden sm:table-cell">
                    <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-surface-700 text-surface-400">{lab.provider}</span>
                  </td>
                  <td className="px-3 py-3 hidden md:table-cell">
                    <span className="text-xs font-mono text-surface-500">{lab.resource_id || '—'}</span>
                  </td>
                  <td className="px-3 py-3">
                    <span className={`flex items-center gap-1 text-sm ${lab.is_expired || lab.time_remaining < 300 ? 'text-accent-red' : 'text-surface-300'}`}>
                      <Clock size={14} />
                      {lab.is_expired ? 'Expired' : formatTime(lab.time_remaining)}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-right">
                    <button type="button" onClick={() => handleTerminate(lab.id)} className="p-2 text-surface-500 hover:text-accent-red">
                      <StopCircle size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <ConfirmDialog
        open={!!bulkConfirm}
        title={bulkConfirm?.action === 'terminate_expired' ? 'Terminate all expired labs?' : 'Terminate selected labs?'}
        message={bulkConfirm?.action === 'terminate_expired'
          ? 'This will stop every running lab that exceeded its time limit.'
          : `Terminate ${selectedIds.size} selected lab(s)? Containers will be removed.`}
        confirmLabel="Terminate"
        danger
        loading={processing}
        onConfirm={handleBulk}
        onClose={() => setBulkConfirm(null)}
      />
    </div>
  )
}
