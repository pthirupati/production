import { useEffect, useState } from 'react'
import { RotateCcw } from '../../ui/eagerIcons'
import { adminApi } from '../../api/admin'

export default function AdminTopbar() {
  const [stats, setStats] = useState(null)
  const [refreshing, setRefreshing] = useState(false)

  const load = async () => {
    try {
      const o = await adminApi.getOverview()
      setStats(o)
    } catch {
      setStats(null)
    }
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 60000)
    return () => clearInterval(t)
  }, [])

  const refresh = () => {
    setRefreshing(true)
    load().finally(() => {
      window.dispatchEvent(new CustomEvent('fixitlab-admin-refresh'))
      setTimeout(() => setRefreshing(false), 600)
    })
  }

  return (
    <header className="sticky top-0 z-40 shrink-0 fx-admin-topbar">
      <div className="flex items-center gap-3 px-4 sm:px-7 h-[56px]">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-accent-green shadow-[0_0_10px] shadow-accent-green animate-pulse" />
          <span className="text-[11px] font-bold uppercase tracking-[0.14em] text-accent-green/85">Live dashboard</span>
        </div>

        <div className="flex-1" />

        {stats && (
          <div className="hidden md:flex items-center gap-3.5 px-4 py-2 rounded-[10px] bg-white/[0.04] border border-white/10 text-xs text-white/50">
            <span><b className="text-white">{(stats.users?.total || 0).toLocaleString()}</b> users</span>
            <span className="w-px h-3 bg-white/15" />
            <span><b className="text-white">{stats.scenarios?.active || 0}</b> scenarios</span>
            <span className="w-px h-3 bg-white/15" />
            <span className="text-accent-green">● Operational</span>
          </div>
        )}

        <button
          type="button"
          onClick={refresh}
          className="inline-flex items-center gap-2 px-3.5 py-2 rounded-[10px] text-xs font-semibold text-white/75 bg-white/[0.04] border border-white/10 hover:border-accent-purple/50 transition-colors"
        >
          <RotateCcw size={14} className={refreshing ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>
    </header>
  )
}
