import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// Tokens are now stored in httpOnly cookies set by the backend — they are NOT
// persisted in localStorage and are never accessible to JavaScript.
// Only non-sensitive user profile data is kept in localStorage so the UI can
// restore the logged-in state across page reloads without reading a cookie.
export const useAuthStore = create(
  persist(
    (set, get) => ({
      user: null,
      // accessToken / refreshToken kept in state (not localStorage) for
      // backwards-compat with the Authorization header path.  They are
      // populated from the JSON response body during the transition period;
      // once the frontend is fully cookie-only these can be removed.
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,

      setAuth: (user, accessToken, refreshToken) =>
        set({ user, accessToken, refreshToken, isAuthenticated: true }),

      logout: () =>
        set({ user: null, accessToken: null, refreshToken: null, isAuthenticated: false }),

      isAdmin: () => get().user?.is_staff === true,
    }),
    {
      name: 'fixitlab-auth',
      // Only persist user profile — tokens live in httpOnly cookies.
      partialize: (state) => ({ user: state.user, isAuthenticated: state.isAuthenticated }),
    }
  )
)
