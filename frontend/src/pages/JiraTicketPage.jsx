import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { jiraApi } from '../api/jira'
import {
  ArrowLeft, MessageSquare, Loader2, ChevronRight, Clock, User,
  Tag, AlertCircle, CheckCircle2, Circle, MoreHorizontal, Search, Bell, HelpCircle
} from 'lucide-react'
import toast from 'react-hot-toast'
import { JiraRichText } from '../components/JiraRichText'
import { StatusLozenge, PriorityIcon, ActivityItem } from '../components/jira/JiraUi'
import { FixitLogo } from '../components/design'

function FieldRow({ label, children }) {
  return (
    <div className="py-2 border-b border-white/[0.06] last:border-0">
      <dt className="text-xs text-surface-500 font-medium mb-1">{label}</dt>
      <dd className="text-sm text-surface-200">{children}</dd>
    </div>
  )
}

export default function JiraTicketPage() {
  const { issueKey } = useParams()
  const [ticket, setTicket] = useState(null)
  const [loading, setLoading] = useState(true)
  const [comment, setComment] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [activeTab, setActiveTab] = useState('comments')

  const loadTicket = async () => {
    try {
      const res = await jiraApi.getIssue(issueKey)
      setTicket(res.data)
    } catch {
      toast.error('Ticket not found')
      setTicket(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadTicket()
  }, [issueKey])

  const handleTransition = async (status) => {
    setSubmitting(true)
    try {
      const res = await jiraApi.transitionIssue(issueKey, status)
      setTicket(res.data)
      toast.success(`Moved to ${status}`)
    } catch (err) {
      toast.error(err.response?.data?.error || 'Failed to update status')
    } finally {
      setSubmitting(false)
    }
  }

  const handleComment = async (e) => {
    e.preventDefault()
    if (!comment.trim()) return
    setSubmitting(true)
    try {
      const res = await jiraApi.addComment(issueKey, comment.trim())
      setTicket(res.data)
      setComment('')
      toast.success('Comment added')
    } catch (err) {
      toast.error(err.response?.data?.error || 'Failed to add comment')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="fx-jira-page flex items-center justify-center">
        <Loader2 className="animate-spin text-[#4C9AFF]" size={32} />
      </div>
    )
  }

  if (!ticket) {
    return (
      <div className="fx-jira-page flex flex-col items-center justify-center gap-4 px-4">
        <div className="fx-panel p-10 max-w-md text-center">
          <AlertCircle size={40} className="text-accent-red mx-auto mb-4" />
          <p className="text-lg font-medium text-white mb-2">Issue not found</p>
          <p className="text-sm text-surface-400 mb-6">
            Issue {issueKey} does not exist or you do not have permission to view it.
          </p>
          <Link to="/dashboard" className="btn-primary inline-flex items-center gap-2 px-5 py-2.5 text-sm">
            <ArrowLeft size={14} /> Return to FixitLab
          </Link>
        </div>
      </div>
    )
  }

  const projectKey = (ticket.issue_key || issueKey || 'KAN').split('-')[0]

  return (
    <div className="fx-jira-page font-sans antialiased">
      {/* Jira top navigation — authentic Jira chrome */}
      <header className="bg-[#0747A6] text-white h-12 flex items-center px-4 gap-4 shadow-sm">
        <div className="flex items-center gap-2 shrink-0">
          <div className="w-7 h-7 bg-white rounded flex items-center justify-center">
            <svg viewBox="0 0 24 24" className="w-5 h-5" fill="#0052CC">
              <path d="M11.571 11.513H0a5.218 5.218 0 0 0 5.232 5.215h2.13v2.057A5.215 5.215 0 0 0 12.575 24V12.518a1.005 1.005 0 0 0-1.005-1.005zm5.723-5.756H5.232a5.215 5.215 0 0 0-5.215 5.214h2.128v2.057a5.218 5.218 0 0 0 5.215 5.214h2.128V11.51a1.005 1.005 0 0 0-1.005-1.005h-.005a1.005 1.005 0 0 0-1.004 1.005v2.057a3.205 3.205 0 0 1-3.204-3.204V5.973a3.205 3.205 0 0 1 3.204-3.204h9.062a3.205 3.205 0 0 1 3.204 3.204v2.057a1.005 1.005 0 0 0 1.004 1.005 1.005 1.005 0 0 0 1.005-1.005V5.973a5.218 5.218 0 0 0-5.215-5.216z" />
            </svg>
          </div>
          <span className="font-semibold text-sm tracking-tight">Jira</span>
          <span className="hidden sm:inline text-[10px] uppercase tracking-wider text-[#DEEBFF]/70 ml-1">Lab Jira</span>
        </div>
        <div className="flex-1 max-w-xl">
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#8993A4]" />
            <input
              type="text"
              placeholder="Search"
              className="w-full pl-9 pr-3 py-1.5 rounded text-sm text-white bg-[#253858] border border-[#344563] placeholder:text-[#8993A4] focus:outline-none focus:ring-2 focus:ring-[#4C9AFF]"
              readOnly
            />
          </div>
        </div>
        <div className="flex items-center gap-3 text-[#DEEBFF]">
          <HelpCircle size={18} className="opacity-80 hidden sm:block" />
          <Bell size={18} className="opacity-80 hidden sm:block" />
          <FixitLogo to="/dashboard" size="sm" showText={false} className="opacity-90 hover:opacity-100" />
        </div>
      </header>

      {/* Project breadcrumb bar */}
      <div className="fx-jira-breadcrumb px-4 sm:px-6 py-2.5 flex items-center justify-between">
        <nav className="flex items-center gap-1 text-sm text-surface-500">
          <span className="font-medium fx-jira-link">{projectKey}</span>
          <ChevronRight size={14} />
          <span className="text-surface-200 font-medium font-mono">{ticket.issue_key}</span>
        </nav>
        <Link
          to="/dashboard"
          className="text-xs text-surface-500 hover:text-accent-cyan flex items-center gap-1 transition-colors"
        >
          <ArrowLeft size={12} /> Back to FixitLab
        </Link>
      </div>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 animate-fx-rise">
        <p className="fx-page-eyebrow mb-4">Incident ticket</p>

        <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-6">
          {/* Main content */}
          <main className="space-y-4">
            {/* Issue header */}
            <div className="fx-jira-card overflow-hidden">
              <div className="px-5 sm:px-6 pt-5 pb-4 border-b border-white/[0.06]">
                <div className="flex items-start gap-3">
                  <div className="mt-1 w-6 h-6 rounded bg-[#FF5630] flex items-center justify-center shrink-0">
                    <AlertCircle size={14} className="text-white" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs text-surface-500 mb-1">
                      Incident / <span className="font-mono text-surface-400">{ticket.issue_key}</span>
                    </p>
                    <h1 className="text-xl font-display font-bold text-white leading-snug">{ticket.summary}</h1>
                  </div>
                </div>

                {(ticket.allowed_transitions || []).length > 0 && (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {ticket.allowed_transitions.map((status) => (
                      <button
                        key={status}
                        type="button"
                        disabled={submitting}
                        onClick={() => handleTransition(status)}
                        className="px-3 py-1.5 text-sm font-medium rounded-lg border border-white/10 bg-white/[0.04] text-surface-300 hover:bg-white/[0.08] hover:border-white/15 transition-colors disabled:opacity-50"
                      >
                        {status === 'Done' || status === 'Closed' ? (
                          <CheckCircle2 size={14} className="inline mr-1 -mt-0.5 text-accent-green" />
                        ) : status === 'In Progress' ? (
                          <Circle size={14} className="inline mr-1 -mt-0.5 text-[#4C9AFF]" />
                        ) : null}
                        {status}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="px-5 sm:px-6 py-5">
                <h2 className="text-xs font-semibold text-surface-500 uppercase tracking-wider mb-3">Description</h2>
                <JiraRichText text={ticket.description || 'No description provided.'} variant="dark" className="text-surface-300" />
                {ticket.scenario && (
                  <div className="mt-4 p-3 rounded-lg bg-[#0052CC]/10 border border-[#4C9AFF]/25 text-xs text-[#79B8FF]">
                    <strong className="text-[#DEEBFF]">Linked lab scenario:</strong> {ticket.scenario.title}
                  </div>
                )}
              </div>
            </div>

            {/* Activity tabs */}
            <div className="fx-jira-card overflow-hidden">
              <div className="flex border-b border-white/[0.06] px-4">
                {[
                  { key: 'comments', label: 'Comments', icon: MessageSquare },
                  { key: 'history', label: 'History', icon: Clock },
                ].map(({ key, label, icon: Icon }) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setActiveTab(key)}
                    className={`flex items-center gap-1.5 px-4 py-3 text-sm font-medium border-b-2 -mb-px transition-colors ${
                      activeTab === key
                        ? 'fx-jira-tab-active'
                        : 'border-transparent text-surface-500 hover:text-surface-300'
                    }`}
                  >
                    <Icon size={14} /> {label}
                  </button>
                ))}
              </div>

              <div className="p-5">
                {activeTab === 'comments' && (
                  <>
                    <form onSubmit={handleComment} className="mb-6">
                      <textarea
                        value={comment}
                        onChange={(e) => setComment(e.target.value)}
                        placeholder="Add a comment… @backup team @database team…"
                        rows={3}
                        disabled={submitting}
                        className="input-field w-full resize-none text-sm"
                      />
                      <div className="mt-2 flex justify-end">
                        <button
                          type="submit"
                          disabled={submitting || !comment.trim()}
                          className="btn-primary px-4 py-1.5 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          Comment
                        </button>
                      </div>
                    </form>

                    <div className="space-y-5">
                      {(ticket.comments || []).map((c, i) => (
                        <div key={i} className="flex gap-3">
                          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-accent-purple to-accent-cyan flex items-center justify-center text-xs font-bold text-white shrink-0">
                            {(c.author || 'U').charAt(0).toUpperCase()}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-baseline gap-2 mb-1">
                              <span className="text-sm font-semibold text-white">{c.author || 'User'}</span>
                              <span className="text-xs text-surface-500">
                                {new Date(c.created_at).toLocaleString(undefined, {
                                  dateStyle: 'medium',
                                  timeStyle: 'short',
                                })}
                              </span>
                            </div>
                            <div className="text-sm text-surface-300 bg-surface-900/60 rounded-lg px-3 py-2 border border-white/[0.06]">
                              <JiraRichText text={c.text} variant="dark" className="text-inherit" />
                            </div>
                          </div>
                        </div>
                      ))}
                      {(!ticket.comments || ticket.comments.length === 0) && (
                        <p className="text-sm text-surface-500 text-center py-6">No comments yet. Be the first to add one.</p>
                      )}
                    </div>
                  </>
                )}

                {activeTab === 'history' && (
                  <ul className="space-y-3">
                    {(ticket.activity || []).map((a, i) => (
                      <li key={i}>
                        <ActivityItem
                          action={a.action}
                          jiraStatus={a.jira_status}
                          createdAt={a.created_at}
                        />
                      </li>
                    ))}
                    {(!ticket.activity || ticket.activity.length === 0) && (
                      <p className="text-sm text-surface-500 text-center py-6">No activity recorded yet.</p>
                    )}
                  </ul>
                )}
              </div>
            </div>
          </main>

          {/* Right sidebar — Details panel */}
          <aside>
            <div className="fx-jira-card sticky top-4">
              <div className="px-4 py-3 border-b border-white/[0.06] flex items-center justify-between">
                <h3 className="text-xs font-semibold text-surface-500 uppercase tracking-wider">Details</h3>
                <MoreHorizontal size={16} className="text-surface-500" />
              </div>
              <dl className="px-4 py-2">
                <FieldRow label="Status">
                  <StatusLozenge status={ticket.jira_status || 'To Do'} />
                </FieldRow>
                <FieldRow label="Priority">
                  <PriorityIcon priority={ticket.priority || 'Medium'} />
                </FieldRow>
                <FieldRow label="Assignee">
                  <span className="inline-flex items-center gap-2">
                    <span className="w-6 h-6 rounded-full bg-accent-green flex items-center justify-center text-[10px] font-bold text-white">Y</span>
                    You
                  </span>
                </FieldRow>
                <FieldRow label="Reporter">
                  <span className="inline-flex items-center gap-2">
                    <User size={14} className="text-surface-500" />
                    {ticket.owner?.username || ticket.owner?.email || 'FixitLab System'}
                  </span>
                </FieldRow>
                <FieldRow label="Labels">
                  <span className="inline-flex items-center gap-1 flex-wrap">
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-white/[0.06] text-surface-400 border border-white/[0.08]">
                      <Tag size={10} /> lab-incident
                    </span>
                    {ticket.scenario?.slug && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-[#0052CC]/15 text-[#79B8FF] border border-[#4C9AFF]/20">
                        {ticket.scenario.slug}
                      </span>
                    )}
                  </span>
                </FieldRow>
                <FieldRow label="Lab attempt">
                  #{ticket.run_count || 1}
                </FieldRow>
                <FieldRow label="Created">
                  {ticket.created_at
                    ? new Date(ticket.created_at).toLocaleDateString(undefined, { dateStyle: 'medium' })
                    : '—'}
                </FieldRow>
              </dl>
            </div>

            <p className="mt-3 text-[10px] text-surface-600 text-center px-2">
              FixitLab live incident environment — Jira Cloud for this lab. No external Atlassian account required.
            </p>
          </aside>
        </div>
      </div>
    </div>
  )
}
