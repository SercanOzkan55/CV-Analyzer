import React from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'

export default function PricingPage() {
  const { t } = useLanguage()
  const { user, plan } = useAuth()

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
      <main className="main-content">
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
                <a href="#" className="btn-outline btn-full">{p.cta}</a>
              ) : (
                <Link to={user ? '#' : '/register'} className={`${p.popular ? 'btn-primary' : 'btn-outline'} btn-full`}>
                  {p.cta}
                </Link>
              )}
            </div>
          ))}
        </div>
      </main>
      {!user && <Footer />}
    </div>
  )
}
