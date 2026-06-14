import React, { useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { motion, useInView, useReducedMotion, useScroll, useSpring, useTransform } from 'framer-motion'
import {
  Brain, FileCheck, Target, Globe2, LayoutGrid, Users,
  Upload, FileText, CheckCircle2, ArrowRight,
  Shield, Sparkles, Zap,
} from 'lucide-react'
import { useLanguage } from '../i18n/LanguageContext'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import AnimatedBackground from '../components/AnimatedBackground'
import TestimonialCarousel from '../components/TestimonialCarousel'
import { SectionTitle } from '../components/ui'
import useAnimatedCounter from '../hooks/useAnimatedCounter'

// ─── Animation Variants ─────────────────────────────────────────
const stagger = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.08 } },
}
const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.25, 0.1, 0.25, 1] } },
}
const scaleIn = {
  hidden: { opacity: 0, scale: 0.92 },
  visible: { opacity: 1, scale: 1, transition: { duration: 0.55, ease: [0.25, 0.1, 0.25, 1] } },
}

// ─── Feature accent colors ───────────────────────────────────────
const FEATURE_COLORS = ['#5b6cff', '#d4a94f', '#0e7490', '#b65d52', '#7c3aed', '#2563eb']
const FEATURE_ICONS  = [Brain, FileCheck, Target, Globe2, LayoutGrid, Users]
const STEP_ICONS     = [Upload, FileText, CheckCircle2]
const STEP_TIMES     = ['< 1 min', '2 min', 'Instant']

// ─── Animated Stat (triggers on in-view) ────────────────────────
function ProofStat({ value, suffix, label }) {
  const ref = useRef(null)
  const isInView = useInView(ref, { once: true })
  const count = useAnimatedCounter(isInView ? value : 0, 1600)
  return (
    <div ref={ref} className="lp-proof-stat">
      <span className="lp-proof-num">
        {count}{suffix}
      </span>
      <span className="lp-proof-label">{label}</span>
    </div>
  )
}

// ─── Demo Card with animated score ──────────────────────────────
function DemoCard({ t }) {
  const ref = useRef(null)
  const isInView = useInView(ref, { once: true, amount: 0.3 })
  const score = useAnimatedCounter(isInView ? 82 : 0, 1400)

  return (
    <div ref={ref} className="lp-demo-wrapper">
      {/* Floating badges */}
      <motion.div
        className="lp-float-badge lp-float-badge-top"
        animate={{ y: [0, -6, 0] }}
        transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
      >
        <FileCheck size={12} style={{ color: 'var(--color-accent)' }} />
        Evidence Scan
      </motion.div>
      <motion.div
        className="lp-float-badge lp-float-badge-bottom"
        animate={{ y: [0, 6, 0] }}
        transition={{ duration: 3.5, repeat: Infinity, ease: 'easeInOut', delay: 0.8 }}
      >
        <Shield size={12} style={{ color: 'var(--color-success)' }} />
        ATS Ready
      </motion.div>

      {/* Main demo card */}
      <motion.div
        className="demo-card lp-demo-card"
        whileHover={{ y: -2 }}
        transition={{ duration: 0.3 }}
      >
        <div className="demo-header">{t('landing.demo_title')}</div>
        <div className="demo-body">
          <div className="demo-score-section">
            <div className="demo-circle lp-demo-circle">
              <span className="demo-num" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                {score}
              </span>
              <span className="demo-pct">%</span>
            </div>
            <span className="demo-label">{t('landing.demo_interpretation')}</span>
          </div>
          <div className="demo-details">
            <div className="demo-row">
              <span>{t('landing.demo_skills_found')}</span>
              <div className="demo-tags">
                {['Python', 'React', 'Docker', 'SQL'].map((s, i) => (
                  <motion.span
                    key={s}
                    className="tag tag-green"
                    initial={{ opacity: 0, scale: 0.7 }}
                    animate={isInView ? { opacity: 1, scale: 1 } : {}}
                    transition={{ delay: 0.5 + i * 0.1, type: 'spring', stiffness: 300 }}
                  >
                    {s}
                  </motion.span>
                ))}
              </div>
            </div>
            <div className="demo-row">
              <span>{t('landing.demo_skills_missing')}</span>
              <div className="demo-tags">
                {['Kubernetes', 'GraphQL'].map((s, i) => (
                  <motion.span
                    key={s}
                    className="tag tag-red"
                    initial={{ opacity: 0, scale: 0.7 }}
                    animate={isInView ? { opacity: 1, scale: 1 } : {}}
                    transition={{ delay: 0.9 + i * 0.1, type: 'spring', stiffness: 300 }}
                  >
                    {s}
                  </motion.span>
                ))}
              </div>
            </div>
            <div className="demo-row">
              <span>{t('landing.demo_ats')}</span>
              <div className="demo-ats-bar">
                <div className="bar-track">
                  <motion.div
                    className="bar-fill"
                    style={{ background: 'var(--gradient-accent)' }}
                    initial={{ width: 0 }}
                    animate={isInView ? { width: '94%' } : {}}
                    transition={{ delay: 0.6, duration: 1.2, ease: 'easeOut' }}
                  />
                </div>
                <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>94%</span>
              </div>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  )
}

