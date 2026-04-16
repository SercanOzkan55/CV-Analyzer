import React, { useEffect, useMemo, useState } from 'react'
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
      const stored = localStorage.getItem(ADMIN_TOKEN_STORAGE_KEY) || ''
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
        localStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, adminToken.trim())
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

  return (
    <div className="app-layout">
      <Navbar />
      <main className="main-content" id="main-content">
        <div className="dashboard-header">
          <div>
            <h1>{tx('title')}</h1>
            <p className="text-muted">{tx('subtitle')}</p>
          </div>
        </div>

        <div className="card" style={{ marginBottom: '1rem' }}>
          <h2>{tx('verifyTitle')}</h2>
          <div className="settings-grid" style={{ gridTemplateColumns: '1fr auto' }}>
            <div className="settings-field" style={{ marginBottom: 0 }}>
              <label>{tx('tokenLabel')}</label>
              <input
                type="password"
                value={adminToken}
                onChange={(e) => setAdminToken(e.target.value)}
                placeholder={tx('tokenPlaceholder')}
              />
            </div>
            <button className="btn-primary" type="button" onClick={verifyAccess} disabled={loading}>
              {loading ? tx('verifyingBtn') : tx('verifyBtn')}
            </button>
          </div>
          <p className="text-muted" style={{ marginTop: '0.5rem' }}>
            {tx('signedInUser')}: {user?.email || '-'}
          </p>
        </div>

        <div className="card" style={{ marginBottom: '1rem' }}>
          <h2>{tx('updateTitle')}</h2>
          <form onSubmit={submitPlanUpdate}>
            <div className="settings-grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
              <div className="settings-field">
                <label>{tx('emailLabel')}</label>
                <input value={targetEmail} onChange={(e) => setTargetEmail(e.target.value)} placeholder="user@example.com" />
              </div>
              <div className="settings-field">
                <label>{tx('supabaseLabel')}</label>
                <input value={targetSupabaseId} onChange={(e) => setTargetSupabaseId(e.target.value)} placeholder="uuid" />
              </div>
              <div className="settings-field">
                <label>{tx('planLabel')}</label>
                <select value={targetPlan} onChange={(e) => setTargetPlan(e.target.value)}>
                  <option value="">{tx('noChange')}</option>
                  <option value="free">free</option>
                  <option value="pro">pro</option>
                  <option value="enterprise">enterprise</option>
                </select>
              </div>
              <div className="settings-field">
                <label>{tx('billingLabel')}</label>
                <select value={targetStatus} onChange={(e) => setTargetStatus(e.target.value)}>
                  <option value="">{tx('noChange')}</option>
                  <option value="active">active</option>
                  <option value="trialing">trialing</option>
                  <option value="past_due">past_due</option>
                  <option value="canceled">canceled</option>
                </select>
              </div>
              <div className="settings-field">
                <label>{tx('roleLabel')}</label>
                <select value={targetRole} onChange={(e) => setTargetRole(e.target.value)}>
                  <option value="">{tx('noChange')}</option>
                  <option value="individual">individual</option>
                  <option value="recruiter">recruiter</option>
                  <option value="admin">admin</option>
                </select>
              </div>
            </div>
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8, marginTop: '0.25rem' }}>
              <input type="checkbox" checked={updateOrganization} onChange={(e) => setUpdateOrganization(e.target.checked)} />
              {tx('updateOrg')}
            </label>
            <div style={{ marginTop: '0.75rem' }}>
              <button className="btn-primary" disabled={saving || !canQuery}>
                {saving ? tx('savingBtn') : tx('saveBtn')}
              </button>
            </div>
          </form>
        </div>

        <div className="card">
          <h2>{tx('listTitle')}</h2>
          <div className="settings-grid" style={{ gridTemplateColumns: '1fr 180px 120px auto' }}>
            <div className="settings-field" style={{ marginBottom: 0 }}>
              <label>Email filtre</label>
              <input value={emailFilter} onChange={(e) => setEmailFilter(e.target.value)} placeholder="parca email" />
            </div>
            <div className="settings-field" style={{ marginBottom: 0 }}>
              <label>Plan filtre</label>
              <select value={planFilter} onChange={(e) => setPlanFilter(e.target.value)}>
                <option value="">all</option>
                <option value="free">free</option>
                <option value="pro">pro</option>
                <option value="enterprise">enterprise</option>
              </select>
            </div>
            <div className="settings-field" style={{ marginBottom: 0 }}>
              <label>Limit</label>
              <select value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
                <option value={25}>25</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
            </div>
            <div style={{ alignSelf: 'end' }}>
              <button className="btn-outline" type="button" onClick={() => loadUsers({ resetOffset: true })} disabled={!canQuery || loading}>
                {loading ? tx('loadingBtn') : tx('listBtn')}
              </button>
            </div>
          </div>

          <div style={{ marginTop: '0.75rem', overflowX: 'auto' }}>
            <table className="data-table">
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
                {users.map((row) => (
                  <tr key={row.id || row.supabase_id}>
                    <td>{row.email}</td>
                    <td>{row.supabase_id}</td>
                    <td>{row.plan_type}</td>
                    <td>{row.billing_status}</td>
                    <td>{row.role}</td>
                  </tr>
                ))}
                {users.length === 0 && (
                  <tr>
                    <td colSpan={5}>{tx('noRecords')}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div style={{ marginTop: '0.75rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="text-muted">{tx('total')}: {total}</span>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                className="btn-outline btn-sm"
                type="button"
                disabled={!hasPrev || !canQuery || loading}
                onClick={() => {
                  const next = Math.max(0, offset - limit)
                  setOffset(next)
                  billingAdminListUsers(token, adminToken.trim(), {
                    limit,
                    offset: next,
                    email: emailFilter,
                    plan_type: planFilter,
                  }).then((data) => {
                    setUsers(Array.isArray(data.items) ? data.items : [])
                    setTotal(Number(data.total || 0))
                    setOffset(Number(data.offset || 0))
                  }).catch((err) => addToast(err.message || tx('pageFail'), 'error'))
                }}
              >
                {tx('prev')}
              </button>
              <button
                className="btn-outline btn-sm"
                type="button"
                disabled={!hasNext || !canQuery || loading}
                onClick={() => {
                  const next = offset + limit
                  setOffset(next)
                  billingAdminListUsers(token, adminToken.trim(), {
                    limit,
                    offset: next,
                    email: emailFilter,
                    plan_type: planFilter,
                  }).then((data) => {
                    setUsers(Array.isArray(data.items) ? data.items : [])
                    setTotal(Number(data.total || 0))
                    setOffset(Number(data.offset || 0))
                  }).catch((err) => addToast(err.message || tx('pageFail'), 'error'))
                }}
              >
                {tx('next')}
              </button>
            </div>
          </div>
        </div>

        <div className="card" style={{ marginTop: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
            <h2>{tx('feedbackTitle')}</h2>
            <button
              className="btn-outline btn-sm"
              type="button"
              disabled={!canQuery || loading}
              onClick={async () => {
                try {
                  const feedbackData = await billingAdminListFeedback(token, adminToken.trim(), { limit: 30 })
                  setFeedbackItems(Array.isArray(feedbackData.items) ? feedbackData.items : [])
                } catch (err) {
                  addToast(err.message || tx('feedbackFailed'), 'error')
                }
              }}
            >
              {tx('refresh')}
            </button>
          </div>

          <div style={{ marginTop: '0.75rem', overflowX: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>{tx('thDate')}</th>
                  <th>{tx('thCategory')}</th>
                  <th>{tx('thSender')}</th>
                  <th>{tx('thMessage')}</th>
                </tr>
              </thead>
              <tbody>
                {feedbackItems.map((item, idx) => (
                  <tr key={`${item.timestamp || 'na'}-${idx}`}>
                    <td>{item.timestamp || '-'}</td>
                    <td>{item.category || '-'}</td>
                    <td>{item.submitter || '-'}</td>
                    <td>{item.message || '-'}</td>
                  </tr>
                ))}
                {feedbackItems.length === 0 && (
                  <tr>
                    <td colSpan={4}>{tx('noFeedback')}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  )
}
