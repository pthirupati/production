import { useState, useEffect, useCallback } from 'react'
import {
  MessageSquare, Plus, Search, ChevronUp, ChevronDown,
  Send, Edit3, Trash2, Pin, Lock, Filter, X, Clock, ImagePlus, Flag
} from 'lucide-react'
import { communityApi } from '../api/community'
import { scenarioApi } from '../api/scenarios'
import { useAuthStore } from '../store/authStore'
import toast from 'react-hot-toast'
import Pagination from '../components/Pagination'

function timeAgo(dateStr) {
  const d = new Date(dateStr)
  const now = new Date()
  const seconds = Math.floor((now - d) / 1000)
  if (seconds < 60) return 'just now'
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  if (seconds < 2592000) return `${Math.floor(seconds / 86400)}d ago`
  return d.toLocaleDateString()
}

export default function Community() {
  const { user } = useAuthStore()
  const isAdmin = user?.is_staff

  const [threads, setThreads] = useState([])
  const [threadCount, setThreadCount] = useState(0)
  const [threadPage, setThreadPage] = useState(1)
  const [selectedThread, setSelectedThread] = useState(null)
  const [technologies, setTechnologies] = useState([])
  const [loading, setLoading] = useState(true)
  const [showNewThread, setShowNewThread] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [techFilter, setTechFilter] = useState('')

  // New thread form
  const [newTitle, setNewTitle] = useState('')
  const [newBody, setNewBody] = useState('')
  const [newThreadFile, setNewThreadFile] = useState(null)
  const [newTech, setNewTech] = useState('')

  // Reply form
  const [replyBody, setReplyBody] = useState('')
  const [editingReply, setEditingReply] = useState(null)
  const [editBody, setEditBody] = useState('')

  const fetchThreads = useCallback(async () => {
    try {
      setLoading(true)
      const data = await communityApi.getThreads({
        technology: techFilter,
        search: searchQuery,
        page: threadPage,
      })
      setThreads(data.results || [])
      setThreadCount(data.count || 0)
    } catch (err) {
      console.error('Failed to fetch threads:', err)
    } finally {
      setLoading(false)
    }
  }, [techFilter, searchQuery, threadPage])

  useEffect(() => {
    fetchThreads()
    scenarioApi.getTechnologies().then(setTechnologies).catch(() => {})
  }, [fetchThreads])

  // Live updates for open thread (poll every 4s)
  useEffect(() => {
    if (!selectedThread?.id) return

    const poll = async () => {
      try {
        const data = await communityApi.getThread(selectedThread.id)
        setSelectedThread((prev) => {
          if (!prev || prev.id !== data.id) return data
          const prevCount = prev.replies?.length || 0
          const newCount = data.replies?.length || 0
          if (newCount !== prevCount || prev.reply_count !== data.reply_count) {
            return { ...prev, replies: data.replies, reply_count: data.reply_count }
          }
          return prev
        })
      } catch {
        /* ignore transient poll errors */
      }
    }

    const interval = setInterval(poll, 4000)
    return () => clearInterval(interval)
  }, [selectedThread?.id])

  const loadThread = async (threadId) => {
    try {
      const data = await communityApi.getThread(threadId)
      setSelectedThread(data)
    } catch {
      toast.error('Failed to load thread')
    }
  }

  const handleCreateThread = async (e) => {
    e.preventDefault()
    if (!newTitle.trim() || !newBody.trim()) return
    try {
      const thread = await communityApi.createThread({
        title: newTitle,
        body: newBody,
        technology: newTech || null,
      })
      if (newThreadFile && thread?.id) {
        await communityApi.uploadAttachment(thread.id, newThreadFile)
      }
      toast.success('Thread created!')
      setShowNewThread(false)
      setNewTitle('')
      setNewBody('')
      setNewTech('')
      setNewThreadFile(null)
      fetchThreads()
    } catch {
      toast.error('Failed to create thread')
    }
  }

  const handleReply = async (e) => {
    e.preventDefault()
    if (!replyBody.trim() || !selectedThread) return
    try {
      await communityApi.createReply(selectedThread.id, { body: replyBody })
      setReplyBody('')
      loadThread(selectedThread.id)
      toast.success('Reply posted!')
    } catch {
      toast.error('Failed to post reply')
    }
  }

  const handleVoteThread = async (threadId, type) => {
    try {
      await communityApi.voteThread(threadId, type)
      if (selectedThread?.id === threadId) loadThread(threadId)
      fetchThreads()
    } catch {
      toast.error('Failed to vote')
    }
  }

  const handleDeleteThread = async (threadId) => {
    if (!confirm('Delete this thread?')) return
    try {
      await communityApi.deleteThread(threadId)
      toast.success('Thread deleted')
      setSelectedThread(null)
      fetchThreads()
    } catch {
      toast.error('Failed to delete')
    }
  }

  const handleReportThread = async (threadId) => {
    const reason = window.prompt('Report reason: spam, abuse, off_topic, or other', 'other')
    if (!reason) return
    try {
      await communityApi.reportThread(threadId, reason.trim().toLowerCase())
      toast.success('Report submitted — our moderators will review it.')
    } catch (err) {
      toast.error(err.response?.data?.error || 'Could not submit report')
    }
  }

  const handleEditReply = async (replyId) => {
    try {
      await communityApi.updateReply(replyId, { body: editBody })
      setEditingReply(null)
      setEditBody('')
      loadThread(selectedThread.id)
      toast.success('Reply updated')
    } catch {
      toast.error('Failed to update')
    }
  }

  const handleDeleteReply = async (replyId) => {
    if (!confirm('Delete this reply?')) return
    try {
      await communityApi.deleteReply(replyId)
      loadThread(selectedThread.id)
      toast.success('Reply deleted')
    } catch {
      toast.error('Failed to delete')
    }
  }

const REACTION_EMOJIS = ['👍', '👎', '❤️', '🎉', '😂', '🚀', '👀', '✅', '🔥', '💡']

  const handleReact = async (replyId, emoji) => {
    try {
      await communityApi.reactToReply(replyId, emoji)
      loadThread(selectedThread.id)
    } catch {
      toast.error('Reaction failed')
    }
  }

  const handleAttachment = async (file, replyId = null) => {
    if (!file || !selectedThread) return
    try {
      await communityApi.uploadAttachment(selectedThread.id, file, replyId)
      loadThread(selectedThread.id)
      toast.success('Screenshot attached')
    } catch {
      toast.error('Upload failed')
    }
  }

  const renderReply = (reply) => (
    <div key={reply.id} className="border-l-2 border-surface-600/50 pl-4 py-3">
      <div className="flex items-center gap-2 mb-1">
        <span className="font-medium text-sm">{reply.author?.username}</span>
        {reply.author?.is_premium && (
          <span className="px-1.5 py-0.5 text-xs bg-amber-500/20 text-amber-400 rounded">PRO</span>
        )}
        <span className="text-xs text-surface-400">{timeAgo(reply.created_at)}</span>
      </div>

      {editingReply === reply.id ? (
        <div className="flex gap-2 mt-1">
          <input
            className="input-field flex-1 text-sm"
            value={editBody}
            onChange={(e) => setEditBody(e.target.value)}
          />
          <button onClick={() => handleEditReply(reply.id)} className="btn-primary text-xs px-3">Save</button>
          <button onClick={() => setEditingReply(null)} className="text-xs text-surface-400 hover:text-surface-200">Cancel</button>
        </div>
      ) : (
        <p className="text-sm text-surface-200 whitespace-pre-wrap leading-relaxed">{reply.body}</p>
      )}

      {reply.attachments?.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-2">
          {reply.attachments.map(att => (
            <a key={att.id} href={att.url} target="_blank" rel="noreferrer" className="block">
              <img src={att.url} alt={att.original_name || 'attachment'} className="max-h-32 rounded border border-surface-700" />
            </a>
          ))}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-1 mt-2">
        {REACTION_EMOJIS.map(em => {
          const count = reply.reactions?.[em] || 0
          const active = reply.user_reactions?.includes(em)
          if (!user && !count) return null
          return (
            <button
              key={em}
              type="button"
              disabled={!user}
              onClick={() => handleReact(reply.id, em)}
              className={`text-xs px-1.5 py-0.5 rounded-full border ${active ? 'border-accent-cyan bg-accent-cyan/10' : 'border-surface-700 text-surface-400 hover:border-surface-500'}`}
            >
              {em}{count ? ` ${count}` : ''}
            </button>
          )
        })}
      </div>

      <div className="flex items-center gap-3 mt-1">
        <button
          onClick={() => communityApi.voteReply(reply.id, 'up').then(() => loadThread(selectedThread.id))}
          className="flex items-center gap-1 text-xs text-surface-400 hover:text-cyan-400"
        >
          <ChevronUp size={14} /> {reply.upvotes || 0}
        </button>
        {(reply.author?.id === user?.id || isAdmin) && (
          <>
            <button
              onClick={() => { setEditingReply(reply.id); setEditBody(reply.body) }}
              className="text-xs text-surface-400 hover:text-blue-400"
            >
              <Edit3 size={12} />
            </button>
            <button
              onClick={() => handleDeleteReply(reply.id)}
              className="text-xs text-surface-400 hover:text-red-400"
            >
              <Trash2 size={12} />
            </button>
          </>
        )}
      </div>

      {reply.children?.map(renderReply)}
    </div>
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="relative overflow-hidden glass-card p-8 mb-6">
        <div className="absolute inset-0 bg-gradient-to-r from-accent-cyan/8 via-transparent to-accent-purple/8" />
        <div className="absolute inset-0 bg-dots-pattern opacity-20" />
        <div className="relative flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-black text-white tracking-tight flex items-center gap-3">
              <MessageSquare className="text-accent-cyan" size={28} /> <span className="bg-gradient-to-r from-accent-cyan to-accent-purple bg-clip-text text-transparent">Community</span>
            </h1>
            <p className="text-surface-400 mt-2">Ask questions, share knowledge, and help others</p>
          </div>
          <button
            onClick={() => setShowNewThread(true)}
            className="btn-primary flex items-center gap-2"
          >
            <Plus size={16} /> New Thread
          </button>
        </div>
      </div>

      {/* Search & Filters */}
      <div className="flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-400" size={16} />
          <input
            type="text"
            placeholder="Search threads..."
            className="input-field pl-10 w-full"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        <select
          className="input-field w-48"
          value={techFilter}
          onChange={(e) => setTechFilter(e.target.value)}
        >
          <option value="">All Topics</option>
          {technologies.map(t => (
            <option key={t.id} value={t.slug}>{t.name}</option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Thread List */}
        <div className="lg:col-span-1 space-y-2">
          {loading ? (
            <div className="text-center py-8 text-surface-400">Loading...</div>
          ) : threads.length === 0 ? (
            <div className="text-center py-8 text-surface-400">
              <MessageSquare size={40} className="mx-auto mb-2 opacity-50" />
              <p>No threads yet. Start one!</p>
            </div>
          ) : (
            threads.map(thread => (
              <button
                key={thread.id}
                onClick={() => loadThread(thread.id)}
                className={`w-full text-left p-4 rounded-lg border transition-all hover:border-cyan-500/50 ${
                  selectedThread?.id === thread.id
                    ? 'border-cyan-500 bg-cyan-500/5'
                    : 'border-surface-700/50 bg-surface-800/50 hover:bg-surface-800'
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  {thread.is_pinned && <Pin size={12} className="text-amber-400" />}
                  {thread.is_locked && <Lock size={12} className="text-red-400" />}
                  <h3 className="font-medium text-sm line-clamp-1">{thread.title}</h3>
                </div>
                <div className="flex items-center gap-3 text-xs text-surface-400">
                  <span>{thread.author?.username}</span>
                  <span className="flex items-center gap-1">
                    <ChevronUp size={12} /> {thread.upvotes || 0}
                  </span>
                  <span className="flex items-center gap-1">
                    <MessageSquare size={12} /> {thread.reply_count || 0}
                  </span>
                  <span className="flex items-center gap-1">
                    <Clock size={12} /> {timeAgo(thread.created_at)}
                  </span>
                </div>
                {thread.technology_name && (
                  <span className="inline-block mt-1 px-2 py-0.5 text-xs bg-cyan-500/10 text-cyan-400 rounded">
                    {thread.technology_name}
                  </span>
                )}
              </button>
            ))
          )}
          {threadCount > 20 && (
            <Pagination
              currentPage={threadPage}
              totalPages={Math.ceil(threadCount / 20)}
              onPageChange={(p) => { setThreadPage(p); setSelectedThread(null) }}
            />
          )}
        </div>

        {/* Thread Detail */}
        <div className="lg:col-span-2">
          {selectedThread ? (
            <div className="glass-card p-6 space-y-4">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    {selectedThread.is_pinned && <Pin size={14} className="text-amber-400" />}
                    {selectedThread.is_locked && <Lock size={14} className="text-red-400" />}
                    <h2 className="text-xl font-bold">{selectedThread.title}</h2>
                  </div>
                  <div className="flex items-center gap-3 text-sm text-surface-400">
                    <span className="font-medium">{selectedThread.author?.username}</span>
                    {selectedThread.author?.is_premium && (
                      <span className="px-1.5 py-0.5 text-xs bg-amber-500/20 text-amber-400 rounded">PRO</span>
                    )}
                    <span>{timeAgo(selectedThread.created_at)}</span>
                    {selectedThread.technology_name && (
                      <span className="px-2 py-0.5 text-xs bg-cyan-500/10 text-cyan-400 rounded">
                        {selectedThread.technology_name}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleVoteThread(selectedThread.id, 'up')}
                    className={`flex items-center gap-1 px-2 py-1 rounded text-sm ${
                      selectedThread.user_vote === 'up' ? 'text-cyan-400' : 'text-surface-400 hover:text-cyan-400'
                    }`}
                  >
                    <ChevronUp size={16} /> {selectedThread.upvotes || 0}
                  </button>
                  {user && selectedThread.author?.id !== user.id && (
                    <button
                      onClick={() => handleReportThread(selectedThread.id)}
                      className="text-surface-400 hover:text-amber-400"
                      title="Report thread"
                    >
                      <Flag size={16} />
                    </button>
                  )}
                  {(selectedThread.author?.id === user?.id || isAdmin) && (
                    <button
                      onClick={() => handleDeleteThread(selectedThread.id)}
                      className="text-surface-400 hover:text-red-400"
                    >
                      <Trash2 size={16} />
                    </button>
                  )}
                </div>
              </div>

              <div className="py-4 border-t border-b border-surface-700/50 whitespace-pre-wrap text-surface-200 leading-relaxed">
                {selectedThread.body}
              </div>
              {selectedThread.attachments?.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {selectedThread.attachments.map(att => (
                    <a key={att.id} href={att.url} target="_blank" rel="noreferrer">
                      <img src={att.url} alt="" className="max-h-40 rounded border border-surface-700" />
                    </a>
                  ))}
                </div>
              )}

              {/* Replies */}
              <div className="space-y-1">
                <h3 className="font-semibold text-sm text-surface-400 uppercase tracking-wide mb-3">
                  Replies ({selectedThread.replies?.length || 0})
                </h3>
                {selectedThread.replies?.map(renderReply)}
              </div>

              {/* Reply Form — admins can reply on locked threads */}
              {(!selectedThread.is_locked || isAdmin) && (
                <form onSubmit={handleReply} className="flex flex-wrap gap-2 pt-4 border-t border-surface-700/50 items-center">
                  <input
                    type="text"
                    placeholder={selectedThread.is_locked && isAdmin ? 'Admin reply (thread locked for others)...' : 'Write a reply...'}
                    className="input-field flex-1 min-w-[200px]"
                    value={replyBody}
                    onChange={(e) => setReplyBody(e.target.value)}
                  />
                  <label className="btn-secondary text-xs px-3 py-2 cursor-pointer flex items-center gap-1">
                    <ImagePlus size={14} /> Attach screenshot
                    <input type="file" accept="image/*" className="hidden" onChange={e => handleAttachment(e.target.files?.[0])} />
                  </label>
                  <button type="submit" className="btn-primary flex items-center gap-1">
                    <Send size={14} /> Reply
                  </button>
                </form>
              )}
              {selectedThread.is_locked && !isAdmin && (
                <p className="text-center text-surface-400 text-sm py-2">
                  This thread is locked. No new replies.
                </p>
              )}
            </div>
          ) : (
            <div className="glass-card p-12 text-center text-surface-400">
              <MessageSquare size={48} className="mx-auto mb-3 opacity-50" />
              <p>Select a thread to view the discussion</p>
            </div>
          )}
        </div>
      </div>

      {/* New Thread Modal */}
      {showNewThread && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="glass-card p-6 w-full max-w-lg space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold">New Thread</h2>
              <button onClick={() => setShowNewThread(false)} className="text-surface-400 hover:text-surface-200">
                <X size={20} />
              </button>
            </div>
            <form onSubmit={handleCreateThread} className="space-y-3">
              <input
                type="text"
                placeholder="Thread title"
                className="input-field w-full"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                required
              />
              <textarea
                placeholder="Describe the issue — include error messages, what you tried, and expected behavior"
                className="input-field w-full h-32 resize-none"
                value={newBody}
                onChange={(e) => setNewBody(e.target.value)}
                required
              />
              <div className="flex flex-wrap items-center gap-3">
                <label className="btn-secondary text-sm px-3 py-2 cursor-pointer flex items-center gap-2">
                  <ImagePlus size={16} />
                  {newThreadFile ? newThreadFile.name : 'Attach error screenshot'}
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/gif,image/webp"
                    className="hidden"
                    onChange={e => setNewThreadFile(e.target.files?.[0] || null)}
                  />
                </label>
                {newThreadFile && (
                  <button type="button" onClick={() => setNewThreadFile(null)} className="text-xs text-surface-400 hover:text-red-400">
                    Remove
                  </button>
                )}
              </div>
              <select
                className="input-field w-full"
                value={newTech}
                onChange={(e) => setNewTech(e.target.value)}
              >
                <option value="">General (no technology)</option>
                {technologies.map(t => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
              <div className="flex gap-2 justify-end">
                <button type="button" onClick={() => setShowNewThread(false)} className="btn-secondary">
                  Cancel
                </button>
                <button type="submit" className="btn-primary">
                  Post Thread
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
