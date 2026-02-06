import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import api from '../services/api'

interface User {
  id: string
  email: string
}

interface AuthState {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  checkAuth: () => Promise<void>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: false,
      isLoading: true,

      login: async (email: string, password: string) => {
        try {
          const response = await api.post('/auth/login', { email, password })
          const { user, token } = response.data

          // Store token for API requests
          localStorage.setItem('auth_token', token)
          api.defaults.headers.common['Authorization'] = `Bearer ${token}`

          set({
            user: { id: user.id, email: user.email },
            isAuthenticated: true,
          })
        } catch (error) {
          throw error
        }
      },

      logout: async () => {
        localStorage.removeItem('auth_token')
        delete api.defaults.headers.common['Authorization']
        set({ user: null, isAuthenticated: false })
      },

      checkAuth: async () => {
        set({ isLoading: true })
        const token = localStorage.getItem('auth_token')

        if (token) {
          api.defaults.headers.common['Authorization'] = `Bearer ${token}`
          set({
            isAuthenticated: true,
            isLoading: false,
          })
        } else {
          // No auth required — allow access without login
          set({
            user: null,
            isAuthenticated: true,
            isLoading: false,
          })
        }
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({ user: state.user, isAuthenticated: state.isAuthenticated }),
    }
  )
)
