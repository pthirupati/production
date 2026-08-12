import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const useThemeStore = create(
  persist(
    (set, get) => ({
      theme: 'dark', // 'dark' | 'light' — default to dark mode

      // Code editor theme, independent of the app chrome. 'auto' follows `theme`,
      // which is the historical behaviour and stays the default; 'dark'/'light'
      // pin the editor so a learner can keep a dark editor inside a light app (or
      // the reverse) without fighting the global toggle.
      editorTheme: 'auto', // 'auto' | 'dark' | 'light'

      setTheme: (theme) => {
        document.documentElement.setAttribute('data-theme', theme)
        set({ theme })
      },

      setEditorTheme: (editorTheme) => set({ editorTheme }),

      /** Resolve 'auto' against the app theme. Returns 'dark' | 'light'. */
      resolvedEditorTheme: () => {
        const { editorTheme, theme } = get()
        if (editorTheme === 'dark' || editorTheme === 'light') return editorTheme
        return theme === 'light' ? 'light' : 'dark'
      },

      toggleTheme: () => {
        const next = get().theme === 'dark' ? 'light' : 'dark'
        document.documentElement.setAttribute('data-theme', next)
        set({ theme: next })
      },

      // Call on app mount to sync DOM with stored preference
      initTheme: () => {
        const theme = get().theme
        document.documentElement.setAttribute('data-theme', theme)
      },
    }),
    {
      name: 'fixitlab-theme',
    }
  )
)
