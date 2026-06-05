import { useState, useEffect } from 'react'
import { adminApi } from '../../api/admin'
import { MessageSquare, Pin, Lock, Trash2, Search, Shield, Reply, X } from 'lucide-react'
import toast from 'react-hot-toast'

export default function AdminThreads() {
  const [threads, setThreads] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [selectedThread, setSelectedThread] = useState(null)
  const [replyBody, setReplyBody] = useState('')
  const [replying, setReplying] = useState(false)

  useEffect(() => { loadThreads() }, [])

  const loadThreads = async () => {
    try {
      const data = await adminApi.getThreads()
      setThreads(data.threads || [])
    } catch {
      toast.error('Failed to load threads')
    } finally {
      setLoading(false)
    }
  }

  const openThread = async (threadId) => {
    try {
      const data = await adminApi.getThreadDetail(threadId)
      setSelectedThread(data)
      setReplyBody('')
    } catch {
      toast.error('Failed to load thread')
    }
  }

  // Live poll for new replies while modal is open
  useEffect(() => {
    if (!selectedThread?.id) return
    const poll = async () => {
      try {
        const data = await adminApi.getThreadDetail(selectedThread.id)
        setSelectedThread((prev) => {
          if (!prev || prev.id !== data.id) return data
          if ((prev.replies?.length || 0) !== (data.replies?.length || 0)) {
            return { ...prev, replies: data.replies, reply_count: data.reply_count }
          }
          return prev
        })
      } catch { /* ignore */ }
    }
    const interval = setInterval(poll, 4000)
    return () => clearInterval(interval)
  }, [selectedThread?.id])

  const handleReply = async () => {
    if (!replyBody.trim() || !selectedThread) return
    setReplying(true)
    try {
      await adminApi.replyToThread(selectedThread.id, replyBody.trim())
      toast.success('Reply posted')
      setReplyBody('')
      openThread(selectedThread.id)
      loadThreads()
    } catch {
      toast.error('Failed to post reply')
    } finally {
      setReplying(false)
    }
  }

  const handleDelete = async (threadId) => {
    if (!confirm('Delete this thread? This action is irreversible.')) return
    try {
      await adminApi.deleteThread(threadId)
      toast.success('Thread deleted')
      if (selectedThread?.id === threadId) setSelectedThread(null)
      loadThreads()
    } catch {
      toast.error('Failed to delete thread')
    }
  }

  const handleTogglePin = async (threadId, current) => {
    try {
      await adminApi.updateThread(threadId, { is_pinned: !current })
      toast.success(current ? 'Thread unpinned' : 'Thread pinned')
      loadThreads()
      if (selectedThread?.id === threadId) openThread(threadId)
    } catch {
      toast.error('Failed to update thread')
    }
  }

  const handleToggleLock = async (threadId, current) => {
    try {
      await adminApi.updateThread(threadId, { is_locked: !current })
      toast.success(current ? 'Thread unlocked' : 'Thread locked')
      loadThreads()
      if (selectedThread?.id === threadId) openThread(threadId)
    } catch {
      toast.error('Failed to update thread')
    }
  }

  const filtered = threads.filter(t =>
    !search ||
    t.title?.toLowerCase().includes(search.toLowerCase()) ||
    t.author?.toLowerCase().includes(search.toLowerCase())
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Shield size={24} className="text-accent-purple" />
          Thread Moderation
        </h1>
        <p className="text-surface-400 mt-1">Manage community discussions, reply as admin, pin or lock threads</p>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-400" size={16} />
        <input
          type="text"
          placeholder="Search threads by title or author..."
          className="input-field pl-10 w-full"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="space-y-3">
        {filtered.map(thread => (
          <div key={thread.id} className="glass-card p-4 flex items-start justify-between gap-4">
            <button
              type="button"
              onClick={() => openThread(thread.id)}
              className="flex-1 min-w-0 text-left hover:opacity-90 transition-opacity"
            >
              <div className="flex items-center gap-2 mb-1">
                {thread.is_pinned && <Pin size={14} className="text-amber-400 shrink-0" />}
                {thread.is_locked && <Lock size={14} className="text-red-400 shrink-0" />}
                <h3 className="font-medium truncate">{thread.title}</h3>
              </div>
              <p className="text-sm text-surface-400 line-clamp-2 mb-2">{thread.body}</p>
              <div className="flex items-center gap-3 text-xs text-surface-500">
                <span>by <span className="text-surface-300">{thread.author}</span></span>
                {thread.technology && (
                  <span className="px-1.5 py-0.5 bg-cyan-500/10 text-cyan-400 rounded">{thread.technology}</span>
                )}
                <span>{thread.reply_count} replies</span>
                <span>{thread.upvotes} upvotes</span>
                <span>{new Date(thread.created_at).toLocaleDateString()}</span>
              </div>
            </button>
            <div className="flex items-center gap-1 shrink-0">
              <button
                onClick={() => openThread(thread.id)}
                className="p-2 rounded-lg hover:bg-surface-700 text-surface-400 hover:text-accent-cyan transition-colors"
                title="View & Reply"
              >
                <Reply size={16} />
              </button>
              <button
                onClick={() => handleTogglePin(thread.id, thread.is_pinned)}
                className={`p-2 rounded-lg hover:bg-surface-700 transition-colors ${thread.is_pinned ? 'text-amber-400' : 'text-surface-400'}`}
                title={thread.is_pinned ? 'Unpin' : 'Pin'}
              >
                <Pin size={16} />
              </button>
              <button
                onClick={() => handleToggleLock(thread.id, thread.is_locked)}
                className={`p-2 rounded-lg hover:bg-surface-700 transition-colors ${thread.is_locked ? 'text-red-400' : 'text-surface-400'}`}
                title={thread.is_locked ? 'Unlock' : 'Lock'}
              >
                <Lock size={16} />
              </button>
              <button
                onClick={() => handleDelete(thread.id)}
                className="p-2 rounded-lg hover:bg-red-500/10 text-surface-400 hover:text-red-400 transition-colors"
                title="Delete Thread"
              >
                <Trash2 size={16} />
              </button>
            </div>
          </div>
        ))}

        {filtered.length === 0 && (
          <div className="text-center py-12 text-surface-400">
            <MessageSquare size={40} className="mx-auto mb-3 opacity-50" />
            <p>{search ? 'No matching threads' : 'No community threads yet'}</p>
          </div>
        )}
      </div>

      {selectedThread && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
          <div className="glass-card w-full max-w-2xl max-h-[85vh] overflow-y-auto p-6 space-y-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-bold text-white">{selectedThread.title}</h2>
                <p className="text-xs text-surface-500 mt-1">
                  by {selectedThread.author}
                  {selectedThread.is_locked && ' · Locked'}
                </p>
              </div>
              <button onClick={() => setSelectedThread(null)} className="p-2 text-surface-400 hover:text-white">
                <X size={18} />
              </button>
            </div>

            <div className="p-4 bg-surface-800/50 rounded-lg text-sm text-surface-300 whitespace-pre-wrap">
              {selectedThread.body}
            </div>

            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-white">
                Replies ({selectedThread.replies?.length || 0})
              </h3>
              {(selectedThread.replies || []).map(r => (
                <div key={r.id} className="p-3 bg-surface-900/50 rounded-lg text-sm">
                  <p className="text-xs text-surface-500 mb-1">
                    {r.author} · {new Date(r.created_at).toLocaleString()}
                  </p>
                  <p className="text-surface-300 whitespace-pre-wrap">{r.body}</p>
                </div>
              ))}
            </div>

            <div className="border-t border-surface-700/50 pt-4 space-y-2">
              <label className="text-xs text-surface-400 flex items-center gap-1">
                <Reply size={12} /> Admin reply {selectedThread.is_locked && '(works on locked threads)'}
              </label>
              <textarea
                className="input-field w-full min-h-[100px]"
                placeholder="Write your reply..."
                value={replyBody}
                onChange={(e) => setReplyBody(e.target.value)}
              />
              <div className="flex justify-end">
                <button
                  onClick={handleReply}
                  disabled={replying || !replyBody.trim()}
                  className="btn-primary text-sm"
                >
                  {replying ? 'Posting...' : 'Post Reply'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
