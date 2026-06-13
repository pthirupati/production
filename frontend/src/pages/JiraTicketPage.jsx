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

function FieldRow({ label, children }) {
  return (
    <div className="py-2 border-b border-[#DFE1E6] last:border-0">
      <dt className="text-xs text-[#6B778C] font-medium mb-1">{label}</dt>
      <dd className="text-sm text-[#172B4D]">{children}</dd>
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
      <div className="min-h-screen bg-[#F4F5F7] flex items-center justify-center">
        <Loader2 className="animate-spin text-[#0052CC]" size={32} />
      </div>
    )
  }

  if (!ticket) {
    return (
      <div className="min-h-screen bg-[#F4F5F7] text-[#172B4D] flex flex-col items-center justify-center gap-4">
        <AlertCircle size={40} className="text-[#DE350B]" />
        <p className="text-lg font-medium">Issue {issueKey} does not exist or you do not have permission to view it.</p>
        <Link to="/dashboard" className="text-[#0052CC] hover:underline text-sm">Return to FixitLab</Link>
      </div>
    )
  }

  const projectKey = (ticket.issue_key || issueKey || 'KAN').split('-')[0]

  return (
    <div className="min-h-screen bg-[#F4F5F7] text-[#172B4D] font-sans antialiased">
      {/* Jira top navigation */}
      <header className="bg-[#0747A6] text-white h-12 flex items-center px-4 gap-4 shadow-sm">
        <div className="flex items-center gap-2 shrink-0">
          <div className="w-7 h-7 bg-white rounded flex items-center justify-center">
            <svg viewBox="0 0 24 24" className="w-5 h-5" fill="#0052CC">
              <path d="M11.571 11.513H0a5.218 5.218 0 0 0 5.232 5.215h2.13v2.057A5.215 5.215 0 0 0 12.575 24V12.518a1.005 1.005 0 0 0-1.005-1.005zm5.723-5.756H5.232a5.215 5.215 0 0 0-5.215 5.214h2.128v2.057a5.218 5.218 0 0 0 5.215 5.214h2.128V11.51a1.005 1.005 0 0 0-1.005-1.005h-.005a1.005 1.005 0 0 0-1.004 1.005v2.057a3.205 3.205 0 0 1-3.204-3.204V5.973a3.205 3.205 0 0 1 3.204-3.204h9.062a3.205 3.205 0 0 1 3.204 3.204v2.057a1.005 1.005 0 0 0 1.004 1.005 1.005 1.005 0 0 0 1.005-1.005V5.973a5.218 5.218 0 0 0-5.215-5.216z" />
            </svg>
          </div>
          <span className="font-semibold text-sm tracking-tight">Jira</span>
        </div>
        <div className="flex-1 max-w-xl">
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#6B778C]" />
            <input
              type="text"
              placeholder="Search"
              className="w-full pl-9 pr-3 py-1.5 rounded text-sm text-[#172B4D] bg-[#253858] border border-[#344563] placeholder:text-[#8993A4] focus:outline-none focus:ring-2 focus:ring-[#4C9AFF]"
              readOnly
            />
          </div>
        </div>
        <div className="flex items-center gap-3 text-[#DEEBFF]">
          <HelpCircle size={18} className="opacity-80" />
          <Bell size={18} className="opacity-80" />
          <div className="w-7 h-7 rounded-full bg-[#6554C0] flex items-center justify-center text-xs font-bold text-white">
            FL
          </div>
        </div>
      </header>

      {/* Project breadcrumb bar */}
      <div className="bg-white border-b border-[#DFE1E6] px-6 py-2 flex items-center justify-between">
        <nav className="flex items-center gap-1 text-sm text-[#6B778C]">
          <span className="font-medium text-[#0052CC]">{projectKey}</span>
          <ChevronRight size={14} />
          <span className="text-[#172B4D] font-medium">{ticket.issue_key}</span>
        </nav>
        <Link
          to="/dashboard"
          className="text-xs text-[#6B778C] hover:text-[#0052CC] flex items-center gap-1"
        >
          <ArrowLeft size={12} /> Back to FixitLab
        </Link>
      </div>

      <div className="max-w-6xl mx-auto px-6 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-6">
          {/* Main content */}
          <main className="space-y-4">
            {/* Issue header */}
            <div className="bg-white rounded border border-[#DFE1E6] shadow-sm">
              <div className="px-6 pt-5 pb-4 border-b border-[#DFE1E6]">
                <div className="flex items-start gap-3">
                  <div className="mt-1 w-6 h-6 rounded bg-[#FF5630] flex items-center justify-center shrink-0">
                    <AlertCircle size={14} className="text-white" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs text-[#6B778C] mb-1">
                      Incident / <span className="font-mono">{ticket.issue_key}</span>
                    </p>
                    <h1 className="text-xl font-normal text-[#172B4D] leading-snug">{ticket.summary}</h1>
                  </div>
                </div>

                {/* Workflow transition buttons */}
                {(ticket.allowed_transitions || []).length > 0 && (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {ticket.allowed_transitions.map((status) => (
                      <button
                        key={status}
                        type="button"
                        disabled={submitting}
                        onClick={() => handleTransition(status)}
                        className="px-3 py-1.5 text-sm font-medium rounded border border-[#DFE1E6] bg-[#FAFBFC] text-[#42526E] hover:bg-[#EBECF0] hover:border-[#C1C7D0] transition-colors disabled:opacity-50"
                      >
                        {status === 'Done' || status === 'Closed' ? (
                          <CheckCircle2 size={14} className="inline mr-1 -mt-0.5" />
                        ) : status === 'In Progress' ? (
                          <Circle size={14} className="inline mr-1 -mt-0.5 text-[#0052CC]" />
                        ) : null}
                        {status}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Description */}
              <div className="px-6 py-5">
                <h2 className="text-xs font-semibold text-[#6B778C] uppercase tracking-wider mb-3">Description</h2>
                <JiraRichText text={ticket.description || 'No description provided.'} />
                {ticket.scenario && (
                  <div className="mt-4 p-3 bg-[#DEEBFF]/40 border border-[#B3D4FF] rounded text-xs text-[#0747A6]">
                    <strong>Linked lab scenario:</strong> {ticket.scenario.title}
                  </div>
                )}
              </div>
            </div>

            {/* Activity tabs */}
            <div className="bg-white rounded border border-[#DFE1E6] shadow-sm">
              <div className="flex border-b border-[#DFE1E6] px-4">
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
                        ? 'border-[#0052CC] text-[#0052CC]'
                        : 'border-transparent text-[#6B778C] hover:text-[#172B4D]'
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
                        placeholder="Add a comment..."
                        rows={3}
                        disabled={submitting}
                        className="w-full px-3 py-2 text-sm border border-[#DFE1E6] rounded focus:outline-none focus:ring-2 focus:ring-[#4C9AFF] focus:border-[#0052CC] resize-none bg-white text-[#172B4D]"
                      />
                      <div className="mt-2 flex justify-end">
                        <button
                          type="submit"
                          disabled={submitting || !comment.trim()}
                          className="px-4 py-1.5 text-sm font-medium rounded bg-[#0052CC] text-white hover:bg-[#0065FF] disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          Comment
                        </button>
                      </div>
                    </form>

                    <div className="space-y-5">
                      {(ticket.comments || []).map((c, i) => (
                        <div key={i} className="flex gap-3">
                          <div className="w-8 h-8 rounded-full bg-[#6554C0] flex items-center justify-center text-xs font-bold text-white shrink-0">
                            {(c.author || 'U').charAt(0).toUpperCase()}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-baseline gap-2 mb-1">
                              <span className="text-sm font-semibold text-[#172B4D]">{c.author || 'User'}</span>
                              <span className="text-xs text-[#6B778C]">
                                {new Date(c.created_at).toLocaleString(undefined, {
                                  dateStyle: 'medium',
                                  timeStyle: 'short',
                                })}
                              </span>
                            </div>
                            <div className="text-sm text-[#172B4D] bg-[#F4F5F7] rounded px-3 py-2 border border-[#EBECF0]">
                              <JiraRichText text={c.text} />
                            </div>
                          </div>
                        </div>
                      ))}
                      {(!ticket.comments || ticket.comments.length === 0) && (
                        <p className="text-sm text-[#6B778C] text-center py-6">No comments yet. Be the first to add one.</p>
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
                          light
                        />
                      </li>
                    ))}
                    {(!ticket.activity || ticket.activity.length === 0) && (
                      <p className="text-sm text-[#6B778C] text-center py-6">No activity recorded yet.</p>
                    )}
                  </ul>
                )}
              </div>
            </div>
          </main>

          {/* Right sidebar — Details panel */}
          <aside>
            <div className="bg-white rounded border border-[#DFE1E6] shadow-sm sticky top-4">
              <div className="px-4 py-3 border-b border-[#DFE1E6] flex items-center justify-between">
                <h3 className="text-xs font-semibold text-[#6B778C] uppercase tracking-wider">Details</h3>
                <MoreHorizontal size={16} className="text-[#6B778C]" />
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
                    <span className="w-6 h-6 rounded-full bg-[#36B37E] flex items-center justify-center text-[10px] font-bold text-white">Y</span>
                    You
                  </span>
                </FieldRow>
                <FieldRow label="Reporter">
                  <span className="inline-flex items-center gap-2">
                    <User size={14} className="text-[#6B778C]" />
                    FixitLab System
                  </span>
                </FieldRow>
                <FieldRow label="Labels">
                  <span className="inline-flex items-center gap-1 flex-wrap">
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-[#DFE1E6] text-[#42526E]">
                      <Tag size={10} /> lab-incident
                    </span>
                    {ticket.scenario?.slug && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-[#DEEBFF] text-[#0052CC]">
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

            <p className="mt-3 text-[10px] text-[#8993A4] text-center px-2">
              FixitLab incident simulation — styled like Jira Cloud. No external Atlassian account required.
            </p>
          </aside>
        </div>
      </div>
    </div>
  )
}
