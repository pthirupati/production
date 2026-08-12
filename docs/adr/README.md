# Architecture Decision Records

Audit Z6-15: there were zero ADRs. Vault, RS256, Gmail-over-SMTP, the four-droplet
topology and simulation-vs-real provisioning were all live decisions with real
trade-offs, documented nowhere — so the reasoning existed only in one person's head
and every one of them looked arbitrary to anyone else reading the code.

An ADR is not documentation of *how* something works (that is `ARCHITECTURE.md`).
It records **why a choice was made, what was rejected, and what it costs** — so the
decision can be revisited deliberately rather than re-argued from scratch, or
overturned by someone who never knew the constraint.

These are written after the fact, which is stated in each one. A retrospective ADR
is weaker than one written at the time, but it is far stronger than nothing: the
constraints are recoverable from the code and the deploy history, and writing them
down is what stops the next change quietly violating one.

## Format

Short. Context → Decision → Consequences → Alternatives rejected. If an ADR needs
more than a page, the decision probably needs splitting.

## Status values

- **Accepted** — in force.
- **Superseded by NNNN** — replaced; kept because the reasoning still explains the code.
- **Proposed** — under consideration, not yet reflected in the code.

| # | Title | Status |
|---|-------|--------|
| [0001](0001-four-droplet-topology.md) | Four-droplet topology | Accepted |
| [0002](0002-simulation-first-labs.md) | Simulation-first lab provisioning | Accepted |
| [0003](0003-rs256-jwt.md) | RS256 JWTs with a dedicated keypair | Accepted |
| [0004](0004-vault-as-rotation-source.md) | Vault as a rotation source, not a runtime dependency | Accepted |
| [0005](0005-gmail-api-for-transactional-email.md) | Gmail API for transactional email | Accepted |
