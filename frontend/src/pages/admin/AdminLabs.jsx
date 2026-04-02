import { useState, useEffect } from 'react'
import { adminApi } from '../../api/admin'
import { MonitorPlay, StopCircle, Trash2, Clock } from 'lucide-react'
import toast from 'react-hot-toast'

export default function AdminLabs() {
  const [labs, setLabs] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => { loadData() }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const data = await adminApi.getActiveLabs()
      setLabs(data)
    } catch { console.error } finally { setLoading(false) }
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

  const handleTerminateIdle = async () => {
    if (!confirm('Terminate all expired labs?')) return
    try {
      const result = await adminApi.terminateIdleLabs()
      toast.success(`${result.terminated} labs terminated`)
      loadData()
    } catch {
      toast.error('Failed')
    }
  }

  const formatTime = (seconds) => {
    if (!seconds) return '—'
    const m = Math.floor(seconds / 60)
    const s = seconds % 60
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Active Labs</h1>
          <p className="text-surface-400 mt-1">{labs.length} labs currently running</p>
        </div>
        <button onClick={handleTerminateIdle} className="btn-danger flex items-center gap-2">
          <Trash2 size={16} /> Terminate Expired
        </button>
      </div>

      <div className="glass-card overflow-hidden">
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
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-700/50 text-left">
                <th className="px-4 py-3 text-xs font-medium text-surface-400 uppercase">User</th>
                <th className="px-4 py-3 text-xs font-medium text-surface-400 uppercase">Scenario</th>
                <th className="px-4 py-3 text-xs font-medium text-surface-400 uppercase">Infra</th>
                <th className="px-4 py-3 text-xs font-medium text-surface-400 uppercase">Resource</th>
                <th className="px-4 py-3 text-xs font-medium text-surface-400 uppercase">Time Left</th>
                <th className="px-4 py-3 text-xs font-medium text-surface-400 uppercase">Started</th>
                <th className="px-4 py-3 text-xs font-medium text-surface-400 uppercase text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {labs.map((lab) => (
                <tr key={lab.id} className="border-b border-surface-800/50 hover:bg-surface-800/30">
                  <td className="px-4 py-3 text-sm text-white">{lab.user}</td>
                  <td className="px-4 py-3 text-sm text-surface-300">{lab.scenario}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                      lab.provider === 'aws_ec2' ? 'bg-amber-500/10 text-amber-400' :
                      lab.provider === 'digitalocean' ? 'bg-blue-500/10 text-blue-400' :
                      'bg-surface-700 text-surface-400'
                    }`}>{lab.provider === 'aws_ec2' ? 'EC2' : lab.provider === 'digitalocean' ? 'DO' : 'Docker'}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-xs font-mono text-surface-500">{lab.resource_id || '—'}</span>
                    {lab.ssh_host && <span className="text-xs text-surface-600 ml-1">({lab.ssh_host})</span>}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`flex items-center gap-1 text-sm ${
                      lab.time_remaining < 300 ? 'text-accent-red' : 'text-surface-300'
                    }`}>
                      <Clock size={14} />
                      {formatTime(lab.time_remaining)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-surface-500">
                    {new Date(lab.started_at).toLocaleTimeString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button onClick={() => handleTerminate(lab.id)}
                      className="p-1.5 text-surface-500 hover:text-accent-red transition-colors">
                      <StopCircle size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
