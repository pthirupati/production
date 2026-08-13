/** Root layout class for simulator panels — embedded in LabRunner or full-screen overlay. */
export function simPanelRoot(embedded, className = '') {
  // Non-embedded must be `absolute` (not `fixed`) so companions inside a fixed
  // LabRunner overlay fill the overlay instead of nesting another viewport-fixed
  // layer (half-page clip + missing lab chrome). Standalone pages that need
  // full-viewport coverage should wrap with a positioned full-height parent.
  const base = embedded
    ? 'h-full min-h-0 flex flex-col overflow-hidden relative'
    : 'absolute inset-0 z-[60] flex flex-col overflow-hidden h-full w-full'
  return className ? `${base} ${className}`.trim() : base
}

/** Full-height shell for monitoring-style sims (Grafana/Prometheus). */
export function simShellClass(embedded) {
  return embedded ? 'mon-sim mon-shell h-full min-h-0 flex flex-col overflow-hidden' : 'mon-sim mon-shell min-h-[100dvh] flex flex-col overflow-hidden'
}
