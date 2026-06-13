import React, { useEffect, useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Shield, KeyRound, Users, UserCog, MessageSquareWarning, ChevronLeft, ChevronRight, RefreshCw, Save, Loader2, Search, CheckCircle2 } from 'lucide-react'
import Navbar from '../components/Navbar'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../components/Toast'
import { useLanguage } from '../i18n/LanguageContext'
import {
  billingAdminListFeedback,
  billingAdminListUsers,
  billingAdminMe,
  billingAdminSetUserPlan,
} from '../api'

const ADMIN_TOKEN_STORAGE_KEY = 'billing_admin_token'

const ADMIN_TEXT = {
  en: {
    title: 'Admin Page',
    subtitle: 'Only allowlisted admin accounts can access this screen.',
    verifyTitle: 'Admin Verification',
    tokenLabel: 'Admin Token',
    tokenPlaceholder: 'Enter admin token',
    verifyBtn: 'Verify',
    verifyingBtn: 'Checking...',
    signedInUser: 'Signed-in user',
    updateTitle: 'Update User Membership',
    emailLabel: 'Email (optional)',
    supabaseLabel: 'Supabase ID (optional)',
    planLabel: 'Plan',
    billingLabel: 'Billing Status',
    roleLabel: 'Role',
    noChange: 'No change',
    updateOrg: 'Also update organization plan/status',
    saveBtn: 'Save Changes',
    savingBtn: 'Saving...',
    listTitle: 'User List',
    listBtn: 'List Users',
    loadingBtn: 'Loading...',
    total: 'Total',
    refresh: 'Refresh',
    feedbackTitle: 'Recent Complaints',
    thDate: 'Date',
    thCategory: 'Category',
    thSender: 'Sender',
    thMessage: 'Message',
    noRecords: 'No records',
    noFeedback: 'No complaint records',
    pageFail: 'Page fetch failed',
    verifyTokenRequired: 'Admin token is required',
    verified: 'Admin access verified',
    verifyFailed: 'Admin verification failed',
    listFailed: 'Could not fetch users',
    feedbackFailed: 'Could not fetch complaints',
    needVerify: 'Verify admin access first',
    requireUserId: 'email or supabase_id is required',
    requireAnyUpdate: 'Choose at least one update: plan, status, or role',
    updateOk: 'User updated successfully',
    updateFail: 'Update failed',
    prev: 'Prev',
    next: 'Next',
  },
  tr: {
    title: 'Admin Sayfasi',
    subtitle: 'Bu ekrana sadece yetkili admin hesaplari erisebilir.',
    verifyTitle: 'Admin Dogrulama',
    tokenLabel: 'Admin Sifresi',
    tokenPlaceholder: 'Admin sifrenizi girin',
    verifyBtn: 'Dogrula',
    verifyingBtn: 'Kontrol...',
    signedInUser: 'Giris yapan kullanici',
    updateTitle: 'Kullanici Uyelik Guncelle',
    emailLabel: 'Email (opsiyonel)',
    supabaseLabel: 'Supabase ID (opsiyonel)',
    planLabel: 'Plan',
    billingLabel: 'Fatura Durumu',
    roleLabel: 'Rol',
    noChange: 'Degistirme',
    updateOrg: 'Organization plan/status bilgilerini de guncelle',
    saveBtn: 'Degisiklikleri Kaydet',
    savingBtn: 'Kaydediliyor...',
    listTitle: 'Kullanici Listesi',
    listBtn: 'Listele',
    loadingBtn: 'Yukleniyor...',
    total: 'Toplam',
    refresh: 'Yenile',
    feedbackTitle: 'Son Sikayetler',
    thDate: 'Tarih',
    thCategory: 'Kategori',
    thSender: 'Gonderen',
    thMessage: 'Mesaj',
    noRecords: 'Kayit yok',
    noFeedback: 'Sikayet kaydi yok',
    pageFail: 'Sayfa alinamadi',
    verifyTokenRequired: 'Admin token gerekli',
    verified: 'Admin erisimi dogrulandi',
    verifyFailed: 'Admin dogrulama basarisiz',
    listFailed: 'Kullanici listesi alinamadi',
    feedbackFailed: 'Sikayetler alinamadi',
    needVerify: 'Once admin dogrulama yap',
    requireUserId: 'email veya supabase_id zorunlu',
    requireAnyUpdate: 'En az bir guncelleme sec: plan, durum veya rol',
    updateOk: 'Kullanici guncellendi',
    updateFail: 'Guncelleme basarisiz',
    prev: 'Prev',
    next: 'Next',
  },
  fr: {},
  de: {},
  es: {},
  ar: {},
}

