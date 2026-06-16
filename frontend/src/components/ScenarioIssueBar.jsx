import { Link } from 'react-router-dom'
import { Ticket, Bot, Lock, ExternalLink, MessageSquare } from 'lucide-react'
import JiraTicketLink from './JiraTicketLink'
import { StatusLozenge } from './jira/JiraUi'

/**
 * Top-of-page incident bar — Jira link for subscribers; upgrade teaser otherwise.
 */
export default function ScenarioIssueBar({
  scenario,
  jiraTicket,
  jiraComments = [],
  isAuthenticated,
  onOpenJira,
}) {
  const canOpenJira = scenario?.is_accessible !== false

  if (!isAuthenticated) {
    return (
      <div className="glass-card p-4 border border-surface-700/80">
        <div className="flex items-start gap-3">
          <Ticket size={18} className="text-surface-500 mt-0.5 shrink-0" />
          <div>
            <p className="text-sm font-medium text-surface-300">Incident ticket</p>
            <p className="text-xs text-surface-500 mt-1">
              Sign in and subscribe to open the incident in Jira, read full customer notes, and ask the Jira bot for help.
            </p>
          </div>
        </div>
      </div>
    )
  }

  if (!canOpenJira) {
    return (
      <div className="glass-card p-4 border border-accent-purple/20 bg-accent-purple/5">
        <div className="flex items-start gap-3">
          <Lock size={18} className="text-accent-purple mt-0.5 shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-white">Incident details in Jira</p>
            <p className="text-xs text-surface-400 mt-1 leading-relaxed">
              Subscribe to <span className="text-white">{scenario.technology?.name}</span> to open the incident ticket,
              see customer impact, timeline, and chat with the Jira bot for guided troubleshooting.
            </p>
            <Link to="/pricing" className="inline-flex items-center gap-1 text-xs text-accent-purple hover:underline mt-2">
              View subscription plans
            </Link>
          </div>
        </div>
      </div>
    )
  }

  if (!jiraTicket?.issue_key) {
    return (
      <div className="glass-card p-4 border border-blue-500/20 bg-blue-500/5">
        <div className="flex items-start gap-3">
          <Ticket size={18} className="text-blue-400 mt-0.5 shrink-0" />
          <div>
            <p className="text-sm font-medium text-blue-300">Incident ticket</p>
            <p className="text-xs text-surface-400 mt-1">
              Loading incident details… Start the lab to sync ticket status to In Progress.
            </p>
          </div>
        </div>
      </div>
    )
  }

  const issueUrl = jiraTicket.issue_url || `/jira/${jiraTicket.issue_key}`

  return (
    <div className="glass-card p-4 border border-blue-500/25 bg-gradient-to-r from-blue-500/10 to-indigo-500/5">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          <Ticket size={18} className="text-blue-400 mt-0.5 shrink-0" />
          <div className="min-w-0">
            <p className="text-[10px] uppercase tracking-wider text-blue-400/80 font-semibold mb-0.5">
              Issue
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <JiraTicketLink
                issueKey={jiraTicket.issue_key}
                issueUrl={issueUrl}
                showIcon
                openInNewTab
              />
              {jiraTicket.jira_status && (
                <StatusLozenge status={jiraTicket.jira_status} className="!text-[10px]" />
              )}
              {jiraTicket.run_count > 1 && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-400">
                  Attempt #{jiraTicket.run_count}
                </span>
              )}
            </div>
            {jiraTicket.summary && (
              <p className="text-sm text-surface-200 mt-1 truncate">{jiraTicket.summary}</p>
            )}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 shrink-0">
          <Link
            to={issueUrl.startsWith('/') ? issueUrl : `/jira/${jiraTicket.issue_key}`}
            onClick={onOpenJira}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-blue-500/30 bg-blue-500/10 text-blue-300 hover:bg-blue-500/20 transition-colors"
          >
            Open Jira <ExternalLink size={12} />
          </Link>
        </div>
      </div>
      <div className="mt-3 pt-3 border-t border-blue-500/15 flex items-start gap-2">
        <Bot size={14} className="text-indigo-400 mt-0.5 shrink-0" />
        <p className="text-xs text-surface-400 leading-relaxed">
          Open Jira for full customer notes, attachments, and lab history. Use the in-app Jira bot to ask follow-up
          questions about impact, error messages, or recent changes — it responds with scenario-aware guidance.
        </p>
      </div>
      {jiraComments.length > 0 && (
        <div className="mt-3 space-y-2">
          <p className="text-[10px] uppercase tracking-wide text-surface-500 flex items-center gap-1">
            <MessageSquare size={11} /> Recent updates
          </p>
          {jiraComments.slice(0, 2).map((c, i) => (
            <div key={i} className="text-xs bg-surface-900/50 rounded p-2 border border-surface-800/50">
              <span className="text-surface-400 font-medium">{c.author}</span>
              <span className="text-surface-600 mx-1">·</span>
              <span className="text-surface-500">{new Date(c.created_at).toLocaleString()}</span>
              <p className="text-surface-400 mt-1 line-clamp-2">{c.text}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
