import { useState, useEffect, useCallback } from 'react'
import {
  MessageSquare, Plus, Search, ChevronUp, ChevronDown,
  Send, Edit3, Trash2, Pin, Lock, Filter, X, Clock, ImagePlus, Flag,
  Users, Sparkles
} from 'lucide-react'
import { communityApi } from '../api/community'
import { useAuthStore } from '../store/authStore'
import { useDataStore } from '../store/dataStore'
import toast from 'react-hot-toast'
import { resolveMediaUrl, IMAGE_UPLOAD_HINTS } from '../utils/mediaUrl'
import Pagination from '../components/Pagination'
import StickyPageToolbar from '../components/StickyPageToolbar'

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

function AuthorAvatar({ username, size = 'sm' }) {
  const initials = (username || '?').slice(0, 2).toUpperCase()
  const colors = [
    'from-accent-cyan/40 to-accent-blue/40 text-accent-cyan border-accent-cyan/20',
    'from-accent-purple/40 to-accent-pink/40 text-accent-purple border-accent-purple/20',
    'from-accent-green/40 to-accent-cyan/40 text-accent-green border-accent-green/20',
    'from-accent-amber/40 to-accent-red/40 text-accent-amber border-accent-amber/20',
  ]
  const idx = (username || '').charCodeAt(0) % colors.length
  const dim = size === 'lg' ? 'w-10 h-10 text-sm' : 'w-7 h-7 text-xs'
  return (
    <div className={`${dim} rounded-lg bg-gradient-to-br ${colors[idx]} border flex items-center justify-center font-bold shrink-0`}>
      {initials}
    </div>
  )
}

