// @vitest-environment jsdom
//
// Audit L479. A ticket opened from inside a lab carried no session id, so the
// ticket page's only exit was a hardcoded /dashboard — the learner could not get
// back to the lab they were working in. The link now threads an opt-in
// sessionId; these tests pin that it is genuinely opt-in, because Dashboard,
// AdminUsers and AdminJira list tickets with no lab in play and must keep
// producing a plain /jira/:key href.
import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import JiraTicketLink from './JiraTicketLink'

afterEach(cleanup)

const hrefFor = (key) => screen.getByRole('link', { name: new RegExp(key) }).getAttribute('href')

describe('JiraTicketLink session round-trip', () => {
  it('carries the lab session when opened from a lab', () => {
    render(<JiraTicketLink issueKey="KAN-12" sessionId="sess-abc" />)
    expect(hrefFor('KAN-12')).toBe('/jira/KAN-12?session=sess-abc')
  })

  it('stays a bare ticket link with no session (Dashboard / admin lists)', () => {
    render(<JiraTicketLink issueKey="KAN-13" />)
    expect(hrefFor('KAN-13')).toBe('/jira/KAN-13')
  })

  it('url-encodes the session id rather than splicing it in raw', () => {
    render(<JiraTicketLink issueKey="KAN-14" sessionId="a b&c=d" />)
    expect(hrefFor('KAN-14')).toBe('/jira/KAN-14?session=a%20b%26c%3Dd')
  })

  it('leaves a staff external Jira URL untouched', () => {
    // allowExternalLink wins over the in-app href; appending our session param
    // to a real Atlassian URL would be meaningless (and would leak the id).
    render(
      <JiraTicketLink
        issueKey="KAN-15"
        issueUrl="https://example.atlassian.net/browse/KAN-15"
        allowExternalLink
        sessionId="sess-abc"
      />,
    )
    expect(hrefFor('KAN-15')).toBe('https://example.atlassian.net/browse/KAN-15')
  })
})
