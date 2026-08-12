// Lazy lifecycle shim for the AWS simulator store (audit Z6-7).
//
// `App.jsx` and `api/auth.js` statically imported `components/aws/store/awsStore`
// for three small lifecycle calls. That single static edge rooted the whole
// `aws-console` chunk in the entry graph, so `dist/index.html` `modulepreload`ed
// **322 kB gz** — 49% of a 654 kB eager payload — on every page load. A visitor
// reading the pricing page downloaded the AWS console simulator before LCP.
//
// This module lives OUTSIDE `src/components/aws/` on purpose: `vite.config.js`
// assigns everything under that path to the `aws-console` chunk, so a helper
// placed there would have been part of the very chunk it is meant to defer.
//
// The dynamic import preserves the existing await semantics exactly, which
// matters more than the bytes: `AuthBootValidator` gates its children on
// rehydration finishing, because LabRunner or the AWS console mounting
// mid-rehydrate undoes AwsLabOverlay's clean-seed reset and throws "Lab
// environment error". Every function here still resolves only after the real
// work has completed.
//
// Each is individually guarded. These are boot and logout paths — failing to
// rehydrate a simulator must never prevent someone signing in or out.

let storePromise = null

function loadStore() {
  // Cached so repeated calls (login, then boot validation) share one fetch.
  if (!storePromise) {
    storePromise = import('../components/aws/store/awsStore')
  }
  return storePromise
}

export async function rehydrateAwsSimForUser() {
  try {
    const mod = await loadStore()
    return await mod.rehydrateAwsSimForUser()
  } catch (err) {
    console.warn('[fixitlab] AWS sim rehydrate skipped:', err)
    return undefined
  }
}

export async function resetAwsSimOnLogout() {
  try {
    const mod = await loadStore()
    return mod.resetAwsSimOnLogout()
  } catch (err) {
    console.warn('[fixitlab] AWS sim reset skipped:', err)
    return undefined
  }
}

// `App.jsx` waited on `useAwsStore.persist` directly. Reaching through the store
// object would defeat the whole point, so the wait moved here and the store is
// only touched once it has been loaded.
export async function waitAwsPersistHydrated(timeoutMs = 2500) {
  try {
    const { useAwsStore } = await loadStore()
    const persist = useAwsStore?.persist
    if (!persist?.hasHydrated) return
    if (persist.hasHydrated()) return
    await new Promise((resolve) => {
      let done = false
      const finish = () => {
        if (done) return
        done = true
        resolve()
      }
      const unsub = persist.onFinishHydration?.(() => {
        try { unsub?.() } catch { /* ignore */ }
        finish()
      })
      setTimeout(finish, timeoutMs)
    })
  } catch (err) {
    console.warn('[fixitlab] AWS sim hydration wait skipped:', err)
  }
}
