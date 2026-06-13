import { Link } from 'react-router-dom'
import { Ticket, MessageSquare, ExternalLink, History } from 'lucide-react'
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
  onTransition,
  transitioning = false,
}) {
  if (!ticket?.issue_key) return null

  const issueUrl = ticket.issue_url || `/jira/${ticket.issue_key}`

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
            {ticket.simulated && (
              <span className="text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-[#DEEBFF] text-[#0052CC] font-semibold">
                Simulation
              </span>
            )}
            {ticket.run_count > 1 && (
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
          <div className={`flex flex-wrap items-center gap-2 mt-2 ${compact ? 'text-[11px]' : 'text-sm'}`}>
            {ticket.jira_status && <StatusLozenge status={ticket.jira_status} className="!text-[10px]" />}
            {ticket.priority && <PriorityIcon priority={ticket.priority} className="!text-xs" />}
          </div>
          {ticket.description && !compact && (
            <div className="mt-3 text-sm text-[#B6C2CF] bg-[#1D2125] rounded-md p-3 border border-[#A6C5E229] max-h-48 overflow-y-auto leading-relaxed">
              <JiraRichText text={ticket.description} />
            </div>
          )}
          {!compact && ticket.allowed_transitions?.length > 0 && onTransition && (
            <div className="mt-3 flex flex-wrap gap-2">
              {ticket.allowed_transitions.map((status) => (
                <button
                  key={status}
                  type="button"
                  disabled={transitioning}
                  onClick={() => onTransition(status)}
                  className="px-2.5 py-1 text-xs rounded border border-[#0052CC]/30 bg-[#DEEBFF]/10 text-[#4C9AFF] hover:bg-[#DEEBFF]/20 disabled:opacity-50"
                >
                  → {status}
                </button>
              ))}
            </div>
          )}
          {!compact && (
            <Link
              to={issueUrl.startsWith('/') ? issueUrl : `/jira/${ticket.issue_key}`}
              className="inline-flex items-center gap-1 text-xs text-[#4C9AFF] hover:underline mt-2"
            >
              Open full Jira view <ExternalLink size={12} />
            </Link>
          )}
        </div>
      </div>

      {((!hideComments && comments.length > 0) || (!hideHistory && activity.length > 0)) && (
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
              {comments.slice(0, compact ? 3 : 5).map((c, i) => (
                <div key={i} className="text-xs bg-surface-900/50 rounded p-2 border border-surface-800/50">
                  <span className="text-surface-400 font-medium">{c.author}</span>
                  <span className="text-surface-600 mx-1">·</span>
                  <span className="text-surface-500">{new Date(c.created_at).toLocaleString()}</span>
                  <div className="text-surface-300 mt-1">
                    <JiraRichText text={c.text} />
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
