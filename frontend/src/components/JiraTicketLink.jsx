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
  // Lab session this ticket was opened from, when there is one. Opt-in on
  // purpose: Dashboard / AdminUsers / AdminJira list tickets with no lab in
  // play, and they must keep linking to the plain /jira/:key page. Passing it
  // is what lets JiraTicketPage offer "Back to lab" instead of dumping the
  // learner on /dashboard (audit L479).
  sessionId = null,
}) {
  if (!issueKey) return null

  // Keep the base path as one unconditional template literal and append the
  // query separately. A ternary over two `/jira/...` literals also works at
  // runtime, but routeReachability.test.js's link extractor reads a template
  // literal only up to its first `${` and would stop seeing this — the sole
  // inbound link to the /jira/:issueKey route — making the route look orphaned.
  const inAppHref = `/jira/${issueKey}`
    + (sessionId ? `?session=${encodeURIComponent(sessionId)}` : '')
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
