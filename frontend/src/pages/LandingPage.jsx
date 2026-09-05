import React, { useRef } from 'react'
import { Link } from 'react-router-dom'
import { motion, useInView, useReducedMotion, useScroll, useSpring, useTransform } from 'framer-motion'
import {
  Brain, FileCheck, Target, Globe2, LayoutGrid, Users,
  Upload, FileText, CheckCircle2, ArrowRight,
  Shield, Sparkles, Zap,
  GraduationCap, Bot, LayoutTemplate, Mail, Mic, Briefcase, Database,
} from 'lucide-react'
import { useLanguage } from '../i18n/LanguageContext'
import { useAuth } from '../context/AuthContext'
import { getHistory } from '../utils/historyStorage'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import AnimatedBackground from '../components/AnimatedBackground'
import CircularProgress from '../components/CircularProgress'
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
const scrollSection = {
  hidden: { opacity: 0, y: 34, scale: 0.992, filter: 'blur(10px)' },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    filter: 'blur(0px)',
    transition: { duration: 0.72, ease: [0.22, 1, 0.36, 1] },
  },
}
const scrollStagger = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.09, delayChildren: 0.08 } },
}
const scrollItem = {
  hidden: { opacity: 0, y: 26, scale: 0.985, filter: 'blur(8px)' },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    filter: 'blur(0px)',
    transition: { duration: 0.58, ease: [0.22, 1, 0.36, 1] },
  },
}
const scrollScaleItem = {
  hidden: { opacity: 0, y: 18, scale: 0.965, filter: 'blur(8px)' },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    filter: 'blur(0px)',
    transition: { duration: 0.62, ease: [0.22, 1, 0.36, 1] },
  },
}
const scrollViewport = { once: true, amount: 0.18, margin: '0px 0px -72px 0px' }
const gridViewport = { once: true, amount: 0.14, margin: '0px 0px -64px 0px' }

// ─── Feature accent colors ───────────────────────────────────────
const FEATURE_COLORS = ['#5b6cff', '#d4a94f', '#0e7490', '#b65d52', '#7c3aed', '#2563eb']
const FEATURE_ICONS  = [Brain, FileCheck, Target, Globe2, LayoutGrid, Users]

