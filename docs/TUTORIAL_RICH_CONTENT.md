# Tutorial Rich Content Contract

FixitLab tutorials are authored locally and rendered offline. Do not add paid APIs
or runtime image fetches. Diagrams should be Mermaid or inline SVG; examples,
quizzes, and lab links are produced by deterministic seeders.

## Required Lesson Surface

Every seeded lesson must include:

- At least one Mermaid diagram or inline diagram block.
- Copyable fenced code or shell commands with expected output.
- A comparison or cheat-sheet table.
- At least two callouts (`NOTE`, `TIP`, `WARNING`, `DANGER`, or `GOTCHA`).
- A generated 5-question scored quiz with `pass_score` 0.8.
- A linked hands-on scenario.

The lesson body should cover: overview, prerequisites, core concept, architecture,
step-by-step practice, worked example, common errors, best practices, cheat sheet,
summary, quiz, and linked lab.

## Commands

```bash
python manage.py seed_tutorials
python manage.py check_tutorial_completeness --all
python manage.py check_tutorial_completeness --technology=Linux
```

`seed_tutorials` is idempotent. It enriches generated sections with offline
Mermaid diagrams, callouts, tables, shell/code examples, assessment sections, and
best-effort linked labs. The CI jobs run `seed_tutorials` followed by
`check_tutorial_completeness --all`.

## Renderer Manual Verification

Open any tutorial page and verify:

- Reading progress bar advances while scrolling.
- Mermaid diagrams render without network calls.
- Code blocks show line numbers, copy button, and collapse controls for long code.
- Shell blocks separate command and expected output.
- Tables have sticky headers and CSV export.
- Callouts render with distinct visual styles.
- The completion checklist requires quiz pass plus linked lab completion.
