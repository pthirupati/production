/** Build a localStorage key scoped to the current user (or anon on logout). */
export function userScopedKey(base, userId) {
  const uid = userId != null && userId !== '' ? String(userId) : 'anon'
  return `${base}:${uid}`
}
