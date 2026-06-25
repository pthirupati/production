const STORAGE_KEY = 'fixitlab_tutorial_progress'

function readAll() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')
  } catch {
    return {}
  }
}

function writeAll(data) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
  } catch { /* ignore */ }
}

export function getLocalTutorialProgress(slug) {
  const all = readAll()
  return all[slug] || { completed_sections: [], last_section_order: 0, completed: false }
}

export function setLocalTutorialProgress(slug, patch) {
  const all = readAll()
  const prev = all[slug] || { completed_sections: [], last_section_order: 0, completed: false }
  all[slug] = { ...prev, ...patch, updated_at: new Date().toISOString() }
  writeAll(all)
  return all[slug]
}

export function markLocalSection(slug, sectionOrder, totalSections) {
  const prev = getLocalTutorialProgress(slug)
  const completed_sections = sortedUnique([...(prev.completed_sections || []), sectionOrder])
  const completed = totalSections > 0 && completed_sections.length >= totalSections
  return setLocalTutorialProgress(slug, {
    completed_sections,
    last_section_order: Math.max(prev.last_section_order || 0, sectionOrder),
    completed,
  })
}

export function listLocalContinue() {
  const all = readAll()
  return Object.entries(all)
    .filter(([, p]) => !p.completed)
    .map(([tutorial_slug, p]) => ({
      tutorial_slug,
      ...p,
      progress_pct: p.progress_pct || 0,
    }))
    .sort((a, b) => (b.updated_at || '').localeCompare(a.updated_at || ''))
    .slice(0, 6)
}

function sortedUnique(arr) {
  return [...new Set(arr.map(Number).filter((n) => !Number.isNaN(n)))].sort((a, b) => a - b)
}

export function progressPct(completedSections, total) {
  if (!total) return 0
  return Math.min(100, Math.round(((completedSections || []).length / total) * 100))
}