export default function AdminBillingPage() {
  const { token, user } = useAuth()
  const { addToast } = useToast()
  const { lang } = useLanguage()

  const tx = (key) => {
    const bucket = ADMIN_TEXT[lang] || ADMIN_TEXT.en
    return bucket[key] || ADMIN_TEXT.en[key] || key
  }

  const [adminToken, setAdminToken] = useState('')
  const [isVerified, setIsVerified] = useState(false)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)

  const [users, setUsers] = useState([])
  const [feedbackItems, setFeedbackItems] = useState([])
  const [total, setTotal] = useState(0)
  const [limit, setLimit] = useState(25)
  const [offset, setOffset] = useState(0)
  const [emailFilter, setEmailFilter] = useState('')
  const [planFilter, setPlanFilter] = useState('')

  const [targetEmail, setTargetEmail] = useState('')
  const [targetSupabaseId, setTargetSupabaseId] = useState('')
  const [targetPlan, setTargetPlan] = useState('')
  const [targetStatus, setTargetStatus] = useState('')
  const [targetRole, setTargetRole] = useState('')
  const [updateOrganization, setUpdateOrganization] = useState(false)

  useEffect(() => {
    document.title = 'Billing Admin - CV Analyzer'
    try {
      localStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY)
      const stored = sessionStorage.getItem(ADMIN_TOKEN_STORAGE_KEY) || ''
      if (stored) {
        setAdminToken(stored)
      }
    } catch {
      // noop
    }
  }, [])

  const canQuery = useMemo(() => !!token && !!adminToken.trim() && isVerified, [token, adminToken, isVerified])

  async function verifyAccess() {
    if (!token || !adminToken.trim()) {
      addToast(tx('verifyTokenRequired'), 'error')
      return
    }

    setLoading(true)
    try {
      await billingAdminMe(token, adminToken.trim())
      setIsVerified(true)
      try {
        localStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY)
        sessionStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, adminToken.trim())
      } catch {
        // noop
      }
      addToast(tx('verified'), 'success')
      try {
        const feedbackData = await billingAdminListFeedback(token, adminToken.trim(), { limit: 30 })
        setFeedbackItems(Array.isArray(feedbackData.items) ? feedbackData.items : [])
      } catch {
        setFeedbackItems([])
      }
    } catch (err) {
      setIsVerified(false)
      addToast(err.message || tx('verifyFailed'), 'error')
    } finally {
      setLoading(false)
    }
  }

  async function loadUsers({ resetOffset = false } = {}) {
    if (!canQuery) return

    const nextOffset = resetOffset ? 0 : offset
    setLoading(true)
    try {
      const data = await billingAdminListUsers(token, adminToken.trim(), {
        limit,
        offset: nextOffset,
        email: emailFilter,
        plan_type: planFilter,
      })
      setUsers(Array.isArray(data.items) ? data.items : [])
      setTotal(Number(data.total || 0))
      setOffset(Number(data.offset || 0))
    } catch (err) {
      addToast(err.message || tx('listFailed'), 'error')
    } finally {
      setLoading(false)
    }
  }

  async function submitPlanUpdate(e) {
    e.preventDefault()
    if (!canQuery) {
      addToast(tx('needVerify'), 'error')
      return
    }
    if (!targetEmail.trim() && !targetSupabaseId.trim()) {
      addToast(tx('requireUserId'), 'error')
      return
    }
    if (!targetPlan && !targetStatus && !targetRole) {
      addToast(tx('requireAnyUpdate'), 'error')
      return
    }

    setSaving(true)
    try {
      await billingAdminSetUserPlan(token, adminToken.trim(), {
        email: targetEmail.trim() || null,
        supabase_id: targetSupabaseId.trim() || null,
        plan_type: targetPlan || null,
        billing_status: targetStatus || null,
        role: targetRole || null,
        update_organization: updateOrganization,
      })
      addToast(tx('updateOk'), 'success')
      await loadUsers()
    } catch (err) {
      addToast(err.message || tx('updateFail'), 'error')
    } finally {
      setSaving(false)
    }
  }

  const hasPrev = offset > 0
  const hasNext = offset + limit < total

  const fadeUp = {
    hidden: { opacity: 0, y: 20 },
    visible: (i = 0) => ({ opacity: 1, y: 0, transition: { delay: i * 0.08, duration: 0.45, ease: [0.25, 0.1, 0.25, 1] } }),
  }

  const planBadge = (plan) => {
    const colors = { free: 'var(--color-text-muted)', pro: 'var(--color-accent)', enterprise: 'var(--color-success)' }
    return <span className="admin-plan-badge" style={{ '--badge-color': colors[plan] || 'var(--color-text-muted)' }}>{plan}</span>
  }

  const statusBadge = (status) => {
    const colors = { active: 'var(--color-success)', trialing: 'var(--color-warning)', past_due: 'var(--color-danger)', canceled: 'var(--color-text-muted)' }
    return <span className="admin-status-badge" style={{ '--badge-color': colors[status] || 'var(--color-text-muted)' }}>{status}</span>
  }

  return (
    <div className="app-layout">
      <Navbar />
      <main className="main-content" id="main-content">

        {/* ── Page Header ─────────────────────── */}
        <motion.div
          className="admin-page-header"
          initial={{ opacity: 0, y: -16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <div className="admin-header-icon-wrap">
            <Shield size={28} />
          </div>
          <div>
            <h1 className="admin-page-title">{tx('title')}</h1>
            <p className="admin-page-subtitle">{tx('subtitle')}</p>
          </div>
        </motion.div>

        {/* ── Verify Card ─────────────────────── */}
        <motion.div
          className="admin-card admin-verify-card"
          variants={fadeUp}
          initial="hidden"
          animate="visible"
          custom={0}
        >
          <div className="admin-card-header">
            <KeyRound size={18} className="admin-card-icon" />
            <h2>{tx('verifyTitle')}</h2>
            {isVerified && (
              <motion.span
                className="admin-verified-badge"
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: 'spring', stiffness: 400, damping: 15 }}
              >
                <CheckCircle2 size={14} /> Verified
              </motion.span>
            )}
          </div>
          <div className="admin-verify-row">
            <div className="admin-input-group">
              <label>{tx('tokenLabel')}</label>
              <input
                type="password"
                value={adminToken}
                onChange={(e) => {
                  setAdminToken(e.target.value)
                  setIsVerified(false)
                }}
                placeholder={tx('tokenPlaceholder')}
                className="admin-input"
              />
            </div>
            <motion.button
              className="btn-primary admin-verify-btn"
              type="button"
              onClick={verifyAccess}
              disabled={loading}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              {loading ? <Loader2 size={16} className="spin-icon" /> : <KeyRound size={16} />}
              {loading ? tx('verifyingBtn') : tx('verifyBtn')}
            </motion.button>
          </div>
          <p className="admin-signed-in">
            {tx('signedInUser')}: <strong>{user?.email || '-'}</strong>
          </p>
        </motion.div>

        <AnimatePresence>
          {isVerified && (
            <>
              {/* ── Update User Card ─────────────── */}
              <motion.div
                className="admin-card"
                variants={fadeUp}
                initial="hidden"
                animate="visible"
                exit={{ opacity: 0, y: -10 }}
                custom={1}
              >
                <div className="admin-card-header">
                  <UserCog size={18} className="admin-card-icon" />
                  <h2>{tx('updateTitle')}</h2>
                </div>
                <form onSubmit={submitPlanUpdate} className="admin-update-form">
                  <div className="admin-form-grid">
                    <div className="admin-input-group">
                      <label>{tx('emailLabel')}</label>
                      <input value={targetEmail} onChange={(e) => setTargetEmail(e.target.value)} placeholder="user@example.com" className="admin-input" />
                    </div>
                    <div className="admin-input-group">
                      <label>{tx('supabaseLabel')}</label>
                      <input value={targetSupabaseId} onChange={(e) => setTargetSupabaseId(e.target.value)} placeholder="uuid" className="admin-input" />
                    </div>
                    <div className="admin-input-group">
                      <label>{tx('planLabel')}</label>
                      <select value={targetPlan} onChange={(e) => setTargetPlan(e.target.value)} className="admin-select">
                        <option value="">{tx('noChange')}</option>
                        <option value="free">free</option>
                        <option value="pro">pro</option>
                        <option value="enterprise">enterprise</option>
                      </select>
                    </div>
                    <div className="admin-input-group">
                      <label>{tx('billingLabel')}</label>
                      <select value={targetStatus} onChange={(e) => setTargetStatus(e.target.value)} className="admin-select">
                        <option value="">{tx('noChange')}</option>
                        <option value="active">active</option>
                        <option value="trialing">trialing</option>
                        <option value="past_due">past_due</option>
                        <option value="canceled">canceled</option>
                      </select>
                    </div>
                    <div className="admin-input-group">
                      <label>{tx('roleLabel')}</label>
                      <select value={targetRole} onChange={(e) => setTargetRole(e.target.value)} className="admin-select">
                        <option value="">{tx('noChange')}</option>
                        <option value="individual">individual</option>
                        <option value="recruiter">recruiter</option>
                        <option value="admin">admin</option>
                      </select>
                    </div>
                  </div>
                  <label className="admin-checkbox-label">
                    <input type="checkbox" checked={updateOrganization} onChange={(e) => setUpdateOrganization(e.target.checked)} />
                    {tx('updateOrg')}
                  </label>
                  <div className="admin-form-actions">
                    <motion.button
                      className="btn-primary"
                      disabled={saving || !canQuery}
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                    >
                      {saving ? <Loader2 size={16} className="spin-icon" /> : <Save size={16} />}
                      {saving ? tx('savingBtn') : tx('saveBtn')}
                    </motion.button>
                  </div>
                </form>
              </motion.div>

              {/* ── User List Card ─────────────────── */}
              <motion.div
                className="admin-card"
                variants={fadeUp}
                initial="hidden"
                animate="visible"
                exit={{ opacity: 0, y: -10 }}
                custom={2}
              >
                <div className="admin-card-header">
                  <Users size={18} className="admin-card-icon" />
                  <h2>{tx('listTitle')}</h2>
                  <span className="admin-count-badge">{total}</span>
                </div>
                <div className="admin-filter-bar">
                  <div className="admin-input-group admin-filter-field">
                    <label><Search size={12} /> Email</label>
                    <input value={emailFilter} onChange={(e) => setEmailFilter(e.target.value)} placeholder="parca email" className="admin-input" />
                  </div>
                  <div className="admin-input-group admin-filter-field">
                    <label>Plan</label>
                    <select value={planFilter} onChange={(e) => setPlanFilter(e.target.value)} className="admin-select">
                      <option value="">all</option>
                      <option value="free">free</option>
                      <option value="pro">pro</option>
                      <option value="enterprise">enterprise</option>
                    </select>
                  </div>
                  <div className="admin-input-group admin-filter-field">
                    <label>Limit</label>
                    <select value={limit} onChange={(e) => setLimit(Number(e.target.value))} className="admin-select">
                      <option value={25}>25</option>
                      <option value={50}>50</option>
                      <option value={100}>100</option>
                    </select>
                  </div>
                  <motion.button
                    className="btn-primary admin-filter-btn"
                    type="button"
                    onClick={() => loadUsers({ resetOffset: true })}
                    disabled={!canQuery || loading}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                  >
                    {loading ? <Loader2 size={14} className="spin-icon" /> : <Search size={14} />}
                    {loading ? tx('loadingBtn') : tx('listBtn')}
                  </motion.button>
                </div>

                <div className="admin-table-wrapper">
                  <table className="data-table data-table-elite admin-table">
                    <thead>
                      <tr>
                        <th>Email</th>
                        <th>Supabase ID</th>
                        <th>Plan</th>
                        <th>Status</th>
                        <th>Role</th>
                      </tr>
                    </thead>
                    <tbody>
                      <AnimatePresence mode="popLayout">
                        {users.map((row, idx) => (
                          <motion.tr
                            key={row.id || row.supabase_id || idx}
                            initial={{ opacity: 0, x: -8 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: 8 }}
                            transition={{ delay: idx * 0.03, duration: 0.25 }}
                          >
                            <td className="admin-email-cell">{row.email}</td>
                            <td className="admin-uuid-cell">{row.supabase_id}</td>
                            <td>{planBadge(row.plan_type)}</td>
                            <td>{statusBadge(row.billing_status)}</td>
                            <td><span className="admin-role-text">{row.role}</span></td>
                          </motion.tr>
                        ))}
                      </AnimatePresence>
                      {users.length === 0 && (
                        <tr><td colSpan={5} className="admin-empty-cell">{tx('noRecords')}</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>

                <div className="admin-pagination">
                  <span className="text-muted">{tx('total')}: <strong>{total}</strong></span>
                  <div className="admin-pagination-btns">
                    <motion.button
                      className="btn-outline btn-sm"
                      type="button"
                      disabled={!hasPrev || !canQuery || loading}
                      whileHover={{ x: -2 }}
                      whileTap={{ scale: 0.95 }}
                      onClick={() => {
                        const next = Math.max(0, offset - limit)
                        setOffset(next)
                        billingAdminListUsers(token, adminToken.trim(), { limit, offset: next, email: emailFilter, plan_type: planFilter })
                          .then((data) => { setUsers(Array.isArray(data.items) ? data.items : []); setTotal(Number(data.total || 0)); setOffset(Number(data.offset || 0)) })
                          .catch((err) => addToast(err.message || tx('pageFail'), 'error'))
                      }}
                    >
                      <ChevronLeft size={14} /> {tx('prev')}
                    </motion.button>
                    <span className="admin-page-indicator">
                      {Math.floor(offset / limit) + 1} / {Math.max(1, Math.ceil(total / limit))}
                    </span>
                    <motion.button
                      className="btn-outline btn-sm"
                      type="button"
                      disabled={!hasNext || !canQuery || loading}
                      whileHover={{ x: 2 }}
                      whileTap={{ scale: 0.95 }}
                      onClick={() => {
                        const next = offset + limit
                        setOffset(next)
                        billingAdminListUsers(token, adminToken.trim(), { limit, offset: next, email: emailFilter, plan_type: planFilter })
                          .then((data) => { setUsers(Array.isArray(data.items) ? data.items : []); setTotal(Number(data.total || 0)); setOffset(Number(data.offset || 0)) })
                          .catch((err) => addToast(err.message || tx('pageFail'), 'error'))
                      }}
                    >
                      {tx('next')} <ChevronRight size={14} />
                    </motion.button>
                  </div>
                </div>
              </motion.div>

              {/* ── Feedback Card ──────────────────── */}
              <motion.div
                className="admin-card"
                variants={fadeUp}
                initial="hidden"
                animate="visible"
                exit={{ opacity: 0, y: -10 }}
                custom={3}
              >
                <div className="admin-card-header">
                  <MessageSquareWarning size={18} className="admin-card-icon" />
                  <h2>{tx('feedbackTitle')}</h2>
                  <motion.button
                    className="btn-outline btn-sm admin-refresh-btn"
                    type="button"
                    disabled={!canQuery || loading}
                    whileHover={{ rotate: 90 }}
                    whileTap={{ scale: 0.9 }}
                    onClick={async () => {
                      try {
                        const feedbackData = await billingAdminListFeedback(token, adminToken.trim(), { limit: 30 })
                        setFeedbackItems(Array.isArray(feedbackData.items) ? feedbackData.items : [])
                      } catch (err) {
                        addToast(err.message || tx('feedbackFailed'), 'error')
                      }
                    }}
                  >
                    <RefreshCw size={14} />
                  </motion.button>
                </div>

                <div className="admin-table-wrapper">
                  <table className="data-table data-table-elite admin-table">
                    <thead>
                      <tr>
                        <th>{tx('thDate')}</th>
                        <th>{tx('thCategory')}</th>
                        <th>{tx('thSender')}</th>
                        <th>{tx('thMessage')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <AnimatePresence mode="popLayout">
                        {feedbackItems.map((item, idx) => (
                          <motion.tr
                            key={`${item.timestamp || 'na'}-${idx}`}
                            initial={{ opacity: 0, x: -8 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: idx * 0.03, duration: 0.25 }}
                          >
                            <td className="admin-date-cell">{item.timestamp || '-'}</td>
                            <td><span className="admin-category-badge">{item.category || '-'}</span></td>
                            <td>{item.submitter || '-'}</td>
                            <td className="admin-message-cell">{item.message || '-'}</td>
                          </motion.tr>
                        ))}
                      </AnimatePresence>
                      {feedbackItems.length === 0 && (
                        <tr><td colSpan={4} className="admin-empty-cell">{tx('noFeedback')}</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </motion.div>
            </>
          )}
        </AnimatePresence>
      </main>
    </div>
  )
}
