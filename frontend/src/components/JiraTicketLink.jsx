import { ExternalLink } from 'lucide-react'

/**
 * Jira issue key — opens in-app Jira in a new tab.
 */
export default function JiraTicketLink({
  issueKey,
  issueUrl,
  className = '',
  showIcon = true,
  allowExternalLink = false,
  onNavigate,
  openInNewTab = true,
}) {
  if (!issueKey) return null

  const inAppHref = `/jira/${issueKey}`
  const useExternal =
    allowExternalLink &&
    issueUrl &&
    issueUrl.startsWith('http') &&
    !issueUrl.includes('/jira/')
  const href = useExternal ? issueUrl : inAppHref
  const baseClass = `font-mono font-semibold text-blue-400 underline decoration-blue-400/40 underline-offset-2 hover:text-blue-300 hover:decoration-blue-300 cursor-pointer transition-colors ${className}`

  const scrollToPanel = (e) => {
    if (onNavigate) {
      e.preventDefault()
      onNavigate()
      return
    }
    if (openInNewTab) {
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

  if (useExternal) {
    return (
      <a
        href={href}
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
      href={href}
      target={openInNewTab ? '_blank' : undefined}
      rel={openInNewTab ? 'noopener noreferrer' : undefined}
      onClick={scrollToPanel}
      className={`inline-flex items-center gap-1 ${baseClass}`}
      title="Open incident ticket (Jira)"
    >
      {issueKey}
      {showIcon && openInNewTab && <ExternalLink size={12} className="opacity-70" />}
    </a>
  )
}