function KineticHeroStage({ t, scrollYProgress }) {
  const prefersReducedMotion = useReducedMotion()
  const rotateX = useSpring(0, { stiffness: 170, damping: 22, mass: 0.7 })
  const rotateY = useSpring(0, { stiffness: 170, damping: 22, mass: 0.7 })
  const stageY = useTransform(scrollYProgress, [0, 0.18], [0, -72])
  const stageScale = useTransform(scrollYProgress, [0, 0.18], [1, 0.94])
  const rearY = useTransform(scrollYProgress, [0, 0.18], [0, 44])
  const frontY = useTransform(scrollYProgress, [0, 0.18], [0, -34])

  const handlePointerMove = (event) => {
    if (prefersReducedMotion) return
    const bounds = event.currentTarget.getBoundingClientRect()
    const x = (event.clientX - bounds.left) / bounds.width - 0.5
    const y = (event.clientY - bounds.top) / bounds.height - 0.5
    rotateX.set(y * -18)
    rotateY.set(x * 22)
  }

  const resetTilt = () => {
    rotateX.set(0)
    rotateY.set(0)
  }

  return (
    <motion.div
      className="hero-kinetic-stage"
      style={prefersReducedMotion ? undefined : { y: stageY, scale: stageScale }}
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
    >
      <motion.div
        className="hero-kinetic-rig"
        onPointerMove={handlePointerMove}
        onPointerLeave={resetTilt}
        onPointerCancel={resetTilt}
        drag={prefersReducedMotion ? false : true}
        dragConstraints={{ top: -18, right: 18, bottom: 18, left: -18 }}
        dragElastic={0.12}
        whileDrag={prefersReducedMotion ? undefined : { scale: 0.985 }}
        style={{ rotateX, rotateY }}
      >
        <motion.div
          className="hero-depth-plane hero-depth-plane-back"
          aria-hidden="true"
          style={prefersReducedMotion ? undefined : { y: rearY }}
        >
          <div className="hero-plane-grid" />
          <div className="hero-plane-scan" />
        </motion.div>

        <motion.div
          className="hero-depth-plane hero-depth-plane-mid"
          aria-hidden="true"
          style={prefersReducedMotion ? undefined : { y: frontY }}
        >
          <div className="hero-metric-tile hero-metric-tile-a">
            <span>ATS</span>
            <strong>94%</strong>
          </div>
          <div className="hero-metric-tile hero-metric-tile-b">
            <span>Match</span>
            <strong>82%</strong>
          </div>
          <div className="hero-flow-line hero-flow-line-a" />
          <div className="hero-flow-line hero-flow-line-b" />
        </motion.div>

        <div className="hero-demo-frame">
          <DemoCard t={t} />
        </div>

        <motion.div
          className="hero-kinetic-float hero-kinetic-float-left"
          aria-hidden="true"
          animate={prefersReducedMotion ? undefined : { y: [0, -10, 0] }}
          transition={{ duration: 4.2, repeat: Infinity, ease: 'easeInOut' }}
        >
          <div className="hero-kinetic-panel hero-kinetic-panel-left">
            <div className="hero-panel-icon"><Target size={16} /></div>
            <span>Role fit</span>
            <strong>High</strong>
          </div>
        </motion.div>

        <motion.div
          className="hero-kinetic-float hero-kinetic-float-right"
          aria-hidden="true"
          animate={prefersReducedMotion ? undefined : { y: [0, 12, 0] }}
          transition={{ duration: 4.8, repeat: Infinity, ease: 'easeInOut', delay: 0.4 }}
        >
          <div className="hero-kinetic-panel hero-kinetic-panel-right">
            <div className="hero-panel-icon"><Sparkles size={16} /></div>
            <span>Signals</span>
            <strong>12 found</strong>
          </div>
        </motion.div>

        <motion.div
          className="hero-kinetic-float hero-kinetic-float-bottom"
          aria-hidden="true"
          animate={prefersReducedMotion ? undefined : { x: [-6, 8, -6] }}
          transition={{ duration: 5.2, repeat: Infinity, ease: 'easeInOut', delay: 0.8 }}
        >
          <div className="hero-kinetic-panel hero-kinetic-panel-bottom">
            <div className="hero-panel-icon"><Zap size={16} /></div>
            <span>Rewrite</span>
            <strong>Ready</strong>
          </div>
        </motion.div>
      </motion.div>
    </motion.div>
  )
}

