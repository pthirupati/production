import TutorialMermaid from '../tutorials/TutorialMermaid'

/** Parse CONTEXT:/ENVIRONMENT:/SYMPTOM:/OBJECTIVE: labelled scenario text. */
export function parseScenarioSections(text = '') {
  const labels = ['CONTEXT', 'ENVIRONMENT', 'SYMPTOM', 'SYMPTOMS', 'OBJECTIVE', 'OBJECTIVES', 'IMPACT', 'TASK']
  const pattern = new RegExp(`\\b(${labels.join('|')})\\s*:\\s*`, 'gi')
  const matches = [...text.matchAll(pattern)]
  if (!matches.length) return null
  const sections = {}
  matches.forEach((m, i) => {
    const key = m[1].toLowerCase()
    const start = m.index + m[0].length
    const end = i + 1 < matches.length ? matches[i + 1].index : text.length
    sections[key] = text.slice(start, end).trim()
  })
  return sections
}

function architectureChart(techSlug = '', simType = '') {
  const key = `${techSlug} ${simType}`.toLowerCase()
  if (/kubernetes|k8s|eks/.test(key)) {
    return `flowchart LR
  subgraph cluster [Kubernetes]
    API[API server] --> POD[Pods]
    POD --> SVC[Services]
    POD --> VOL[Volumes]
  end
  OPS[kubectl] --> API`
  }
  if (/aws|ec2|terraform/.test(key)) {
    return `flowchart TB
  subgraph aws [AWS]
    IAM[IAM] --> VPC[VPC]
    VPC --> EC2[EC2]
    EC2 --> S3[(S3)]
  end`
  }
  if (/docker|container/.test(key)) {
    return `flowchart LR
  IMG[Image] --> RT[Runtime]
  RT --> CTR[Container]
  CTR --> NET[Network]`
  }
  if (/linux|rhel/.test(key)) {
    return `flowchart TB
  SHELL[Shell] --> SVC[systemd]
  SVC --> FS[Filesystem]
  FS --> NET[Network]`
  }
  if (/windows/.test(key)) {
    return `flowchart LR
  AD[AD] --> SRV[Server]
  SRV --> SVC[Services]
  SVC --> EVT[Event log]`
  }
  if (/devops|jenkins|github|gitlab|argo|flux/.test(key)) {
    return `flowchart LR
  GIT[Git] --> CI[CI/CD]
  CI --> TEST[Test]
  TEST --> DEPLOY[Deploy]`
  }
  return `flowchart LR
  INC[Incident] --> DIAG[Diagnose]
  DIAG --> FIX[Fix]
  FIX --> VERIFY[Validate]`
}

/**
 * Structured incident narrative for scenario detail pages — replaces a wall of
 * labelled template text with readable sections and an architecture diagram.
 */
export default function ScenarioNarrative({ scenario }) {
  const description = (scenario?.description || '').trim()
  const sections = parseScenarioSections(description)
  const techSlug = scenario?.technology?.slug || ''
  const simType = scenario?.simulation_type || ''

  if (!description) return null

  if (!sections) {
    return (
      <div className="glass-card p-6 space-y-4">
        <h2 className="text-base font-semibold text-white">What you will fix</h2>
        <p className="text-sm text-surface-300 leading-relaxed whitespace-pre-wrap">{description}</p>
        <ArchitecturePanel techSlug={techSlug} simType={simType} title={scenario?.title} />
      </div>
    )
  }

  const blocks = [
    { key: 'context', label: 'Background', text: sections.context },
    { key: 'impact', label: 'Impact', text: sections.impact },
    { key: 'symptom', label: 'Symptoms', text: sections.symptom || sections.symptoms },
    { key: 'environment', label: 'Environment', text: sections.environment },
    { key: 'objective', label: 'Your goal', text: sections.objective || sections.objectives || sections.task },
  ].filter((b) => b.text)

  return (
    <div className="glass-card p-6 space-y-5">
      <div>
        <h2 className="text-base font-semibold text-white mb-1">Incident briefing</h2>
        <p className="text-xs text-surface-500">
          Read this like a real on-call ticket — then SSH in and fix it under time pressure.
        </p>
      </div>
      <ArchitecturePanel techSlug={techSlug} simType={simType} title={scenario?.title} />
      <div className="space-y-4">
        {blocks.map((block) => (
          <section key={block.key} className="rounded-lg border border-surface-800/80 bg-surface-900/40 p-4">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-accent-cyan mb-2">{block.label}</h3>
            <p className="text-sm text-surface-300 leading-relaxed whitespace-pre-wrap">{block.text}</p>
          </section>
        ))}
      </div>
    </div>
  )
}

function ArchitecturePanel({ techSlug, simType, title }) {
  const chart = architectureChart(techSlug, simType)
  return (
    <div className="rounded-lg border border-surface-800 overflow-hidden bg-surface-950/60">
      <div className="px-4 py-2 border-b border-surface-800 text-xs font-semibold text-surface-400 uppercase tracking-wider">
        Architecture — {title || techSlug || 'lab environment'}
      </div>
      <div className="p-3 tutorial-diagram">
        <TutorialMermaid chart={chart} />
      </div>
    </div>
  )
}
