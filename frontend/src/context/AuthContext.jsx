import React, { createContext, useContext, useEffect, useState } from 'react'
import { supabase } from '../supabaseClient'
import { fetchUsage } from '../api'

const AuthContext = createContext(null)

const DAILY_LIMIT_FREE = 5

function checkBillingAdmin(email) {
  const configured = String(import.meta.env.VITE_BILLING_ADMIN_EMAILS || '')
    .split(',')
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean)
  return !!email && configured.includes(String(email).toLowerCase())
}

export function AuthProvider({ children }) {
  const cachedPlan = (() => {
    try { return localStorage.getItem('cv_plan_cache') } catch { return null }
  })()
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(null)
  const [loading, setLoading] = useState(true)
  const [planLoading, setPlanLoading] = useState(!cachedPlan)
  const [plan, setPlan] = useState(cachedPlan || 'free')
  const [role, setRole] = useState('individual')
  const [usageToday, setUsageToday] = useState(0)
  const [dailyLimit, setDailyLimit] = useState(DAILY_LIMIT_FREE)
  const [usageSource, setUsageSource] = useState('unknown')

  async function refreshUsage(accessToken = token, { background = false, email = null } = {}) {
    if (!accessToken) {
      setUsageToday(0)
      setDailyLimit(DAILY_LIMIT_FREE)
      setPlan('free')
      setUsageSource('unknown')
      setPlanLoading(false)
      return
    }

    // Resolve admin status immediately using the passed email (avoids stale state)
    const isAdmin = checkBillingAdmin(email || user?.email)

    if (!background) setPlanLoading(true)
    try {
      const usage = await fetchUsage(accessToken)
      const planType = usage?.plan_type || 'free'
      const limit = Number(usage?.daily?.limit ?? DAILY_LIMIT_FREE)
      const used = Number(usage?.daily?.used ?? 0)
      const source = usage?.source || 'unknown'
      setPlan(isAdmin ? 'admin' : planType)
      try { localStorage.setItem('cv_plan_cache', isAdmin ? 'admin' : planType) } catch {}
      setRole(isAdmin ? 'admin' : (usage?.role || 'individual'))
      setDailyLimit(isAdmin ? Infinity : (planType === 'free' ? limit : Infinity))
      setUsageToday(used)
      setUsageSource(source)
    } catch {
      // Keep existing values if usage endpoint is temporarily unavailable.
      if (isAdmin) {
        setPlan('admin')
        setRole('admin')
        setDailyLimit(Infinity)
      }
    } finally {
      if (!background) setPlanLoading(false)
    }
  }

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null)
      setToken(session?.access_token ?? null)
      if (session?.access_token) {
        refreshUsage(session.access_token, { background: !!cachedPlan, email: session?.user?.email })
      } else {
        setPlanLoading(false)
      }
      setLoading(false)
    })

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null)
      setToken(session?.access_token ?? null)
      if (session?.access_token) {
        refreshUsage(session.access_token, { background: !!cachedPlan, email: session?.user?.email })
      } else {
        setPlanLoading(false)
        setPlan('free')
        setUsageToday(0)
        setDailyLimit(DAILY_LIMIT_FREE)
        setUsageSource('unknown')
        setRole('individual')
      }
    })

    return () => subscription.unsubscribe()
  }, [])

  // Refresh usage count from backend every minute when authenticated.
  useEffect(() => {
    const interval = setInterval(() => {
      if (token) refreshUsage(token, { background: true })
    }, 60000)
    return () => clearInterval(interval)
  }, [token])

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
    setPlan('free')
    try { localStorage.removeItem('cv_plan_cache') } catch {}
    setUsageToday(0)
    setDailyLimit(DAILY_LIMIT_FREE)
    setUsageSource('unknown')
    setRole('individual')
  }

  async function deleteUser() {
    // Calls a Supabase RPC that deletes the authenticated user inside a security definer function.
    // Required SQL: CREATE OR REPLACE FUNCTION delete_user() RETURNS void LANGUAGE sql SECURITY DEFINER AS $$ DELETE FROM auth.users WHERE id = auth.uid(); $$;
    const { error } = await supabase.rpc('delete_user')
    if (error) throw error
    setUser(null)
    setToken(null)
    setPlan('free')
    try { localStorage.removeItem('cv_plan_cache') } catch {}
    setUsageToday(0)
    setDailyLimit(DAILY_LIMIT_FREE)
    setUsageSource('unknown')
    setRole('individual')
  }

  const isBillingAdmin = checkBillingAdmin(user?.email)

  function canAnalyze() {
    if (isBillingAdmin) return true
    if (planLoading) return true
    if (plan !== 'free') return true
    return usageToday < dailyLimit
  }

  function recordAnalysis() {
    const newCount = usageToday + 1
    setUsageToday(newCount)
    return newCount
  }

  return (
    <AuthContext.Provider value={{
      user, token, loading, planLoading, plan, role, usageToday, dailyLimit,
      usageSource, isBillingAdmin,
      signUp, signIn, signInWithGoogle, signOut, deleteUser,
      resetPassword, updatePassword,
      canAnalyze, recordAnalysis, refreshUsage
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
