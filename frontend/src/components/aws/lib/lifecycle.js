// Durable, generalized resource-lifecycle engine.
//
// Instead of ad-hoc setTimeout calls that are lost on reload / HMR, every
// transitioning resource records WHEN it should finish (stateTransitionAt,
// epoch ms) and WHAT it becomes (pendingTransition). A single global 1s tick
// (armed exactly once, HMR-safe) plus reconcile() on store init/rehydrate
// resolves everything — including transitions that came due while the tab was
// closed. Timings are lab-fast and centralized here.

// ---------- Timing constants (lab-fast) ----------
export const EC2_TIMING = {
  pendingToRunning: [8000, 12000], // pending -> running
  checkPhase1: 3000, // running: initializing -> 1/2
  checkPhase2: 3000, // running: 1/2 -> 2/2 (after phase1)
  stopping: 6000, // stopping -> stopped
  rebooting: 7000, // rebooting -> running (checks reset then re-run)
  shuttingDown: 6000, // shutting-down -> terminated
  terminatedLinger: 60000, // hide terminated instances after this
}

export const GENERIC_TIMING = {
  createStep: 4000, // per intermediate create state
  action: 4000, // reboot/modify interim -> final
  deleting: 3000, // deleting -> removed
}

const TICK_MS = 1000

function rand(range) {
  const [lo, hi] = range
  return lo + Math.random() * (hi - lo)
}

/** epoch ms `range`/`ms` in the future. */
export function dueIn(rangeOrMs) {
  const ms = Array.isArray(rangeOrMs) ? rand(rangeOrMs) : rangeOrMs
  return Date.now() + ms
}

// ---------- Two-phase EC2 status checks ----------
export function initializingChecks() {
  return { system: 'initializing', instance: 'initializing', reachability: 'initializing', summary: 'initializing' }
}
export function phase1Checks() {
  return { system: 'passed', instance: 'initializing', reachability: 'initializing', summary: '1/2' }
}
export function passedChecks() {
  return { system: 'passed', instance: 'passed', reachability: 'passed', summary: '2/2' }
}
export function noChecks() {
  return { system: '-', instance: '-', reachability: '-', summary: '-' }
}

// ---------- Global single tick (HMR-safe) ----------
// Module-level flag survives re-import within a session; on HMR dispose we
// clear the old interval before a new module instance re-arms it.
let _timer = null
let _tickFn = null

/** Arm the global 1s interval exactly once. `tick` is invoked every second. */
export function armLifecycleTick(tick) {
  _tickFn = tick
  if (_timer != null) return // already armed
  if (typeof setInterval !== 'function') return
  _timer = setInterval(() => {
    try { if (_tickFn) _tickFn() } catch { /* ignore tick errors */ }
  }, TICK_MS)
  // HMR: dispose old timer so we never stack intervals.
  if (typeof import.meta !== 'undefined' && import.meta.hot) {
    import.meta.hot.dispose(() => {
      if (_timer != null) { clearInterval(_timer); _timer = null }
    })
  }
}

/** Test/util hook to stop the interval. */
export function stopLifecycleTick() {
  if (_timer != null) { clearInterval(_timer); _timer = null }
}
