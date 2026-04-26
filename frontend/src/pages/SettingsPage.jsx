import React, { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { useTheme } from '../context/ThemeContext'
import { useToast } from '../components/Toast'
import { Link, useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'

export default function SettingsPage() {
  const { user, plan, planLoading, updatePassword, deleteUser } = useAuth()
  const { t, lang, setLang } = useLanguage()
  const { theme, setTheme } = useTheme()
  const { addToast } = useToast()
  const navigate = useNavigate()

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passError, setPassError] = useState(null)
  const [passLoading, setPassLoading] = useState(false)
  const [deleteLoading, setDeleteLoading] = useState(false)

  const billingAdminEmails = String(import.meta.env.VITE_BILLING_ADMIN_EMAILS || '')
    .split(',')
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean)
  const isBillingAdmin = !!user?.email && billingAdminEmails.includes(String(user.email).toLowerCase())

  useEffect(() => {
    document.title = `${t('nav.settings')} — CV Analyzer`
  }, [t])

  async function handlePasswordChange(e) {
    e.preventDefault()
    setPassError(null)
    if (newPassword !== confirmPassword) {
      setPassError(t('auth.passwords_no_match'))
      return
    }
    try {
      setPassLoading(true)
      await updatePassword(newPassword)
      addToast(t('settings.password_updated'), 'success')
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (err) {
      setPassError(err.message)
    } finally {
      setPassLoading(false)
    }
  }

  async function handleDeleteAccount() {
    if (!window.confirm(t('settings.delete_account_desc'))) return
    try {
      setDeleteLoading(true)
      await deleteUser()
      addToast(t('toast.account_deleted'), 'success')
      navigate('/')
    } catch (err) {
      addToast(err.message, 'error')
    } finally {
      setDeleteLoading(false)
    }
  }

  const planFeatures = {
    free: [t('pricing.free_f1'), t('pricing.free_f2'), t('pricing.free_f3'), t('pricing.free_f4')],
    pro: [t('pricing.pro_f1'), t('pricing.pro_f2'), t('pricing.pro_f3'), t('pricing.pro_f4'), t('pricing.pro_f5')],
    admin: [
      t('pricing.pro_f1'),
      t('pricing.pro_f2'),
      t('pricing.pro_f3'),
      t('pricing.pro_f4'),
      t('pricing.pro_f5'),
    ],
  }

  const effectivePlan = isBillingAdmin ? 'admin' : plan
  const planLabel =
    effectivePlan === 'admin'
      ? 'Admin'
      : effectivePlan === 'free'
      ? t('dashboard.free_plan')
      : t('dashboard.pro_plan')

  return (
    <div className="app-layout">
      <Navbar />
      <main className="main-content" id="main-content">
        <h1>{t('settings.title')}</h1>

        <div className="settings-grid">
          {/* Profile */}
          <div className="card">
            <h2>{t('settings.profile')}</h2>
            <p className="text-muted">{t('settings.profile_subtitle')}</p>
            <div className="settings-field">
              <label>{t('settings.email')}</label>
              <input type="email" value={user?.email || ''} disabled className="input-disabled" />
            </div>
          </div>

          {/* Change Password */}
          <div className="card">
            <h2>{t('settings.change_password')}</h2>
            <form onSubmit={handlePasswordChange}>
              <div className="settings-field">
                <label>{t('settings.new_password')}</label>
                <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required minLength={6} autoComplete="new-password" />
              </div>
              <div className="settings-field">
                <label>{t('settings.confirm_password')}</label>
                <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required minLength={6} autoComplete="new-password" />
              </div>
              {passError && <p className="error">{passError}</p>}
              <button type="submit" className="btn-primary" disabled={passLoading}>
                {passLoading ? t('common.loading') : t('settings.update_password')}
              </button>
            </form>
          </div>

          {/* Preferences */}
          <div className="card">
            <h2>{t('settings.preferences')}</h2>
            <div className="settings-field">
              <label>{t('settings.language')}</label>
              <div className="radio-group">
                <label className={`radio-option ${lang === 'en' ? 'active' : ''}`}>
                  <input type="radio" name="lang" value="en" checked={lang === 'en'} onChange={() => setLang('en')} />
                  🇬🇧 English
                </label>
                <label className={`radio-option ${lang === 'tr' ? 'active' : ''}`}>
                  <input type="radio" name="lang" value="tr" checked={lang === 'tr'} onChange={() => setLang('tr')} />
                  🇹🇷 Türkçe
                </label>
              </div>
            </div>
            <div className="settings-field">
              <label>{t('settings.theme')}</label>
              <div className="radio-group">
                <label className={`radio-option ${theme === 'dark' ? 'active' : ''}`}>
                  <input type="radio" name="theme" value="dark" checked={theme === 'dark'} onChange={() => setTheme('dark')} />
                  🌙 {t('settings.dark_mode')}
                </label>
                <label className={`radio-option ${theme === 'light' ? 'active' : ''}`}>
                  <input type="radio" name="theme" value="light" checked={theme === 'light'} onChange={() => setTheme('light')} />
                  ☀️ {t('settings.light_mode')}
                </label>
              </div>
            </div>
          </div>

          {/* Plan */}
          <div className="card">
            <h2>{t('settings.plan_management')}</h2>
            <div className="plan-badge-row">
              <span className="plan-badge">{planLoading ? '...' : planLabel}</span>
              {!planLoading && effectivePlan === 'free' && <Link to="/pricing" className="btn-primary btn-sm">{t('settings.change_plan')}</Link>}
            </div>
            <h4>{t('settings.plan_features')}</h4>
            <ul className="plan-features-list">
              {((planLoading ? planFeatures.free : (planFeatures[effectivePlan] || planFeatures.free))).map((f, i) => (
                <li key={i}>✓ {f}</li>
              ))}
            </ul>
          </div>

          {/* Danger Zone */}
          <div className="card card-danger">
            <h2>{t('settings.danger_zone')}</h2>
            <p className="text-muted">{t('settings.delete_account_desc')}</p>
            <button className="btn-danger" onClick={handleDeleteAccount} disabled={deleteLoading}>
              {deleteLoading ? t('common.loading') : t('settings.delete_account')}
            </button>
          </div>

        </div>
      </main>
    </div>
  )
}
