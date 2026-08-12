import { useState, useEffect } from 'react'
import { Sparkles } from '../ui/eagerIcons'
import api from '../api/client'
import ConfirmModal from './ConfirmModal'
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

  if (!entries.length) return null

  return (
    <ConfirmModal open={open} onClose={dismiss} title="What's new" maxWidth="max-w-md">
      <div className="flex items-center gap-2 text-accent-cyan text-xs font-medium mb-3 -mt-1">
        <Sparkles size={14} /> Latest updates
      </div>
      <ul className="space-y-3 max-h-72 overflow-y-auto text-sm mb-4">
        {entries.map((entry, i) => (
          <li key={entry.id || i} className="border-b border-surface-800/50 pb-3 last:border-0">
            <p className="font-medium text-white">{entry.title || entry.summary}</p>
            {entry.date && <p className="text-[10px] text-surface-500 mt-0.5">{entry.date}</p>}
            <p className="text-surface-400 text-xs mt-1">{entry.body || entry.description}</p>
          </li>
        ))}
      </ul>
      <button type="button" onClick={dismiss} className="btn-primary w-full text-sm">
        Got it
      </button>
    </ConfirmModal>
  )
}
