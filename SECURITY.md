# Security Policy

FixitLab runs interactive lab environments and stores candidate interview data, so
we take reports seriously and respond to all of them.

## Reporting a vulnerability

**Please do not open a public issue for a security problem.** Use either:

- **Email** — security@fixitlab.in
- **GitHub** — [private security advisory](https://github.com/pthirupati/production/security/advisories/new)

Machine-readable contact: [`/.well-known/security.txt`](https://fixitlab.in/.well-known/security.txt) (RFC 9116).

Include what you need to make it reproducible: the URL or endpoint, the steps, what
you expected, what happened, and any proof-of-concept. Please tell us if you believe
data was exposed — that changes our notification obligations and our timeline.

### What to expect

| Stage | Target |
|---|---|
| Acknowledgement of your report | 3 working days |
| Initial assessment + severity | 7 working days |
| Fix or documented mitigation for critical issues | 30 days |
| Public credit (if you want it) | on release of the fix |

If we disagree that something is a vulnerability, we will explain why rather than
close it silently.

## Safe harbour

We will not pursue legal action, or ask your hosting provider to act against you, for
security research conducted in good faith under this policy. Good faith means:

- You only access data belonging to accounts you control. If you encounter someone
  else's personal data — resumes, interview transcripts, email addresses — **stop,
  do not download or retain it, and tell us what you saw**.
- You do not degrade the service for others: no DoS or load testing, no mass
  scanning that affects availability, no spam through platform email.
- You do not modify or destroy data that is not yours.
- You give us a reasonable chance to fix the issue before publishing.

Lab containers are yours to break — that is what they are for. Escaping a lab
container to reach the host or another user's session is very much in scope, and we
want to hear about it.

## In scope

- `fixitlab.in` and its API
- Lab container isolation and sandbox escape (including the code-grading sandbox)
- Authentication, session handling, and JWT issuance/validation
- Cross-user data access: labs, interviews, resumes, certificates, billing
- Payment flows and webhook signature verification
- Certificate issuance and verification, and privilege escalation to staff/admin

## Out of scope

- Missing security headers or TLS configuration with no demonstrated impact
- Rate limiting on unauthenticated read-only endpoints
- Self-XSS, or issues requiring a compromised device or physical access
- Social engineering of staff or users
- Automated scanner output with no working proof of concept
- Vulnerabilities in a dependency with no exploitable path in FixitLab — report
  those upstream, though we appreciate a heads-up

## Handling a confirmed breach

If a report shows personal data was exposed, we notify affected users and the Data
Protection Board of India within the DPDP Act timeline, and record what was
accessed, when, and the remediation. The privacy contact for data-protection
questions (as opposed to vulnerability reports) is in
[the privacy policy](https://fixitlab.in/privacy).
