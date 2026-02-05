import { useEffect } from 'react'
import { useAuthStore } from '../store/authStore'
import { supabase } from '../services/supabase'

export function useAuth() {
  const { user, isAuthenticated, isLoading, login, logout, checkAuth } = useAuthStore()

  useEffect(() => {
    checkAuth()

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session?.user) {
        useAuthStore.setState({
          user: { id: session.user.id, email: session.user.email || '' },
          isAuthenticated: true,
          isLoading: false,
        })
      } else {
        useAuthStore.setState({
          user: null,
          isAuthenticated: false,
          isLoading: false,
        })
      }
    })

    return () => subscription.unsubscribe()
  }, [checkAuth])

  return {
    user,
    isAuthenticated,
    isLoading,
    login,
    logout,
  }
}
