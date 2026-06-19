import { create } from 'zustand'
import api from '../api/client'

export const useNotificationStore = create((set, get) => ({
  notifications: [],
  unreadCount: 0,
  loading: false,
  lastFetchError: null,

  fetchNotifications: async () => {
    set({ loading: true })
    try {
      const { data } = await api.get('/notifications/', { silentError: true })
      set({
        notifications: data.notifications || data.results || [],
        unreadCount: data.unread_count ?? 0,
        lastFetchError: null,
        loading: false,
      })
    } catch (err) {
      if (!get().lastFetchError) {
        console.warn('Failed to fetch notifications:', err.message)
      }
      set({ lastFetchError: err.message, loading: false })
    }
  },

  markRead: async (id) => {
    try {
      await api.post(`/notifications/${id}/read/`, {}, { silentError: true })
      set((state) => ({
        notifications: state.notifications.map(n =>
          n.id === id ? { ...n, read: true } : n
        ),
        unreadCount: Math.max(0, state.unreadCount - 1),
      }))
    } catch { /* ignore */ }
  },

  markAllRead: async () => {
    try {
      await api.post('/notifications/read/', {}, { silentError: true })
      set((state) => ({
        notifications: state.notifications.map(n => ({ ...n, read: true })),
        unreadCount: 0,
      }))
    } catch { /* ignore */ }
  },

  clearAll: async () => {
    try {
      await api.delete('/notifications/clear/', { silentError: true })
      set({ notifications: [], unreadCount: 0 })
    } catch { /* ignore */ }
  },

  dismiss: async (id) => {
    try {
      await api.delete(`/notifications/${id}/`, { silentError: true })
      set((state) => {
        const target = state.notifications.find(n => n.id === id)
        return {
          notifications: state.notifications.filter(n => n.id !== id),
          unreadCount: target && !target.read
            ? Math.max(0, state.unreadCount - 1)
            : state.unreadCount,
        }
      })
    } catch { /* ignore */ }
  },
}))