// ─── Main LandingPage ────────────────────────────────────────────
export default function LandingPage() {
  const { t, pricing } = useLanguage()
  const { scrollYProgress } = useScroll()

  useEffect(() => {
    document.title = 'CV Analyzer — AI-Powered Resume Analysis'
    return () => { document.title = 'CV Analyzer' }
  }, [])

  const features = [
    { title: t('landing.feature_ai_title'),       desc: t('landing.feature_ai_desc') },
    { title: t('landing.feature_ats_title'),      desc: t('landing.feature_ats_desc') },
    { title: t('landing.feature_skills_title'),   desc: t('landing.feature_skills_desc') },
    { title: 'Multi-Language Support',            desc: t('landing.feature_multi_desc') },
    { title: t('landing.feature_history_title'),  desc: t('landing.feature_history_desc') },
    { title: t('landing.feature_recruiter_title'),desc: t('landing.feature_recruiter_desc') },
  ]

  const steps = [
    { num: '01', title: t('landing.how_step1_title'), desc: t('landing.how_step1_desc'), time: STEP_TIMES[0] },
    { num: '02', title: t('landing.how_step2_title'), desc: t('landing.how_step2_desc'), time: STEP_TIMES[1] },
    { num: '03', title: t('landing.how_step3_title'), desc: t('landing.how_step3_desc'), time: STEP_TIMES[2] },
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

      {/* ── Hero ─────────────────────────────────────────── */}
      <section className="hero hero-kinetic-section" id="main-content">
        <div className="hero-grid">
          {/* Left: Content */}
          <motion.div
            className="hero-content"
            initial="hidden"
            animate="visible"
            variants={stagger}
          >
            <motion.div className="hero-badge" variants={fadeUp}>
              <FileCheck size={14} /> Resume intelligence workspace
            </motion.div>

            <motion.h1 variants={fadeUp}>{t('landing.hero_title')}</motion.h1>

            <motion.p className="hero-subtitle" variants={fadeUp}>
              {t('landing.hero_subtitle')}
            </motion.p>

            <motion.div className="hero-actions" variants={fadeUp}>
              <motion.div whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.97 }}>
                <Link to="/register" className="btn-primary btn-lg">
                  <ArrowRight size={16} />
                  {t('landing.try_now')}
                </Link>
              </motion.div>
              <a href="#pricing" className="btn-ghost btn-lg">{t('landing.view_pricing')}</a>
            </motion.div>

            <motion.p className="hero-note" variants={fadeUp}>{t('landing.trusted_by')}</motion.p>

            {/* Stats Row */}
            <motion.div className="hero-stats" variants={fadeUp}>
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
            </motion.div>
          </motion.div>

          {/* Right: Animated Demo */}
          <motion.div
            className="hero-demo"
            initial="hidden"
            animate="visible"
            variants={scaleIn}
          >
            <KineticHeroStage t={t} scrollYProgress={scrollYProgress} />
          </motion.div>
        </div>
      </section>

      {/* ── Social Proof Strip ────────────────────────────── */}
      <motion.div
        className="lp-proof-strip"
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.5 }}
      >
        <ProofStat value={10000} suffix="+" label={t('landing.stat_cvs') || 'CVs Analyzed'} />
        <div className="lp-proof-divider" />
        <ProofStat value={95} suffix="%" label={t('landing.stat_accuracy') || 'Accuracy Rate'} />
        <div className="lp-proof-divider" />
        <ProofStat value={50} suffix="+" label={t('landing.stat_skills') || 'Skills Tracked'} />
        <div className="lp-proof-divider" />
        <div className="lp-proof-stat">
          <span className="lp-proof-num" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            {[...Array(5)].map((_, i) => (
              <motion.span
                key={i}
                initial={{ opacity: 0, scale: 0 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.06 + 0.2, type: 'spring', stiffness: 400 }}
                style={{ color: '#fbbf24', fontSize: '1.1rem' }}
              >
                ★
              </motion.span>
            ))}
          </span>
          <span className="lp-proof-label">4.9 / 5 Rating</span>
        </div>
      </motion.div>

      {/* ── Features ─────────────────────────────────────── */}
      <section id="features" className="section">
        <SectionTitle title={t('landing.features_title')} subtitle={t('landing.features_subtitle')} />
        <motion.div
          className="features-grid"
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.1 }}
          variants={stagger}
        >
          {features.map((f, i) => {
            const Icon = FEATURE_ICONS[i]
            const color = FEATURE_COLORS[i]
            return (
              <motion.article
                key={i}
                className={`feature-card lp-feature-card lp-flip-card${i < 2 ? ' feature-card-lg' : ''}`}
                style={{ '--feature-color': color }}
                variants={fadeUp}
                whileHover={{ y: -2, transition: { duration: 0.15 } }}
                tabIndex={0}
                aria-label={`${f.title}: ${f.desc}`}
              >
                <div className="lp-flip-card-inner">
                  <div className="lp-flip-card-face lp-flip-card-front">
                    <div
                      className="feature-icon lp-feature-icon"
                      style={{
                        background: `${color}15`,
                        border: `1px solid ${color}25`,
                      }}
                    >
                      <Icon size={22} style={{ color }} strokeWidth={1.8} />
                    </div>
                    <h3>{f.title}</h3>
                    <p>{f.desc}</p>
                  </div>

                  <div className="lp-flip-card-face lp-flip-card-back">
                    <span className="lp-flip-kicker">Signal layer {String(i + 1).padStart(2, '0')}</span>
                    <h3>{f.title}</h3>
                    <p>{f.desc}</p>
                    <div className="lp-flip-meta">
                      <span>Inspect depth</span>
                      <ArrowRight size={15} />
                    </div>
                  </div>
                </div>
              </motion.article>
            )
          })}
        </motion.div>
      </section>

      {/* ── How It Works ─────────────────────────────────── */}
      <section className="section section-alt">
        <SectionTitle title={t('landing.how_title')} subtitle={t('landing.how_subtitle')} />
        <motion.div
          className="lp-steps-grid"
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.2 }}
          variants={stagger}
        >
          {steps.map((s, i) => {
            const Icon = STEP_ICONS[i]
            return (
              <motion.div key={i} className="lp-step-card" variants={fadeUp}>
                {/* Connector line (not for last) */}
                {i < steps.length - 1 && <div className="lp-step-connector" />}

                <div className="lp-step-top">
                  <span className="lp-step-num-large">{s.num}</span>
                  <motion.div
                    className="lp-step-icon-wrap"
                    whileHover={{ scale: 1.12, rotate: 6 }}
                    transition={{ type: 'spring', stiffness: 300 }}
                  >
                    <Icon size={26} color="var(--color-accent)" strokeWidth={1.5} />
                  </motion.div>
                </div>
                <span className="lp-step-time">{s.time}</span>
                <h3 className="lp-step-title">{s.title}</h3>
                <p className="lp-step-desc">{s.desc}</p>
              </motion.div>
            )
          })}
        </motion.div>
      </section>

      {/* ── Testimonials ─────────────────────────────────── */}
      <section id="testimonials" className="section section-alt" style={{ padding: 0 }}>
        <TestimonialCarousel t={t} />
      </section>

      {/* ── Pricing ──────────────────────────────────────── */}
      <section id="pricing" className="section">
        <SectionTitle title={t('landing.pricing_title')} subtitle={t('landing.pricing_subtitle')} />
        <motion.div
          className="pricing-grid"
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.1 }}
          variants={stagger}
        >
          <motion.div className="pricing-card" variants={fadeUp} whileHover={{ y: -2 }}>
            <h3>{t('pricing.free_name')}</h3>
            <div className="pricing-price">{pricing.free}<span>/{t(pricing.periodKey)}</span></div>
            <ul>
              <li>{t('pricing.free_f1')}</li>
              <li>{t('pricing.free_f2')}</li>
              <li>{t('pricing.free_f3')}</li>
              <li>{t('pricing.free_f4')}</li>
            </ul>
            <Link to="/register" className="btn-outline btn-full">{t('pricing.free_cta')}</Link>
          </motion.div>

          <motion.div className="pricing-card popular lp-pricing-popular" variants={scaleIn} whileHover={{ y: -2 }}>
            <div className="popular-badge">{t('pricing.popular')}</div>
            <div className="lp-pricing-header">
              <h3>{t('pricing.pro_name')}</h3>
              <div className="pricing-price">{pricing.pro}<span>/{t(pricing.periodKey)}</span></div>
            </div>
            <ul>
              <li>{t('pricing.pro_f1')}</li>
              <li>{t('pricing.pro_f2')}</li>
              <li>{t('pricing.pro_f3')}</li>
              <li>{t('pricing.pro_f4')}</li>
              <li>{t('pricing.pro_f5')}</li>
            </ul>
            <Link to="/register" className="btn-primary btn-full">{t('pricing.pro_cta')}</Link>
          </motion.div>

          <motion.div className="pricing-card" variants={fadeUp} whileHover={{ y: -2 }}>
            <h3>{t('pricing.enterprise_name')}</h3>
            <div className="pricing-price">{pricing.enterprise}<span>/{t(pricing.periodKey)}</span></div>
            <ul>
              <li>{t('pricing.enterprise_f1')}</li>
              <li>{t('pricing.enterprise_f2')}</li>
              <li>{t('pricing.enterprise_f3')}</li>
              <li>{t('pricing.enterprise_f4')}</li>
              <li>{t('pricing.enterprise_f5')}</li>
            </ul>
            <a href="mailto:sales@cvanalyzer.app" className="btn-outline btn-full">{t('pricing.enterprise_cta')}</a>
          </motion.div>
        </motion.div>
      </section>

      {/* ── FAQ ──────────────────────────────────────────── */}
      <section id="faq" className="section section-alt">
        <SectionTitle title={t('landing.faq_title')} />
        <motion.div
          className="faq-list"
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.1 }}
          variants={stagger}
        >
          {faqs.map((faq, i) => (
            <motion.details key={i} className="faq-item" variants={fadeUp}>
              <summary>{faq.q}</summary>
              <p>{faq.a}</p>
            </motion.details>
          ))}
        </motion.div>
      </section>

      {/* ── CTA Strip ────────────────────────────────────── */}
      <section className="lp-cta-strip">
        <div className="lp-cta-orb lp-cta-orb-1" />
        <div className="lp-cta-orb lp-cta-orb-2" />
        <div className="lp-cta-inner">
          <motion.div
            className="lp-cta-badge"
            initial={{ opacity: 0, scale: 0.8 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, type: 'spring', stiffness: 260 }}
          >
            <FileCheck size={13} /> {t('landing.try_now')}
          </motion.div>
          <motion.h2
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: 0.1 }}
          >
            {t('landing.cta_title') || t('landing.hero_title')}
          </motion.h2>
          <motion.p
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: 0.2 }}
          >
            {t('landing.cta_subtitle') || t('landing.hero_subtitle')}
          </motion.p>
          <motion.div
            className="lp-cta-actions"
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: 0.3 }}
          >
            <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.97 }}>
              <Link to="/register" className="btn-primary btn-lg">
                <ArrowRight size={16} /> {t('landing.try_now')}
              </Link>
            </motion.div>
            <motion.div whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}>
              <Link to="/cv-builder" className="lp-cta-secondary">
                {t('nav.cv_builder')} <ArrowRight size={14} />
              </Link>
            </motion.div>
          </motion.div>
          <p className="lp-cta-note">
            Free to start | No credit card | Instant results
          </p>
        </div>
      </section>

      <Footer />
    </div>
  )
}
