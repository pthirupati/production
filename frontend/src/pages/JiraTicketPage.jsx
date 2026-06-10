import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { jiraApi } from '../api/jira'
import { ArrowLeft, MessageSquare, Ticket, Loader2 } from 'lucide-react'
import toast from 'react-hot-toast'

const STATUS_COLORS = {
  'To Do': 'bg-surface-600 text-surface-100',
  'In Progress': 'bg-blue-500/20 text-blue-300 border border-blue-500/30',
  'On Hold': 'bg-amber-500/20 text-amber-300 border border-amber-500/30',
  'Done': 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30',
  'Closed': 'bg-surface-700 text-surface-400 border border-surface-600',
}

export default function JiraTicketPage() {
  const { issueKey } = useParams()
  const [ticket, setTicket] = useState(null)
  const [loading, setLoading] = useState(true)
  const [comment, setComment] = useState('')
  const [submitting, setSubmitting] = useState(false)

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
      toast.success(`Status updated to ${status}`)
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
      <div className="min-h-screen bg-[#0c1424] flex items-center justify-center">
        <Loader2 className="animate-spin text-blue-400" size={32} />
      </div>
    )
  }

  if (!ticket) {
    return (
      <div className="min-h-screen bg-[#0c1424] text-surface-200 flex flex-col items-center justify-center gap-4">
        <p>Ticket {issueKey} not found.</p>
        <Link to="/dashboard" className="text-blue-400 hover:underline">Back to dashboard</Link>
      </div>
    )
  }

  const statusClass = STATUS_COLORS[ticket.jira_status] || STATUS_COLORS['To Do']

  return (
    <div className="min-h-screen bg-[#0c1424] text-surface-100">
      <header className="border-b border-[#1e293b] bg-[#071018] px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Ticket className="text-blue-400" size={22} />
          <div>
            <p className="text-xs text-surface-500 uppercase tracking-wide">FixitLab Jira Simulation</p>
            <h1 className="font-mono text-lg font-semibold text-blue-300">{ticket.issue_key}</h1>
          </div>
        </div>
        <Link to="/dashboard" className="text-sm text-surface-400 hover:text-surface-200 flex items-center gap-1">
          <ArrowLeft size={14} /> FixitLab
        </Link>
      </header>

      <div className="max-w-5xl mx-auto px-6 py-8 grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-6">
          <div>
            <h2 className="text-2xl font-semibold text-white mb-2">{ticket.summary}</h2>
            {ticket.scenario && (
              <p className="text-sm text-surface-400">
                Scenario: {ticket.scenario.title}
              </p>
            )}
          </div>

          <section className="bg-[#111827] border border-[#1e293b] rounded-lg p-5">
            <h3 className="text-sm font-semibold text-surface-300 mb-3 uppercase tracking-wide">Description</h3>
            <pre className="text-sm text-surface-300 whitespace-pre-wrap font-sans leading-relaxed">
              {ticket.description || 'No description.'}
            </pre>
          </section>

          <section className="bg-[#111827] border border-[#1e293b] rounded-lg p-5">
            <h3 className="text-sm font-semibold text-surface-300 mb-4 flex items-center gap-2">
              <MessageSquare size={16} /> Comments
            </h3>
            <form onSubmit={handleComment} className="mb-4 flex gap-2">
              <input
                type="text"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="Add a comment..."
                className="input-field flex-1 text-sm"
                disabled={submitting}
              />
              <button type="submit" className="btn-primary text-sm px-4" disabled={submitting || !comment.trim()}>
                Add
              </button>
            </form>
            <div className="space-y-3">
              {(ticket.comments || []).map((c, i) => (
                <div key={i} className="border-l-2 border-blue-500/40 pl-3 py-1">
                  <p className="text-xs text-surface-500">
                    <span className="font-medium text-surface-300">{c.author}</span>
                    {' · '}
                    {new Date(c.created_at).toLocaleString()}
                  </p>
                  <p className="text-sm text-surface-200 mt-1 whitespace-pre-wrap">{c.text}</p>
                </div>
              ))}
              {(!ticket.comments || ticket.comments.length === 0) && (
                <p className="text-sm text-surface-500">No comments yet.</p>
              )}
            </div>
          </section>
        </div>

        <aside className="space-y-4">
          <div className="bg-[#111827] border border-[#1e293b] rounded-lg p-5 space-y-4">
            <div>
              <p className="text-xs text-surface-500 uppercase mb-1">Status</p>
              <span className={`inline-block px-3 py-1 rounded text-sm font-medium ${statusClass}`}>
                {ticket.jira_status}
              </span>
            </div>
            <div>
              <p className="text-xs text-surface-500 uppercase mb-1">Priority</p>
              <p className="text-sm">{ticket.priority || 'Medium'}</p>
            </div>
            <div>
              <p className="text-xs text-surface-500 uppercase mb-1">Attempts</p>
              <p className="text-sm">{ticket.run_count || 1}</p>
            </div>

            {(ticket.allowed_transitions || []).length > 0 && (
              <div>
                <p className="text-xs text-surface-500 uppercase mb-2">Update status</p>
                <div className="flex flex-col gap-2">
                  {ticket.allowed_transitions.map((status) => (
                    <button
                      key={status}
                      type="button"
                      disabled={submitting}
                      onClick={() => handleTransition(status)}
                      className="text-left text-sm px-3 py-2 rounded border border-[#334155] hover:border-blue-500/50 hover:bg-blue-500/10 transition-colors disabled:opacity-50"
                    >
                      → {status}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {(ticket.activity || []).length > 0 && (
            <div className="bg-[#111827] border border-[#1e293b] rounded-lg p-5">
              <p className="text-xs text-surface-500 uppercase mb-3">Activity</p>
              <ul className="space-y-2 text-xs text-surface-400">
                {ticket.activity.slice(0, 8).map((a, i) => (
                  <li key={i}>
                    {a.action} · {a.jira_status}
                    <span className="block text-surface-600">{new Date(a.created_at).toLocaleString()}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </aside>
      </div>
    </div>
  )
}
