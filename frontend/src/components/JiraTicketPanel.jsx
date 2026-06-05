import { Ticket, MessageSquare, ExternalLink } from 'lucide-react'

/**
 * In-app Jira incident panel with link to the Jira ticket.
 * Learners with Atlassian access can open the ticket; others see details here.
 */
export default function JiraTicketPanel({ ticket, comments = [], compact = false }) {
  if (!ticket?.issue_key) return null

  const ticketUrl = ticket.issue_url || null

  return (
    <div className={`border border-blue-500/20 bg-blue-500/5 rounded-lg ${compact ? 'p-3' : 'p-4 mb-6'}`}>
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex items-start gap-2">
          <Ticket size={compact ? 16 : 18} className="text-blue-400 mt-0.5 shrink-0" />
          <div>
            <p className={`font-medium text-blue-400 uppercase tracking-wide ${compact ? 'text-[10px]' : 'text-xs'}`}>
              Your incident ticket
            </p>
            {ticketUrl ? (
              <a
                href={ticketUrl}
                target="_blank"
                rel="noopener noreferrer"
                className={`inline-flex items-center gap-1.5 text-blue-400 hover:text-blue-300 hover:underline font-mono ${compact ? 'text-sm' : 'text-base'}`}
                title="Open ticket in Jira"
              >
                {ticket.issue_key}
                <ExternalLink size={compact ? 12 : 14} />
              </a>
            ) : (
              <p className={`text-surface-200 font-mono ${compact ? 'text-sm' : 'text-base'}`}>
                {ticket.issue_key}
              </p>
            )}
            <p className={`text-surface-400 ${compact ? 'text-[11px]' : 'text-sm'} mt-0.5`}>
              {ticket.jira_status ? `Status: ${ticket.jira_status}` : 'Open'}
              {ticket.run_count > 1 && ` · Attempt #${ticket.run_count}`}
            </p>
            {!compact && (
              <p className="text-xs text-surface-500 mt-2 max-w-md">
                Your personal ticket — other learners get separate tickets for this scenario.
              </p>
            )}
          </div>
        </div>
        {ticketUrl && (
          <a
            href={ticketUrl}
            target="_blank"
            rel="noopener noreferrer"
            className={`flex items-center gap-1.5 shrink-0 rounded-lg border border-blue-500/20 bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 transition-colors ${compact ? 'px-2 py-1 text-[10px]' : 'px-3 py-1.5 text-sm'}`}
            title="Open ticket in Jira"
          >
            <ExternalLink size={compact ? 12 : 14} />
            View in Jira
          </a>
        )}
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
