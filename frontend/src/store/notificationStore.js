import { create } from 'zustand'
import api from '../api/client'

export const useNotificationStore = create((set, get) => ({
  notifications: [],
  unreadCount: 0,
  loading: false,
  lastFetchError: null,

  fetchNotifications: async () => {
    try {
      const { data } = await api.get('/notifications/')
      set({
        notifications: data.notifications || data.results || [],
        unreadCount: data.unread_count ?? 0,
        lastFetchError: null,
      })
    } catch (err) {
      // Only log on first failure, don't spam
      if (!get().lastFetchError) {
        console.warn('Failed to fetch notifications:', err.message)
      }
      set({ lastFetchError: err.message })
    }
  },

  markRead: async (id) => {
    try {
      await api.post(`/notifications/${id}/read/`)
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
      await api.post('/notifications/read/')
      set((state) => ({
        notifications: state.notifications.map(n => ({ ...n, read: true })),
        unreadCount: 0,
      }))
    } catch { /* ignore */ }
  },

  clearAll: async () => {
    try {
      await api.post('/notifications/read/')
      set({ notifications: [], unreadCount: 0 })
    } catch { /* ignore */ }
  },
}))
