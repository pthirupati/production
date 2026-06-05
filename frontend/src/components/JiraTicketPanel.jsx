import { Ticket, MessageSquare } from 'lucide-react'
import { useAuthStore } from '../store/authStore'

/**
 * In-app Jira incident panel — users never need Atlassian login.
 * External Jira link is staff-only (managers use JIRA_EMAIL bot account).
 */
export default function JiraTicketPanel({ ticket, comments = [], compact = false }) {
  const { user } = useAuthStore()
  const isStaff = user?.is_staff

  if (!ticket?.issue_key) return null

  return (
    <div className={`border border-blue-500/20 bg-blue-500/5 rounded-lg ${compact ? 'p-3' : 'p-4 mb-6'}`}>
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex items-start gap-2">
          <Ticket size={compact ? 16 : 18} className="text-blue-400 mt-0.5 shrink-0" />
          <div>
            <p className={`font-medium text-blue-400 uppercase tracking-wide ${compact ? 'text-[10px]' : 'text-xs'}`}>
              Your incident ticket
            </p>
            <p className={`text-surface-200 font-mono ${compact ? 'text-sm' : 'text-base'}`}>
              {ticket.issue_key}
            </p>
            <p className={`text-surface-400 ${compact ? 'text-[11px]' : 'text-sm'} mt-0.5`}>
              {ticket.jira_status ? `Status: ${ticket.jira_status}` : 'Open'}
              {ticket.run_count > 1 && ` · Attempt #${ticket.run_count}`}
            </p>
            {!compact && (
              <p className="text-xs text-surface-500 mt-2 max-w-md">
                This ticket is yours only — other learners get separate tickets for the same scenario.
                Updates appear here; you do not need a Jira login.
              </p>
            )}
          </div>
        </div>
        {isStaff && ticket.issue_url && (
          <a
            href={ticket.issue_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-blue-400 hover:underline shrink-0"
            title="Staff only — opens Atlassian Jira"
          >
            Open in Jira ↗
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
