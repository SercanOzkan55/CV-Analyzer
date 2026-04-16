import React, { useState, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import { useToast } from '../components/Toast'
import {
  createCheckoutSession,
  createBillingPortalSession,
  createContactSalesRequest,
} from '../api'

const PLAN_ANALYTICS_META = {
  free: { billing_period: 'monthly', price: 0, currency: 'USD' },
  pro: { billing_period: 'monthly', price: 19, currency: 'USD' },
  enterprise: { billing_period: 'custom', price: null, currency: 'USD' },
}

export default function PricingPage() {
  const { t } = useLanguage()
  const { user, token, plan, refreshUsage } = useAuth()
  const location = useLocation()
  const { addToast } = useToast()
  const [busyKey, setBusyKey] = useState('')

  useEffect(() => {
    document.title = `${t('nav.pricing')} — CV Analyzer`
  }, [t])
  const publicContactSalesHref =
    import.meta.env.VITE_CONTACT_SALES_URL ||
    'mailto:sales@cvanalyzer.local?subject=Enterprise%20plan%20inquiry'

  async function onUpgrade(targetPlan) {
    if (!user || !token) return
    try {
      setBusyKey(`upgrade-${targetPlan}`)
      const planMeta = PLAN_ANALYTICS_META[targetPlan] || PLAN_ANALYTICS_META.pro
      const session = await createCheckoutSession(token, {
        plan_type: targetPlan,
        billing_period: planMeta.billing_period,
        price: planMeta.price,
        currency: planMeta.currency,
        source: 'web_pricing_page',
      })

      if (session?.mode === 'mock') {
        await refreshUsage(token)
        addToast(t('toast.premium_trial_activated'), 'success')
        return
      }

      if (session?.url) {
        window.location.assign(session.url)
        return
      }
      addToast(t('toast.billing_unavailable'), 'error')
    } catch {
      addToast(t('toast.billing_unavailable'), 'error')
    } finally {
      setBusyKey('')
    }
  }

  async function onManageBilling() {
    if (!user || !token) return
    try {
      setBusyKey('manage-billing')
      const session = await createBillingPortalSession(token, {
        return_url: `${window.location.origin}/dashboard`,
      })
      if (session?.mode === 'mock') {
        return
      }
      if (session?.url) {
        window.location.assign(session.url)
        return
      }
      addToast(t('toast.billing_unavailable'), 'error')
    } catch {
      addToast(t('toast.billing_unavailable'), 'error')
    } finally {
      setBusyKey('')
    }
  }

  async function onContactSales() {
    if (!user || !token) {
      window.location.assign(publicContactSalesHref)
      return
    }
    try {
      setBusyKey('contact-sales')
      const result = await createContactSalesRequest(token, {
        plan_type: 'enterprise',
        source: 'web_pricing_page',
      })
      if (result?.contact_url) {
        window.location.assign(result.contact_url)
        return
      }
      addToast(t('toast.contact_sales_received'), 'success')
    } catch {
      addToast(t('toast.billing_unavailable'), 'error')
    } finally {
      setBusyKey('')
    }
  }

  const plans = [
    {
      key: 'free',
      name: t('pricing.free_name'),
      price: t('pricing.free_price'),
      period: t('pricing.free_period'),
      features: [t('pricing.free_f1'), t('pricing.free_f2'), t('pricing.free_f3'), t('pricing.free_f4')],
      cta: t('pricing.free_cta'),
      popular: false,
    },
    {
      key: 'pro',
      name: t('pricing.pro_name'),
      price: t('pricing.pro_price'),
      period: t('pricing.pro_period'),
      features: [t('pricing.pro_f1'), t('pricing.pro_f2'), t('pricing.pro_f3'), t('pricing.pro_f4'), t('pricing.pro_f5')],
      cta: t('pricing.pro_cta'),
      popular: true,
    },
    {
      key: 'enterprise',
      name: t('pricing.enterprise_name'),
      price: t('pricing.enterprise_price'),
      period: t('pricing.enterprise_period'),
      features: [t('pricing.enterprise_f1'), t('pricing.enterprise_f2'), t('pricing.enterprise_f3'), t('pricing.enterprise_f4'), t('pricing.enterprise_f5')],
      cta: t('pricing.enterprise_cta'),
      popular: false,
    },
  ]

  return (
    <div className="app-layout">
      <Navbar />
      <main className="main-content" id="main-content">
        {location?.state?.reason === 'recruiter_required' && (
          <div className="card" style={{ marginBottom: 16, borderColor: '#f59e0b' }}>
            <h3>{t('recruiter.role_required')}</h3>
            <p className="text-muted">{t('recruiter.role_required_desc')}</p>
          </div>
        )}
        <div className="pricing-page-header">
          <h1>{t('pricing.title')}</h1>
          <p className="text-muted">{t('pricing.subtitle')}</p>
        </div>

        <div className="pricing-grid">
          {plans.map((p) => (
            <div key={p.key} className={`pricing-card ${p.popular ? 'popular' : ''}`}>
              {p.popular && <div className="popular-badge">{t('pricing.popular')}</div>}
              <h3>{p.name}</h3>
              <div className="pricing-price">
                {p.price}<span>/{p.period}</span>
              </div>
              <ul>
                {p.features.map((f, i) => <li key={i}>{f}</li>)}
              </ul>
              {plan === p.key ? (
                <button className="btn-outline btn-full" disabled>{t('pricing.current_plan')}</button>
              ) : p.key === 'enterprise' ? (
                <button
                  type="button"
                  className="btn-outline btn-full"
                  onClick={onContactSales}
                  disabled={busyKey.length > 0}
                >
                  {busyKey === 'contact-sales' ? t('pricing.redirecting') : p.cta}
                </button>
              ) : user ? (
                <button
                  type="button"
                  className={`${p.popular ? 'btn-primary' : 'btn-outline'} btn-full`}
                  onClick={() => onUpgrade(p.key)}
                  disabled={busyKey.length > 0}
                >
                  {busyKey === `upgrade-${p.key}` ? t('pricing.redirecting') : p.cta}
                </button>
              ) : (
                <Link to={user ? '#' : '/register'} className={`${p.popular ? 'btn-primary' : 'btn-outline'} btn-full`}>
                  {p.cta}
                </Link>
              )}
            </div>
          ))}
        </div>

        {user && (
          <div className="card" style={{ marginTop: 24 }}>
            <div className="card-header">
              <h2>{t('pricing.billing_title')}</h2>
            </div>
            <p className="text-muted" style={{ marginBottom: 12 }}>{t('pricing.billing_subtitle')}</p>
            <button
              type="button"
              className="btn-outline"
              onClick={onManageBilling}
              disabled={busyKey.length > 0}
            >
              {busyKey === 'manage-billing' ? t('pricing.redirecting') : t('pricing.manage_billing')}
            </button>
          </div>
        )}
      </main>
      {!user && <Footer />}
    </div>
  )
}
