/** Root layout class for simulator panels — embedded in LabRunner or full-screen overlay. */
export function simPanelRoot(embedded, className = '') {
  const base = embedded
    ? 'h-full min-h-0 flex flex-col overflow-hidden relative'
    : 'fixed inset-0 z-[60] flex flex-col overflow-hidden'
  return className ? `${base} ${className}`.trim() : base
}

/** Full-height shell for monitoring-style sims (Grafana/Prometheus). */
export function simShellClass(embedded) {
  return embedded ? 'mon-sim mon-shell h-full min-h-0 flex flex-col overflow-hidden' : 'mon-sim mon-shell min-h-[100dvh] flex flex-col overflow-hidden'
}
