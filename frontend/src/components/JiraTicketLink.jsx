import { ExternalLink } from 'lucide-react'

/**
 * Jira issue key display. External Atlassian links are staff-only — learners
 * use the in-app JiraTicketPanel (server-side API) and do not have Jira logins.
 */
export default function JiraTicketLink({
  issueKey,
  issueUrl,
  className = '',
  showIcon = true,
  allowExternalLink = false,
}) {
  if (!issueKey) return null

  const baseClass = `font-mono font-semibold text-blue-400 ${allowExternalLink ? 'hover:text-blue-300 transition-colors' : ''} ${className}`

  if (allowExternalLink && issueUrl) {
    return (
      <a
        href={issueUrl}
        target="_blank"
        rel="noopener noreferrer"
        className={`inline-flex items-center gap-1 ${baseClass}`}
        title="Open in Jira (staff)"
      >
        {issueKey}
        {showIcon && <ExternalLink size={12} className="opacity-70" />}
      </a>
    )
  }

  return (
    <span className={baseClass} title="View details in the incident panel">
      {issueKey}
    </span>
  )
}
