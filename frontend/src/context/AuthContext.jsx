import React, { createContext, useContext, useEffect, useState } from 'react'
import { supabase } from '../supabaseClient'

const AuthContext = createContext(null)

const DAILY_LIMIT_FREE = 3

function getUsageToday() {
  const key = 'cv-analyzer-usage-' + new Date().toISOString().slice(0, 10)
  return parseInt(localStorage.getItem(key) || '0', 10)
}

function incrementUsage() {
  const key = 'cv-analyzer-usage-' + new Date().toISOString().slice(0, 10)
  const current = getUsageToday()
  localStorage.setItem(key, String(current + 1))
  return current + 1
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(null)
  const [loading, setLoading] = useState(true)
  const [plan, setPlan] = useState('free')
  const [usageToday, setUsageToday] = useState(getUsageToday())

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null)
      setToken(session?.access_token ?? null)
      setLoading(false)
    })

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null)
      setToken(session?.access_token ?? null)
    })

    return () => subscription.unsubscribe()
  }, [])

  // Refresh usage count every minute
  useEffect(() => {
    const interval = setInterval(() => setUsageToday(getUsageToday()), 60000)
    return () => clearInterval(interval)
  }, [])

  async function signUp(email, password) {
    const { data, error } = await supabase.auth.signUp({ email, password })
    if (error) throw error
    return data
  }

  async function signIn(email, password) {
    const { data, error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) throw error
    return data
  }

  async function signInWithGoogle() {
    const { data, error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin + '/dashboard' }
    })
    if (error) throw error
    return data
  }

  async function resetPassword(email) {
    const { data, error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: window.location.origin + '/login'
    })
    if (error) throw error
    return data
  }

  async function updatePassword(newPassword) {
    const { data, error } = await supabase.auth.updateUser({ password: newPassword })
    if (error) throw error
    return data
  }

  async function signOut() {
    const { error } = await supabase.auth.signOut()
    if (error) throw error
    setUser(null)
    setToken(null)
  }

  function canAnalyze() {
    if (plan !== 'free') return true
    return getUsageToday() < DAILY_LIMIT_FREE
  }

  function recordAnalysis() {
    const newCount = incrementUsage()
    setUsageToday(newCount)
    return newCount
  }

  const dailyLimit = plan === 'free' ? DAILY_LIMIT_FREE : Infinity

  return (
    <AuthContext.Provider value={{
      user, token, loading, plan, usageToday, dailyLimit,
      signUp, signIn, signInWithGoogle, signOut,
      resetPassword, updatePassword,
      canAnalyze, recordAnalysis
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
