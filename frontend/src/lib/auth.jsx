import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { api } from './api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem('pa_user')
    return raw ? JSON.parse(raw) : null
  })

  const persist = useCallback((res) => {
    localStorage.setItem('pa_token', res.access_token)
    localStorage.setItem('pa_user', JSON.stringify(res.user))
    setUser(res.user)
    return res.user
  }, [])

  const value = useMemo(
    () => ({
      user,
      isProvider: user?.role === 'PROVIDER_STAFF',
      isPayer: user?.role === 'PAYER_REVIEWER',
      login: async (payload) => persist(await api.post('/api/auth/login', payload)),
      signupProvider: async (payload) =>
        persist(await api.post('/api/auth/signup/provider', payload)),
      signupPayer: async (payload) =>
        persist(await api.post('/api/auth/signup/payer', payload)),
      refresh: async () => {
        const me = await api.get('/api/auth/me')
        localStorage.setItem('pa_user', JSON.stringify(me))
        setUser(me)
        return me
      },
      logout: () => {
        localStorage.removeItem('pa_token')
        localStorage.removeItem('pa_user')
        setUser(null)
      },
    }),
    [user, persist],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}

export function RequireRole({ role, children }) {
  const { user } = useAuth()
  const location = useLocation()
  if (!user) {
    const to = role === 'PROVIDER_STAFF' ? '/hospital/signin' : '/payer/signin'
    return <Navigate to={to} state={{ from: location }} replace />
  }
  if (user.role !== role) {
    return <Navigate to={user.role === 'PROVIDER_STAFF' ? '/hospital' : '/payer'} replace />
  }
  return children
}