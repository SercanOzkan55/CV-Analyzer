import React, { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useLanguage } from '../i18n/LanguageContext'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import AnimatedBackground from '../components/AnimatedBackground'

export default function LandingPage() {
  const { t } = useLanguage()

  useEffect(() => {
    document.title = 'CV Analyzer — AI-Powered CV Analysis'
    return () => { document.title = 'CV Analyzer' }
  }, [])

  const features = [
    { icon: '🤖', title: t('landing.feature_ai_title'), desc: t('landing.feature_ai_desc') },
    { icon: '📋', title: t('landing.feature_ats_title'), desc: t('landing.feature_ats_desc') },
    { icon: '🎯', title: t('landing.feature_skills_title'), desc: t('landing.feature_skills_desc') },
    { icon: '🌍', title: t('landing.feature_multi_title'), desc: t('landing.feature_multi_desc') },
    { icon: '📊', title: t('landing.feature_history_title'), desc: t('landing.feature_history_desc') },
    { icon: '👔', title: t('landing.feature_recruiter_title'), desc: t('landing.feature_recruiter_desc') },
  ]

  const steps = [
    { num: '01', title: t('landing.how_step1_title'), desc: t('landing.how_step1_desc'), icon: '📤' },
    { num: '02', title: t('landing.how_step2_title'), desc: t('landing.how_step2_desc'), icon: '📝' },
    { num: '03', title: t('landing.how_step3_title'), desc: t('landing.how_step3_desc'), icon: '✅' },
  ]

  const faqs = [
    { q: t('landing.faq1_q'), a: t('landing.faq1_a') },
    { q: t('landing.faq2_q'), a: t('landing.faq2_a') },
    { q: t('landing.faq3_q'), a: t('landing.faq3_a') },
    { q: t('landing.faq4_q'), a: t('landing.faq4_a') },
    { q: t('landing.faq5_q'), a: t('landing.faq5_a') },
  ]

  return (
    <div className="landing">
      <AnimatedBackground />
      <Navbar />

      {/* Hero */}
      <section className="hero" id="main-content">
        <div className="hero-badge">AI-Powered Resume Analysis</div>
        <h1>{t('landing.hero_title')}</h1>
        <p className="hero-subtitle">{t('landing.hero_subtitle')}</p>
        <div className="hero-actions">
          <Link to="/register" className="btn-primary btn-lg">{t('landing.try_now')}</Link>
          <a href="#pricing" className="btn-ghost btn-lg">{t('landing.view_pricing')}</a>
        </div>
        <p className="hero-note">{t('landing.trusted_by')}</p>

        {/* Stats Row */}
        <div className="hero-stats">
          <div className="hero-stat">
            <span className="hero-stat-num">10K+</span>
            <span className="hero-stat-label">{t('landing.stat_cvs') || 'CVs Analyzed'}</span>
          </div>
          <div className="hero-stat-divider" />
          <div className="hero-stat">
            <span className="hero-stat-num">95%</span>
            <span className="hero-stat-label">{t('landing.stat_accuracy') || 'Accuracy Rate'}</span>
          </div>
          <div className="hero-stat-divider" />
          <div className="hero-stat">
            <span className="hero-stat-num">50+</span>
            <span className="hero-stat-label">{t('landing.stat_skills') || 'Skills Tracked'}</span>
          </div>
        </div>

        {/* Demo Preview */}
        <div className="demo-card">
          <div className="demo-header">{t('landing.demo_title')}</div>
          <div className="demo-body">
            <div className="demo-score-section">
              <div className="demo-circle">
                <span className="demo-num">82</span>
                <span className="demo-pct">%</span>
              </div>
              <span className="demo-label">{t('landing.demo_interpretation')}</span>
            </div>
            <div className="demo-details">
              <div className="demo-row">
                <span>{t('landing.demo_skills_found')}</span>
                <div className="demo-tags">
                  <span className="tag tag-green">Python</span>
                  <span className="tag tag-green">React</span>
                  <span className="tag tag-green">Docker</span>
                  <span className="tag tag-green">SQL</span>
                </div>
              </div>
              <div className="demo-row">
                <span>{t('landing.demo_skills_missing')}</span>
                <div className="demo-tags">
                  <span className="tag tag-red">Kubernetes</span>
                  <span className="tag tag-red">GraphQL</span>
                </div>
              </div>
              <div className="demo-row">
                <span>{t('landing.demo_ats')}</span>
                <div className="demo-ats-bar">
                  <div className="bar-track"><div className="bar-fill" style={{ width: '94%', background: '#22c55e' }} /></div>
                  <span>94%</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="section">
        <h2 className="section-title">{t('landing.features_title')}</h2>
        <p className="section-subtitle">{t('landing.features_subtitle')}</p>
        <div className="features-grid">
          {features.map((f, i) => (
            <div key={i} className="feature-card">
              <div className="feature-icon">{f.icon}</div>
              <h3>{f.title}</h3>
              <p>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="section section-alt">
        <h2 className="section-title">{t('landing.how_title')}</h2>
        <p className="section-subtitle">{t('landing.how_subtitle')}</p>
        <div className="steps-grid">
          {steps.map((s, i) => (
            <div key={i} className="step-card">
              <div className="step-icon">{s.icon}</div>
              <div className="step-num">{s.num}</div>
              <h3>{s.title}</h3>
              <p>{s.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="section">
        <h2 className="section-title">{t('landing.pricing_title')}</h2>
        <p className="section-subtitle">{t('landing.pricing_subtitle')}</p>
        <div className="pricing-grid">
          <div className="pricing-card">
            <h3>{t('pricing.free_name')}</h3>
            <div className="pricing-price">{t('pricing.free_price')}<span>/{t('pricing.free_period')}</span></div>
            <ul>
              <li>{t('pricing.free_f1')}</li>
              <li>{t('pricing.free_f2')}</li>
              <li>{t('pricing.free_f3')}</li>
              <li>{t('pricing.free_f4')}</li>
            </ul>
            <Link to="/register" className="btn-outline btn-full">{t('pricing.free_cta')}</Link>
          </div>
          <div className="pricing-card popular">
            <div className="popular-badge">{t('pricing.popular')}</div>
            <h3>{t('pricing.pro_name')}</h3>
            <div className="pricing-price">{t('pricing.pro_price')}<span>/{t('pricing.pro_period')}</span></div>
            <ul>
              <li>{t('pricing.pro_f1')}</li>
              <li>{t('pricing.pro_f2')}</li>
              <li>{t('pricing.pro_f3')}</li>
              <li>{t('pricing.pro_f4')}</li>
              <li>{t('pricing.pro_f5')}</li>
            </ul>
            <Link to="/register" className="btn-primary btn-full">{t('pricing.pro_cta')}</Link>
          </div>
          <div className="pricing-card">
            <h3>{t('pricing.enterprise_name')}</h3>
            <div className="pricing-price">{t('pricing.enterprise_price')}<span>/{t('pricing.enterprise_period')}</span></div>
            <ul>
              <li>{t('pricing.enterprise_f1')}</li>
              <li>{t('pricing.enterprise_f2')}</li>
              <li>{t('pricing.enterprise_f3')}</li>
              <li>{t('pricing.enterprise_f4')}</li>
              <li>{t('pricing.enterprise_f5')}</li>
            </ul>
            <a href="mailto:sales@cvanalyzer.app" className="btn-outline btn-full">{t('pricing.enterprise_cta')}</a>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="section section-alt">
        <h2 className="section-title">{t('landing.faq_title')}</h2>
        <div className="faq-list">
          {faqs.map((faq, i) => (
            <details key={i} className="faq-item">
              <summary>{faq.q}</summary>
              <p>{faq.a}</p>
            </details>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="section cta-section">
        <h2>{t('landing.hero_title')}</h2>
        <p>{t('landing.hero_subtitle')}</p>
        <Link to="/register" className="btn-primary btn-lg">{t('landing.try_now')}</Link>
      </section>

      <Footer />
    </div>
  )
}
