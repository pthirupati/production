import { useAuthStore } from '../store/authStore'

/** Build a localStorage key scoped to the current user (or anon on logout). */
export function userScopedKey(base, userId) {
  const uid = userId != null && userId !== '' ? String(userId) : 'anon'
  return `${base}:${uid}`
}

/**
 * Scoped key for whoever is logged in *right now*.
 *
 * Read lazily at call time rather than captured at module scope: the auth store
 * rehydrates from localStorage synchronously on import, but components that
 * compute a key during module evaluation would still bind before a login/logout
 * later in the session and keep writing to the previous user's bucket.
 */
export function currentUserScopedKey(base) {
  return userScopedKey(base, useAuthStore.getState().user?.id)
}

/**
 * One-time move of a pre-scoping unscoped key into the current user's bucket.
 *
 * Without this, shipping per-user scoping silently invalidates every existing
 * dismissal — on deploy the whole user base gets the changelog modal, onboarding
 * tour, support bot and campaign banner re-shown simultaneously. The first
 * logged-in reader after deploy adopts the legacy value, then the legacy key is
 * removed so a second account on the same browser does NOT inherit it (which is
 * the cross-account leak this scoping exists to fix).
 *
 * Returns the scoped key so callers can read/write through it directly.
 */
export function migrateUnscopedKey(base) {
  const scoped = currentUserScopedKey(base)
  try {
    const legacy = localStorage.getItem(base)
    if (legacy !== null) {
      // Never clobber a value already written under the scoped key.
      if (localStorage.getItem(scoped) === null) {
        localStorage.setItem(scoped, legacy)
      }
      localStorage.removeItem(base)
    }
  } catch {
    /* private mode / quota — scoping still applies, migration is best-effort */
  }
  return scoped
}
