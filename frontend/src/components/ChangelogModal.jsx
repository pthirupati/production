import { useState, useEffect } from 'react'
import { X, Sparkles } from 'lucide-react'
import api from '../api/client'
import { currentUserScopedKey, migrateUnscopedKey } from '../utils/userScopedStorage'

// Scoped per user: on a shared browser an unscoped key let account B inherit
// account A's dismissal and never see the changelog.
const STORAGE_KEY_BASE = 'fixitlab_changelog_dismissed'

export default function ChangelogModal() {
  const [open, setOpen] = useState(false)
  const [entries, setEntries] = useState([])

  useEffect(() => {
    api.get('/config/')
      .then(res => {
        const log = res.data?.changelog || []
        if (!log.length) return
        const latest = log[0]
        const dismissed = localStorage.getItem(migrateUnscopedKey(STORAGE_KEY_BASE))
        if (dismissed !== latest.id && dismissed !== latest.date) {
          setEntries(log.slice(0, 5))
          setOpen(true)
        }
      })
      .catch(() => {})
  }, [])

  const dismiss = () => {
    const latest = entries[0]
    if (latest) {
      localStorage.setItem(currentUserScopedKey(STORAGE_KEY_BASE), latest.id || latest.date || 'seen')
    }
    setOpen(false)
  }

  if (!open || !entries.length) return null

  return (
    <div className="fixed inset-0 z-[100] flex items-end sm:items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-md glass-card border border-surface-700 shadow-2xl animate-in fade-in slide-in-from-bottom-4">
        <div className="flex items-center justify-between p-4 border-b border-surface-800">
          <h2 className="font-semibold text-white flex items-center gap-2">
            <Sparkles size={16} className="text-accent-cyan" /> What&apos;s new
          </h2>
          <button type="button" onClick={dismiss} className="text-surface-500 hover:text-white p-1">
            <X size={18} />
          </button>
        </div>
        <ul className="p-4 space-y-3 max-h-72 overflow-y-auto text-sm">
          {entries.map((entry, i) => (
            <li key={entry.id || i} className="border-b border-surface-800/50 pb-3 last:border-0">
              <p className="font-medium text-white">{entry.title || entry.summary}</p>
              {entry.date && <p className="text-[10px] text-surface-500 mt-0.5">{entry.date}</p>}
              <p className="text-surface-400 text-xs mt-1">{entry.body || entry.description}</p>
            </li>
          ))}
        </ul>
        <div className="p-4 pt-0">
          <button type="button" onClick={dismiss} className="btn-primary w-full text-sm">
            Got it
          </button>
        </div>
      </div>
    </div>
  )
}
