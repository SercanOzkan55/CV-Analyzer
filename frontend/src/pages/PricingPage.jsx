import React, { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'

export default function PricingPage() {
  const { t } = useLanguage()
  const { user } = useAuth()

  useEffect(() => {
    document.title = `${t('nav.pricing')} — CV Analyzer`
  }, [t])

  const features = [
    t('pricing.f1'),
    t('pricing.f2'),
    t('pricing.f3'),
    t('pricing.f4'),
    t('pricing.f5'),
  ]

  return (
    <div className="app-layout">
      <Navbar />
      <main className="main-content" id="main-content">
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
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
          style={{ gridTemplateColumns: 'minmax(0, 480px)', justifyContent: 'center' }}
        >
          <div className="pricing-card popular">
            <h3>{t('pricing.free_name')}</h3>
            <div className="pricing-price">
              {t('pricing.zero_price')}<span>/{t('pricing.forever')}</span>
            </div>
            <ul>
              {features.map((f, i) => <li key={i}>{f}</li>)}
            </ul>
            {user ? (
              <Link to="/dashboard" className="btn-primary btn-full">{t('pricing.go_to_dashboard')}</Link>
            ) : (
              <Link to="/register" className="btn-primary btn-full">{t('pricing.free_cta')}</Link>
            )}
          </div>
        </motion.div>

        <motion.div
          className="card"
          style={{ marginTop: 32, textAlign: 'center' }}
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.4, delay: 0.15 }}
        >
          <h2>{t('pricing.local_worker_title')}</h2>
          <p className="text-muted">{t('pricing.local_worker_desc')}</p>
          <Link to="/recruiter" className="btn-outline">{t('pricing.local_worker_cta')}</Link>
        </motion.div>
      </main>
      {!user && <Footer />}
    </div>
  )
}
