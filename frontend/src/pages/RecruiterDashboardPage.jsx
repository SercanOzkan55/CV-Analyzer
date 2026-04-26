import React, { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Users, TrendingUp, Trophy, Search, Eye, Mail, Check, X,
  Plus, Trash2, FileText, Send, ChevronDown, ChevronUp,
  Briefcase, ThumbsUp, ThumbsDown, Sparkles, AlertTriangle,
  ArrowUpDown, Settings, Copy, Camera,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import Navbar from '../components/Navbar'
import ScoreCircle from '../components/ScoreCircle'
import Modal from '../components/Modal'
import SkillTags from '../components/SkillTags'
import FilterChips from '../components/FilterChips'
import CameraScanModal from '../components/CameraScanModal'
import { useToast } from '../components/Toast'
import {
  recruiterCreateJob, recruiterListJobs,
  recruiterDashboardRank, recruiterDashboardPreview,
  recruiterDashboardAction, recruiterDashboardActions,
  recruiterCreateTemplate, recruiterListTemplates, recruiterDeleteTemplate,
  recruiterPreviewTemplate, recruiterSendEmail,
} from '../api'
import {
  validateEmail,
  validateCVText,
  validateFileUploads,
  safeApiCall,
  formatErrorMessage,
  isRateLimitError,
  isValidationError,
} from '../utils/recruiterErrorHandling'

/* ── helpers ──────────────────────────────────────────────────── */

// Simple logger utility
const logger = {
  info: (msg, data) => console.log(`[INFO] ${msg}`, data),
  warn: (msg, data) => console.warn(`[WARN] ${msg}`, data),
  error: (msg, data) => console.error(`[ERROR] ${msg}`, data),
}

function getScoreColor(s) {
  if (s >= 75) return '#22c55e'
  if (s >= 50) return '#eab308'
  return '#ef4444'
}

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  visible: (i = 0) => ({
    opacity: 1, y: 0,
    transition: { delay: i * 0.08, duration: 0.45, ease: [0.25, 0.1, 0.25, 1] },
  }),
}
const stagger = { hidden: {}, visible: { transition: { staggerChildren: 0.08 } } }

/* ── tabs ─────────────────────────────────────────────────────── */
const TABS = [
  { id: 'rank',      icon: Trophy,   label: 'Rank & Evaluate' },
  { id: 'actions',   icon: FileText, label: 'Decisions' },
  { id: 'templates', icon: Mail,     label: 'Email Templates' },
]