export default function Community() {
  const { user } = useAuthStore()
  const isAdmin = user?.is_staff
  const getTechnologies = useDataStore(s => s.getTechnologies)

  const [threads, setThreads] = useState([])
  const [threadCount, setThreadCount] = useState(0)
  const [threadPage, setThreadPage] = useState(1)
  const [selectedThread, setSelectedThread] = useState(null)
  const [technologies, setTechnologies] = useState([])
  const [loading, setLoading] = useState(true)
  const [showNewThread, setShowNewThread] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchInput, setSearchInput] = useState(searchQuery)
  const [techFilter, setTechFilter] = useState('')

  useEffect(() => {
    const timer = setTimeout(() => setSearchQuery(searchInput), 300)
    return () => clearTimeout(timer)
  }, [searchInput])

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
    getTechnologies().then(techs => setTechnologies(techs)).catch(() => {})
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
    } catch (err) {
      toast.error(err.response?.data?.error || 'Upload failed')
    }
  }

  const renderReply = (reply) => (
    <div key={reply.id} className="border-l-2 border-surface-600/40 pl-4 py-3 group/msg">
      <div className="flex items-center gap-2.5 mb-2">
        <AuthorAvatar username={reply.author?.username} />
        <span className="font-medium text-sm text-white">{reply.author?.username}</span>
        {reply.author?.is_premium && (
          <span className="px-1.5 py-0.5 text-[10px] bg-accent-amber/20 text-accent-amber rounded-md border border-accent-amber/20 font-semibold">PRO</span>
        )}
        <span className="text-xs text-surface-500">{timeAgo(reply.created_at)}</span>
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
            <a key={att.id} href={resolveMediaUrl(att.url)} target="_blank" rel="noreferrer" className="block">
              <img src={resolveMediaUrl(att.url)} alt={att.original_name || 'attachment'} className="max-h-48 max-w-full rounded-lg border border-surface-700 object-contain bg-surface-900/50" onError={(e) => { e.currentTarget.classList.add('opacity-40') }} />
            </a>
          ))}
        </div>
      )}

      <div className="relative mt-2 min-h-[1.25rem]">
        <div className="flex flex-wrap items-center gap-1">
          {REACTION_EMOJIS.map(em => {
            const count = reply.reactions?.[em] || 0
            const active = reply.user_reactions?.includes(em)
            if (!count) return null
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
        {user && (
          <div className="absolute -top-9 left-0 z-10 flex items-center gap-0.5 px-2 py-1 rounded-lg bg-surface-800 border border-surface-700 shadow-lg opacity-0 invisible group-hover/msg:opacity-100 group-hover/msg:visible transition-all duration-150">
            {REACTION_EMOJIS.map(em => {
              const active = reply.user_reactions?.includes(em)
              return (
                <button
                  key={`pick-${em}`}
                  type="button"
                  title={`React with ${em}`}
                  onClick={() => handleReact(reply.id, em)}
                  className={`text-base leading-none px-1 py-0.5 rounded hover:bg-surface-700/80 hover:scale-110 transition-transform ${active ? 'bg-accent-cyan/10' : ''}`}
                >
                  {em}
                </button>
              )
            })}
          </div>
        )}
      </div>

      <div className="flex items-center gap-3 mt-1">
        <button
          onClick={() => communityApi.voteReply(reply.id, 'up').then(() => loadThread(selectedThread.id))}
          className="flex items-center gap-1 text-xs text-surface-400 hover:text-accent-cyan transition-colors"
        >
          <ChevronUp size={14} /> {reply.upvotes || 0}
        </button>
        {(reply.author?.id === user?.id || isAdmin) && (
          <>
            <button
              onClick={() => { setEditingReply(reply.id); setEditBody(reply.body) }}
              className="text-xs text-surface-400 hover:text-accent-blue transition-colors"
            >
              <Edit3 size={12} />
            </button>
            <button
              onClick={() => handleDeleteReply(reply.id)}
              className="text-xs text-surface-400 hover:text-accent-red transition-colors"
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
    <div className="space-y-5">
      <StickyPageToolbar>
        {/* ── Header ─────────────────────────────────────────── */}
        <div className="relative overflow-hidden glass-card p-6 sm:p-7">
          <div className="absolute inset-0 bg-gradient-to-r from-accent-cyan/8 via-transparent to-accent-purple/8 pointer-events-none" />
          <div className="absolute inset-0 bg-dots-pattern opacity-20 pointer-events-none" />
          <div className="relative flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="min-w-0">
              <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-accent-cyan/10 border border-accent-cyan/20 flex items-center justify-center shrink-0">
                  <MessageSquare size={20} className="text-accent-cyan" />
                </div>
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-accent-cyan to-accent-purple">
                  Community
                </span>
              </h1>
              <p className="text-surface-400 mt-1.5 text-sm ml-[3.25rem]">Ask questions, share knowledge, and help others</p>
            </div>
            <button
              onClick={() => setShowNewThread(true)}
              className="btn-primary flex items-center gap-2 shrink-0 self-start sm:self-auto"
            >
              <Plus size={16} /> New Thread
            </button>
          </div>
        </div>

        {/* ── Search + tech filter ────────────────────────────── */}
        <div className="flex gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-400 pointer-events-none" size={16} />
            <input
              type="text"
              placeholder="Search threads..."
              className="input-field pl-10 w-full"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
            />
          </div>
          <select
            className="input-field w-44"
            value={techFilter}
            onChange={(e) => { setTechFilter(e.target.value); setThreadPage(1) }}
          >
            <option value="">All Topics</option>
            {technologies.map(t => (
              <option key={t.id} value={t.slug}>{t.name}</option>
            ))}
          </select>
        </div>

        {/* ── Category filter chips ───────────────────────────── */}
        {technologies.length > 0 && (
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => { setTechFilter(''); setThreadPage(1) }}
              className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                !techFilter
                  ? 'border-accent-cyan/50 bg-accent-cyan/10 text-accent-cyan'
                  : 'border-surface-700 text-surface-400 hover:border-surface-500 hover:text-surface-200'
              }`}
            >
              All
            </button>
            {technologies.map(t => (
              <button
                key={t.id}
                onClick={() => { setTechFilter(t.slug); setThreadPage(1) }}
                className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                  techFilter === t.slug
                    ? 'border-accent-cyan/50 bg-accent-cyan/10 text-accent-cyan'
                    : 'border-surface-700 text-surface-400 hover:border-surface-500 hover:text-surface-200'
                }`}
              >
                {t.name}
              </button>
            ))}
          </div>
        )}
      </StickyPageToolbar>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* ── Thread List ──────────────────────────────────────── */}
        <div className="lg:col-span-1 space-y-2">
          {loading ? (
            <div className="glass-card p-8 text-center">
              <div className="w-8 h-8 border-2 border-accent-cyan/30 border-t-accent-cyan rounded-full animate-spin mx-auto mb-3" />
              <p className="text-surface-400 text-sm">Loading threads...</p>
            </div>
          ) : threads.length === 0 ? (
            <div className="glass-card p-8 text-center">
              <div className="w-12 h-12 rounded-xl bg-surface-800 flex items-center justify-center mx-auto mb-3">
                <MessageSquare size={24} className="text-surface-500" />
              </div>
              <p className="text-surface-400 text-sm mb-3">No threads yet</p>
              <button onClick={() => setShowNewThread(true)} className="btn-primary text-sm flex items-center gap-1 mx-auto">
                <Plus size={14} /> Start a thread
              </button>
            </div>
          ) : (
            threads.map(thread => (
              <button
                key={thread.id}
                onClick={() => loadThread(thread.id)}
                className={`w-full text-left p-4 rounded-xl border transition-all group ${
                  selectedThread?.id === thread.id
                    ? 'border-accent-cyan/50 bg-accent-cyan/5'
                    : 'border-surface-700/50 bg-surface-800/40 hover:border-accent-cyan/30 hover:bg-surface-800/60'
                }`}
              >
                {/* Title row */}
                <div className="flex items-start gap-2 mb-2">
                  {thread.is_pinned && <Pin size={11} className="text-accent-amber shrink-0 mt-0.5" />}
                  {thread.is_locked && <Lock size={11} className="text-accent-red shrink-0 mt-0.5" />}
                  <h3 className="font-medium text-sm text-white group-hover:text-accent-cyan transition-colors line-clamp-2 leading-snug">{thread.title}</h3>
                </div>

                {/* Meta row */}
                <div className="flex items-center gap-2 mb-2">
                  <AuthorAvatar username={thread.author?.username} />
                  <span className="text-xs text-surface-400 font-medium">{thread.author?.username}</span>
                </div>

                {/* Stats row */}
                <div className="flex items-center gap-3 text-xs text-surface-500">
                  <span className="flex items-center gap-1">
                    <ChevronUp size={12} className="text-accent-cyan" />
                    <span className="text-surface-300 font-medium">{thread.upvotes || 0}</span>
                  </span>
                  <span className="flex items-center gap-1">
                    <MessageSquare size={11} />
                    <span>{thread.reply_count || 0}</span>
                  </span>
                  <span className="flex items-center gap-1 ml-auto">
                    <Clock size={11} />
                    {timeAgo(thread.created_at)}
                  </span>
                </div>

                {thread.technology_name && (
                  <span className="inline-block mt-2 px-2 py-0.5 text-[10px] bg-accent-cyan/10 text-accent-cyan rounded-md border border-accent-cyan/20 font-medium">
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

        {/* ── Thread Detail ────────────────────────────────────── */}
        <div className="lg:col-span-2">
          {selectedThread ? (
            <div className="glass-card p-6 space-y-5">
              {/* Thread header */}
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-2 flex-wrap">
                    {selectedThread.is_pinned && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs bg-accent-amber/10 text-accent-amber rounded-md border border-accent-amber/20">
                        <Pin size={10} /> Pinned
                      </span>
                    )}
                    {selectedThread.is_locked && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs bg-accent-red/10 text-accent-red rounded-md border border-accent-red/20">
                        <Lock size={10} /> Locked
                      </span>
                    )}
                    {selectedThread.technology_name && (
                      <span className="px-2 py-0.5 text-xs bg-accent-cyan/10 text-accent-cyan rounded-md border border-accent-cyan/20 font-medium">
                        {selectedThread.technology_name}
                      </span>
                    )}
                  </div>
                  <h2 className="text-xl font-bold text-white leading-snug">{selectedThread.title}</h2>
                  <div className="flex items-center gap-2.5 mt-2">
                    <AuthorAvatar username={selectedThread.author?.username} />
                    <span className="text-sm font-medium text-surface-200">{selectedThread.author?.username}</span>
                    {selectedThread.author?.is_premium && (
                      <span className="px-1.5 py-0.5 text-[10px] bg-accent-amber/20 text-accent-amber rounded-md border border-accent-amber/20 font-semibold">PRO</span>
                    )}
                    <span className="text-xs text-surface-500">{timeAgo(selectedThread.created_at)}</span>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => handleVoteThread(selectedThread.id, 'up')}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-sm font-medium transition-colors ${
                      selectedThread.user_vote === 'up'
                        ? 'border-accent-cyan/50 bg-accent-cyan/10 text-accent-cyan'
                        : 'border-surface-700 text-surface-400 hover:border-accent-cyan/30 hover:text-accent-cyan'
                    }`}
                  >
                    <ChevronUp size={14} /> {selectedThread.upvotes || 0}
                  </button>
                  {user && selectedThread.author?.id !== user.id && (
                    <button
                      onClick={() => handleReportThread(selectedThread.id)}
                      className="w-8 h-8 flex items-center justify-center rounded-lg border border-surface-700 text-surface-400 hover:border-accent-amber/30 hover:text-accent-amber transition-colors"
                      title="Report thread"
                    >
                      <Flag size={14} />
                    </button>
                  )}
                  {(selectedThread.author?.id === user?.id || isAdmin) && (
                    <button
                      onClick={() => handleDeleteThread(selectedThread.id)}
                      className="w-8 h-8 flex items-center justify-center rounded-lg border border-surface-700 text-surface-400 hover:border-accent-red/30 hover:text-accent-red transition-colors"
                    >
                      <Trash2 size={14} />
                    </button>
                  )}
                </div>
              </div>

              {/* Body */}
              <div className="py-4 border-t border-b border-surface-700/40 whitespace-pre-wrap text-surface-200 leading-relaxed text-sm">
                {selectedThread.body}
              </div>

              {/* Attachments */}
              {selectedThread.attachments?.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {selectedThread.attachments.map(att => (
                    <a key={att.id} href={resolveMediaUrl(att.url)} target="_blank" rel="noreferrer">
                      <img src={resolveMediaUrl(att.url)} alt={att.original_name || 'Screenshot'} className="max-h-56 max-w-full rounded-xl border border-surface-700 object-contain bg-surface-900/50" onError={(e) => { e.currentTarget.classList.add('opacity-40') }} />
                    </a>
                  ))}
                </div>
              )}

              {/* Replies */}
              <div className="space-y-1">
                <h3 className="text-xs font-bold text-surface-500 uppercase tracking-widest mb-3 flex items-center gap-2">
                  <MessageSquare size={12} />
                  {selectedThread.replies?.length || 0} {selectedThread.replies?.length === 1 ? 'Reply' : 'Replies'}
                </h3>
                <div className="space-y-1">
                  {selectedThread.replies?.map(renderReply)}
                </div>
              </div>

              {/* Reply form — admins can reply on locked threads */}
              {(!selectedThread.is_locked || isAdmin) ? (
                <form onSubmit={handleReply} className="flex flex-wrap gap-2 pt-4 border-t border-surface-700/40 items-center">
                  <input
                    type="text"
                    placeholder={selectedThread.is_locked && isAdmin ? 'Admin reply (thread locked for others)...' : 'Write a reply...'}
                    className="input-field flex-1 min-w-[200px]"
                    value={replyBody}
                    onChange={(e) => setReplyBody(e.target.value)}
                  />
                  <label className="btn-secondary text-xs px-3 py-2 cursor-pointer flex items-center gap-1">
                    <ImagePlus size={14} /> Screenshot
                    <input type="file" accept="image/png,image/jpeg,image/gif,image/webp" className="hidden" title={IMAGE_UPLOAD_HINTS.community_screenshot} onChange={e => handleAttachment(e.target.files?.[0])} />
                  </label>
                  <button type="submit" className="btn-primary flex items-center gap-1.5 px-4">
                    <Send size={14} /> Reply
                  </button>
                </form>
              ) : (
                <p className="text-center text-surface-400 text-sm py-2 border-t border-surface-700/40">
                  <Lock size={12} className="inline mr-1" /> This thread is locked. No new replies.
                </p>
              )}
            </div>
          ) : (
            <div className="glass-card p-16 text-center">
              <div className="w-16 h-16 rounded-2xl bg-surface-800 flex items-center justify-center mx-auto mb-4">
                <MessageSquare size={28} className="text-surface-500" />
              </div>
              <p className="text-surface-300 font-medium mb-1">Select a thread</p>
              <p className="text-surface-500 text-sm">Choose a thread from the list to view the discussion</p>
              <button onClick={() => setShowNewThread(true)} className="btn-primary mt-5 flex items-center gap-2 mx-auto">
                <Plus size={14} /> Start a new thread
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ── New Thread Modal ─────────────────────────────────────── */}
      {showNewThread && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="glass-card p-6 w-full max-w-lg space-y-4 animate-scale-in">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-accent-cyan/10 border border-accent-cyan/20 flex items-center justify-center">
                  <Plus size={16} className="text-accent-cyan" />
                </div>
                <h2 className="text-lg font-bold text-white">New Thread</h2>
              </div>
              <button onClick={() => setShowNewThread(false)} className="w-8 h-8 flex items-center justify-center rounded-lg text-surface-400 hover:text-white hover:bg-surface-700 transition-colors">
                <X size={18} />
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
                  {newThreadFile ? newThreadFile.name : 'Attach screenshot'}
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/gif,image/webp"
                    className="hidden"
                    onChange={e => setNewThreadFile(e.target.files?.[0] || null)}
                  />
                </label>
                {newThreadFile && (
                  <button type="button" onClick={() => setNewThreadFile(null)} className="text-xs text-surface-400 hover:text-accent-red transition-colors">
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
              <div className="flex gap-2 justify-end pt-1">
                <button type="button" onClick={() => setShowNewThread(false)} className="btn-secondary">
                  Cancel
                </button>
                <button type="submit" className="btn-primary flex items-center gap-2">
                  <Send size={14} /> Post Thread
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
