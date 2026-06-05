import { Ticket, MessageSquare } from 'lucide-react'
import JiraTicketLink from './JiraTicketLink'

/**
 * In-app Jira incident panel — user's personal ticket for this scenario only.
 */
export default function JiraTicketPanel({ ticket, comments = [], compact = false }) {
  if (!ticket?.issue_key) return null

  return (
    <div className={`border border-blue-500/20 bg-blue-500/5 rounded-lg ${compact ? 'p-3' : 'p-4 mb-6'}`}>
      <div className="flex items-start gap-2">
        <Ticket size={compact ? 16 : 18} className="text-blue-400 mt-0.5 shrink-0" />
        <div className="min-w-0 flex-1">
          <p className={`font-medium text-blue-400 uppercase tracking-wide ${compact ? 'text-[10px]' : 'text-xs'}`}>
            Your incident ticket
          </p>
          <div className={`mt-0.5 ${compact ? 'text-sm' : 'text-base'}`}>
            <JiraTicketLink
              issueKey={ticket.issue_key}
              issueUrl={ticket.issue_url}
              showIcon={!compact}
            />
          </div>
          {ticket.summary && (
            <p className={`text-surface-200 font-medium mt-1 ${compact ? 'text-xs' : 'text-sm'}`}>
              {ticket.summary}
            </p>
          )}
          <p className={`text-surface-400 ${compact ? 'text-[11px]' : 'text-sm'} mt-0.5`}>
            {ticket.jira_status ? `Status: ${ticket.jira_status}` : 'Open'}
            {ticket.run_count > 1 && ` · Attempt #${ticket.run_count}`}
          </p>
          {ticket.description && !compact && (
            <pre className="mt-3 text-xs text-surface-400 whitespace-pre-wrap font-sans max-h-48 overflow-y-auto bg-surface-900/40 rounded p-3 border border-surface-700/50">
              {ticket.description}
            </pre>
          )}
          {!compact && (
            <p className="text-xs text-surface-500 mt-2">
              Personal ticket — only you see this. Other learners get their own ticket for this scenario.
            </p>
          )}
        </div>
      </div>

      {comments.length > 0 && (
        <div className={`mt-3 pt-3 border-t border-blue-500/10 ${compact ? 'space-y-2' : 'space-y-3'}`}>
          <p className="text-[10px] uppercase tracking-wide text-surface-500 flex items-center gap-1">
            <MessageSquare size={12} /> Activity
          </p>
          {comments.slice(0, compact ? 3 : 5).map((c, i) => (
            <div key={i} className="text-xs bg-surface-900/50 rounded p-2">
              <span className="text-surface-400 font-medium">{c.author}</span>
              <span className="text-surface-600 mx-1">·</span>
              <span className="text-surface-500">{new Date(c.created_at).toLocaleString()}</span>
              <p className="text-surface-300 mt-1 whitespace-pre-wrap">{c.text}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
