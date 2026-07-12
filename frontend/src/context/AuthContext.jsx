import React, { createContext, useContext, useEffect, useState } from 'react'
import { supabase } from '../supabaseClient'
import { deleteMyAccount, fetchUsage } from '../api'

/**
 * @typedef {Object} AuthContextValue
 * @property {any} user
 * @property {string | null} token
 * @property {boolean} loading
 * @property {boolean} planLoading
 * @property {string} plan
 * @property {string} role
 * @property {number} usageToday
 * @property {number} dailyLimit
 * @property {string} usageSource
 * @property {boolean} isBillingAdmin
 * @property {(email: string, password: string) => Promise<any>} signUp
 * @property {(email: string, password: string) => Promise<any>} signIn
 * @property {() => Promise<any>} signInWithGoogle
 * @property {() => Promise<void>} signOut
 * @property {() => Promise<void>} deleteUser
 * @property {(email: string) => Promise<any>} resetPassword
 * @property {(newPassword: string) => Promise<any>} updatePassword
 * @property {() => boolean} canAnalyze
 * @property {() => number} recordAnalysis
 * @property {(accessToken?: string | null, options?: { background?: boolean, email?: string | null }) => Promise<void>} refreshUsage
 */

const AUTH_CONTEXT_KEY = '__CV_ANALYZER_AUTH_CONTEXT__'

/**
 * Keep a single context instance across Vite HMR updates.
 * Without this, Fast Refresh can recreate the context object and
 * temporarily desync AuthProvider/useAuth, causing runtime null-context errors.
 */
const AuthContext = (() => {
  if (typeof globalThis !== 'undefined' && globalThis[AUTH_CONTEXT_KEY]) {
    return globalThis[AUTH_CONTEXT_KEY]
  }

  const ctx = createContext(/** @type {AuthContextValue | null} */ (null))
  if (typeof globalThis !== 'undefined') {
    globalThis[AUTH_CONTEXT_KEY] = ctx
  }
  return ctx
})()

const DAILY_LIMIT_FREE = 5
const BILLABLE_USAGE_EVENT = 'cv-analyzer:billable-usage'

function checkBillingAdmin(email) {
  const configured = String(import.meta.env.VITE_BILLING_ADMIN_EMAILS || '')
    .split(',')
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean)
  return !!email && configured.includes(String(email).toLowerCase())
}

const LEGACY_USER_DATA_KEYS = new Set([
  'cv_analyzer_job_tracker',
  'cv-analyzer:interview-session-v2',
  'recruiter_usage_rights',
])

function isLegacyRecruiterMonthKey(key) {
  return /^recruiter_(batch_results|candidate_actions|decisions)_\d{4}-\d{2}$/.test(key)
}

export function clearLocalUserData(userId) {
  if (!userId || typeof localStorage === 'undefined') return
  const keysToRemove = []
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i)
    if (key && (key.includes(userId) || LEGACY_USER_DATA_KEYS.has(key) || isLegacyRecruiterMonthKey(key))) {
      keysToRemove.push(key)
    }
  }
  keysToRemove.forEach((key) => localStorage.removeItem(key))
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

    // Resolve admin status with both local config and backend role.
    const localAdmin = checkBillingAdmin(email || user?.email)

    if (!background) setPlanLoading(true)
    try {
      const usage = await fetchUsage(accessToken)
      const planType = usage?.plan_type || 'free'
      const backendRole = usage?.role || 'individual'
      const isAdmin = localAdmin || backendRole === 'admin'
      const limit = Number(usage?.daily?.limit ?? DAILY_LIMIT_FREE)
      const used = Number(usage?.daily?.used ?? 0)
      const source = usage?.source || 'unknown'
      setPlan(isAdmin ? 'admin' : planType)
      try { localStorage.setItem('cv_plan_cache', isAdmin ? 'admin' : planType) } catch {}
      setRole(isAdmin ? 'admin' : backendRole)
      setDailyLimit(isAdmin ? Infinity : (planType === 'free' ? limit : Infinity))
      setUsageToday(used)
      setUsageSource(source)
    } catch {
      // Keep existing values if usage endpoint is temporarily unavailable.
      if (localAdmin || role === 'admin') {
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
    const userId = user?.id
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
    try {
      clearLocalUserData(userId)
    } catch (e) {
      console.warn('Failed to clear user-scoped localStorage on signOut:', e)
    }
  }

  async function deleteUser() {
    const userId = user?.id
    // Purge all application data (CV texts, stored files, analyses, recruiter
    // records) before removing the auth user — the Supabase RPC only deletes
    // the auth.users row. If the purge fails we abort so no orphaned data
    // survives behind a deleted login.
    await deleteMyAccount(token)
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
    try {
      clearLocalUserData(userId)
    } catch (e) {
      console.warn('Failed to clear user-scoped localStorage on deleteUser:', e)
    }
  }

  const isBillingAdmin = checkBillingAdmin(user?.email) || role === 'admin'

  useEffect(() => {
    if (typeof window === 'undefined') return undefined

    function handleBillableUsage() {
      if (!token) return
      if (!isBillingAdmin && role !== 'admin') {
        setUsageToday((prev) => prev + 1)
      }
      refreshUsage(token, { background: true })
    }

    window.addEventListener(BILLABLE_USAGE_EVENT, handleBillableUsage)
    return () => window.removeEventListener(BILLABLE_USAGE_EVENT, handleBillableUsage)
  }, [token, isBillingAdmin, role])

  function canAnalyze() {
    if (isBillingAdmin || role === 'admin') return true
    if (planLoading) return true
    if (plan !== 'free') return true
    return usageToday < dailyLimit
  }

  function recordAnalysis() {
    const newCount = usageToday + 1
    setUsageToday(newCount)
    if (token) refreshUsage(token, { background: true })
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
  /** @type {AuthContextValue | null} */
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
