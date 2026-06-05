import { ExternalLink } from 'lucide-react'

/**
 * Clickable Jira issue key — opens Atlassian in a new tab when issue_url is set.
 */
export default function JiraTicketLink({ issueKey, issueUrl, className = '', showIcon = true }) {
  if (!issueKey) return null

  const baseClass = `font-mono font-semibold text-blue-400 hover:text-blue-300 transition-colors ${className}`

  if (issueUrl) {
    return (
      <a
        href={issueUrl}
        target="_blank"
        rel="noopener noreferrer"
        className={`inline-flex items-center gap-1 ${baseClass}`}
        title="Open in Jira (new tab)"
      >
        {issueKey}
        {showIcon && <ExternalLink size={12} className="opacity-70" />}
      </a>
    )
  }

  return <span className={baseClass}>{issueKey}</span>
}
