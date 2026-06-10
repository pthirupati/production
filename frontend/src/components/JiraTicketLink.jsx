import { ExternalLink } from 'lucide-react'

/**
 * Jira issue key — clickable in-app link to the incident panel.
 * Staff may also open the external Atlassian URL when allowExternalLink is set.
 */
export default function JiraTicketLink({
  issueKey,
  issueUrl,
  className = '',
  showIcon = true,
  allowExternalLink = false,
  onNavigate,
}) {
  if (!issueKey) return null

  const baseClass = `font-mono font-semibold text-blue-400 underline decoration-blue-400/40 underline-offset-2 hover:text-blue-300 hover:decoration-blue-300 cursor-pointer transition-colors ${className}`

  const scrollToPanel = (e) => {
    if (onNavigate) {
      e.preventDefault()
      onNavigate()
      return
    }
    e.preventDefault()
    const panel = document.getElementById('jira-ticket-panel')
    if (panel) {
      panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
      panel.classList.add('ring-2', 'ring-blue-400/50')
      setTimeout(() => panel.classList.remove('ring-2', 'ring-blue-400/50'), 2000)
    }
  }

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
    <a
      href="#jira-ticket-panel"
      onClick={scrollToPanel}
      className={`inline-flex items-center gap-1 ${baseClass}`}
      title="View incident ticket details"
    >
      {issueKey}
    </a>
  )
}