/* ═══════════════════════════════════════════════════════════════ */
export default function RecruiterDashboardPage() {
  const { token, user } = useAuth()
  const { t }     = useLanguage()
  const toast     = useToast()

  /* ── shared state ─────────────── */
  const [activeTab, setActiveTab] = useState('rank')
  const [jobs, setJobs]           = useState([])
  const [selectedJob, setSelectedJob] = useState(null)

  /* ── rank tab state ───────────── */
  const [jdText,      setJdText]      = useState('')
  const [cvEntries,   setCvEntries]   = useState([]) // [{name,email,cv_text}]
  const [rankLoading, setRankLoading] = useState(false)
  const [ranked,      setRanked]      = useState([]) // results from /rank
  const [activeFilter, setActiveFilter] = useState('all')
  const [sortDir,     setSortDir]     = useState('desc')

  /* ── preview / detail ─────────── */
  const [previewData, setPreviewData] = useState(null)
  const [previewOpen, setPreviewOpen] = useState(false)

  /* ── action state ─────────────── */
  const [actions, setActions]         = useState([])
  const [actionsLoading, setActionsLoading] = useState(false)

  /* ── template state ───────────── */
  const [templates, setTemplates]     = useState([])
  const [tplLoading, setTplLoading]   = useState(false)
  const [tplForm, setTplForm]         = useState({ name: '', template_type: 'accept', subject: '', body: '' })
  const [tplPreview, setTplPreview]   = useState(null)

  /* ── job create ───────────────── */
  const [jobModal, setJobModal]       = useState(false)
  const [jobForm, setJobForm]         = useState({ title: '', description: '' })

  /* ── email send ───────────────── */
  const [emailModal, setEmailModal]   = useState(false)
  const [emailTarget, setEmailTarget] = useState(null) // candidate obj
  const [emailTplId, setEmailTplId]   = useState('')
  const [emailSending, setEmailSending] = useState(false)
  const [emailAddr, setEmailAddr]     = useState('')
  const [senderEmail, setSenderEmail] = useState('')

  /* ── CV text input modal ──────── */
  const [cvModal, setCvModal]         = useState(false)
  const [cvDraft, setCvDraft]         = useState({ name: '', email: '', cv_text: '' })

  /* ── Camera scan modal ──────── */
  const [scanModal, setScanModal]     = useState(false)

  useEffect(() => {
    document.title = 'Recruiter Dashboard — CV Analyzer'
  }, [])

  /* ─── load jobs ────────────────────────────────────────────── */
  const loadJobs = useCallback(async () => {
    if (!token) return
    try {
      const data = await recruiterListJobs(token)
      const list = Array.isArray(data) ? data : data?.jobs || []
      setJobs(list)
      if (!selectedJob && list.length > 0) setSelectedJob(list[0])
    } catch { /* ignore */ }
  }, [token])

  useEffect(() => { loadJobs() }, [loadJobs])

  /* ─── load actions for selected job ────────────────────────── */
  useEffect(() => {
    if (activeTab !== 'actions' || !selectedJob?.id || !token) return
    let cancelled = false
    setActionsLoading(true)
    recruiterDashboardActions(token, selectedJob.id)
      .then(data => { if (!cancelled) setActions(Array.isArray(data) ? data : data?.actions || []) })
      .catch(() => { if (!cancelled) setActions([]) })
      .finally(() => { if (!cancelled) setActionsLoading(false) })
    return () => { cancelled = true }
  }, [activeTab, selectedJob, token])

  /* ─── load templates ───────────────────────────────────────── */
  useEffect(() => {
    if (activeTab !== 'templates' || !token) return
    let cancelled = false
    setTplLoading(true)
    recruiterListTemplates(token)
      .then(data => { if (!cancelled) setTemplates(Array.isArray(data) ? data : data?.templates || []) })
      .catch(() => { if (!cancelled) setTemplates([]) })
      .finally(() => { if (!cancelled) setTplLoading(false) })
    return () => { cancelled = true }
  }, [activeTab, token])

  /* ═══════════════════ HANDLERS ═════════════════════════════════ */

  /* create job */
  async function handleCreateJob(e) {
    e.preventDefault()
    if (!jobForm.title.trim()) return
    try {
      await recruiterCreateJob(token, jobForm)
      toast.success('Job created')
      setJobModal(false)
      setJobForm({ title: '', description: '' })
      loadJobs()
    } catch (err) {
      toast.error(err.message)
    }
  }

  /* add CV entry */
  function handleAddCv(e) {
    e.preventDefault()
    if (!cvDraft.cv_text.trim()) return
    setCvEntries(prev => [...prev, { ...cvDraft }])
    setCvDraft({ name: '', email: '', cv_text: '' })
    setCvModal(false)
  }

  /* rank candidates */
  async function handleRank() {
    // Pre-validation using utility functions
    if (!jdText.trim()) {
      toast.error('Enter job description')
      return
    }
    
    if (cvEntries.length === 0) {
      toast.error('Add at least 1 CV')
      return
    }
    
    // Validate each CV entry has sufficient text
    const invalidCVs = cvEntries.filter(cv => !validateCVText(cv.cv_text, 50))
    if (invalidCVs.length > 0) {
      toast.error(`${invalidCVs.length} CV(s) have insufficient text (minimum 50 characters)`)
      return
    }
    
    setRankLoading(true)
    try {
      // Use safe API wrapper with logging
      const data = await safeApiCall(
        () => recruiterDashboardRank(token, {
          job_description: jdText,
          cv_texts: cvEntries,
        }),
        'Rank Candidates',
        { logContext: { cvCount: cvEntries.length } }
      )
      
      const ranked = data?.ranking || []
      setRanked(ranked)
      toast.success(`${ranked.length} candidates ranked`)
    } catch (err) {
      // Better error handling
      if (isRateLimitError(err)) {
        toast.error('Rate limited. Please wait before ranking more candidates.')
      } else if (isValidationError(err)) {
        toast.error('Invalid input. Please check job description and CVs.')
      } else {
        toast.error(await formatErrorMessage(err, 'Failed to rank candidates'))
      }
      logger.warn('rank_failed', { error: err.message, cvCount: cvEntries.length })
    } finally {
      setRankLoading(false)
    }
  }

  /* preview candidate */
  async function handlePreview(candidate) {
    try {
      const data = await recruiterDashboardPreview(token, {
        cv_text: candidate.cv_text || '',
        job_description: jdText,
      })
      setPreviewData({ ...data, ...candidate })
      setPreviewOpen(true)
    } catch (err) {
      toast.error(err.message)
    }
  }

  /* accept / reject */
  async function handleAction(candidate, action) {
    if (!selectedJob?.id) {
      toast.error('Select a job first')
      return
    }
    try {
      await recruiterDashboardAction(token, {
        job_id: selectedJob.id,
        candidate_name: candidate.name || candidate.candidate_name || '',
        candidate_email: candidate.email || candidate.candidate_email || '',
        cv_text: candidate.cv_text || '',
        final_score: candidate.final_score ?? null,
        ats_score: candidate.ats_score ?? null,
        action,
      })
      toast.success(`${candidate.candidate_name || 'Candidate'} ${action}`)
      // update local state
      setRanked(prev => prev.map(r =>
        r.candidate_name === candidate.candidate_name ? { ...r, _action: action } : r
      ))
    } catch (err) {
      toast.error(err.message)
    }
  }

  /* open email modal */
  function openEmailModal(candidate) {
    setEmailTarget(candidate)
    setEmailTplId('')
    setEmailAddr(candidate.email || candidate.candidate_email || '')
    setSenderEmail(user?.email || '')
    setEmailModal(true)
  }

  /* send email */
  async function handleSendEmail() {
    // Validation before API call
    if (!emailTarget || !emailTplId) {
      toast.error('Select a template')
      return
    }
    
    // Use imported validation utility
    if (!validateEmail(emailAddr)) {
      toast.error('Please enter a valid email address')
      return
    }
    
    setEmailSending(true)
    try {
      // Use safe API wrapper for better error handling
      const result = await safeApiCall(
        () => recruiterSendEmail(token, {
          candidate_name: emailTarget.name || emailTarget.candidate_name || '',
          candidate_email: emailAddr.trim(),
          cv_text: emailTarget.cv_text || '',
          job_description: jdText,
          template_id: Number(emailTplId),
          job_id: selectedJob?.id || null,
          sender_email: senderEmail.trim(),
        }),
        'Send Email',
        { logContext: { recipient: emailAddr, template: emailTplId } }
      )
      
      if (result) {
        toast.success('Email sent successfully')
        setEmailModal(false)
      }
    } catch (err) {
      // Use utility function to format error message
      const errorMsg = isRateLimitError(err) 
        ? 'Too many emails sent. Please wait a moment.'
        : isValidationError(err)
        ? 'Invalid email or template. Please check and try again.'
        : await formatErrorMessage(err, 'Failed to send email')
      
      toast.error(errorMsg)
      logger.warn('email_send_failed', { error: err.message, email: emailAddr })
    } finally {
      setEmailSending(false)
    }
  }

  /* create template */
  async function handleCreateTemplate(e) {
    e.preventDefault()
    if (!tplForm.name.trim() || !tplForm.body.trim()) return
    try {
      await recruiterCreateTemplate(token, tplForm)
      toast.success('Template created')
      setTplForm({ name: '', template_type: 'accept', subject: '', body: '' })
      // reload
      const data = await recruiterListTemplates(token)
      setTemplates(Array.isArray(data) ? data : data?.templates || [])
    } catch (err) {
      toast.error(err.message)
    }
  }

  /* delete template */
  async function handleDeleteTemplate(id) {
    try {
      await recruiterDeleteTemplate(token, id)
      setTemplates(prev => prev.filter(t => t.id !== id))
      toast.success('Template deleted')
    } catch (err) {
      toast.error(err.message)
    }
  }

  /* preview template */
  async function handlePreviewTemplate(tpl) {
    try {
      const data = await recruiterPreviewTemplate(token, {
        template_id: tpl.id,
        candidate_name: 'Jane Doe',
        candidate_email: 'jane@example.com',
        cv_text: 'Sample CV text',
        job_description: jdText || 'Sample position',
      })
      setTplPreview(data)
    } catch (err) {
      toast.error(err.message)
    }
  }

  /* ─── filtered & sorted ranked list ───────────────────────── */
  const displayRanked = (() => {
    let list = [...ranked]
    if (activeFilter === 'high')   list = list.filter(c => c.final_score >= 75)
    if (activeFilter === 'medium') list = list.filter(c => c.final_score >= 50 && c.final_score < 75)
    if (activeFilter === 'low')    list = list.filter(c => c.final_score < 50)
    list.sort((a, b) => sortDir === 'desc' ? b.final_score - a.final_score : a.final_score - b.final_score)
    return list
  })()

  const filterChips = [
    { id: 'all',    label: 'All',        count: ranked.length },
    { id: 'high',   label: 'High ≥75%',  count: ranked.filter(c => c.final_score >= 75).length,              variant: 'high' },
    { id: 'medium', label: 'Medium',      count: ranked.filter(c => c.final_score >= 50 && c.final_score < 75).length, variant: 'medium' },
    { id: 'low',    label: 'Low <50%',    count: ranked.filter(c => c.final_score < 50).length,               variant: 'low' },
  ]

  /* ═══════════════════ RENDER ═══════════════════════════════════ */
  return (
    <div className="app-layout">
      <Navbar />
      <main className="main-content" id="main-content">

        {/* ── Header ─────────────────────────────────────────── */}
        <motion.div
          className="recruiter-page-header"
          initial={{ opacity: 0, y: -16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <div className="recruiter-header-icon-wrap">
            <Briefcase size={28} />
          </div>
          <div style={{ flex: 1 }}>
            <h1 className="recruiter-page-title">Recruiter Dashboard</h1>
            <p className="recruiter-page-subtitle">Rank, evaluate, and manage candidates</p>
          </div>
          <motion.button
            className="btn-primary btn-sm"
            onClick={() => setJobModal(true)}
            whileHover={{ scale: 1.04 }}
            whileTap={{ scale: 0.96 }}
          >
            <Plus size={14} /> New Job
          </motion.button>
        </motion.div>

        {/* ── Job Selector ───────────────────────────────────── */}
        {jobs.length > 0 && (
          <motion.div
            className="admin-card"
            variants={fadeUp}
            initial="hidden"
            animate="visible"
            custom={0}
            style={{ padding: '12px 20px' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
              <Briefcase size={16} style={{ color: 'var(--color-accent)', flexShrink: 0 }} />
              <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>Active Job:</span>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {jobs.map(j => (
                  <motion.button
                    key={j.id}
                    className={`btn-outline btn-sm ${selectedJob?.id === j.id ? 'btn-active' : ''}`}
                    onClick={() => setSelectedJob(j)}
                    whileHover={{ scale: 1.03 }}
                    whileTap={{ scale: 0.97 }}
                    style={selectedJob?.id === j.id ? { background: 'var(--color-accent)', color: '#fff', borderColor: 'var(--color-accent)' } : {}}
                  >
                    {j.title}
                  </motion.button>
                ))}
              </div>
            </div>
          </motion.div>
        )}

        {/* ── Tabs ───────────────────────────────────────────── */}
        <motion.div
          className="admin-card"
          variants={fadeUp}
          initial="hidden"
          animate="visible"
          custom={1}
          style={{ padding: '8px 16px' }}
        >
          <div style={{ display: 'flex', gap: 4 }}>
            {TABS.map(tab => {
              const Icon = tab.icon
              const active = activeTab === tab.id
              return (
                <motion.button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className="btn-ghost"
                  whileHover={{ scale: 1.03 }}
                  whileTap={{ scale: 0.97 }}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    padding: '10px 18px', borderRadius: 8, fontSize: '0.875rem', fontWeight: 600,
                    background: active ? 'var(--color-accent)' : 'transparent',
                    color: active ? '#fff' : 'var(--color-text-secondary)',
                    transition: 'all 0.2s',
                  }}
                >
                  <Icon size={15} /> {tab.label}
                </motion.button>
              )
            })}
          </div>
        </motion.div>

        {/* ═══════ TAB: RANK ═══════════════════════════════════ */}
        <AnimatePresence mode="wait">
          {activeTab === 'rank' && (
            <motion.div key="rank" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }} transition={{ duration: 0.3 }}>

              {/* Camera Scan Banner */}
              <motion.div
                variants={fadeUp} initial="hidden" animate="visible" custom={1}
                onClick={() => setScanModal(true)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 16,
                  padding: '18px 22px', borderRadius: 14,
                  border: '2px solid #a78bfa',
                  background: 'linear-gradient(135deg, rgba(139,92,246,0.15), rgba(99,102,241,0.10))',
                  cursor: 'pointer', marginBottom: 20,
                  transition: 'all 0.2s',
                  boxShadow: '0 2px 12px rgba(139,92,246,0.15)',
                }}
                whileHover={{ scale: 1.01, boxShadow: '0 4px 20px rgba(139,92,246,0.25)' }}
              >
                <Camera size={32} style={{ color: '#a78bfa', flexShrink: 0 }} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 700, fontSize: 16, color: '#c4b5fd' }}>
                    📷 {t('recruiter.scan_cv') || 'Scan Physical CV'}
                  </div>
                  <div style={{ fontSize: 13, color: '#94a3b8', marginTop: 3 }}>
                    {t('recruiter.scan_cv_desc') || 'Use camera to capture a paper CV → instant OCR + ATS analysis + PDF export'}
                  </div>
                </div>
                <ChevronDown size={20} style={{ color: '#a78bfa', transform: 'rotate(-90deg)' }} />
              </motion.div>

              {/* Job Description Input */}
              <motion.div className="admin-card" variants={fadeUp} initial="hidden" animate="visible" custom={2}>
                <div className="admin-card-header">
                  <FileText size={18} className="admin-card-icon" />
                  <h2>Job Description</h2>
                </div>
                <textarea
                  className="recruiter-textarea"
                  value={jdText}
                  onChange={e => setJdText(e.target.value)}
                  rows={5}
                  placeholder="Paste the job description here..."
                  style={{ width: '100%', marginTop: 8 }}
                />
              </motion.div>

              {/* CV Entries */}
              <motion.div className="admin-card" variants={fadeUp} initial="hidden" animate="visible" custom={3}>
                <div className="admin-card-header">
                  <Users size={18} className="admin-card-icon" />
                  <h2>Candidates ({cvEntries.length})</h2>
                  <motion.button
                    className="btn-outline btn-sm"
                    onClick={() => setCvModal(true)}
                    whileHover={{ scale: 1.04 }}
                    whileTap={{ scale: 0.96 }}
                  >
                    <Plus size={14} /> Add CV
                  </motion.button>
                </div>

                {cvEntries.length > 0 && (
                  <div className="admin-table-wrapper" style={{ marginTop: 12 }}>
                    <table className="data-table data-table-elite admin-table">
                      <thead><tr><th>#</th><th>Name</th><th>Email</th><th>CV Length</th><th></th></tr></thead>
                      <tbody>
                        {cvEntries.map((c, i) => (
                          <tr key={i}>
                            <td>{i + 1}</td>
                            <td className="candidate-name">{c.name || '-'}</td>
                            <td className="text-muted">{c.email || '-'}</td>
                            <td className="text-muted">{c.cv_text.length} chars</td>
                            <td>
                              <button className="btn-ghost btn-sm" onClick={() => setCvEntries(prev => prev.filter((_, j) => j !== i))}>
                                <X size={14} />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
                  <motion.button
                    className="btn-primary"
                    onClick={handleRank}
                    disabled={rankLoading}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                  >
                    {rankLoading ? <span className="spin-icon">&#9203;</span> : <Trophy size={16} />}
                    {rankLoading ? 'Ranking...' : 'Rank Candidates'}
                  </motion.button>
                </div>
              </motion.div>

              {/* Ranked Results */}
              <AnimatePresence>
                {ranked.length > 0 && (
                  <motion.div
                    className="admin-card"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                  >
                    <div className="admin-card-header">
                      <Trophy size={18} className="admin-card-icon" />
                      <h2>Ranking Results</h2>
                      <motion.button
                        className="btn-ghost btn-sm"
                        onClick={() => setSortDir(d => d === 'desc' ? 'asc' : 'desc')}
                        whileHover={{ scale: 1.05 }}
                      >
                        {sortDir === 'desc' ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
                        Sort
                      </motion.button>
                    </div>

                    <FilterChips
                      chips={filterChips}
                      active={activeFilter}
                      onChange={setActiveFilter}
                      onClear={() => setActiveFilter('all')}
                      label="Filter:"
                    />

                    <div className="admin-table-wrapper" style={{ marginTop: 12 }}>
                      <table className="data-table data-table-elite admin-table">
                        <thead>
                          <tr>
                            <th>#</th>
                            <th>Candidate</th>
                            <th>Score</th>
                            <th>ATS</th>
                            <th>Strengths</th>
                            <th>Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          <AnimatePresence mode="popLayout">
                            {displayRanked.map((c, i) => (
                              <motion.tr
                                key={`${c.name}-${i}`}
                                initial={{ opacity: 0, x: -8 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: 8 }}
                                transition={{ delay: i * 0.03, duration: 0.25 }}
                              >
                                <td>
                                  <span className={`rank-num ${i === 0 ? 'gold' : i === 1 ? 'silver' : i === 2 ? 'bronze' : ''}`}>
                                    {i + 1}
                                  </span>
                                </td>
                                <td className="candidate-name">{c.candidate_name || `Candidate ${i + 1}`}</td>
                                <td>
                                  <span
                                    className="score-badge-lg"
                                    style={{ color: getScoreColor(c.final_score), fontFamily: "'JetBrains Mono', monospace" }}
                                  >
                                    {Math.round(c.final_score)}%
                                  </span>
                                </td>
                                <td style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.85rem' }}>
                                  {Math.round(c.ats_score || 0)}%
                                </td>
                                <td>
                                  {c.strengths?.slice(0, 2).map((s, si) => (
                                    <span key={si} style={{ display: 'inline-block', padding: '2px 8px', borderRadius: 6, background: '#22c55e18', color: '#22c55e', fontSize: '0.75rem', marginRight: 4 }}>
                                      {s}
                                    </span>
                                  ))}
                                </td>
                                <td>
                                  <div style={{ display: 'flex', gap: 4, flexWrap: 'nowrap' }}>
                                    <motion.button className="btn-outline btn-sm" onClick={() => handlePreview(c)} whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} title="Preview">
                                      <Eye size={13} />
                                    </motion.button>
                                    <motion.button
                                      className="btn-outline btn-sm"
                                      onClick={() => handleAction(c, 'accepted')}
                                      whileHover={{ scale: 1.05 }}
                                      whileTap={{ scale: 0.95 }}
                                      title="Accept"
                                      style={c._action === 'accepted' ? { background: '#22c55e', color: '#fff', borderColor: '#22c55e' } : {}}
                                    >
                                      <ThumbsUp size={13} />
                                    </motion.button>
                                    <motion.button
                                      className="btn-outline btn-sm"
                                      onClick={() => handleAction(c, 'rejected')}
                                      whileHover={{ scale: 1.05 }}
                                      whileTap={{ scale: 0.95 }}
                                      title="Reject"
                                      style={c._action === 'rejected' ? { background: '#ef4444', color: '#fff', borderColor: '#ef4444' } : {}}
                                    >
                                      <ThumbsDown size={13} />
                                    </motion.button>
                                    <motion.button className="btn-outline btn-sm" onClick={() => openEmailModal(c)} whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} title="Send Email">
                                      <Mail size={13} />
                                    </motion.button>
                                  </div>
                                </td>
                              </motion.tr>
                            ))}
                          </AnimatePresence>
                        </tbody>
                      </table>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          )}

          {/* ═══════ TAB: ACTIONS ════════════════════════════════ */}
          {activeTab === 'actions' && (
            <motion.div key="actions" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }} transition={{ duration: 0.3 }}>
              <motion.div className="admin-card" variants={fadeUp} initial="hidden" animate="visible" custom={2}>
                <div className="admin-card-header">
                  <FileText size={18} className="admin-card-icon" />
                  <h2>Candidate Decisions {selectedJob ? `— ${selectedJob.title}` : ''}</h2>
                </div>
                {!selectedJob ? (
                  <div className="empty-state" style={{ padding: '32px 0' }}>
                    <div className="empty-icon">&#128188;</div>
                    <h3>Select a Job</h3>
                    <p>Choose a job from the selector above to view decisions</p>
                  </div>
                ) : actionsLoading ? (
                  <p style={{ padding: 16, color: 'var(--color-text-secondary)' }}>Loading...</p>
                ) : actions.length === 0 ? (
                  <div className="empty-state" style={{ padding: '32px 0' }}>
                    <div className="empty-icon">&#128203;</div>
                    <h3>No decisions yet</h3>
                    <p>Accept or reject candidates from the Rank tab</p>
                  </div>
                ) : (
                  <div className="admin-table-wrapper" style={{ marginTop: 12 }}>
                    <table className="data-table data-table-elite admin-table">
                      <thead><tr><th>Candidate</th><th>Email</th><th>Score</th><th>Decision</th><th>Email Sent</th><th>Date</th></tr></thead>
                      <tbody>
                        {actions.map((a, i) => (
                          <motion.tr
                            key={a.id || i}
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ delay: i * 0.03 }}
                          >
                            <td className="candidate-name">{a.candidate_name || '-'}</td>
                            <td className="text-muted">{a.candidate_email || '-'}</td>
                            <td>
                              <span style={{ color: getScoreColor(a.final_score || 0), fontFamily: "'JetBrains Mono', monospace" }}>
                                {Math.round(a.final_score || 0)}%
                              </span>
                            </td>
                            <td>
                              <span style={{
                                padding: '3px 10px', borderRadius: 6, fontWeight: 600, fontSize: '0.8rem',
                                background: a.action === 'accepted' ? '#22c55e18' : a.action === 'rejected' ? '#ef444418' : '#eab30818',
                                color: a.action === 'accepted' ? '#22c55e' : a.action === 'rejected' ? '#ef4444' : '#eab308',
                              }}>
                                {a.action}
                              </span>
                            </td>
                            <td>
                              {a.email_sent ? (
                                <Check size={14} style={{ color: '#22c55e' }} />
                              ) : (
                                <X size={14} style={{ color: 'var(--color-text-secondary)', opacity: 0.4 }} />
                              )}
                            </td>
                            <td className="text-muted">{a.created_at ? new Date(a.created_at).toLocaleDateString() : '-'}</td>
                          </motion.tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </motion.div>
            </motion.div>
          )}

          {/* ═══════ TAB: TEMPLATES ═════════════════════════════ */}
          {activeTab === 'templates' && (
            <motion.div key="templates" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }} transition={{ duration: 0.3 }}>

              {/* Create Template Form */}
              <motion.div className="admin-card" variants={fadeUp} initial="hidden" animate="visible" custom={2}>
                <div className="admin-card-header">
                  <Plus size={18} className="admin-card-icon" />
                  <h2>Create Email Template</h2>
                </div>
                <form onSubmit={handleCreateTemplate} style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 12 }}>
                  <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                    <input
                      className="admin-input"
                      placeholder="Template name"
                      value={tplForm.name}
                      onChange={e => setTplForm(f => ({ ...f, name: e.target.value }))}
                      style={{ flex: 1, minWidth: 180 }}
                    />
                    <select
                      className="admin-input"
                      value={tplForm.template_type}
                      onChange={e => setTplForm(f => ({ ...f, template_type: e.target.value }))}
                      style={{ width: 140 }}
                    >
                      <option value="accept">Accept</option>
                      <option value="reject">Reject</option>
                      <option value="custom">Custom</option>
                    </select>
                  </div>
                  <input
                    className="admin-input"
                    placeholder="Email subject — use {candidate_name}, {position}, etc."
                    value={tplForm.subject}
                    onChange={e => setTplForm(f => ({ ...f, subject: e.target.value }))}
                  />
                  <textarea
                    className="recruiter-textarea"
                    placeholder={'Email body — variables: {candidate_name}, {candidate_email}, {position}, {company}, {score}, {top_skills}'}
                    value={tplForm.body}
                    onChange={e => setTplForm(f => ({ ...f, body: e.target.value }))}
                    rows={6}
                  />
                  <motion.button className="btn-primary btn-sm" type="submit" whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} style={{ alignSelf: 'flex-start' }}>
                    <Plus size={14} /> Create Template
                  </motion.button>
                </form>
              </motion.div>

              {/* Template List */}
              <motion.div className="admin-card" variants={fadeUp} initial="hidden" animate="visible" custom={3}>
                <div className="admin-card-header">
                  <Mail size={18} className="admin-card-icon" />
                  <h2>Templates ({templates.length})</h2>
                </div>
                {tplLoading ? (
                  <p style={{ padding: 16, color: 'var(--color-text-secondary)' }}>Loading...</p>
                ) : templates.length === 0 ? (
                  <div className="empty-state" style={{ padding: '32px 0' }}>
                    <div className="empty-icon">&#128231;</div>
                    <h3>No templates yet</h3>
                    <p>Create your first email template above</p>
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 12 }}>
                    {templates.map(tpl => (
                      <motion.div
                        key={tpl.id}
                        style={{
                          padding: '14px 18px', borderRadius: 10, border: '1px solid var(--color-border)',
                          background: 'var(--color-surface)',
                        }}
                        whileHover={{ y: -2 }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
                          <div>
                            <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>{tpl.name}</div>
                            <span style={{
                              display: 'inline-block', marginTop: 4, padding: '2px 8px', borderRadius: 6,
                              fontSize: '0.75rem', fontWeight: 600,
                              background: tpl.template_type === 'accept' ? '#22c55e18' : tpl.template_type === 'reject' ? '#ef444418' : '#6366f118',
                              color: tpl.template_type === 'accept' ? '#22c55e' : tpl.template_type === 'reject' ? '#ef4444' : '#6366f1',
                            }}>
                              {tpl.template_type}
                            </span>
                            <div className="text-muted" style={{ marginTop: 6, fontSize: '0.85rem' }}>
                              Subject: {tpl.subject || '(no subject)'}
                            </div>
                          </div>
                          <div style={{ display: 'flex', gap: 4 }}>
                            <motion.button className="btn-outline btn-sm" onClick={() => handlePreviewTemplate(tpl)} whileHover={{ scale: 1.05 }} title="Preview">
                              <Eye size={13} />
                            </motion.button>
                            <motion.button className="btn-outline btn-sm" onClick={() => handleDeleteTemplate(tpl.id)} whileHover={{ scale: 1.05 }} title="Delete" style={{ color: '#ef4444' }}>
                              <Trash2 size={13} />
                            </motion.button>
                          </div>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                )}
              </motion.div>

              {/* Template Preview */}
              <AnimatePresence>
                {tplPreview && (
                  <motion.div
                    className="admin-card"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                  >
                    <div className="admin-card-header">
                      <Eye size={18} className="admin-card-icon" />
                      <h2>Template Preview</h2>
                      <button className="btn-ghost btn-sm" onClick={() => setTplPreview(null)}><X size={14} /></button>
                    </div>
                    <div style={{ padding: 16, background: 'var(--color-bg)', borderRadius: 8, marginTop: 12 }}>
                      <div style={{ fontWeight: 600, marginBottom: 8 }}>Subject: {tplPreview.rendered_subject}</div>
                      <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{tplPreview.rendered_body}</div>
                      {tplPreview.missing_vars?.length > 0 && (
                        <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 6, color: '#eab308', fontSize: '0.85rem' }}>
                          <AlertTriangle size={14} /> Missing variables: {tplPreview.missing_vars.join(', ')}
                        </div>
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ═══════ MODALS ════════════════════════════════════════ */}

        {/* Create Job Modal */}
        <Modal open={jobModal} onClose={() => setJobModal(false)} title="Create New Job">
          <form onSubmit={handleCreateJob} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <input className="admin-input" placeholder="Job title" value={jobForm.title} onChange={e => setJobForm(f => ({ ...f, title: e.target.value }))} />
            <textarea className="recruiter-textarea" placeholder="Job description (optional)" value={jobForm.description} onChange={e => setJobForm(f => ({ ...f, description: e.target.value }))} rows={4} />
            <motion.button className="btn-primary" type="submit" whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
              <Plus size={16} /> Create Job
            </motion.button>
          </form>
        </Modal>

        {/* Add CV Modal */}
        <Modal open={cvModal} onClose={() => setCvModal(false)} title="Add Candidate CV">
          <form onSubmit={handleAddCv} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <input className="admin-input" placeholder="Candidate name" value={cvDraft.name} onChange={e => setCvDraft(d => ({ ...d, name: e.target.value }))} />
            <input className="admin-input" placeholder="Candidate email" value={cvDraft.email} onChange={e => setCvDraft(d => ({ ...d, email: e.target.value }))} type="email" />
            <textarea className="recruiter-textarea" placeholder="Paste CV text here..." value={cvDraft.cv_text} onChange={e => setCvDraft(d => ({ ...d, cv_text: e.target.value }))} rows={8} />
            <motion.button className="btn-primary" type="submit" whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
              <Plus size={16} /> Add CV
            </motion.button>
          </form>
        </Modal>

        {/* Send Email Modal */}
        <Modal open={emailModal} onClose={() => setEmailModal(false)} title={`Send Email to ${emailTarget?.name || emailTarget?.candidate_name || 'Candidate'}`}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <label style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: 6, display: 'block' }}>Your Email (Sender / Reply-To)</label>
              <input className="admin-input" type="email" placeholder="your@email.com" value={senderEmail} onChange={e => setSenderEmail(e.target.value)} style={{ width: '100%' }} />
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4, display: 'block' }}>Candidates will reply to this address</span>
            </div>
            <div>
              <label style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: 6, display: 'block' }}>Candidate Email</label>
              <input className="admin-input" type="email" placeholder="candidate@example.com" value={emailAddr} onChange={e => setEmailAddr(e.target.value)} style={{ width: '100%' }} />
            </div>
            <div>
              <label style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: 6, display: 'block' }}>Select Template</label>
              <select className="admin-input" value={emailTplId} onChange={e => setEmailTplId(e.target.value)} style={{ width: '100%' }}>
                <option value="">-- Choose template --</option>
                {templates.map(tpl => (
                  <option key={tpl.id} value={tpl.id}>{tpl.name} ({tpl.template_type})</option>
                ))}
              </select>
            </div>
            {!templates.length && (
              <p className="text-muted" style={{ fontSize: '0.85rem' }}>
                No templates available. Create one in the Email Templates tab first.
              </p>
            )}
            <motion.button
              className="btn-primary"
              onClick={handleSendEmail}
              disabled={emailSending || !emailTplId}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              {emailSending ? <span className="spin-icon">&#9203;</span> : <Send size={16} />}
              {emailSending ? 'Sending...' : 'Send Email'}
            </motion.button>
          </div>
        </Modal>

        {/* Candidate Preview Modal */}
        <Modal open={previewOpen} onClose={() => setPreviewOpen(false)} title="Candidate Preview">
          {previewData && (
            <div className="modal-detail">
              <div className="modal-score-row">
                <ScoreCircle score={Math.round(previewData.preview?.score || previewData.final_score || 0)} size={100} />
                <div>
                  <h3>{previewData.preview?.name || previewData.name || 'Unknown'}</h3>
                  {previewData.preview?.email && (
                    <p className="text-muted" style={{ fontSize: '0.85rem' }}>{previewData.preview.email}</p>
                  )}
                  {previewData.preview?.summary && (
                    <p style={{ marginTop: 6, fontSize: '0.9rem', lineHeight: 1.5 }}>{previewData.preview.summary}</p>
                  )}
                </div>
              </div>

              {/* Strengths */}
              {previewData.strengths?.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <h4 style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
                    <ThumbsUp size={15} style={{ color: '#22c55e' }} /> Strengths
                  </h4>
                  <ul style={{ paddingLeft: 20, margin: 0 }}>
                    {previewData.strengths.map((s, i) => (
                      <li key={i} style={{ color: '#22c55e', marginBottom: 4, fontSize: '0.9rem' }}>{s}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Weaknesses */}
              {previewData.weaknesses?.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <h4 style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
                    <AlertTriangle size={15} style={{ color: '#ef4444' }} /> Areas for Improvement
                  </h4>
                  <ul style={{ paddingLeft: 20, margin: 0 }}>
                    {previewData.weaknesses.map((w, i) => (
                      <li key={i} style={{ color: '#ef4444', marginBottom: 4, fontSize: '0.9rem' }}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Top Skills */}
              {previewData.preview?.top_skills?.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <h4 style={{ marginBottom: 8 }}>Top Skills</h4>
                  <SkillTags skills={previewData.preview.top_skills} variant="normal" />
                </div>
              )}

              {/* Experience */}
              {previewData.preview?.last_experience && (
                <div style={{ marginTop: 16 }}>
                  <h4 style={{ marginBottom: 8 }}>Latest Experience</h4>
                  <p style={{ fontSize: '0.9rem', lineHeight: 1.5 }}>{previewData.preview.last_experience}</p>
                </div>
              )}

              {/* Education */}
              {previewData.preview?.education && (
                <div style={{ marginTop: 16 }}>
                  <h4 style={{ marginBottom: 8 }}>Education</h4>
                  <p style={{ fontSize: '0.9rem', lineHeight: 1.5 }}>{previewData.preview.education}</p>
                </div>
              )}
            </div>
          )}
        </Modal>

        {/* Camera Scan Modal */}
        <CameraScanModal open={scanModal} onClose={() => setScanModal(false)} />

      </main>
    </div>
  )
}
