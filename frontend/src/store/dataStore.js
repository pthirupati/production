import { create } from 'zustand'
import { scenarioApi } from '../api/scenarios'

export const useDataStore = create((set, get) => ({
  technologies: null,
  technologiesLoadedAt: null,
  STALE_MS: 5 * 60 * 1000, // 5 minutes

  getTechnologies: async () => {
    const { technologies, technologiesLoadedAt, STALE_MS } = get()
    const now = Date.now()
    if (technologies && technologiesLoadedAt && (now - technologiesLoadedAt) < STALE_MS) {
      return technologies
    }
    try {
      const data = await scenarioApi.getTechnologies()
      const techs = data.technologies || data || []
      set({ technologies: techs, technologiesLoadedAt: now })
      return techs
    } catch (err) {
      // Return cached even if stale rather than breaking
      if (technologies) return technologies
      throw err
    }
  },

  invalidateTechnologies: () => set({ technologies: null, technologiesLoadedAt: null }),
}))