const TOOL_COLORS = ['#5b6cff', '#7c3aed', '#0e7490', '#d4a94f', '#2563eb', '#b65d52', '#059669', '#dc2626']
const TOOL_ICONS   = [GraduationCap, Bot, FileText, LayoutTemplate, Mail, Mic, Briefcase, Database]
const STEP_ICONS     = [Upload, FileText, CheckCircle2]
const STEP_TIMES     = ['< 1 min', '2 min', 'Instant']
const HERO_HOLOGRAM_PARTICLES = [
  { x: 8, y: 20, size: 3, drift: -10, delay: -0.2 },
  { x: 14, y: 64, size: 4, drift: 12, delay: -1.4 },
  { x: 24, y: 12, size: 2, drift: -8, delay: -2.3 },
  { x: 34, y: 78, size: 3, drift: 10, delay: -0.8 },
  { x: 48, y: 24, size: 2, drift: -12, delay: -1.8 },
  { x: 56, y: 70, size: 4, drift: 14, delay: -2.7 },
  { x: 68, y: 16, size: 3, drift: -10, delay: -0.5 },
  { x: 74, y: 52, size: 2, drift: 9, delay: -1.2 },
  { x: 84, y: 30, size: 3, drift: -12, delay: -2.1 },
  { x: 90, y: 72, size: 2, drift: 10, delay: -0.9 },
]

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
// Signed-in visitors who have already analyzed a CV on this device see
// their own last real result here instead of the static illustrative
// mock -- getHistory() is per-browser localStorage (see utils/historyStorage.js),
// so this is empty for anonymous visitors and during SEO prerendering,
// which keeps the always-crawlable fallback exactly as illustrative as
// before (see project_adsense-rejection memory on why that labeling
// matters: a fabricated specific score reads as a false claim, a
// generic "Sample" doesn't).
function DemoCard({ t }) {
  const ref = useRef(null)
  const isInView = useInView(ref, { once: true, amount: 0.3 })
  const { user } = useAuth()

  const lastReal = user ? getHistory(user)[0]?.result : null
  const isReal = Boolean(lastReal && typeof lastReal.final_score === 'number')

  const scoreValue = isReal ? Math.round(lastReal.final_score) : 100
  const scoreDisplay = isReal ? String(scoreValue) : t('landing.demo_badge')
  const interpretationLabel = isReal
    ? (lastReal.interpretation || t('landing.demo_interpretation'))
    : t('landing.demo_interpretation')
  const detectedSkills = isReal && lastReal.detected_skills?.length
    ? lastReal.detected_skills.slice(0, 4)
    : ['Python', 'React', 'Docker', 'SQL']
  const missingSkillsList = isReal && lastReal.missing_skills?.length
    ? lastReal.missing_skills.slice(0, 2)
    : ['Kubernetes', 'GraphQL']
  const atsPercent = isReal && typeof lastReal.ats_score === 'number' ? Math.round(lastReal.ats_score) : 72
  // These two floating badges were already plain hardcoded English in the
  // original (not run through t()), so the "real" variants stay consistent
  // with that rather than introducing new translation keys for one string.
  const bottomBadgeLabel = isReal ? 'Your last scan' : 'Illustrative check'
  const previewAriaLabel = isReal ? 'Your last analysis result' : 'Illustrative result preview'

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
        {bottomBadgeLabel}
      </motion.div>

      {/* Main demo card */}
      <motion.div
        className="demo-card lp-demo-card"
        whileHover={{ y: -2 }}
        transition={{ duration: 0.3 }}
      >
        <div className="lp-demo-hologram" aria-hidden="true">
          <div className="lp-holo-aura" />
          <div className="lp-holo-sphere" />
          <div className="lp-holo-floor" />
          {HERO_HOLOGRAM_PARTICLES.map((particle, index) => (
            <span
              key={`hero-particle-${index}`}
              className="lp-holo-particle"
              style={{
                '--x': `${particle.x}%`,
                '--y': `${particle.y}%`,
                '--particle-size': `${particle.size}px`,
                '--particle-drift': `${particle.drift}px`,
                '--particle-delay': `${particle.delay}s`,
              }}
            />
          ))}
        </div>
        <div className="demo-header">{t('landing.demo_title')}</div>
        <div className="demo-body">
          <div className="demo-score-section">
            <CircularProgress
              value={scoreValue}
              size={104}
              strokeWidth={8}
              color="var(--color-success)"
              trackColor="var(--landing-progress-track, color-mix(in srgb, var(--color-success) 14%, var(--color-border)))"
              glow="color-mix(in srgb, var(--color-success) 28%, transparent)"
              className="demo-ring lp-demo-circle"
              label={previewAriaLabel}
            >
              <span className="demo-score-value">
                <span className="demo-num" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                  {scoreDisplay}{isReal ? '%' : ''}
                </span>
              </span>
            </CircularProgress>
            <span className="demo-label">{interpretationLabel}</span>
          </div>
          <div className="demo-details">
            <div className="demo-row">
              <span>{t('landing.demo_skills_found')}</span>
              <div className="demo-tags">
                {detectedSkills.map((s, i) => (
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
                {missingSkillsList.map((s, i) => (
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
                    animate={isInView ? { width: `${atsPercent}%` } : {}}
                    transition={{ delay: 0.6, duration: 1.2, ease: 'easeOut' }}
                  />
                </div>
                <span>{t('landing.demo_check_label')}</span>
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
    rotateX.set(y * -13)
    rotateY.set(x * 16)
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
            <strong>{t('landing.demo_badge')}</strong>
          </div>
          <div className="hero-metric-tile hero-metric-tile-b">
            <span>{t('landing.hero_float_match_label')}</span>
            <strong>{t('landing.demo_signal_label')}</strong>
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
            <span>{t('landing.hero_float_fit_label')}</span>
            <strong>{t('landing.hero_float_fit_value')}</strong>
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
            <span>{t('landing.hero_float_match_label')}</span>
            <strong>{t('landing.hero_float_match_value')}</strong>
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
            <span>{t('landing.hero_float_rewrite_label')}</span>
            <strong>{t('landing.hero_float_rewrite_value')}</strong>
          </div>
        </motion.div>
      </motion.div>
    </motion.div>
  )
}

// ─── Main LandingPage ────────────────────────────────────────────
function ScrollAnalysisStory({ t }) {
  const sectionRef = useRef(null)
  const prefersReducedMotion = useReducedMotion()
  const { scrollYProgress } = useScroll({
    target: sectionRef,
    offset: ['start end', 'end start'],
  })
  const rotateY = useTransform(scrollYProgress, [0, 0.5, 1], [-28, 152, 332])
  const rotateX = useTransform(scrollYProgress, [0, 0.5, 1], [10, -6, 8])
  const objectY = useTransform(scrollYProgress, [0, 0.5, 1], [72, 0, -72])
  const objectScale = useTransform(scrollYProgress, [0, 0.5, 1], [0.86, 1, 0.88])
  const ringRotate = useTransform(scrollYProgress, [0, 1], [-35, 325])
  const scanY = useTransform(scrollYProgress, [0.12, 0.82], ['8%', '88%'])

  const objectMotion = prefersReducedMotion
    ? { rotateX: 0, rotateY: -12, y: 0, scale: 1 }
    : { rotateX, rotateY, y: objectY, scale: objectScale }

  return (
    <section ref={sectionRef} className="lp-scroll-story" aria-labelledby="scroll-story-title">
      <div className="lp-scroll-story-sticky">
        <motion.div
          className="lp-scroll-story-copy"
          initial={prefersReducedMotion ? false : { opacity: 0, y: 24 }}
          whileInView={prefersReducedMotion ? undefined : { opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.5 }}
          transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
        >
          <span className="lp-scroll-story-kicker">CV intelligence / 03</span>
          <h2 id="scroll-story-title">{t('landing.demo_title')}</h2>
          <p>{t('landing.demo_subtitle')}</p>
          <div className="lp-scroll-story-signals" aria-label={t('landing.demo_title')}>
            <span><FileText size={15} /> CV</span>
            <span><Brain size={15} /> AI Match</span>
            <span><CheckCircle2 size={15} /> ATS check</span>
          </div>
        </motion.div>

        <div className="lp-scroll-scene" aria-hidden="true">
          <motion.div
            className="lp-scroll-orbit lp-scroll-orbit-outer"
            style={prefersReducedMotion ? undefined : { rotate: ringRotate }}
          >
            <span className="lp-scroll-orbit-node lp-scroll-orbit-node-a" />
            <span className="lp-scroll-orbit-node lp-scroll-orbit-node-b" />
          </motion.div>
          <div className="lp-scroll-orbit lp-scroll-orbit-inner" />

          <motion.div className="lp-scroll-object" style={objectMotion}>
            <div className="lp-scroll-sheet lp-scroll-sheet-front">
              <div className="lp-scroll-sheet-topline">
                <span className="lp-scroll-sheet-mark"><FileText size={18} /></span>
                <span>Candidate profile</span>
                <strong>01</strong>
              </div>
              <div className="lp-scroll-sheet-heading" />
              <div className="lp-scroll-sheet-subheading" />
              <div className="lp-scroll-sheet-grid">
                <div>
                  <span className="lp-scroll-sheet-label">Experience</span>
                  <i /><i /><i />
                </div>
                <div className="lp-scroll-sheet-score">
                  <strong>✓</strong>
                  <span>Signals</span>
                </div>
              </div>
              <div className="lp-scroll-sheet-skills">
                <span>React</span><span>Python</span><span>SQL</span>
              </div>
              <motion.div
                className="lp-scroll-sheet-scan"
                style={prefersReducedMotion ? { top: '48%' } : { top: scanY }}
              />
            </div>

            <div className="lp-scroll-sheet lp-scroll-sheet-back">
              <div className="lp-scroll-sheet-topline">
                <span className="lp-scroll-sheet-mark"><Target size={18} /></span>
                <span>Evidence map</span>
                <strong>02</strong>
              </div>
              <div className="lp-scroll-evidence-ring">
                <span>4</span>
                <small>checks</small>
              </div>
              <div className="lp-scroll-evidence-row"><span>Role fit</span><strong>Review</strong></div>
              <div className="lp-scroll-evidence-row"><span>Signals</span><strong>Explained</strong></div>
              <div className="lp-scroll-evidence-row"><span>Rewrite</span><strong>User choice</strong></div>
            </div>

            <div className="lp-scroll-sheet-edge" />
          </motion.div>

          <div className="lp-scroll-scene-caption lp-scroll-scene-caption-left">
            <span>INPUT</span><strong>Structured CV</strong>
          </div>
          <div className="lp-scroll-scene-caption lp-scroll-scene-caption-right">
            <span>OUTPUT</span><strong>Actionable evidence</strong>
          </div>
        </div>
      </div>
    </section>
  )
}

export default function LandingPage() {
  const { t } = useLanguage()
  const prefersReducedMotion = useReducedMotion()
  const { scrollYProgress } = useScroll()
  const revealSectionProps = prefersReducedMotion
    ? { initial: false }
    : { initial: 'hidden', whileInView: 'visible', viewport: scrollViewport, variants: scrollSection }
  const revealGridProps = prefersReducedMotion
    ? { initial: false }
    : { initial: 'hidden', whileInView: 'visible', viewport: gridViewport, variants: scrollStagger }

  const features = [
    { title: t('landing.feature_ai_title'),       desc: t('landing.feature_ai_desc') },
    { title: t('landing.feature_ats_title'),      desc: t('landing.feature_ats_desc') },
    { title: t('landing.feature_skills_title'),   desc: t('landing.feature_skills_desc') },
    { title: t('landing.feature_multi_title'),    desc: t('landing.feature_multi_desc') },
    { title: t('landing.feature_history_title'),  desc: t('landing.feature_history_desc') },
    { title: t('landing.feature_recruiter_title'),desc: t('landing.feature_recruiter_desc') },
  ]

  const tools = [
    { title: 'Career Studio', href: '/career-studio' },
    { title: 'AI Agent Hub', href: '/agents' },
    { title: t('nav.cv_builder'), href: '/cv-builder' },
    { title: 'Templates', href: '/template-marketplace' },
    { title: t('nav.cover_letter'), href: '/cover-letter' },
    { title: t('nav.interview'), href: '/interview-simulator' },
    { title: t('nav.job_tracker'), href: '/job-tracker' },
    { title: 'Data Center', href: '/data-center' },
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
      <main id="main-content">

      {/* ── Hero ─────────────────────────────────────────── */}
      <section className="hero hero-kinetic-section">
        <div className="hero-grid">
          {/* Left: Content */}
          <motion.div
            className="hero-content"
            initial="hidden"
            animate="visible"
            variants={stagger}
          >
            <motion.div className="hero-badge" variants={fadeUp}>
              <FileCheck size={14} /> {t('landing.workspace_badge')}
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
              <Link to="/pricing" className="btn-ghost btn-lg">{t('landing.view_pricing')}</Link>
            </motion.div>

            <motion.p className="hero-note" variants={fadeUp}>{t('landing.trust_note')}</motion.p>

            {/* Stats Row */}
            <motion.div className="hero-stats" variants={fadeUp}>
              <div className="hero-stat">
                <span className="hero-stat-num">ATS</span>
                <span className="hero-stat-label">{t('landing.stat_readability')}</span>
              </div>
              <div className="hero-stat-divider" />
              <div className="hero-stat">
                <span className="hero-stat-num">{t('landing.stat_evidence_value')}</span>
                <span className="hero-stat-label">{t('landing.stat_evidence')}</span>
              </div>
              <div className="hero-stat-divider" />
              <div className="hero-stat">
                <span className="hero-stat-num">{t('landing.stat_control_value')}</span>
                <span className="hero-stat-label">{t('landing.stat_control')}</span>
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
        initial={prefersReducedMotion ? false : 'hidden'}
        whileInView={prefersReducedMotion ? undefined : 'visible'}
        viewport={scrollViewport}
        variants={scrollScaleItem}
      >
        <div className="lp-proof-stat">
          <span className="lp-proof-num">ATS</span>
          <span className="lp-proof-label">{t('landing.proof_ats')}</span>
        </div>
        <div className="lp-proof-divider" />
        <div className="lp-proof-stat">
          <span className="lp-proof-num">{t('landing.proof_content_value')}</span>
          <span className="lp-proof-label">{t('landing.proof_content')}</span>
        </div>
        <div className="lp-proof-divider" />
        <div className="lp-proof-stat">
          <span className="lp-proof-num">{t('landing.proof_match_value')}</span>
          <span className="lp-proof-label">{t('landing.proof_match')}</span>
        </div>
        <div className="lp-proof-divider" />
        <div className="lp-proof-stat">
          <span className="lp-proof-num">{t('landing.proof_privacy_value')}</span>
          <span className="lp-proof-label">{t('landing.proof_privacy')}</span>
        </div>
      </motion.div>

      {/* ── Features ─────────────────────────────────────── */}
      <motion.section id="features" className="section" {...revealSectionProps}>
        <SectionTitle title={t('landing.features_title')} subtitle={t('landing.features_subtitle')} />
        <motion.div
          className="features-grid"
          {...revealGridProps}
        >
          {features.map((f, i) => {
            const Icon = FEATURE_ICONS[i]
            const color = FEATURE_COLORS[i]
            return (
              <motion.article
                key={i}
                className={`feature-card lp-feature-card lp-flip-card${i < 2 ? ' feature-card-lg' : ''}`}
                style={{ '--feature-color': color }}
                variants={scrollItem}
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

                  <div className="lp-flip-card-face lp-flip-card-back" aria-hidden="true">
                    <span className="lp-flip-kicker">{t('landing.feature_kicker')} {String(i + 1).padStart(2, '0')}</span>
                    <h3>{f.title}</h3>
                    <p>{f.desc}</p>
                    <div className="lp-flip-meta">
                      <span>{t('landing.inspect_depth')}</span>
                      <ArrowRight size={15} />
                    </div>
                  </div>
                </div>
              </motion.article>
            )
          })}
        </motion.div>
      </motion.section>

      <ScrollAnalysisStory t={t} />

      {/* ── How It Works ─────────────────────────────────── */}
      <motion.section className="section section-alt" {...revealSectionProps}>
        <SectionTitle title={t('landing.how_title')} subtitle={t('landing.how_subtitle')} />
        <motion.div
          className="lp-steps-grid"
          {...revealGridProps}
        >
          {steps.map((s, i) => {
            const Icon = STEP_ICONS[i]
            return (
              <motion.div key={i} className="lp-step-card" variants={scrollItem}>
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
      </motion.section>

      {/* ── Tools ────────────────────────────────────────── */}
      <motion.section id="tools" className="section" {...revealSectionProps}>
        <SectionTitle title={t('landing.tools_title')} subtitle={t('landing.tools_subtitle')} />
        <motion.div
          className="features-grid"
          {...revealGridProps}
        >
          {tools.map((tool, i) => {
            const Icon = TOOL_ICONS[i]
            const color = TOOL_COLORS[i]
            return (
              <motion.div key={tool.href} variants={scrollItem}>
                <Link
                  to={tool.href}
                  className="feature-card"
                  style={{ display: 'block', height: '100%' }}
                >
                  <div
                    className="feature-icon"
                    style={{ background: `${color}15`, border: `1px solid ${color}25`, color }}
                  >
                    <Icon size={22} strokeWidth={1.8} />
                  </div>
                  <h3>{tool.title}</h3>
                </Link>
              </motion.div>
            )
          })}
        </motion.div>
      </motion.section>

      {/* ── FAQ ──────────────────────────────────────────── */}
      <motion.section id="faq" className="section section-alt" {...revealSectionProps}>
        <SectionTitle title={t('landing.faq_title')} />
        <motion.div
          className="faq-list"
          {...revealGridProps}
        >
          {faqs.map((faq, i) => (
            <motion.details key={i} className="faq-item" variants={scrollItem}>
              <summary>{faq.q}</summary>
              <p>{faq.a}</p>
            </motion.details>
          ))}
        </motion.div>
      </motion.section>

      {/* ── CTA Strip ────────────────────────────────────── */}
      <motion.section className="lp-cta-strip" {...revealSectionProps}>
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
            {t('landing.cta_note')}
          </p>
        </div>
      </motion.section>

      </main>
      <Footer />
    </div>
  )
}
