import React, { useState, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
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
  const { t, countryCode, pricing } = useLanguage()
  const { user, token, plan, refreshUsage } = useAuth()
  const location = useLocation()
  const { addToast } = useToast()
  const [busyKey, setBusyKey] = useState('')

  useEffect(() => {
    document.title = `${t('nav.pricing')} — CV Analyzer`
  }, [t])

  const publicContactSalesHref =
    import.meta.env.VITE_CONTACT_SALES_URL ||
    'mailto:sales@cvanalyzer.dev?subject=Enterprise%20plan%20inquiry'

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
      price: pricing.free,
      period: t(pricing.periodKey),
      features: [t('pricing.free_f1'), t('pricing.free_f2'), t('pricing.free_f3'), t('pricing.free_f4')],
      cta: t('pricing.free_cta'),
      popular: false,
    },
    {
      key: 'pro',
      name: t('pricing.pro_name'),
      price: pricing.pro,
      period: t(pricing.periodKey),
      features: [t('pricing.pro_f1'), t('pricing.pro_f2'), t('pricing.pro_f3'), t('pricing.pro_f4'), t('pricing.pro_f5')],
      cta: t('pricing.pro_cta'),
      popular: true,
    },
    {
      key: 'enterprise',
      name: t('pricing.enterprise_name'),
      price: pricing.enterprise,
      period: t(pricing.periodKey),
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

        {/* [CORPORATE DETECTION BANNER] */}
        {user?.email && !['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'icloud.com'].some(d => user.email.endsWith(d)) && (
          <motion.div 
            className="corporate-perk-banner"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            style={{
              background: 'var(--bg-card)',
              padding: '24px',
              borderRadius: 'var(--radius-lg)',
              marginBottom: '32px',
              border: '1px solid var(--color-border)',
              display: 'flex',
              alignItems: 'center',
              gap: '20px',
              boxShadow: 'var(--shadow-md)'
            }}
          >
            <div style={{ fontSize: '32px' }}>🏢</div>
            <div>
              <h4 style={{ margin: 0, color: 'var(--color-text)', fontSize: '1.1rem' }}>{t('pricing.corporate_detected_title') || 'Şirket Hesabı Tespit Edildi'}</h4>
              <p style={{ margin: '6px 0 0 0', color: 'var(--color-text-secondary)', fontSize: '14.5px' }}>
                {t('pricing.corporate_detected_desc') || 'Kurumsal domain kullandığınız için Enterprise paketine özel %20 indirim ve ücretsiz toplu CV sıralama denemesi kazandınız.'}
              </p>
            </div>
            <button className="btn-primary" style={{ marginLeft: 'auto' }} onClick={onContactSales}>
              {t('pricing.claim_offer') || 'Teklifi Al'}
            </button>
          </motion.div>
        )}

        <motion.div
          className="pricing-page-header"
          initial={{ opacity: 0, y: -16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <h1>{t('pricing.title')}</h1>
          <p className="text-muted">{t('pricing.subtitle')}</p>
        </motion.div>

        <motion.div
          className="pricing-grid"
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, amount: 0.2 }}
          variants={{ hidden: {}, show: { transition: { staggerChildren: 0.12 } } }}
        >
          {plans.map((p) => (
            <motion.div
              key={p.key}
              className={`pricing-card ${p.popular ? 'popular' : ''}`}
              variants={p.popular
                ? { hidden: { opacity: 0, scale: 0.92 }, show: { opacity: 1, scale: 1 } }
                : { hidden: { opacity: 0, y: 24 }, show: { opacity: 1, y: 0 } }
              }
              whileHover={{ y: p.popular ? -8 : -6, transition: { duration: 0.2 } }}
            >
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
            </motion.div>
          ))}
        </motion.div>
        
        {/* [NON-CORPORATE HINT] */}
        {user?.email && ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'icloud.com'].some(d => user.email.endsWith(d)) && (
          <motion.div 
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            style={{ 
              textAlign: 'center', 
              marginTop: '24px', 
              padding: '16px',
              background: 'rgba(255,255,255,0.03)',
              borderRadius: '12px',
              border: '1px dashed rgba(255,255,255,0.1)',
              fontSize: '14px',
              color: '#94a3b8'
            }}
          >
            <div style={{ marginBottom: '8px' }}>
              <span style={{ color: '#f59e0b', marginRight: '8px' }}>💡</span>
              {t('pricing.corporate_discount_info') || 'Kurumsal mail adresi (@şirketiniz.com) ile doğrulama yaparak Enterprise paketinde anında indirim alabilirsiniz.'}
            </div>
            <Link 
              to="/settings"
              style={{ 
                color: 'var(--color-accent)', 
                textDecoration: 'none', 
                fontWeight: '600',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px'
              }}
            >
              {t('pricing.update_email_for_discount') || 'E-postanı Güncelle ve İndirim Kazan'} →
            </Link>
          </motion.div>
        )}

        {/* [ENTERPRISE INFO SECTION] */}
        <motion.div 
          className="enterprise-info-section"
          initial={{ opacity: 0, y: 32 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          style={{ marginTop: '80px' }}
        >
          <div style={{ textAlign: 'center', marginBottom: '48px' }}>
            <h2 style={{ fontSize: '32px', marginBottom: '16px' }}>{t('pricing.enterprise_capabilities_title') || 'Kurumsal Çözümlerimiz'}</h2>
            <p className="text-muted">{t('pricing.enterprise_capabilities_subtitle') || 'Büyük ölçekli işe alım süreçleriniz için tam entegre, güvenli ve güçlü altyapı.'}</p>
          </div>

          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', 
            gap: '24px' 
          }}>
            <div className="card" style={{ padding: '24px' }}>
              <div style={{ fontSize: '32px', marginBottom: '16px' }}>🚀</div>
              <h4>{t('pricing.bulk_processing') || 'Toplu CV İşleme'}</h4>
              <p className="text-muted" style={{ fontSize: '14px' }}>Binlerce CV'yi saniyeler içinde analiz edin ve en iyi adayları otomatik sıralayın.</p>
            </div>
            <div className="card" style={{ padding: '24px' }}>
              <div style={{ fontSize: '32px', marginBottom: '16px' }}>🔐</div>
              <h4>{t('pricing.data_privacy') || 'Veri Gizliliği & On-Premise'}</h4>
              <p className="text-muted" style={{ fontSize: '14px' }}>Verilerinizi kendi sunucularınızda saklayın. KVKK ve GDPR uyumlu kurumsal güvenlik.</p>
            </div>
            <div className="card" style={{ padding: '24px' }}>
              <div style={{ fontSize: '32px', marginBottom: '16px' }}>🔗</div>
              <h4>{t('pricing.api_access') || 'Tam API Erişimi'}</h4>
              <p className="text-muted" style={{ fontSize: '14px' }}>Mevcut ATS ve İK yazılımlarınıza CV Analyzer gücünü entegre edin.</p>
            </div>
            <div className="card" style={{ padding: '24px' }}>
              <div style={{ fontSize: '32px', marginBottom: '16px' }}>🎧</div>
              <h4>{t('pricing.dedicated_support') || 'Özel Danışmanlık'}</h4>
              <p className="text-muted" style={{ fontSize: '14px' }}>Size özel atanan müşteri başarı yöneticisi ve teknik destek ekibi.</p>
            </div>
          </div>
        </motion.div>

        {user && (
          <motion.div
            className="card"
            style={{ marginTop: 24 }}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, delay: 0.1 }}
          >
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
          </motion.div>
        )}
      </main>
      {!user && <Footer />}
    </div>
  )
}
