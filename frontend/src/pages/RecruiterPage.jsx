import React, { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Users, TrendingUp, Trophy, Search, ArrowUpDown, ChevronUp, ChevronDown,
  Download, Eye, Upload, X, Sparkles, BarChart3, Mail, Plus, Trash2,
  FileText, Send, ThumbsUp, ThumbsDown, AlertTriangle, Briefcase, Check, Camera,
  CheckSquare, Square, Loader, FileJson, FileSpreadsheet,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { useRecruiterSession } from '../context/RecruiterSessionContext'
import Navbar from '../components/Navbar'
import ScoreCircle from '../components/ScoreCircle'
import Modal from '../components/Modal'
import ScoreBars from '../components/ScoreBars'
import SkillTags from '../components/SkillTags'
import SkeletonLoader from '../components/SkeletonLoader'
import FilterChips from '../components/FilterChips'
import { useToast } from '../components/Toast'
import EnhancedCandidatePreview from '../components/EnhancedCandidatePreview'
import {
  fetchCandidates, fetchTopCandidates, searchRecruiter,
  fetchRecruiterCandidateDetail, recruiterBatchRank,
  recruiterCreateJob, recruiterListJobs,
  recruiterDashboardRank, recruiterDashboardPreview,
  recruiterDashboardAction, recruiterDashboardActions,
  recruiterCreateTemplate, recruiterListTemplates, recruiterDeleteTemplate,
  recruiterPreviewTemplate, recruiterSendEmail,
  recruiterUpdateActionStage,
  recruiterScanCV,
  recruiterSendEmailBulk,
  recruiterExportRankings,
  recruiterExportCandidates,
} from '../api'
import {
  exportBatchToCSV, exportBatchToHTML, exportBatchToJSON,
  exportDecisionsToCSV, exportUsageStatsToCSV
} from '../utils/exportUtils'
import CameraScanModal from '../components/CameraScanModal'
import BatchUploadModal from '../components/BatchUploadModal'

function SortIcon({ sortKey, sortConfig }) {
  if (sortConfig.key !== sortKey) return <ArrowUpDown size={13} className="sort-icon" />
  return sortConfig.direction === 'asc'
    ? <ChevronUp size={13} className="sort-icon sorted" style={{ color: 'var(--color-accent)', opacity: 1 }} />
    : <ChevronDown size={13} className="sort-icon sorted" style={{ color: 'var(--color-accent)', opacity: 1 }} />
}

function SortHeader({ sortKey, sortConfig, onSort, children }) {
  const isSorted = sortConfig.key === sortKey
  const ariaSort = isSorted
    ? (sortConfig.direction === 'asc' ? 'ascending' : 'descending')
    : 'none'

  return (
    <th className={`th-sortable ${isSorted ? 'sorted' : ''}`} aria-sort={ariaSort}>
      <button
        type="button"
        className="th-sort-button"
        onClick={() => onSort(sortKey)}
      >
        <span className="th-inner">
          {children} <SortIcon sortKey={sortKey} sortConfig={sortConfig} />
        </span>
      </button>
    </th>
  )
}

function getScoreColor(score) {
  if (score >= 75) return 'var(--status-success)'
  if (score >= 50) return 'var(--status-warning)'
  return 'var(--status-danger)'
}

function assessJobDescriptionQuality(text) {
  const value = String(text || '').trim()
  if (!value) return { status: 'missing', valid: false, reason: 'empty', word_count: 0 }

  const tokens = value.match(/[\p{L}0-9+#.]{2,}/gu) || []
  const lower = value.toLowerCase()
  const roleTerms = [
    'developer', 'engineer', 'analyst', 'manager', 'designer', 'intern', 'specialist',
    'consultant', 'assistant', 'coordinator', 'architect', 'technician', 'administrator',
    'backend', 'frontend', 'fullstack', 'full-stack', 'software', 'data', 'devops',
    'qa', 'tester', 'sales', 'marketing', 'teacher', 'nurse', 'accountant', 'product',
    'recruiter', 'junior', 'senior', 'lead', 'muhendis', 'gelistirici', 'uzman',
    'stajyer', 'analist', 'tasarimci', 'yonetici', 'ogretmen', 'hemsire', 'satis',
  ]
  const knownSkillTerms = [
    'python', 'java', 'javascript', 'typescript', 'react', 'node', 'sql', 'docker',
    'aws', 'azure', 'kubernetes', 'excel', 'powerbi', 'figma', 'php', 'c++', 'c#',
  ]
  const hasRole = roleTerms.some(term => new RegExp(`\\b${term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'i').test(lower))
  const hasSkill = knownSkillTerms.some(term => lower.includes(term))
  const alphaTokens = tokens.filter(tok => /\p{L}/u.test(tok))
  const meaningfulAlpha = alphaTokens.filter(tok => /[aeiou]/i.test(tok) || ['qa', 'hr', 'ui', 'ux', 'c++', 'c#'].includes(tok.toLowerCase()))

  if (!hasRole && !hasSkill && tokens.length < 4) {
    return { status: 'invalid', valid: false, reason: 'too_short_without_role_or_skill', word_count: tokens.length }
  }
  if (!hasRole && !hasSkill && alphaTokens.length > 0 && meaningfulAlpha.length === 0) {
    return { status: 'invalid', valid: false, reason: 'gibberish_like_text', word_count: tokens.length }
  }
  if (tokens.length < 15) {
    return { status: 'weak', valid: true, reason: 'too_short_for_reliable_matching', word_count: tokens.length }
  }
  return { status: 'ok', valid: true, reason: 'ok', word_count: tokens.length }
}

function getJdQualityMeta(quality) {
  const status = quality?.status
  if (status === 'invalid') {
    return {
      level: 'invalid',
      label: 'Invalid JD',
      title: 'Job description is invalid',
      message: 'Enter a real role description before ranking candidates. Match scores are disabled for meaningless text.',
      color: 'var(--status-danger)',
      background: 'var(--status-danger-bg)',
      border: 'var(--status-danger-border)',
    }
  }
  if (status === 'weak') {
    return {
      level: 'weak',
      label: 'Weak JD',
      title: 'Job description is too short',
      message: 'Add responsibilities, required skills, seniority, and role context. Match scores may be capped.',
      color: 'var(--status-warning)',
      background: 'var(--status-warning-bg)',
      border: 'var(--status-warning-border)',
    }
  }
  return null
}

function getBatchJdQuality(batchResult) {
  if (batchResult?.job_description_quality?.status) return batchResult.job_description_quality
  const row = (batchResult?.ranking || []).find(item => item?.job_description_quality?.status)
  return row?.job_description_quality || null
}

function getRowJdQuality(row, batchResult) {
  return row?.job_description_quality?.status ? row.job_description_quality : getBatchJdQuality(batchResult)
}

function SkeletonTableRows({ count = 5 }) {
  return Array.from({ length: count }).map((_, i) => (
    <tr key={i} className="skeleton-row">
      <td><div className="skeleton skeleton-line" style={{ width: 24, height: 14 }} /></td>
      <td><div className="skeleton skeleton-line" style={{ width: '80%', height: 14 }} /></td>
      <td><div className="skeleton skeleton-line" style={{ width: 50, height: 14 }} /></td>
      <td><div className="skeleton skeleton-line" style={{ width: 80, height: 14 }} /></td>
      <td><div className="skeleton skeleton-line" style={{ width: 60, height: 28, borderRadius: 6 }} /></td>
    </tr>
  ))
}

export default function RecruiterPage() {
  const { t } = useLanguage()
  const { token, user } = useAuth()
  const toast = useToast()
  const recruiterSession = useRecruiterSession()

  const [candidates,    setCandidates]    = useState([])
  const [topCandidates, setTopCandidates] = useState([])
  const [selected,      setSelected]      = useState(null)
  const [loading,       setLoading]       = useState(true)
  const [error,         setError]         = useState(null)
  const [searchQuery,   setSearchQuery]   = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [jdText,        setJdText]        = useState('')
  const [jdFile,        setJdFile]        = useState(null)
  const [cvFiles,       setCvFiles]       = useState([])
  const [batchLoading,  setBatchLoading]  = useState(false)
  const [batchProgress, setBatchProgress] = useState({ processed: 0, total: 0 }) // Track batch progress
  const [batchResult,   setBatchResult]   = useState(null)
  const [sortConfig,    setSortConfig]    = useState({ key: 'score', direction: 'desc' })
  const [activeFilter,  setActiveFilter]  = useState('all')
  const [exportMenuOpen, setExportMenuOpen] = useState(false)
  const [dbExportOpen, setDbExportOpen] = useState(false)

  // ── Dashboard state ──────────────────────────────────────────────────────────
  const [activeSection, setActiveSection] = useState('overview') // overview | decisions | templates
  const [jobs, setJobs]                   = useState([])
  const [selectedJob, setSelectedJob]     = useState(null)
  const [jobModal, setJobModal]           = useState(false)
  const [jobForm, setJobForm]             = useState({ title: '', description: '' })

  // candidate actions from ranking
  const [candidateActions, setCandidateActions] = useState({}) // { name: 'accepted'|'rejected' }
  const [previewData, setPreviewData]     = useState(null)
  const [previewOpen, setPreviewOpen]     = useState(false)

  // decisions tab
  const [actions, setActions]             = useState([])
  const [actionsLoading, setActionsLoading] = useState(false)

  // email templates
  const [templates, setTemplates]         = useState([])
  const [tplLoading, setTplLoading]       = useState(false)
  const [tplForm, setTplForm]             = useState({ name: '', template_type: 'accept', subject: '', body: '' })
  const [tplPreview, setTplPreview]       = useState(null)

  // camera scan
  const [scanModal, setScanModal]         = useState(false)
  const [batchUploadOpen, setBatchUploadOpen] = useState(false)

  // decision feedback modal
  const [actionModal, setActionModal]     = useState({ open: false, candidate: null, action: null, message: '' })

  // bulk selection
  const [bulkSelected, setBulkSelected]   = useState(new Set())
  const [bulkProcessing, setBulkProcessing] = useState(false)
  const [bulkSending, setBulkSending]     = useState(false)
  const [bulkProgress, setBulkProgress]   = useState([])  // [{name, email, status:'pending'|'sending'|'sent'|'error', error?}]
  const [bulkEmailModal, setBulkEmailModal] = useState(false)
  const [bulkEmailTplId, setBulkEmailTplId] = useState('')
  const [bulkSenderEmail, setBulkSenderEmail] = useState('')

  // email send
  const [emailModal, setEmailModal]       = useState(false)
  const [emailTarget, setEmailTarget]     = useState(null)
  const [emailTplId, setEmailTplId]       = useState('')
  const [emailSending, setEmailSending]   = useState(false)
  const [emailAddr, setEmailAddr]         = useState('')
  const [senderEmail, setSenderEmail]     = useState('')

  useEffect(() => {
    document.title = `${t('nav.recruiter')} — CV Analyzer`
  }, [t])

  // Restore batch results from session on mount
  useEffect(() => {
    const savedBatchResults = recruiterSession.loadBatchResults()
    if (savedBatchResults && savedBatchResults.length > 0) {
      // Only restore if we don't have current results
      if (!batchResult) {
        setBatchResult(savedBatchResults[savedBatchResults.length - 1])
      }
    }
    
    const savedActions = recruiterSession.loadCandidateActions()
    if (savedActions && Object.keys(savedActions).length > 0) {
      setCandidateActions(savedActions)
    }
  }, [recruiterSession])

  useEffect(() => {
    let cancelled = false
    async function load() {
      if (!token) { if (!cancelled) { setCandidates([]); setTopCandidates([]); setLoading(false) }; return }
      setLoading(true); setError(null)
      try {
        const [all, top] = await Promise.all([fetchCandidates(token), fetchTopCandidates(token)])
        if (cancelled) return
        setCandidates(Array.isArray(all?.candidates) ? all.candidates : [])
        setTopCandidates(Array.isArray(top?.top_candidates) ? top.top_candidates : [])
      } catch (e) {
        if (!cancelled) setError(e.message || 'Failed to load candidates')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [token])

  // ── Sort & filter ─────────────────────────────────────────────────────────────
  function handleSort(key) {
    setSortConfig(prev => ({ key, direction: prev.key === key && prev.direction === 'desc' ? 'asc' : 'desc' }))
  }

  function getScore(c) { return c.final_score || c.similarity_score || 0 }

  function getSortedFiltered(list) {
    let result = [...list]
    if (activeFilter === 'high')   result = result.filter(c => getScore(c) >= 75)
    if (activeFilter === 'medium') result = result.filter(c => { const s = getScore(c); return s >= 50 && s < 75 })
    if (activeFilter === 'low')    result = result.filter(c => getScore(c) < 50)

    if (sortConfig.key) {
      result.sort((a, b) => {
        let aVal, bVal
        if (sortConfig.key === 'score') { aVal = getScore(a); bVal = getScore(b) }
        else if (sortConfig.key === 'name') {
          aVal = (a.name || a.candidate_name || '').toLowerCase()
          bVal = (b.name || b.candidate_name || '').toLowerCase()
        } else if (sortConfig.key === 'date') {
          aVal = new Date(a.created_at || 0).getTime()
          bVal = new Date(b.created_at || 0).getTime()
        }
        if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1
        if (aVal > bVal) return sortConfig.direction === 'asc' ? 1 : -1
        return 0
      })
    }
    return result
  }

  const displayCandidates = getSortedFiltered(candidates)

  const filterChips = [
    { id: 'all',    label: t('recruiter.filter_all')    || 'All',         count: candidates.length },
    { id: 'high',   label: t('recruiter.filter_high')   || 'High ≥75%',  count: candidates.filter(c => getScore(c) >= 75).length,              variant: 'high' },
    { id: 'medium', label: t('recruiter.filter_medium') || 'Medium',      count: candidates.filter(c => { const s = getScore(c); return s >= 50 && s < 75 }).length, variant: 'medium' },
    { id: 'low',    label: t('recruiter.filter_low')    || 'Low <50%',    count: candidates.filter(c => getScore(c) < 50).length,               variant: 'low' },
  ]

  // ── Search ────────────────────────────────────────────────────────────────────
  async function handleSearch(e) {
    e.preventDefault()
    const q = searchQuery.trim()
    if (!q || !token) { setSearchResults([]); return }
    setError(null)
    try {
      const res = await searchRecruiter(token, q)
      setSearchResults(Array.isArray(res?.results) ? res.results : [])
    } catch (e) {
      setError(e.message || 'Search failed'); setSearchResults([])
    }
  }

  // ── Batch ranking ──────────────────────────────────────────────────────────────
  async function handleBatchRank(e) {
    e.preventDefault()
    if (!token) return
    if (!cvFiles.length) { setError('Select at least one CV PDF'); return }
    if (!jdText.trim() && !jdFile) { setError('Enter job description or upload JD file'); return }
    const preflightJdQuality = jdText.trim() ? assessJobDescriptionQuality(jdText) : null
    const preflightJdMeta = getJdQualityMeta(preflightJdQuality)
    if (preflightJdMeta?.level === 'invalid') {
      setError(preflightJdMeta.message)
      toast.error(preflightJdMeta.message)
      return
    }
    setError(null); setBatchLoading(true); setBatchProgress({ processed: 0, total: cvFiles.length })
    try {
      // Split into batches of 200 CVs to avoid FormData parsing issues
      const BATCH_SIZE = 200
      const allResults = []
      const allSkipped = []
      const allWarnings = []
      let jobDescriptionQuality = preflightJdQuality
      let scoreVersion = ''
      const batches = []
      
      for (let i = 0; i < cvFiles.length; i += BATCH_SIZE) {
        batches.push(cvFiles.slice(i, i + BATCH_SIZE))
      }
      
      for (let batchIdx = 0; batchIdx < batches.length; batchIdx++) {
        const batchFiles = batches[batchIdx]
        
        // Only use jd_file on first batch to avoid duplicate processing
        const jd = batchIdx === 0 ? jdFile : null
        
        const percent = Math.round((batchIdx / batches.length) * 100)
        const processed = batchIdx * BATCH_SIZE
        setBatchProgress({ processed, total: cvFiles.length })
        toast.info(`${percent}% - Batch ${batchIdx + 1}/${batches.length} (${batchFiles.length} CVs)...`)
        
        const result = await recruiterBatchRank(token, { jobDescription: jdText, jdFile: jd, cvFiles: batchFiles })
        
        // Merge results - backend uses 'ranking' not 'ranked'
        if (result.ranking && Array.isArray(result.ranking)) {
          allResults.push(...result.ranking)
        }
        if (Array.isArray(result.warnings)) {
          allWarnings.push(...result.warnings)
        }
        if (result.job_description_quality?.status) {
          jobDescriptionQuality = result.job_description_quality
        } else if (result.ranking?.[0]?.job_description_quality?.status) {
          jobDescriptionQuality = result.ranking[0].job_description_quality
        }
        if (result.score_version) {
          scoreVersion = result.score_version
        } else if (result.ranking?.[0]?.score_version) {
          scoreVersion = result.ranking[0].score_version
        }
        
        // Collect skipped files for feedback
        if (result.skipped_files && Array.isArray(result.skipped_files)) {
          allSkipped.push(...result.skipped_files)
        }
      }
      
      // Create combined result object
      const combinedResult = {
        ranking: allResults,
        total_candidates: allResults.length,
        skipped_count: allSkipped.length,
        skipped_files: allSkipped,
        job_description_preview: jdText.substring(0, 300),
        job_description_quality: jobDescriptionQuality,
        score_version: scoreVersion,
        warnings: [...new Set(allWarnings.filter(Boolean))],
        analytics: {
          avg_score: allResults.length > 0 ? Math.round(allResults.reduce((sum, r) => sum + r.final_score, 0) / allResults.length * 100) / 100 : 0,
          candidate_distribution: {
            high: allResults.filter(r => r.final_score >= 75).length,
            medium: allResults.filter(r => r.final_score >= 50 && r.final_score < 75).length,
            low: allResults.filter(r => r.final_score < 50).length,
          }
        }
      }
      
      setBatchResult(combinedResult)
      setBatchProgress({ processed: cvFiles.length, total: cvFiles.length })
      recruiterSession.saveBatchResult(combinedResult)
      // Also update the main candidates state so the table/stats reflect
      // the newly processed batch (otherwise the Candidates list stays
      // showing only DB-backed records).
      setCandidates(allResults)
      const msg = `Batch ranking completed - ${allResults.length} CVs processed${allSkipped.length > 0 ? `, ${allSkipped.length} skipped` : ''}`
      toast.success(msg)
    } catch (e) {
      setError(e.message || 'Batch ranking failed')
      toast.error(e.message || 'Batch ranking failed')
    } finally {
      setBatchLoading(false)
      setBatchProgress({ processed: 0, total: 0 })
    }
  }

  // ── Export - CSV (Improved format) ──────────────────────────────────────────────
  function handleExportCsv() {
    if (!batchResult) return
    const result = exportBatchToCSV(batchResult)
    if (result.success) {
      toast.success(result.message)
      recruiterSession.updateUsageRights({ exports: { ...recruiterSession.usageRights.exports, used: (recruiterSession.usageRights.exports?.used || 0) + 1 } })
    } else {
      toast.error(result.message)
    }
    setExportMenuOpen(false)
  }

  // ── Export - HTML (Beautiful formatted table) ──────────────────────────────────
  function handleExportHtml() {
    if (!batchResult) return
    const result = exportBatchToHTML(batchResult)
    if (result.success) {
      toast.success(result.message)
      recruiterSession.updateUsageRights({ exports: { ...recruiterSession.usageRights.exports, used: (recruiterSession.usageRights.exports?.used || 0) + 1 } })
    } else {
      toast.error(result.message)
    }
    setExportMenuOpen(false)
  }

  // ── Export - JSON (Complete data) ──────────────────────────────────────────────
  function handleExportJson() {
    if (!batchResult) return
    const result = exportBatchToJSON(batchResult)
    if (result.success) {
      toast.success(result.message)
      recruiterSession.updateUsageRights({ exports: { ...recruiterSession.usageRights.exports, used: (recruiterSession.usageRights.exports?.used || 0) + 1 } })
    } else {
      toast.error(result.message)
    }
    setExportMenuOpen(false)
  }

  // ── Export Decisions - CSV ────────────────────────────────────────────────────
  function handleExportDecisions() {
    const decisionsToExport = recruiterSession.loadDecisions()
    if (!decisionsToExport?.length) {
      toast.error('No decisions to export')
      return
    }
    const result = exportDecisionsToCSV(decisionsToExport)
    if (result.success) {
      toast.success(result.message)
    } else {
      toast.error(result.message)
    }
  }

  // ── Export Usage Stats - CSV ───────────────────────────────────────────────────
  function handleExportUsageStats() {
    const result = exportUsageStatsToCSV(recruiterSession.usageRights)
    if (result.success) {
      toast.success(result.message)
    } else {
      toast.error(result.message)
    }
  }

  const triggerDownload = (blob, filename) => {
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', filename)
    document.body.appendChild(link)
    link.click()
    link.parentNode.removeChild(link)
    window.URL.revokeObjectURL(url)
  }

  async function handleDbExportRankings(format) {
    if (!selectedJob?.id) {
      toast.error('Select a job first')
      return
    }
    try {
      toast.info(`Exporting database rankings as ${format.toUpperCase()}...`)
      const blob = await recruiterExportRankings(token, selectedJob.id, format)
      triggerDownload(blob, `stored_rankings_job_${selectedJob.id}.${format}`)
      toast.success('Export completed successfully')
    } catch (err) {
      toast.error(err.message || 'Export failed')
    }
    setDbExportOpen(false)
  }

  async function handleDbExportCandidates(format) {
    try {
      toast.info(`Exporting database candidates as ${format.toUpperCase()}...`)
      const blob = await recruiterExportCandidates(token, format)
      triggerDownload(blob, `stored_candidates.${format}`)
      toast.success('Export completed successfully')
    } catch (err) {
      toast.error(err.message || 'Export failed')
    }
    setDbExportOpen(false)
  }

  async function openCandidateDetail(candidate) {
    if (!candidate?.analysis_id || !token) { setSelected(candidate); return }
    try {
      const detail = await fetchRecruiterCandidateDetail(token, candidate.analysis_id)
      setSelected({ ...candidate, result: detail })
    } catch { setSelected(candidate) }
  }

  const avgScore = candidates.length
    ? Math.round(candidates.reduce((sum, c) => sum + getScore(c), 0) / candidates.length) : 0
  const distribution = batchResult?.analytics?.candidate_distribution || { high: 0, medium: 0, low: 0 }
  const batchJdQuality = getBatchJdQuality(batchResult)
  const batchJdQualityMeta = getJdQualityMeta(batchJdQuality)
  const draftJdQuality = jdText.trim() ? assessJobDescriptionQuality(jdText) : null
  const draftJdQualityMeta = jdText.trim() ? getJdQualityMeta(draftJdQuality) : null

  // ── Load jobs ───────────────────────────────────────────────────────────────
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

  // ── Load actions for selected job ────────────────────────────────────────────
  useEffect(() => {
    if (activeSection !== 'decisions' || !selectedJob?.id || !token) return
    let cancelled = false
    setActionsLoading(true)
    recruiterDashboardActions(token, selectedJob.id)
      .then(data => { if (!cancelled) setActions(Array.isArray(data) ? data : data?.actions || []) })
      .catch(() => { if (!cancelled) setActions([]) })
      .finally(() => { if (!cancelled) setActionsLoading(false) })
    return () => { cancelled = true }
  }, [activeSection, selectedJob, token])

  // ── Load email templates ────────────────────────────────────────────────────
  useEffect(() => {
    if (activeSection !== 'templates' || !token) return
    let cancelled = false
    setTplLoading(true)
    recruiterListTemplates(token)
      .then(data => { if (!cancelled) setTemplates(Array.isArray(data) ? data : data?.templates || []) })
      .catch(() => { if (!cancelled) setTemplates([]) })
      .finally(() => { if (!cancelled) setTplLoading(false) })
    return () => { cancelled = true }
  }, [activeSection, token])

  async function handleDecisionStageChange(actionId, stage) {
    if (!token || !actionId) return
    try {
      const data = await recruiterUpdateActionStage(token, actionId, { stage })
      const updated = data?.action
      setActions(prev => prev.map(item => item.id === actionId ? { ...item, ...(updated || {}), action: stage, stage } : item))
      toast.success('Pipeline stage updated')
    } catch (err) {
      toast.error(err.message || 'Stage update failed')
    }
  }

  // ── Create job ──────────────────────────────────────────────────────────────
  async function handleCreateJob(e) {
    e.preventDefault()
    if (!jobForm.title.trim()) return
    try {
      await recruiterCreateJob(token, jobForm)
      toast.success('Job created')
      setJobModal(false)
      setJobForm({ title: '', description: '' })
      loadJobs()
    } catch (err) { toast.error(err.message) }
  }

  // ── Accept / Reject candidate ────────────────────────────────────────────────
  function openActionModal(candidate, action) {
    if (!selectedJob?.id) { toast.error('Select a job first'); return }
    let msg = '';
    const strengths = candidate.strengths || candidate.details?.strong_keywords || candidate.details?.skills_found || [];
    const weaknesses = candidate.weaknesses || candidate.missing_skills || candidate.details?.missing_skills || [];
    
    // Filter out numbers
    const validStr = strengths.filter(s => typeof s === 'string' && isNaN(Number(s))).slice(0, 3).join(', ');
    const validWeak = weaknesses.filter(s => typeof s === 'string' && isNaN(Number(s))).slice(0, 3).join(', ');

    if (action === 'accepted') {
      msg = `Tebrikler! Özgeçmişiniz ${selectedJob.title || 'ilgili pozisyon'} ilanımızla yüksek oranda eşleştiği için seçildiniz. Özellikle ${validStr ? validStr + ' gibi ' : ''}nitelikleriniz ve yetkinlikleriniz dikkatimizi çekti.`;
    } else {
      msg = `Üzgünüz, özgeçmişinizi detaylı bir şekilde inceledik ancak bu rol için aradığımız bazı özellikler (${validWeak || 'gerekli teknik yetkinlikler'}) eksik olduğundan sizinle devam edemiyoruz.`;
    }
    
    setActionModal({ open: true, candidate, action, message: msg });
  }

  async function confirmAction() {
    const { candidate, action, message } = actionModal;
    try {
      await recruiterDashboardAction(token, {
        job_id: selectedJob.id,
        candidate_name: candidate.candidate_name || candidate.name || '',
        candidate_email: candidate.email || candidate.candidate_email || '',
        cv_text: candidate.cv_text || '',
        final_score: candidate.final_score ?? null,
        ats_score: candidate.ats_score ?? null,
        action,
        feedback: message
      })
      toast.success(`${candidate.candidate_name || candidate.name || 'Candidate'} ${action}`)
      setCandidateActions(prev => ({ ...prev, [candidate.candidate_name || candidate.name]: action }))
      // Save to session
      recruiterSession.saveCandidateAction(candidate.candidate_name || candidate.name, action)
      recruiterSession.saveDecision({
        candidate_name: candidate.candidate_name || candidate.name || '',
        candidate_email: candidate.email || candidate.candidate_email || '',
        action,
        final_score: candidate.final_score ?? null,
        job_id: selectedJob.id,
        job_title: selectedJob.title,
        feedback: message
      })
      setActionModal(prev => ({ ...prev, open: false }))
    } catch (err) { toast.error(err.message) }
  }

  async function handleCandidateAction(candidate, action) {
    // Only used directly if bypassing modal
    openActionModal(candidate, action);
  }

  // ── Preview candidate with strength/weakness ────────────────────────────────
  async function handleDashboardPreview(candidate) {
    try {
      const data = await recruiterDashboardPreview(token, {
        cv_text: candidate.cv_text || '',
        job_description: jdText,
      })
      
      let pdfUrl = null;
      const fname = candidate.filename || candidate.file_name;
      if (cvFiles && cvFiles.length > 0 && fname) {
        const file = cvFiles.find(f => f.name === fname);
        if (file) {
          pdfUrl = URL.createObjectURL(file);
        }
      }

      setPreviewData({ ...data, ...candidate, pdfUrl })
      setPreviewOpen(true)
    } catch (err) { toast.error(err.message) }
  }

  // ── Open email modal ────────────────────────────────────────────────────────
  function openEmailModal(candidate) {
    setEmailTarget(candidate)
    setEmailTplId('')
    setEmailAddr(candidate.email || candidate.candidate_email || '')
    setSenderEmail(user?.email || '')
    // load templates if not already loaded
    if (!templates.length) {
      recruiterListTemplates(token)
        .then(data => setTemplates(Array.isArray(data) ? data : data?.templates || []))
        .catch(() => {})
    }
    setEmailModal(true)
  }

  // ── Send email ──────────────────────────────────────────────────────────────
  async function handleSendEmail() {
    if (!emailTarget || !emailTplId) { toast.error('Select a template'); return }
    if (!emailAddr.trim()) { toast.error('Enter candidate email address'); return }
    setEmailSending(true)
    try {
      await recruiterSendEmail(token, {
        candidate_name: emailTarget.candidate_name || emailTarget.name || '',
        candidate_email: emailAddr.trim(),
        cv_text: emailTarget.cv_text || '',
        job_description: jdText,
        template_id: Number(emailTplId),
        job_id: selectedJob?.id || null,
        sender_email: senderEmail.trim(),
      })
      toast.success('Email sent successfully')
      setEmailModal(false)
    } catch (err) { toast.error(err.message) }
    finally { setEmailSending(false) }
  }

  // ── Create email template ───────────────────────────────────────────────────
  async function handleCreateTemplate(e) {
    e.preventDefault()
    if (!tplForm.name.trim() || !tplForm.body.trim()) return
    try {
      await recruiterCreateTemplate(token, tplForm)
      toast.success('Template created')
      setTplForm({ name: '', template_type: 'accept', subject: '', body: '' })
      const data = await recruiterListTemplates(token)
      setTemplates(Array.isArray(data) ? data : data?.templates || [])
    } catch (err) { toast.error(err.message) }
  }

  // ── Delete email template ───────────────────────────────────────────────────
  async function handleDeleteTemplate(id) {
    try {
      await recruiterDeleteTemplate(token, id)
      setTemplates(prev => prev.filter(t => t.id !== id))
      toast.success('Template deleted')
    } catch (err) { toast.error(err.message) }
  }

  // ── Preview email template ──────────────────────────────────────────────────
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
    } catch (err) { toast.error(err.message) }
  }

  // ── Bulk toggle helpers ──────────────────────────────────────────────────────
  function toggleBulkSelect(key) {
    setBulkSelected(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key); else next.add(key)
      return next
    })
  }
  function toggleBulkSelectAll() {
    const rows = batchResult?.ranking || []
    if (bulkSelected.size === rows.length) {
      setBulkSelected(new Set())
    } else {
      setBulkSelected(new Set(rows.map((_, i) => i)))
    }
  }
  function getSelectedCandidates() {
    const rows = batchResult?.ranking || []
    return [...bulkSelected].map(i => rows[i]).filter(Boolean)
  }

  // ── Bulk accept/reject ──────────────────────────────────────────────────────
  async function handleBulkAction(action) {
    if (!selectedJob?.id) { toast.error('Select a job first'); return }
    const selected = getSelectedCandidates()
    if (!selected.length) { toast.error('Select at least one candidate'); return }
    if (bulkProcessing) return
    
    setBulkProcessing(true)
    let ok = 0, fail = 0
    for (const c of selected) {
      try {
        await recruiterDashboardAction(token, {
          job_id: selectedJob.id,
          candidate_name: c.candidate_name || c.name || '',
          candidate_email: c.email || c.candidate_email || '',
          cv_text: c.cv_text || '',
          final_score: c.final_score ?? null,
          ats_score: c.ats_score ?? null,
          action,
        })
        setCandidateActions(prev => ({ ...prev, [c.candidate_name || c.name]: action }))
        ok++
      } catch (err) { 
        console.error(`Bulk action error for ${c.candidate_name}:`, err)
        fail++ 
      }
    }
    setBulkProcessing(false)
    toast.success(`${action.toUpperCase()}: ${ok} successful${fail ? `, ${fail} failed` : ''}`)
    setBulkSelected(new Set())
  }

  // ── Clear bulk selection ────────────────────────────────────────────────────
  function handleClearSelection() {
    setBulkSelected(new Set())
    setBatchResult(null)
    setCvFiles([])
    setJdText('')
    setCandidateActions({})
    if (recruiterSession && typeof recruiterSession.clearAllData === 'function') {
      recruiterSession.clearAllData()
    }
    toast.success('Batch results cleared')
  }

  // ── Bulk email: open modal ──────────────────────────────────────────────────
  function openBulkEmailModal() {
    const selected = getSelectedCandidates()
    if (!selected.length) { toast.error('Select at least one candidate'); return }
    setBulkEmailTplId('')
    setBulkSenderEmail(user?.email || '')
    setBulkProgress(selected.map(c => ({
      name: c.candidate_name || c.name || '',
      email: c.email || c.candidate_email || '',
      status: 'pending',
    })))
    // load templates if not already loaded
    if (!templates.length) {
      recruiterListTemplates(token)
        .then(data => setTemplates(Array.isArray(data) ? data : data?.templates || []))
        .catch(err => { console.error('Failed to load templates:', err) })
    }
    setBulkEmailModal(true)
  }

  async function handleBulkSendEmail() {
    if (!bulkEmailTplId) { toast.error('Select a template'); return }
    const selected = getSelectedCandidates()
    if (!selected.length) return
    setBulkSending(true)

    setBulkProgress(prev => prev.map(p => ({ ...p, status: 'sending' })))

    try {
      const emails = selected.map(c => c.email || c.candidate_email || '').filter(Boolean)
      if (!emails.length) {
        toast.error('None of the selected candidates have a valid email address')
        setBulkSending(false)
        return
      }

      const res = await recruiterSendEmailBulk(token, {
        template_id: Number(bulkEmailTplId),
        candidate_emails: emails,
        job_id: selectedJob?.id || null,
        sender_email: bulkSenderEmail.trim() || null
      })

      const resultsMap = {}
      if (res.results && Array.isArray(res.results)) {
        res.results.forEach(r => {
          resultsMap[r.email] = r
        })
      }

      setBulkProgress(prev => prev.map(p => {
        const match = resultsMap[p.email]
        if (match) {
          return {
            ...p,
            status: match.status === 'success' ? 'sent' : 'error',
            error: match.error || null
          }
        }
        return { ...p, status: 'error', error: 'No response from server' }
      }))

      if (res.failed > 0) {
        toast.warning(`Bulk email complete: ${res.successful} sent, ${res.failed} failed`)
      } else {
        toast.success(`Bulk email sent successfully to ${res.successful} candidates`)
      }
    } catch (err) {
      toast.error(err.message || 'Failed to send bulk email')
      setBulkProgress(prev => prev.map(p => ({ ...p, status: 'error', error: err.message || 'Failed' })))
    } finally {
      setBulkSending(false)
      setBulkSelected(new Set())
    }
  }

  const fadeUp = {
    hidden: { opacity: 0, y: 20 },
    visible: (i = 0) => ({ opacity: 1, y: 0, transition: { delay: i * 0.08, duration: 0.45, ease: [0.25, 0.1, 0.25, 1] } }),
  }
  const stagger = { hidden: {}, visible: { transition: { staggerChildren: 0.08 } } }

  return (
    <div className="app-layout">
      <Navbar />
      <main className="main-content" id="main-content">

        {/* ── Page header ────────────────────── */}
        <motion.div
          className="recruiter-page-header"
          initial={{ opacity: 0, y: -16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <div className="recruiter-header-icon-wrap">
            <Users size={28} />
          </div>
          <div>
            <h1 className="recruiter-page-title">{t('recruiter.title')}</h1>
            <p className="recruiter-page-subtitle">{t('recruiter.subtitle')}</p>
          </div>
        </motion.div>

        {/* ── Stats ──────────────────────────── */}
        <motion.div
          className="recruiter-stats-grid"
          variants={stagger}
          initial="hidden"
          animate="visible"
        >
          {[
            { icon: <Users size={24} strokeWidth={1.8} />, value: candidates.length, label: t('recruiter.total_analyzed'), color: 'var(--color-accent)' },
            { icon: <TrendingUp size={24} strokeWidth={1.8} />, value: `${avgScore}%`, label: t('recruiter.avg_score'), color: 'var(--color-warning)', mono: true },
            { icon: <Trophy size={24} strokeWidth={1.8} />, value: topCandidates.length, label: t('recruiter.top_candidates'), color: 'var(--color-success)' },
          ].map((stat, i) => (
            <motion.div
              key={i}
              className="recruiter-stat-card"
              variants={fadeUp}
              custom={i}
              whileHover={{ y: -2 }}
            >
              <div className="recruiter-stat-icon" style={{ color: stat.color }}>{stat.icon}</div>
              <div className="recruiter-stat-info">
                <span className="recruiter-stat-value" style={stat.mono ? { fontFamily: "'JetBrains Mono', monospace" } : {}}>{stat.value}</span>
                <span className="recruiter-stat-label">{stat.label}</span>
              </div>
            </motion.div>
          ))}
        </motion.div>

        {/* ── Job Selector & Section Tabs ──────────────────────── */}
        <motion.div
          className="admin-card"
          variants={fadeUp}
          initial="hidden"
          animate="visible"
          custom={0.5}
          style={{ padding: '12px 20px' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', marginBottom: 10 }}>
            <Briefcase size={16} style={{ color: 'var(--color-accent)', flexShrink: 0 }} />
            <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>Job:</span>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', flex: 1 }}>
              {jobs.map(j => (
                <motion.button
                  key={j.id}
                  className="btn-outline btn-sm"
                  onClick={() => setSelectedJob(j)}
                  whileHover={{ scale: 1.03 }}
                  whileTap={{ scale: 0.97 }}
                  style={selectedJob?.id === j.id ? { background: 'var(--color-accent)', color: '#fff', borderColor: 'var(--color-accent)' } : {}}
                >
                  {j.title}
                </motion.button>
              ))}
              <motion.button
                className="btn-ghost btn-sm"
                onClick={() => setJobModal(true)}
                whileHover={{ scale: 1.04 }}
                whileTap={{ scale: 0.96 }}
              >
                <Plus size={13} /> New Job
              </motion.button>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 4, borderTop: '1px solid var(--color-border)', paddingTop: 10 }}>
            {[
              { id: 'overview',  icon: Trophy,    label: t('recruiter.batch_title') || 'Overview' },
              { id: 'decisions', icon: FileText,  label: 'Decisions' },
              { id: 'templates', icon: Mail,      label: 'Email Templates' },
            ].map(tab => {
              const Icon = tab.icon
              const active = activeSection === tab.id
              return (
                <motion.button
                  key={tab.id}
                  onClick={() => setActiveSection(tab.id)}
                  className="btn-ghost"
                  whileHover={{ scale: 1.03 }}
                  whileTap={{ scale: 0.97 }}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    padding: '8px 16px', borderRadius: 8, fontSize: '0.85rem', fontWeight: 600,
                    background: active ? 'var(--color-accent)' : 'transparent',
                    color: active ? '#fff' : 'var(--color-text-secondary)',
                    transition: 'all 0.2s',
                  }}
                >
                  <Icon size={14} /> {tab.label}
                </motion.button>
              )
            })}
          </div>
        </motion.div>

        {/* ═══════ SECTION: OVERVIEW ═══════════════════════════════ */}
        <AnimatePresence mode="wait">
        {activeSection === 'overview' && (
          <motion.div key="overview" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }} transition={{ duration: 0.3 }}>

        {/* ── Camera Scan Banner ────────────── */}
        <motion.div
          variants={fadeUp} initial="hidden" animate="visible" custom={0.5}
          onClick={() => setScanModal(true)}
          style={{
            display: 'flex', alignItems: 'center', gap: 16,
            padding: '18px 22px', borderRadius: 14,
            border: '2px solid var(--status-accent-border)',
            background: 'var(--status-accent-bg)',
            cursor: 'pointer', marginBottom: 20,
            transition: 'all 0.2s',
            boxShadow: 'var(--shadow-sm)',
          }}
          whileHover={{ scale: 1.01, boxShadow: 'var(--shadow-md)' }}
        >
          <Camera size={32} style={{ color: 'var(--status-accent)', flexShrink: 0 }} />
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700, fontSize: 16, color: 'var(--status-accent)' }}>
              📷 {t('recruiter.scan_cv') || 'Fiziksel CV Tara'}
            </div>
            <div style={{ fontSize: 13, color: 'var(--color-text-secondary)', marginTop: 3 }}>
              {t('recruiter.scan_cv_desc') || 'Kamera ile kağıt CV tarayın → anlık OCR + ATS analizi + PDF çıktısı'}
            </div>
          </div>
          <ChevronDown size={20} style={{ color: 'var(--status-accent)', transform: 'rotate(-90deg)' }} />
        </motion.div>

        {/* ── Batch Ranking Form ────────────── */}
        <motion.div
          className="admin-card recruiter-batch-card"
          variants={fadeUp}
          initial="hidden"
          animate="visible"
          custom={1}
        >
          <div className="admin-card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Upload size={18} className="admin-card-icon" />
              <h2>{t('recruiter.batch_title')}</h2>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginLeft: 'auto' }}>
              <motion.button
                type="button"
                className="btn-outline btn-sm"
                onClick={() => setBatchUploadOpen(true)}
                whileHover={{ scale: 1.04 }}
                whileTap={{ scale: 0.96 }}
                style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.8rem', padding: '6px 12px' }}
              >
                <Sparkles size={13} /> SaaS Cloud Upload
              </motion.button>
              <span className="recruiter-cv-count">
                <Upload size={13} /> {cvFiles.length} / 5000
              </span>
            </div>
          </div>
          <form onSubmit={handleBatchRank} className="recruiter-batch-form">
            <div className="recruiter-form-group">
              <label>{t('recruiter.jd_text_label')}</label>
              <textarea className="recruiter-textarea" value={jdText} onChange={e => setJdText(e.target.value)} rows={5} placeholder={t('recruiter.jd_text_placeholder')} />
              {draftJdQualityMeta && (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 10,
                    marginTop: 10,
                    padding: '10px 12px',
                    borderRadius: 8,
                    border: `1px solid ${draftJdQualityMeta.border}`,
                    background: draftJdQualityMeta.background,
                    color: draftJdQualityMeta.color,
                    fontSize: '0.82rem',
                    lineHeight: 1.45,
                  }}
                >
                  <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: 2 }} />
                  <div>
                    <strong>{draftJdQualityMeta.title}</strong>
                    <div style={{ color: 'var(--color-text-secondary)', marginTop: 2 }}>
                      {draftJdQualityMeta.message}
                    </div>
                  </div>
                </div>
              )}
            </div>
            <div className="recruiter-form-row">
              <div className="recruiter-form-group recruiter-file-group">
                <label>{t('recruiter.jd_file_label')}</label>
                <input type="file" accept=".txt,.pdf,text/plain,application/pdf" onChange={e => setJdFile(e.target.files?.[0] || null)} className="admin-input" disabled={!!jdText.trim()} style={jdText.trim() ? { opacity: 0.4 } : {}} />
              </div>
              <div className="recruiter-form-group recruiter-file-group">
                <label>{t('recruiter.cv_upload_label')}</label>
                <input type="file" multiple accept="application/pdf,.pdf" onChange={e => setCvFiles(Array.from(e.target.files || []).slice(0, 5000))} className="admin-input" />
              </div>
            </div>
            <motion.button
              className="btn-primary recruiter-rank-btn"
              type="submit"
              disabled={batchLoading}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              {batchLoading ? <span className="spin-icon">⏳</span> : <Trophy size={16} />}
              {batchLoading ? t('recruiter.ranking_in_progress') : t('recruiter.run_batch_ranking')}
            </motion.button>
            {batchLoading && batchProgress.total > 0 && (
              <div style={{ marginTop: 16, padding: '12px', backgroundColor: 'var(--status-accent-bg)', borderRadius: 8, border: '1px solid var(--status-accent-border)' }}>
                <div style={{ fontSize: 12, fontWeight: 500, marginBottom: 8, color: 'var(--text-secondary)' }}>
                  {Math.round((batchProgress.processed / batchProgress.total) * 100)}% - {batchProgress.processed}/{batchProgress.total} CVs
                </div>
                <div style={{ height: 6, backgroundColor: 'var(--bg-input)', borderRadius: 3, overflow: 'hidden' }}>
                  <div 
                    style={{
                      height: '100%',
                      backgroundColor: 'var(--color-accent)',
                      width: `${(batchProgress.processed / batchProgress.total) * 100}%`,
                      transition: 'width 0.3s ease'
                    }}
                  />
                </div>
              </div>
            )}
          </form>
        </motion.div>

        {/* ── Analytics ──────────────────────── */}
        <AnimatePresence>
          {batchResult?.analytics && (
            <motion.div
              className="admin-card"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.4 }}
            >
              <div className="admin-card-header">
                <BarChart3 size={18} className="admin-card-icon" />
                <h2>{t('recruiter.recruiter_analytics')}</h2>
              </div>
              <div className="recruiter-stats-grid" style={{ marginBottom: 16 }}>
                <div className="recruiter-stat-card">
                  <div className="recruiter-stat-icon" style={{ color: 'var(--color-accent)' }}><TrendingUp size={22} /></div>
                  <div className="recruiter-stat-info">
                    <span className="recruiter-stat-value" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{batchResult.analytics.avg_score}%</span>
                    <span className="recruiter-stat-label">{t('recruiter.avg_score')}</span>
                  </div>
                </div>
                <div className="recruiter-stat-card">
                  <div className="recruiter-stat-icon" style={{ color: 'var(--color-warning)' }}><Sparkles size={22} /></div>
                  <div className="recruiter-stat-info">
                    <span className="recruiter-stat-value">{batchResult.analytics.top_skills?.[0]?.skill || '-'}</span>
                    <span className="recruiter-stat-label">{t('recruiter.top_skill')}</span>
                  </div>
                </div>
                <div className="recruiter-stat-card">
                  <div className="recruiter-stat-icon" style={{ color: 'var(--color-success)' }}><BarChart3 size={22} /></div>
                  <div className="recruiter-stat-info">
                    <span className="recruiter-stat-value">
                      <span style={{ color: 'var(--color-success)' }}>H:{distribution.high}</span>{' '}
                      <span style={{ color: 'var(--color-warning)' }}>M:{distribution.medium}</span>{' '}
                      <span style={{ color: 'var(--color-danger)' }}>L:{distribution.low}</span>
                    </span>
                    <span className="recruiter-stat-label">{t('recruiter.candidate_distribution')}</span>
                  </div>
                </div>
              </div>
              {batchResult.analytics.top_skills?.length > 0 && (
                <>
                  <h3 className="recruiter-subsection-title">{t('recruiter.top_skills')}</h3>
                  <SkillTags skills={batchResult.analytics.top_skills.map(x => `${x.skill} (${x.count})`)} variant="normal" />
                </>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── Batch Ranking Results ──────────── */}
        <AnimatePresence>
          {batchResult?.ranking?.length > 0 && (
            <motion.div
              className="admin-card"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
            >
              <div className="admin-card-header">
                <Trophy size={18} className="admin-card-icon" />
                <h2>{t('recruiter.batch_ranking')}</h2>
                <div style={{ display: 'flex', gap: 6, marginLeft: 'auto', alignItems: 'center' }}>
                  {bulkSelected.size > 0 && (
                    <span style={{ fontSize: '0.8rem', color: 'var(--color-accent)', fontWeight: 600 }}>
                      {bulkSelected.size} selected
                    </span>
                  )}
                  {/* Export Menu */}
                  <div style={{ position: 'relative' }}>
                    <motion.button
                      className="btn-outline btn-sm"
                      onClick={() => setExportMenuOpen(!exportMenuOpen)}
                      whileHover={{ scale: 1.04 }}
                      whileTap={{ scale: 0.96 }}
                      title="Export in multiple formats"
                    >
                      <Download size={14} /> {t('recruiter.export_csv') || 'Export'}
                    </motion.button>
                    <AnimatePresence>
                      {exportMenuOpen && (
                        <motion.div
                          className="export-menu"
                          initial={{ opacity: 0, y: -8, scale: 0.95 }}
                          animate={{ opacity: 1, y: 0, scale: 1 }}
                          exit={{ opacity: 0, y: -8, scale: 0.95 }}
                          style={{
                            position: 'absolute',
                            top: '100%',
                            right: 0,
                            marginTop: 6,
                            background: 'var(--color-surface)',
                            border: '1px solid var(--color-border)',
                            borderRadius: 8,
                            zIndex: 1000,
                            minWidth: 200,
                            boxShadow: '0 4px 12px rgba(0,0,0,0.15)'
                          }}
                        >
                          <button
                            onClick={handleExportCsv}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 8,
                              width: '100%',
                              padding: '10px 14px',
                              border: 'none',
                              background: 'transparent',
                              color: 'var(--color-text)',
                              cursor: 'pointer',
                              fontSize: '0.875rem',
                              fontWeight: 500,
                              borderBottom: '1px solid var(--color-border)'
                            }}
                            onMouseEnter={e => e.target.style.background = 'var(--color-accent)08'}
                            onMouseLeave={e => e.target.style.background = 'transparent'}
                          >
                            <FileSpreadsheet size={14} /> CSV (Spreadsheet)
                          </button>
                          <button
                            onClick={handleExportHtml}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 8,
                              width: '100%',
                              padding: '10px 14px',
                              border: 'none',
                              background: 'transparent',
                              color: 'var(--color-text)',
                              cursor: 'pointer',
                              fontSize: '0.875rem',
                              fontWeight: 500,
                              borderBottom: '1px solid var(--color-border)'
                            }}
                            onMouseEnter={e => e.target.style.background = 'var(--color-accent)08'}
                            onMouseLeave={e => e.target.style.background = 'transparent'}
                          >
                            📊 HTML (Formatted Report)
                          </button>
                          <button
                            onClick={handleExportJson}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 8,
                              width: '100%',
                              padding: '10px 14px',
                              border: 'none',
                              background: 'transparent',
                              color: 'var(--color-text)',
                              cursor: 'pointer',
                              fontSize: '0.875rem',
                              fontWeight: 500
                            }}
                            onMouseEnter={e => e.target.style.background = 'var(--color-accent)08'}
                            onMouseLeave={e => e.target.style.background = 'transparent'}
                          >
                            <FileJson size={14} /> JSON (Complete Data)
                          </button>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </div>
              </div>

              {/* ── Bulk Action Bar ──────────── */}
              <AnimatePresence>
                {bulkSelected.size > 0 && (
                  <motion.div
                    className="bulk-action-bar"
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap',
                      padding: '10px 16px', marginBottom: 12, borderRadius: 8,
                      background: 'var(--color-surface)', border: '1px solid var(--color-border)',
                    }}
                  >
                    <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-text)', marginRight: 4 }}>
                      Bulk Actions:
                    </span>
                    <motion.button
                      className="btn-outline btn-sm"
                      onClick={() => handleBulkAction('accepted')}
                      disabled={bulkProcessing}
                      whileHover={!bulkProcessing ? { scale: 1.03 } : {}}
                      whileTap={!bulkProcessing ? { scale: 0.97 } : {}}
                      style={{ color: 'var(--status-success)', borderColor: 'var(--status-success-border)', opacity: bulkProcessing ? 0.6 : 1, cursor: bulkProcessing ? 'not-allowed' : 'pointer' }}
                    >
                      {bulkProcessing ? <Loader size={13} className="spin" /> : <ThumbsUp size={13} />} Accept ({bulkSelected.size})
                    </motion.button>
                    <motion.button
                      className="btn-outline btn-sm"
                      onClick={() => handleBulkAction('rejected')}
                      disabled={bulkProcessing}
                      whileHover={!bulkProcessing ? { scale: 1.03 } : {}}
                      whileTap={!bulkProcessing ? { scale: 0.97 } : {}}
                      style={{ color: 'var(--status-danger)', borderColor: 'var(--status-danger-border)', opacity: bulkProcessing ? 0.6 : 1, cursor: bulkProcessing ? 'not-allowed' : 'pointer' }}
                    >
                      {bulkProcessing ? <Loader size={13} className="spin" /> : <ThumbsDown size={13} />} Reject ({bulkSelected.size})
                    </motion.button>
                    <motion.button
                      className="btn-outline btn-sm"
                      onClick={openBulkEmailModal}
                      disabled={bulkProcessing}
                      whileHover={!bulkProcessing ? { scale: 1.03 } : {}}
                      whileTap={!bulkProcessing ? { scale: 0.97 } : {}}
                      style={{ color: 'var(--color-accent)', borderColor: 'var(--color-accent)', opacity: bulkProcessing ? 0.6 : 1, cursor: bulkProcessing ? 'not-allowed' : 'pointer' }}
                    >
                      {bulkProcessing ? <Loader size={13} className="spin" /> : <Mail size={13} />} Send Email ({bulkSelected.size})
                    </motion.button>
                    <motion.button
                      className="btn-ghost btn-sm"
                      onClick={handleClearSelection}
                      whileHover={{ scale: 1.03 }}
                      style={{ marginLeft: 'auto', fontSize: '0.8rem', color: 'var(--color-text-secondary)' }}
                    >
                      <X size={13} /> Clear
                    </motion.button>
                  </motion.div>
                )}
              </AnimatePresence>
              {batchJdQualityMeta && (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 10,
                    padding: '12px 14px',
                    marginBottom: 12,
                    borderRadius: 8,
                    border: `1px solid ${batchJdQualityMeta.border}`,
                    background: batchJdQualityMeta.background,
                    color: batchJdQualityMeta.color,
                    fontSize: '0.85rem',
                    lineHeight: 1.45,
                  }}
                >
                  <AlertTriangle size={16} style={{ flexShrink: 0, marginTop: 2 }} />
                  <div>
                    <strong>{batchJdQualityMeta.title}</strong>
                    <div style={{ color: 'var(--color-text-secondary)', marginTop: 2 }}>
                      {batchJdQualityMeta.message}
                    </div>
                  </div>
                </div>
              )}
              <div className="admin-table-wrapper">
                <table className="data-table data-table-elite admin-table">
                  <thead>
                    <tr>
                      <th style={{ width: 36, textAlign: 'center' }}>
                        <button
                          type="button"
                          className="btn-icon table-select-button"
                          onClick={toggleBulkSelectAll}
                          aria-label={bulkSelected.size === (batchResult?.ranking?.length || 0) && bulkSelected.size > 0 ? 'Clear candidate selection' : 'Select all candidates'}
                        >
                          {bulkSelected.size === (batchResult?.ranking?.length || 0) && bulkSelected.size > 0
                            ? <CheckSquare size={15} style={{ color: 'var(--color-accent)' }} />
                            : <Square size={15} style={{ color: 'var(--color-text-secondary)' }} />}
                        </button>
                      </th>
                      <th>#</th>
                      <th>{t('recruiter.candidates')}</th>
                      <th>Email</th>
                      <th>Match</th>
                      <th>CV Quality</th>
                      <th>Skill Fit</th>
                      <th>JD</th>
                      <th>Strengths</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {batchResult.ranking.map((r, i) => (
                      <motion.tr
                        key={`${r.file_name}-${i}`}
                        initial={{ opacity: 0, x: -8 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: i * 0.04, duration: 0.3 }}
                        style={bulkSelected.has(i) ? { background: 'rgba(167,139,250,0.06)' } : {}}
                      >
                        <td style={{ textAlign: 'center' }}>
                          <button
                            type="button"
                            className="btn-icon table-select-button"
                            onClick={() => toggleBulkSelect(i)}
                            aria-label={`${bulkSelected.has(i) ? 'Deselect' : 'Select'} ${r.candidate_name || r.filename || 'candidate'}`}
                          >
                            {bulkSelected.has(i)
                              ? <CheckSquare size={15} style={{ color: 'var(--color-accent)' }} />
                              : <Square size={15} style={{ color: 'var(--color-text-secondary)' }} />}
                          </button>
                        </td>
                        <td>
                          <span className={`rank-num ${i === 0 ? 'gold' : i === 1 ? 'silver' : i === 2 ? 'bronze' : ''}`}>
                            {r.rank || i + 1}
                          </span>
                        </td>
                        <td className="candidate-name">{r.candidate_name}</td>
                        <td className="text-muted" style={{ fontSize: '0.82rem' }}>{r.candidate_email || '-'}</td>
                        <td>
                          <span className="score-badge-lg" style={{ color: getScoreColor(r.final_score), fontFamily: "'JetBrains Mono', monospace" }}>
                            {Math.round(r.final_score)}%
                          </span>
                        </td>
                        <td style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.85rem' }}>{Math.round(r.ats_score)}%</td>
                        <td style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.85rem' }}>{Math.round(r.skill_score)}%</td>
                        <td>
                          {(() => {
                            const rowMeta = getJdQualityMeta(getRowJdQuality(r, batchResult))
                            if (!rowMeta) {
                              return <span style={{ color: 'var(--status-success)', fontSize: '0.78rem', fontWeight: 700 }}>OK</span>
                            }
                            return (
                              <span
                                title={rowMeta.message}
                                style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: 4,
                                  padding: '3px 7px',
                                  borderRadius: 6,
                                  background: rowMeta.background,
                                  color: rowMeta.color,
                                  border: `1px solid ${rowMeta.border}`,
                                  fontSize: '0.72rem',
                                  fontWeight: 700,
                                  whiteSpace: 'nowrap',
                                }}
                              >
                                <AlertTriangle size={12} /> {rowMeta.label}
                              </span>
                            )
                          })()}
                        </td>
                        <td>
                          {(r.strengths || []).filter(s => typeof s === 'string' && isNaN(Number(s))).slice(0, 2).map((s, si) => (
                            <span key={si} style={{ display: 'inline-block', padding: '2px 7px', borderRadius: 6, background: 'var(--status-success-bg)', color: 'var(--status-success)', fontSize: '0.72rem', marginRight: 3 }}>
                              {s}
                            </span>
                          ))}
                        </td>
                        <td>
                          <div style={{ display: 'flex', gap: 3, flexWrap: 'nowrap' }}>
                            <motion.button
                              className="btn-outline btn-sm"
                              onClick={() => handleDashboardPreview(r)}
                              whileHover={{ scale: 1.05 }}
                              whileTap={{ scale: 0.95 }}
                              title="Preview"
                              aria-label={`Preview ${r.candidate_name || r.filename || 'candidate'}`}
                            >
                              <Eye size={13} />
                            </motion.button>
                            <motion.button
                              className="btn-outline btn-sm"
                              onClick={() => {
                                const fname = r.filename || r.file_name;
                                if (cvFiles && cvFiles.length > 0 && fname) {
                                  const file = cvFiles.find(f => f.name === fname);
                                  if (file) {
                                    window.open(URL.createObjectURL(file), '_blank');
                                    return;
                                  }
                                }
                                toast.error('PDF file not found in current session');
                              }}
                              whileHover={{ scale: 1.05 }}
                              whileTap={{ scale: 0.95 }}
                              title="Open PDF"
                              aria-label={`Open PDF for ${r.candidate_name || r.filename || 'candidate'}`}
                              style={{ color: 'var(--status-danger)', borderColor: 'var(--status-danger-border)' }}
                            >
                              <FileText size={13} />
                            </motion.button>
                            <motion.button
                              className="btn-outline btn-sm"
                              onClick={() => handleCandidateAction(r, 'accepted')}
                              whileHover={{ scale: 1.05 }}
                              whileTap={{ scale: 0.95 }}
                              title="Accept"
                              aria-label={`Accept ${r.candidate_name || r.filename || 'candidate'}`}
                              style={candidateActions[r.candidate_name] === 'accepted' ? { background: 'var(--status-success)', color: '#fff', borderColor: 'var(--status-success)' } : {}}
                            >
                              <ThumbsUp size={13} />
                            </motion.button>
                            <motion.button
                              className="btn-outline btn-sm"
                              onClick={() => handleCandidateAction(r, 'rejected')}
                              whileHover={{ scale: 1.05 }}
                              whileTap={{ scale: 0.95 }}
                              title="Reject"
                              aria-label={`Reject ${r.candidate_name || r.filename || 'candidate'}`}
                              style={candidateActions[r.candidate_name] === 'rejected' ? { background: 'var(--status-danger)', color: '#fff', borderColor: 'var(--status-danger)' } : {}}
                            >
                              <ThumbsDown size={13} />
                            </motion.button>
                            <motion.button
                              className="btn-outline btn-sm"
                              onClick={() => openEmailModal(r)}
                              whileHover={{ scale: 1.05 }}
                              whileTap={{ scale: 0.95 }}
                              title="Send Email"
                              aria-label={`Send email to ${r.candidate_name || r.filename || 'candidate'}`}
                            >
                              <Mail size={13} />
                            </motion.button>
                          </div>
                        </td>
                      </motion.tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── Semantic Search ────────────────── */}
        <motion.div
          className="admin-card recruiter-search-card"
          variants={fadeUp}
          initial="hidden"
          animate="visible"
          custom={2}
        >
          <form className="recruiter-search-row" onSubmit={handleSearch}>
            <Search size={17} className="recruiter-search-icon" />
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder={t('recruiter.search_placeholder')}
              className="recruiter-search-input"
            />
            {searchQuery && (
              <button type="button" className="btn-ghost btn-sm" onClick={() => { setSearchQuery(''); setSearchResults([]) }}>
                <X size={14} />
              </button>
            )}
            <motion.button
              className="btn-primary btn-sm"
              type="submit"
              whileHover={{ scale: 1.04 }}
              whileTap={{ scale: 0.96 }}
            >
              <Search size={14} /> {t('recruiter.search')}
            </motion.button>
          </form>
          {error && <p className="text-danger" style={{ marginTop: '0.5rem', fontSize: '0.875rem' }}>{error}</p>}
        </motion.div>

        <AnimatePresence>
          {searchResults.length > 0 && (
            <motion.div
              className="admin-card"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
            >
              <h3 className="recruiter-subsection-title">{t('recruiter.search_results')} ({searchResults.length})</h3>
              <div className="admin-table-wrapper">
                <table className="data-table data-table-elite admin-table">
                  <thead><tr><th>ID</th><th>Preview</th><th>Rank</th></tr></thead>
                  <tbody>
                    {searchResults.map(r => (
                      <motion.tr key={r.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                        <td>{r.id}</td>
                        <td>{r.cv_preview || '-'}</td>
                        <td style={{ fontFamily: "'JetBrains Mono', monospace" }}>{typeof r.rank === 'number' ? r.rank.toFixed(3) : '-'}</td>
                      </motion.tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── Candidate Table ────────────────── */}
        <motion.div
          className="admin-card"
          variants={fadeUp}
          initial="hidden"
          animate="visible"
          custom={3}
        >
          <div className="admin-card-header">
            <Users size={18} className="admin-card-icon" />
            <h2>
              {t('recruiter.candidates')}
              {!loading && candidates.length > 0 && (
                <span className="admin-count-badge" style={{ marginLeft: 8 }}>
                  {displayCandidates.length}/{candidates.length}
                </span>
              )}
            </h2>
          </div>

          {/* Filter Chips */}
          {!loading && candidates.length > 0 && (
            <FilterChips
              chips={filterChips}
              active={activeFilter}
              onChange={setActiveFilter}
              onClear={() => setActiveFilter('all')}
              label={t('recruiter.filter_by') || 'Filter:'}
            />
          )}

          {loading ? (
            <div className="admin-table-wrapper" style={{ marginTop: 16 }}>
              <table className="data-table data-table-elite admin-table">
                <thead>
                  <tr><th>#</th><th>{t('recruiter.candidates')}</th><th>{t('dashboard.score')}</th><th>{t('dashboard.date')}</th><th></th></tr>
                </thead>
                <tbody><SkeletonTableRows count={5} /></tbody>
              </table>
            </div>
          ) : displayCandidates.length > 0 ? (
            <div className="admin-table-wrapper">
              <table className="data-table data-table-elite admin-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <SortHeader sortKey="name" sortConfig={sortConfig} onSort={handleSort}>
                      {t('recruiter.candidates')}
                    </SortHeader>
                    <SortHeader sortKey="score" sortConfig={sortConfig} onSort={handleSort}>
                      {t('dashboard.score')}
                    </SortHeader>
                    <SortHeader sortKey="date" sortConfig={sortConfig} onSort={handleSort}>
                      {t('dashboard.date')}
                    </SortHeader>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  <AnimatePresence mode="popLayout">
                    {displayCandidates.map((c, i) => (
                      <motion.tr
                        key={c.id || c.analysis_id || i}
                        initial={{ opacity: 0, x: -8 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: 8 }}
                        transition={{ delay: i * 0.03, duration: 0.25 }}
                      >
                        <td>
                          <span className={`rank-num ${i === 0 ? 'gold' : i === 1 ? 'silver' : i === 2 ? 'bronze' : ''}`}>{i + 1}</span>
                        </td>
                        <td className="candidate-name">{c.name || c.candidate_name || `Candidate ${i + 1}`}</td>
                        <td>
                          <span className="score-badge" style={{ color: getScoreColor(getScore(c)), fontFamily: "'JetBrains Mono', monospace" }}>
                            {Math.round(getScore(c))}%
                          </span>
                        </td>
                        <td className="text-muted">{c.created_at ? new Date(c.created_at).toLocaleDateString() : ''}</td>
                        <td>
                          <motion.button
                            className="btn-outline btn-sm"
                            onClick={() => openCandidateDetail(c)}
                            whileHover={{ scale: 1.05 }}
                            whileTap={{ scale: 0.95 }}
                          >
                            <Eye size={13} /> {t('recruiter.view_cv')}
                          </motion.button>
                        </td>
                      </motion.tr>
                    ))}
                  </AnimatePresence>
                </tbody>
              </table>
            </div>
          ) : (
            <motion.div
              className="empty-state"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.4 }}
            >
              <div className="empty-icon">👔</div>
              <h3>{activeFilter !== 'all' ? 'No candidates match this filter' : t('recruiter.no_candidates')}</h3>
              <p>{activeFilter !== 'all' ? 'Try a different filter' : t('recruiter.no_candidates_desc')}</p>
              {activeFilter !== 'all' && (
                <button className="btn-outline" onClick={() => setActiveFilter('all')}>Clear filter</button>
              )}
            </motion.div>
          )}
        </motion.div>

          </motion.div>
        )}

        {/* ═══════ SECTION: DECISIONS ══════════════════════════════ */}
        {activeSection === 'decisions' && (
          <motion.div key="decisions" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }} transition={{ duration: 0.3 }}>
            <motion.div className="admin-card" variants={fadeUp} initial="hidden" animate="visible" custom={2}>
              <div className="admin-card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <FileText size={18} className="admin-card-icon" />
                  <h2>Candidate Decisions {selectedJob ? `— ${selectedJob.title}` : ''}</h2>
                </div>
                {selectedJob && (
                  <div style={{ position: 'relative', marginLeft: 'auto' }}>
                    <motion.button
                      className="btn-outline btn-sm"
                      onClick={() => setDbExportOpen(!dbExportOpen)}
                      whileHover={{ scale: 1.04 }}
                      whileTap={{ scale: 0.96 }}
                      title="Export stored database data"
                    >
                      <Download size={14} /> Database Export
                    </motion.button>
                    <AnimatePresence>
                      {dbExportOpen && (
                        <motion.div
                          className="export-menu"
                          initial={{ opacity: 0, y: -8, scale: 0.95 }}
                          animate={{ opacity: 1, y: 0, scale: 1 }}
                          exit={{ opacity: 0, y: -8, scale: 0.95 }}
                          style={{
                            position: 'absolute',
                            top: '100%',
                            right: 0,
                            marginTop: 6,
                            background: 'var(--color-surface)',
                            border: '1px solid var(--color-border)',
                            borderRadius: 8,
                            zIndex: 1000,
                            minWidth: 220,
                            boxShadow: '0 4px 12px rgba(0,0,0,0.15)'
                          }}
                        >
                          <div style={{ padding: '6px 14px 2px 14px', fontSize: '0.75rem', color: 'var(--color-text-secondary)', textTransform: 'uppercase', fontWeight: 600 }}>Rankings</div>
                          <button
                            onClick={() => handleDbExportRankings('csv')}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 8,
                              width: '100%',
                              padding: '8px 14px',
                              border: 'none',
                              background: 'transparent',
                              color: 'var(--color-text)',
                              cursor: 'pointer',
                              fontSize: '0.875rem',
                              fontWeight: 500,
                              textAlign: 'left'
                            }}
                            onMouseEnter={e => e.target.style.background = 'var(--color-accent)08'}
                            onMouseLeave={e => e.target.style.background = 'transparent'}
                          >
                            <FileSpreadsheet size={14} /> Export Job Rankings (CSV)
                          </button>
                          <button
                            onClick={() => handleDbExportRankings('json')}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 8,
                              width: '100%',
                              padding: '8px 14px',
                              border: 'none',
                              background: 'transparent',
                              color: 'var(--color-text)',
                              cursor: 'pointer',
                              fontSize: '0.875rem',
                              fontWeight: 500,
                              borderBottom: '1px solid var(--color-border)',
                              textAlign: 'left'
                            }}
                            onMouseEnter={e => e.target.style.background = 'var(--color-accent)08'}
                            onMouseLeave={e => e.target.style.background = 'transparent'}
                          >
                            <FileJson size={14} /> Export Job Rankings (JSON)
                          </button>
                          <div style={{ padding: '6px 14px 2px 14px', fontSize: '0.75rem', color: 'var(--color-text-secondary)', textTransform: 'uppercase', fontWeight: 600 }}>Candidates</div>
                          <button
                            onClick={() => handleDbExportCandidates('csv')}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 8,
                              width: '100%',
                              padding: '8px 14px',
                              border: 'none',
                              background: 'transparent',
                              color: 'var(--color-text)',
                              cursor: 'pointer',
                              fontSize: '0.875rem',
                              fontWeight: 500,
                              textAlign: 'left'
                            }}
                            onMouseEnter={e => e.target.style.background = 'var(--color-accent)08'}
                            onMouseLeave={e => e.target.style.background = 'transparent'}
                          >
                            <FileSpreadsheet size={14} /> Export All Candidates (CSV)
                          </button>
                          <button
                            onClick={() => handleDbExportCandidates('json')}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 8,
                              width: '100%',
                              padding: '8px 14px',
                              border: 'none',
                              background: 'transparent',
                              color: 'var(--color-text)',
                              cursor: 'pointer',
                              fontSize: '0.875rem',
                              fontWeight: 500,
                              textAlign: 'left'
                            }}
                            onMouseEnter={e => e.target.style.background = 'var(--color-accent)08'}
                            onMouseLeave={e => e.target.style.background = 'transparent'}
                          >
                            <FileJson size={14} /> Export All Candidates (JSON)
                          </button>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                )}
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
                  <p>Accept or reject candidates from the Overview tab</p>
                </div>
              ) : (
                <div className="admin-table-wrapper" style={{ marginTop: 12 }}>
                  <table className="data-table data-table-elite admin-table">
                    <thead><tr><th>Candidate</th><th>Email</th><th>Score</th><th>Decision</th><th>Pipeline</th><th>Email Sent</th><th>Date</th></tr></thead>
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
                              background: a.action === 'accepted' ? 'var(--status-success-bg)' : a.action === 'rejected' ? 'var(--status-danger-bg)' : 'var(--status-warning-bg)',
                              color: a.action === 'accepted' ? 'var(--status-success)' : a.action === 'rejected' ? 'var(--status-danger)' : 'var(--status-warning)',
                            }}>
                              {a.action}
                            </span>
                          </td>
                          <td>
                            <select
                              className="admin-input"
                              value={a.stage || a.action || 'pending'}
                              onChange={(e) => handleDecisionStageChange(a.id, e.target.value)}
                              style={{ minWidth: 120, padding: '6px 8px', fontSize: '0.8rem' }}
                            >
                              <option value="pending">Pending</option>
                              <option value="shortlist">Shortlist</option>
                              <option value="interview">Interview</option>
                              <option value="offer">Offer</option>
                              <option value="accepted">Accepted</option>
                              <option value="rejected">Rejected</option>
                              <option value="withdrawn">Withdrawn</option>
                            </select>
                          </td>
                          <td>
                            {a.email_sent
                              ? <Check size={14} style={{ color: 'var(--status-success)' }} />
                              : <X size={14} style={{ color: 'var(--color-text-secondary)', opacity: 0.4 }} />}
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

        {/* ═══════ SECTION: TEMPLATES ═════════════════════════════ */}
        {activeSection === 'templates' && (
          <motion.div key="templates" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }} transition={{ duration: 0.3 }}>

            {/* Create Template Form */}
            <motion.div className="admin-card" variants={fadeUp} initial="hidden" animate="visible" custom={2}>
              <div className="admin-card-header">
                <Plus size={18} className="admin-card-icon" />
                <h2>Create Email Template</h2>
              </div>
              <form onSubmit={handleCreateTemplate} style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 12 }}>
                <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                  <input className="admin-input" placeholder="Template name" value={tplForm.name} onChange={e => setTplForm(f => ({ ...f, name: e.target.value }))} style={{ flex: 1, minWidth: 180 }} />
                  <select className="admin-input" value={tplForm.template_type} onChange={e => setTplForm(f => ({ ...f, template_type: e.target.value }))} style={{ width: 140 }}>
                    <option value="accept">Accept</option>
                    <option value="reject">Reject</option>
                    <option value="custom">Custom</option>
                  </select>
                </div>
                <input className="admin-input" placeholder="Email subject — use {candidate_name}, {position}, etc." value={tplForm.subject} onChange={e => setTplForm(f => ({ ...f, subject: e.target.value }))} />
                <textarea className="recruiter-textarea" placeholder={'Email body — variables: {candidate_name}, {candidate_email}, {position}, {company}, {score}, {top_skills}'} value={tplForm.body} onChange={e => setTplForm(f => ({ ...f, body: e.target.value }))} rows={6} />
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
                        padding: '14px 18px', borderRadius: 10,
                        border: '1px solid var(--color-border)', background: 'var(--color-surface)',
                      }}
                      whileHover={{ y: -2 }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
                        <div>
                          <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>{tpl.name}</div>
                          <span style={{
                            display: 'inline-block', marginTop: 4, padding: '2px 8px', borderRadius: 6,
                            fontSize: '0.75rem', fontWeight: 600,
                            background: tpl.template_type === 'accept' ? 'var(--status-success-bg)' : tpl.template_type === 'reject' ? 'var(--status-danger-bg)' : 'var(--status-accent-bg)',
                            color: tpl.template_type === 'accept' ? 'var(--status-success)' : tpl.template_type === 'reject' ? 'var(--status-danger)' : 'var(--status-accent)',
                          }}>
                            {tpl.template_type}
                          </span>
                          <div className="text-muted" style={{ marginTop: 6, fontSize: '0.85rem' }}>
                            Subject: {tpl.subject || '(no subject)'}
                          </div>
                        </div>
                        <div style={{ display: 'flex', gap: 4 }}>
                          <motion.button className="btn-outline btn-sm" onClick={() => handlePreviewTemplate(tpl)} whileHover={{ scale: 1.05 }} title="Preview" aria-label={`Preview template ${tpl.name || tpl.id}`}>
                            <Eye size={13} />
                          </motion.button>
                          <motion.button className="btn-outline btn-sm" onClick={() => handleDeleteTemplate(tpl.id)} whileHover={{ scale: 1.05 }} title="Delete" aria-label={`Delete template ${tpl.name || tpl.id}`} style={{ color: 'var(--status-danger)' }}>
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
                <motion.div className="admin-card" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}>
                  <div className="admin-card-header">
                    <Eye size={18} className="admin-card-icon" />
                    <h2>Template Preview</h2>
                    <button type="button" className="btn-ghost btn-sm" onClick={() => setTplPreview(null)} aria-label="Close template preview"><X size={14} /></button>
                  </div>
                  <div style={{ padding: 16, background: 'var(--color-bg)', borderRadius: 8, marginTop: 12 }}>
                    <div style={{ fontWeight: 600, marginBottom: 8 }}>Subject: {tplPreview.rendered_subject}</div>
                    <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{tplPreview.rendered_body}</div>
                    {tplPreview.missing_vars?.length > 0 && (
                      <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 6, color: 'var(--status-warning)', fontSize: '0.85rem' }}>
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

        {/* ═══════ MODALS ═════════════════════════════════════════ */}

        {/* Candidate Detail Modal */}
        <Modal open={!!selected} onClose={() => setSelected(null)} title={t('recruiter.candidate_detail')}>
          {selected?.result && (
            <div className="modal-detail">
              <div className="modal-score-row">
                <ScoreCircle score={selected.result.final_score} size={100} />
                <div>
                  <h3>{selected.name || selected.candidate_name}</h3>
                  <p className="text-muted">{selected.result.interpretation}</p>
                </div>
              </div>
              {(() => {
                const selectedJdMeta = getJdQualityMeta(selected.result.job_description_quality)
                if (!selectedJdMeta) return null
                return (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: 10,
                      padding: '10px 12px',
                      borderRadius: 8,
                      border: `1px solid ${selectedJdMeta.border}`,
                      background: selectedJdMeta.background,
                      color: selectedJdMeta.color,
                      fontSize: '0.84rem',
                    }}
                  >
                    <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: 2 }} />
                    <div>
                      <strong>{selectedJdMeta.title}</strong>
                      <div style={{ color: 'var(--color-text-secondary)', marginTop: 2 }}>
                        {selectedJdMeta.message}
                      </div>
                    </div>
                  </div>
                )
              })()}
              <ScoreBars items={[
                { label: t('results.semantic'),   value: selected.result.semantic_score },
                { label: t('results.keyword'),    value: selected.result.keyword_score },
                { label: t('results.skill'),      value: selected.result.skill_score },
                { label: t('results.experience'), value: selected.result.experience_score },
                { label: t('results.ats'),        value: selected.result.ats_score },
              ]} />
              {selected.result.score_breakdown && (
                <>
                  <h4>{t('results.ats_breakdown')}</h4>
                  <ScoreBars items={[
                    { label: t('results.skills_dimension'),     value: selected.result.score_breakdown.skills },
                    { label: t('results.keywords_dimension'),   value: selected.result.score_breakdown.keywords },
                    { label: t('results.format_dimension'),     value: selected.result.score_breakdown.format },
                    { label: t('results.experience_dimension'), value: selected.result.score_breakdown.experience },
                  ]} />
                </>
              )}
              {selected.result.missing_skills?.length > 0 && (
                <>
                  <h4>{t('results.missing_skills')}</h4>
                  <SkillTags skills={selected.result.missing_skills} variant="missing" />
                </>
              )}
              {selected.result.keyword_gap?.missing_words?.length > 0 && (
                <>
                  <h4>{t('results.missing_keywords')}</h4>
                  <SkillTags skills={selected.result.keyword_gap.missing_words} variant="missing" />
                </>
              )}
            </div>
          )}
        </Modal>

        {/* Preview with Enhanced Candidate Details Modal */}
        <Modal 
          open={previewOpen} 
          onClose={() => setPreviewOpen(false)} 
          title="Candidate Profile"
          style={{ maxWidth: '900px', width: '90vw' }}
        >
          {previewData && (
            <EnhancedCandidatePreview
              candidate={previewData}
              result={previewData}
              previewData={previewData}
              onClose={() => setPreviewOpen(false)}
            />
          )}
        </Modal>

        {/* Send Email Modal */}
        <Modal open={emailModal} onClose={() => setEmailModal(false)} title={`Send Email to ${emailTarget?.candidate_name || emailTarget?.name || 'Candidate'}`}>
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

        {/* Bulk Send Email Modal */}
        <Modal open={bulkEmailModal} onClose={() => { if (!bulkSending) setBulkEmailModal(false) }} title={`Send Email to ${bulkProgress.length} candidates`}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <label style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: 6, display: 'block' }}>Your Email (Sender / Reply-To)</label>
              <input className="admin-input" type="email" placeholder="your@email.com" value={bulkSenderEmail} onChange={e => setBulkSenderEmail(e.target.value)} style={{ width: '100%' }} disabled={bulkSending} />
            </div>
            <div>
              <label style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: 6, display: 'block' }}>Select Template</label>
              <select className="admin-input" value={bulkEmailTplId} onChange={e => setBulkEmailTplId(e.target.value)} style={{ width: '100%' }} disabled={bulkSending}>
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

            {/* Progress list */}
            <div style={{ borderRadius: 8, border: '1px solid var(--color-border)', overflow: 'hidden' }}>
              <div style={{ padding: '8px 14px', background: 'var(--color-surface)', borderBottom: '1px solid var(--color-border)', fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text-secondary)' }}>
                Recipients ({bulkProgress.filter(p => p.status === 'sent').length}/{bulkProgress.length} sent)
              </div>
              <div style={{ maxHeight: 240, overflowY: 'auto' }}>
                {bulkProgress.map((p, i) => (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '8px 14px', borderBottom: '1px solid var(--color-border)',
                    fontSize: '0.85rem',
                    background: p.status === 'sent' ? 'var(--status-success-bg)' : p.status === 'error' ? 'var(--status-danger-bg)' : 'transparent',
                  }}>
                    <div style={{ width: 18, flexShrink: 0, display: 'flex', justifyContent: 'center' }}>
                      {p.status === 'pending' && <Square size={14} style={{ color: 'var(--color-text-secondary)', opacity: 0.4 }} />}
                      {p.status === 'sending' && <Loader size={14} style={{ color: 'var(--color-accent)', animation: 'spin 1s linear infinite' }} />}
                      {p.status === 'sent' && <Check size={14} style={{ color: 'var(--status-success)' }} />}
                      {p.status === 'error' && <X size={14} style={{ color: 'var(--status-danger)' }} />}
                    </div>
                    <span style={{ flex: 1, fontWeight: 500 }}>{p.name}</span>
                    <span style={{ color: 'var(--color-text-secondary)', fontSize: '0.8rem' }}>{p.email || '(no email)'}</span>
                    {p.status === 'sent' && <span style={{ color: 'var(--status-success)', fontSize: '0.75rem', fontWeight: 600 }}>Sent</span>}
                    {p.status === 'error' && <span style={{ color: 'var(--status-danger)', fontSize: '0.75rem', fontWeight: 600 }}>{p.error}</span>}
                  </div>
                ))}
              </div>
            </div>

            <div style={{ display: 'flex', gap: 8 }}>
              <motion.button
                className="btn-primary"
                onClick={handleBulkSendEmail}
                disabled={bulkSending || !bulkEmailTplId}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                style={{ flex: 1 }}
              >
                {bulkSending ? <Loader size={16} style={{ animation: 'spin 1s linear infinite' }} /> : <Send size={16} />}
                {bulkSending ? `Sending... (${bulkProgress.filter(p => p.status === 'sent').length}/${bulkProgress.length})` : `Send to ${bulkProgress.length} candidates`}
              </motion.button>
              {!bulkSending && (
                <motion.button
                  className="btn-ghost"
                  onClick={() => setBulkEmailModal(false)}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                >
                  Cancel
                </motion.button>
              )}
            </div>
          </div>
        </Modal>

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

        {/* Action Decision Modal */}
        <Modal open={actionModal.open} onClose={() => setActionModal({ ...actionModal, open: false })} title={actionModal.action === 'accepted' ? 'Approve Candidate' : 'Reject Candidate'}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-primary)' }}>
              Are you sure you want to <strong>{actionModal.action}</strong> {actionModal.candidate?.candidate_name || actionModal.candidate?.name}?
            </p>
            <div>
              <label style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: 6, display: 'block' }}>Feedback Reason (Optional)</label>
              <textarea 
                className="recruiter-textarea" 
                value={actionModal.message} 
                onChange={e => setActionModal({ ...actionModal, message: e.target.value })} 
                rows={4} 
                placeholder="Enter a reason..."
              />
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4, display: 'block' }}>This feedback is saved with the decision and can be used in emails later.</span>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <motion.button
                className="btn-primary"
                onClick={confirmAction}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                style={{ flex: 1, background: actionModal.action === 'accepted' ? 'var(--status-success)' : 'var(--status-danger)', borderColor: actionModal.action === 'accepted' ? 'var(--status-success)' : 'var(--status-danger)' }}
              >
                {actionModal.action === 'accepted' ? <ThumbsUp size={16} /> : <ThumbsDown size={16} />}
                Confirm {actionModal.action === 'accepted' ? 'Acceptance' : 'Rejection'}
              </motion.button>
            </div>
          </div>
        </Modal>

         <CameraScanModal open={scanModal} onClose={() => setScanModal(false)} />
        <BatchUploadModal
          isOpen={batchUploadOpen}
          onClose={() => setBatchUploadOpen(false)}
          onSuccess={() => {
            toast.success('Bulk upload and processing started successfully')
          }}
          jobs={jobs}
        />
      </main>
    </div>
  )
}
