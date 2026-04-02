import { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { Bell, Check, CheckCheck, Award, Zap, AlertCircle, MessageCircle, Trash2 } from 'lucide-react'
import { useNotificationStore } from '../../store/notificationStore'

const TYPE_CONFIG = {
  achievement: { icon: Award, color: 'text-accent-amber' },
  lab_expired: { icon: Zap, color: 'text-accent-red' },
  streak: { icon: Zap, color: 'text-orange-400' },
  system: { icon: AlertCircle, color: 'text-accent-cyan' },
  welcome: { icon: MessageCircle, color: 'text-accent-green' },
}

export default function NotificationBell() {
  const { notifications, unreadCount, fetchNotifications, markRead, markAllRead, clearAll } = useNotificationStore()
  const [open, setOpen] = useState(false)
  const btnRef = useRef(null)
  const panelRef = useRef(null)
  const [pos, setPos] = useState({ top: 0, left: 0 })

  // Poll every 60s
  useEffect(() => {
    fetchNotifications()
    const interval = setInterval(fetchNotifications, 60_000)
    return () => clearInterval(interval)
  }, [])

  // Position the panel relative to the bell using a portal
  useEffect(() => {
    if (!open || !btnRef.current) return
    const rect = btnRef.current.getBoundingClientRect()
    // Open upward-right from the bell icon
    setPos({
      top: rect.top - 4, // panel bottom aligns near bell top
      left: rect.left + rect.width + 8, // panel opens to the right of the bell
    })
  }, [open])

  // Close on outside click
  useEffect(() => {
    if (!open) return
    const handler = (e) => {
      if (
        panelRef.current && !panelRef.current.contains(e.target) &&
        btnRef.current && !btnRef.current.contains(e.target)
      ) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  // Close on Escape
  useEffect(() => {
    if (!open) return
    const handler = (e) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open])

  const timeAgo = (dateStr) => {
    const diff = (Date.now() - new Date(dateStr).getTime()) / 1000
    if (diff < 60) return 'just now'
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
    return `${Math.floor(diff / 86400)}d ago`
  }

  const panel = open && createPortal(
    <div
      ref={panelRef}
      style={{ position: 'fixed', bottom: `${window.innerHeight - pos.top}px`, left: `${pos.left}px` }}
      className="w-80 bg-surface-900 border border-surface-700/50 rounded-xl shadow-2xl z-[9999] overflow-hidden animate-scale-in"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-surface-800">
        <h3 className="text-sm font-semibold text-surface-50">Notifications</h3>
        <div className="flex items-center gap-2">
          {unreadCount > 0 && (
            <button
              onClick={markAllRead}
              className="text-xs text-accent-cyan hover:underline flex items-center gap-1"
            >
              <CheckCheck size={12} /> Mark read
            </button>
          )}
          {notifications.length > 0 && (
            <button
              onClick={() => { clearAll(); setOpen(false) }}
              className="text-xs text-accent-red hover:underline flex items-center gap-1"
            >
              <Trash2 size={12} /> Clear
            </button>
          )}
        </div>
      </div>

      {/* List */}
      <div className="max-h-80 overflow-y-auto">
        {notifications.length === 0 ? (
          <div className="text-center py-8">
            <Bell size={24} className="text-surface-600 mx-auto mb-2" />
            <p className="text-sm text-surface-500">No notifications yet</p>
          </div>
        ) : (
          notifications.map((n) => {
            const cfg = TYPE_CONFIG[n.type] || TYPE_CONFIG.system
            const Icon = cfg.icon
            return (
              <div
                key={n.id}
                onClick={() => { if (!n.read) markRead(n.id) }}
                className={`flex items-start gap-3 px-4 py-3 border-b border-surface-800/50 cursor-pointer transition-colors ${
                  n.read ? 'opacity-60' : 'bg-surface-800/20 hover:bg-surface-800/40'
                }`}
              >
                <div className={`mt-0.5 shrink-0 ${cfg.color}`}>
                  <Icon size={16} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-surface-50 font-medium truncate">{n.title}</p>
                  {n.message && <p className="text-xs text-surface-400 mt-0.5 line-clamp-2">{n.message}</p>}
                  <p className="text-[10px] text-surface-600 mt-1">{timeAgo(n.created_at)}</p>
                </div>
                {!n.read && (
                  <div className="w-2 h-2 rounded-full bg-accent-cyan mt-1.5 shrink-0" />
                )}
              </div>
            )
          })
        )}
      </div>
    </div>,
    document.body
  )

  return (
    <div className="relative">
      <button
        ref={btnRef}
        onClick={() => setOpen(!open)}
        className="relative p-2 text-surface-400 hover:text-surface-50 transition-colors rounded-lg hover:bg-surface-800"
        aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ''}`}
      >
        <Bell size={18} />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-accent-red text-white text-[10px] font-bold rounded-full flex items-center justify-center animate-pulse">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>
      {panel}
    </div>
  )
}
