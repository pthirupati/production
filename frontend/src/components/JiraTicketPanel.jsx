import { Link } from 'react-router-dom'
import { useState } from 'react'
import { Ticket, MessageSquare, ExternalLink, History, Send } from 'lucide-react'
import JiraTicketLink from './JiraTicketLink'
import { JiraRichText } from './JiraRichText'
import { StatusLozenge, PriorityIcon, ActivityItem } from './jira/JiraUi'

/**
 * In-app Jira incident panel — user's personal ticket for this scenario only.
 */
export default function JiraTicketPanel({
  ticket,
  comments = [],
  activity = [],
  compact = false,
  hideHistory = false,
  hideComments = false,
  hideStatus = false,
  labInfoMode = false,
  onTransition,
  onComment,
  transitioning = false,
  commenting = false,
}) {
  const [commentText, setCommentText] = useState('')

  if (!ticket?.issue_key) return null

  const issueUrl = ticket.issue_url || `/jira/${ticket.issue_key}`
  const infoMode = labInfoMode || compact

  const handleSubmitComment = async (e) => {
    e.preventDefault()
    if (!commentText.trim() || !onComment) return
    await onComment(commentText.trim())
    setCommentText('')
  }

  return (
    <div
      id="jira-ticket-panel"
      className={`border border-blue-500/25 bg-gradient-to-br from-blue-500/10 to-indigo-500/5 rounded-lg scroll-mt-4 ${compact ? 'p-3' : 'p-4 mb-6'}`}
    >
      <div className="flex items-start gap-2">
        <Ticket size={compact ? 16 : 18} className="text-blue-400 mt-0.5 shrink-0" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className={`font-medium text-blue-400 uppercase tracking-wide ${compact ? 'text-[10px]' : 'text-xs'}`}>
              Incident ticket
            </p>
            {ticket.simulated && !infoMode && (
              <span className="text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-300 font-semibold">
                Simulation
              </span>
            )}
            {ticket.run_count > 1 && !infoMode && (
              <span className="text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-400 font-semibold">
                Attempt #{ticket.run_count}
              </span>
            )}
          </div>
          <div className={`mt-0.5 ${compact ? 'text-sm' : 'text-base'}`}>
            <JiraTicketLink
              issueKey={ticket.issue_key}
              issueUrl={issueUrl}
              showIcon={!compact}
              openInNewTab
            />
          </div>
          {ticket.summary && (
            <p className={`text-surface-200 font-medium mt-1 ${compact ? 'text-xs' : 'text-sm'}`}>
              {ticket.summary}
            </p>
          )}
          {!hideStatus && !infoMode && (
            <div className={`flex flex-wrap items-center gap-2 mt-2 ${compact ? 'text-[11px]' : 'text-sm'}`}>
              {ticket.jira_status && <StatusLozenge status={ticket.jira_status} className="!text-[10px]" />}
              {ticket.priority && <PriorityIcon priority={ticket.priority} className="!text-xs" />}
            </div>
          )}
          {ticket.description && (
            <div className={`mt-3 text-xs font-mono whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto rounded p-3 border ${
              infoMode
                ? 'text-surface-400 bg-surface-950 border-surface-800'
                : 'text-surface-300 bg-surface-900/60 border-surface-800/80'
            }`}>
              <JiraRichText text={ticket.description} variant="dark" className="text-inherit" />
            </div>
          )}
          {!compact && !infoMode && ticket.allowed_transitions?.length > 0 && onTransition && (
            <div className="mt-3 flex flex-wrap gap-2">
              {ticket.allowed_transitions.map((status) => (
                <button
                  key={status}
                  type="button"
                  disabled={transitioning}
                  onClick={() => onTransition(status)}
                  className="px-2.5 py-1 text-xs rounded border border-blue-500/30 bg-blue-500/10 text-blue-300 hover:bg-blue-500/20 disabled:opacity-50"
                >
                  → {status}
                </button>
              ))}
            </div>
          )}
          {!infoMode && (
            <Link
              to={issueUrl.startsWith('/') ? issueUrl : `/jira/${ticket.issue_key}`}
              className="inline-flex items-center gap-1 text-xs text-blue-300 hover:underline mt-2"
            >
              Open full Jira view <ExternalLink size={12} />
            </Link>
          )}
        </div>
      </div>

      {!infoMode && onComment && (
        <form onSubmit={handleSubmitComment} className="mt-3 flex gap-2">
          <input
            type="text"
            value={commentText}
            onChange={(e) => setCommentText(e.target.value)}
            placeholder="Comment on Jira — @backup team @database team @application team @storage team @network team…"
            className="input-field flex-1 text-xs py-1.5"
            disabled={commenting}
          />
          <button type="submit" disabled={commenting || !commentText.trim()} className="btn-secondary px-2 py-1.5 disabled:opacity-50">
            <Send size={14} />
          </button>
        </form>
      )}

      {((!hideComments && comments.length > 0) || (!hideHistory && activity.length > 0)) && !infoMode && (
        <div className={`mt-3 pt-3 border-t border-blue-500/15 ${compact ? 'space-y-2' : 'space-y-3'}`}>
          {!hideHistory && activity.length > 0 && (
            <div className="space-y-2">
              <p className="text-[10px] uppercase tracking-wide text-surface-500 flex items-center gap-1">
                <History size={12} /> Lab history
              </p>
              {activity.slice(0, compact ? 2 : 4).map((a, i) => (
                <ActivityItem
                  key={`act-${i}`}
                  action={a.action}
                  jiraStatus={a.jira_status}
                  createdAt={a.created_at}
                  compact={compact}
                />
              ))}
            </div>
          )}
          {!hideComments && comments.length > 0 && (
            <div className="space-y-2">
              <p className="text-[10px] uppercase tracking-wide text-surface-500 flex items-center gap-1">
                <MessageSquare size={12} /> Comments
              </p>
              {comments.slice(0, compact ? 3 : 8).map((c, i) => (
                <div key={i} className="text-xs bg-surface-900/50 rounded p-2 border border-surface-800/50">
                  <span className="text-surface-300 font-medium">{c.author}</span>
                  <span className="text-surface-600 mx-1">·</span>
                  <span className="text-surface-500">{new Date(c.created_at).toLocaleString()}</span>
                  <div className="text-surface-400 mt-1 font-mono text-[11px] leading-relaxed">
                    <JiraRichText text={c.text} variant="dark" className="text-inherit" />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
