import React, { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Briefcase, Plus, X, GripVertical, Calendar, Building2, MapPin,
  Star, Trophy, Target, TrendingUp, Trash2, Edit3, Check, ChevronDown,
  Flame, Award, Zap, ExternalLink, Clock, FileText, BarChart3,
  Bell, Mail,
} from 'lucide-react'
import Navbar from '../components/Navbar'
import { useLanguage } from '../i18n/LanguageContext'
import { useToast } from '../components/Toast'
import { useAuth } from '../context/AuthContext'
import { createReminder, updateReminder, deleteReminder, sendReminderTest } from '../api'

const STORAGE_KEY = 'cv_analyzer_job_tracker'

const COLUMNS = [
  { id: 'wishlist',  color: '#60a5fa', icon: Star },
  { id: 'applied',   color: '#a78bfa', icon: FileText },
  { id: 'interview', color: '#fbbf24', icon: Briefcase },
  { id: 'offer',     color: '#34d399', icon: Trophy },
  { id: 'rejected',  color: '#ef4444', icon: X },
]

const PRIORITY_COLORS = { high: '#ef4444', medium: '#fbbf24', low: '#60a5fa' }

function generateId() { return Date.now().toString(36) + Math.random().toString(36).slice(2, 7) }

function copy(lang, tr, en) { return lang === 'tr' ? tr : en }

function toDateTimeLocal(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000)
  return local.toISOString().slice(0, 16)
}

function daysUntil(value) {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return Math.ceil((date.getTime() - Date.now()) / 86400000)
}

function formatReminderDate(value, lang) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString(lang === 'tr' ? 'tr-TR' : 'en-US', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function reminderTypeFromStatus(status) {
  if (status === 'offer') return 'offer'
  if (status === 'interview') return 'interview'
  return 'follow_up'
}

function loadJobs() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {} } catch { return {} }
}
function saveJobs(data) { localStorage.setItem(STORAGE_KEY, JSON.stringify(data)) }

const containerVariants = { hidden: {}, show: { transition: { staggerChildren: 0.06 } } }
const itemVariants = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.35 } } }

// ── Add/Edit Modal ──
function JobModal({ job, initialStatus, userEmail, onSave, onClose, t, lang }) {
  const defaultReminder = ['interview', 'offer'].includes(job?.status || initialStatus)
  const [form, setForm] = useState({
    company: job?.company || '',
    role: job?.role || '',
    location: job?.location || '',
    url: job?.url || '',
    salary: job?.salary || '',
    notes: job?.notes || '',
    priority: job?.priority || 'medium',
    appliedDate: job?.appliedDate || new Date().toISOString().slice(0, 10),
    reminderEnabled: job?.reminderEnabled ?? defaultReminder,
    reminderDate: toDateTimeLocal(job?.reminderDate || ''),
    reminderEmail: job?.reminderEmail || userEmail || '',
    reminderType: job?.reminderType || reminderTypeFromStatus(job?.status || initialStatus),
  })
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.company.trim() || !form.role.trim()) return
    if (form.reminderEnabled && !form.reminderDate) return
    setSaving(true)
    try {
      await onSave(form)
    } finally {
      setSaving(false)
    }
  }

  const set = (k, v) => setForm(prev => ({ ...prev, [k]: v }))

  return (
    <motion.div className="jt-modal-overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}>
      <motion.div className="jt-modal" initial={{ scale: 0.92, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.92, opacity: 0 }}
        onClick={e => e.stopPropagation()}>
        <div className="jt-modal-header">
          <h3>{job ? t('jt.edit_job') : t('jt.add_job')}</h3>
          <button className="jt-modal-close" onClick={onClose}><X size={18} /></button>
        </div>
        <form onSubmit={handleSubmit} className="jt-modal-form">
          <div className="jt-form-row">
            <div className="jt-form-field">
              <label>{t('jt.company')} *</label>
              <div className="jt-input-wrap"><Building2 size={15} className="jt-input-icon" /><input value={form.company} onChange={e => set('company', e.target.value)} placeholder={t('jt.company_ph')} required /></div>
            </div>
            <div className="jt-form-field">
              <label>{t('jt.role')} *</label>
              <div className="jt-input-wrap"><Briefcase size={15} className="jt-input-icon" /><input value={form.role} onChange={e => set('role', e.target.value)} placeholder={t('jt.role_ph')} required /></div>
            </div>
          </div>
          <div className="jt-form-row">
            <div className="jt-form-field">
              <label>{t('jt.location')}</label>
              <div className="jt-input-wrap"><MapPin size={15} className="jt-input-icon" /><input value={form.location} onChange={e => set('location', e.target.value)} placeholder={t('jt.location_ph')} /></div>
            </div>
            <div className="jt-form-field">
              <label>{t('jt.date')}</label>
              <div className="jt-input-wrap"><Calendar size={15} className="jt-input-icon" /><input type="date" value={form.appliedDate} onChange={e => set('appliedDate', e.target.value)} /></div>
            </div>
          </div>
          <div className="jt-form-row">
            <div className="jt-form-field">
              <label>{t('jt.url')}</label>
              <div className="jt-input-wrap"><ExternalLink size={15} className="jt-input-icon" /><input value={form.url} onChange={e => set('url', e.target.value)} placeholder="https://..." /></div>
            </div>
            <div className="jt-form-field">
              <label>{t('jt.salary')}</label>
              <div className="jt-input-wrap"><BarChart3 size={15} className="jt-input-icon" /><input value={form.salary} onChange={e => set('salary', e.target.value)} placeholder={t('jt.salary_ph')} /></div>
            </div>
          </div>
          <div className="jt-form-field">
            <label>{t('jt.priority')}</label>
            <div className="jt-priority-selector">
              {['high', 'medium', 'low'].map(p => (
                <button key={p} type="button" className={`jt-priority-btn ${form.priority === p ? 'jt-priority-active' : ''}`}
                  style={form.priority === p ? { '--p-color': PRIORITY_COLORS[p] } : {}} onClick={() => set('priority', p)}>
                  {t(`jt.priority_${p}`)}
                </button>
              ))}
            </div>
          </div>
          <div className="jt-form-field">
            <label>{t('jt.notes')}</label>
            <textarea value={form.notes} onChange={e => set('notes', e.target.value)} rows={3} placeholder={t('jt.notes_ph')} className="jt-notes-textarea" />
          </div>
          <div className="jt-reminder-editor">
            <label className="jt-reminder-toggle">
              <input
                type="checkbox"
                checked={!!form.reminderEnabled}
                onChange={e => set('reminderEnabled', e.target.checked)}
              />
              <span>
                <Bell size={15} />
                {copy(lang, 'Mail hatırlatma kur', 'Set email reminder')}
              </span>
            </label>
            {form.reminderEnabled && (
              <>
                <div className="jt-form-row">
                  <div className="jt-form-field">
                    <label>{copy(lang, 'Hatırlatma türü', 'Reminder type')}</label>
                    <select className="jt-select" value={form.reminderType} onChange={e => set('reminderType', e.target.value)}>
                      <option value="interview">{copy(lang, 'Mülakat', 'Interview')}</option>
                      <option value="offer">{copy(lang, 'Teklif / son tarih', 'Offer / deadline')}</option>
                      <option value="follow_up">{copy(lang, 'Takip', 'Follow-up')}</option>
                      <option value="deadline">{copy(lang, 'Son tarih', 'Deadline')}</option>
                    </select>
                  </div>
                  <div className="jt-form-field">
                    <label>{copy(lang, 'Tarih ve saat', 'Date and time')} *</label>
                    <div className="jt-input-wrap">
                      <Calendar size={15} className="jt-input-icon" />
                      <input
                        type="datetime-local"
                        value={form.reminderDate}
                        onChange={e => set('reminderDate', e.target.value)}
                        required={!!form.reminderEnabled}
                      />
                    </div>
                  </div>
                </div>
                <div className="jt-form-field">
                  <label>{copy(lang, 'Mail nereye gelsin?', 'Send email to')}</label>
                  <div className="jt-input-wrap">
                    <Mail size={15} className="jt-input-icon" />
                    <input
                      type="email"
                      value={form.reminderEmail}
                      onChange={e => set('reminderEmail', e.target.value)}
                      placeholder={userEmail || 'you@example.com'}
                    />
                  </div>
                </div>
                <p className="jt-reminder-help">
                  {copy(lang, 'CV Analyzer etkinliğe 3 gün ve 1 gün kala otomatik mail gönderir.', 'CV Analyzer sends automatic email reminders 3 days and 1 day before the event.')}
                </p>
              </>
            )}
          </div>
          <div className="jt-modal-actions">
            <button type="button" className="jt-btn-secondary" onClick={onClose}>{t('common.cancel')}</button>
            <button type="submit" className="jt-btn-primary" disabled={saving}><Check size={16} /> {saving ? copy(lang, 'Kaydediliyor', 'Saving') : job ? t('jt.save') : t('jt.add')}</button>
          </div>
        </form>
      </motion.div>
    </motion.div>
  )
}

// ── Job Card ──
function JobCard({ job, onEdit, onDelete, onSendReminderTest, dragHandlers, isDragging }) {
  const { t, lang } = useLanguage()
  const daysSince = Math.floor((Date.now() - new Date(job.appliedDate).getTime()) / 86400000)
  const reminderDays = daysUntil(job.reminderDate)

  return (
    <motion.div className={`jt-card ${isDragging ? 'jt-card-dragging' : ''}`}
      layout layoutId={job.id}
      draggable onDragStart={e => dragHandlers.onDragStart(e, job)}
      onDragEnd={dragHandlers.onDragEnd}
      whileHover={{ y: -2 }}>
      <div className="jt-card-top">
        <div className="jt-card-grip" title="Drag"><GripVertical size={14} /></div>
        <span className="jt-card-priority" style={{ background: PRIORITY_COLORS[job.priority] || '#fbbf24' }} />
        <div className="jt-card-actions">
          <button onClick={() => onEdit(job)} title={t('jt.edit_job')}><Edit3 size={13} /></button>
          <button onClick={() => onDelete(job.id)} title={t('jt.delete')}><Trash2 size={13} /></button>
        </div>
      </div>
      <h4 className="jt-card-company">{job.company}</h4>
      <p className="jt-card-role">{job.role}</p>
      {job.location && <p className="jt-card-location"><MapPin size={11} /> {job.location}</p>}
      {job.salary && <p className="jt-card-salary"><BarChart3 size={11} /> {job.salary}</p>}
      {job.reminderEnabled && job.reminderDate && (
        <div className={`jt-card-reminder ${job.reminderSyncError ? 'jt-card-reminder-error' : job.reminderId ? 'jt-card-reminder-active' : ''}`}>
          <Bell size={11} />
          <span>{formatReminderDate(job.reminderDate, lang)}</span>
          {reminderDays !== null && <b>{reminderDays <= 0 ? copy(lang, 'bugün', 'today') : `${reminderDays}d`}</b>}
          {job.reminderId && (
            <button
              type="button"
              onClick={e => { e.stopPropagation(); onSendReminderTest?.(job) }}
              title={copy(lang, 'Test maili gönder', 'Send test email')}
            >
              <Mail size={11} />
            </button>
          )}
        </div>
      )}
      <div className="jt-card-footer">
        <span className="jt-card-date"><Clock size={11} /> {daysSince}d</span>
        {job.url && <a href={job.url} target="_blank" rel="noopener noreferrer" className="jt-card-link"><ExternalLink size={11} /></a>}
      </div>
    </motion.div>
  )
}

// ── Main Page ──
export default function JobTrackerPage() {
  const { t, lang } = useLanguage()
  const { addToast } = useToast()
  const { user, token } = useAuth()
  const userEmail = user?.email || ''

  const [jobs, setJobs] = useState(() => loadJobs())
  const [modalOpen, setModalOpen] = useState(false)
  const [editingJob, setEditingJob] = useState(null)
  const [addToColumn, setAddToColumn] = useState('wishlist')
  const [draggedJob, setDraggedJob] = useState(null)
  const [dragOverCol, setDragOverCol] = useState(null)

  useEffect(() => { document.title = `${t('jt.title')} — CV Analyzer` }, [t])
  useEffect(() => { saveJobs(jobs) }, [jobs])

  // ── Helpers ──
  const allJobs = Object.values(jobs)
  const getColumnJobs = useCallback(colId => allJobs.filter(j => j.status === colId).sort((a, b) => (a.order || 0) - (b.order || 0)), [allJobs])

  // ── Gamification Stats ──
  const totalApps = allJobs.filter(j => j.status !== 'wishlist').length
  const interviews = allJobs.filter(j => j.status === 'interview').length
  const offers = allJobs.filter(j => j.status === 'offer').length
  const interviewRate = totalApps > 0 ? Math.round((interviews + offers) / totalApps * 100) : 0
  const upcomingReminders = allJobs
    .filter(j => j.reminderEnabled && j.reminderDate && daysUntil(j.reminderDate) !== null && daysUntil(j.reminderDate) >= 0)
    .sort((a, b) => new Date(a.reminderDate).getTime() - new Date(b.reminderDate).getTime())
    .slice(0, 4)

  // Weekly streak
  const thisWeekApps = allJobs.filter(j => {
    const d = new Date(j.appliedDate)
    const now = new Date()
    const weekAgo = new Date(now.getTime() - 7 * 86400000)
    return d >= weekAgo && j.status !== 'wishlist'
  }).length

  // ── CRUD ──
  function buildReminderPayload(job) {
    const eventDate = job.reminderDate ? new Date(job.reminderDate) : null
    return {
      title: `${job.company} - ${job.role}`.trim(),
      description: [job.location, job.notes].filter(Boolean).join('\n\n'),
      reminder_type: job.reminderType || reminderTypeFromStatus(job.status),
      event_date: eventDate?.toISOString(),
      target_email: job.reminderEmail || userEmail,
      is_active: !!job.reminderEnabled,
    }
  }

  async function syncReminder(job) {
    if (!job.reminderEnabled || !job.reminderDate) {
      if (token && job.reminderId) {
        await deleteReminder(token, job.reminderId).catch(() => null)
      }
      return { ...job, reminderId: null, reminderSyncError: '' }
    }

    if (!token) {
      return {
        ...job,
        reminderSyncError: copy(lang, 'Mail hatırlatma için giriş gerekir.', 'Login is required for email reminders.'),
      }
    }

    const payload = buildReminderPayload(job)
    const saved = job.reminderId
      ? await updateReminder(token, job.reminderId, payload)
      : await createReminder(token, payload)

    return {
      ...job,
      reminderId: saved.id || job.reminderId,
      reminderEmail: saved.target_email || job.reminderEmail || userEmail,
      reminderSyncError: '',
    }
  }

  async function handleAddJob(formData) {
    const id = generateId()
    const colJobs = getColumnJobs(addToColumn)
    let newJob = { ...formData, id, status: addToColumn, order: colJobs.length, createdAt: Date.now() }
    try {
      newJob = await syncReminder(newJob)
    } catch (err) {
      newJob = { ...newJob, reminderSyncError: err.message || 'Reminder sync failed' }
      addToast(copy(lang, 'Başvuru kaydedildi ama mail hatırlatma kurulamadı.', 'Job saved, but email reminder could not be scheduled.'), 'warning')
    }
    setJobs(prev => ({ ...prev, [id]: newJob }))
    setModalOpen(false)
    addToast(newJob.reminderId ? copy(lang, 'Başvuru ve mail hatırlatma kaydedildi', 'Job and email reminder saved') : t('jt.job_added'), 'success')
  }
  async function handleEditJob(formData) {
    if (!editingJob) return
    let updatedJob = { ...editingJob, ...formData }
    try {
      updatedJob = await syncReminder(updatedJob)
    } catch (err) {
      updatedJob = { ...updatedJob, reminderSyncError: err.message || 'Reminder sync failed' }
      addToast(copy(lang, 'Başvuru güncellendi ama mail hatırlatma senkronize edilemedi.', 'Job updated, but email reminder could not be synced.'), 'warning')
    }
    setJobs(prev => ({ ...prev, [editingJob.id]: updatedJob }))
    setEditingJob(null)
    setModalOpen(false)
    addToast(t('jt.job_updated'), 'success')
  }
  function handleDeleteJob(id) {
    const job = jobs[id]
    if (token && job?.reminderId) deleteReminder(token, job.reminderId).catch(() => null)
    setJobs(prev => { const copy = { ...prev }; delete copy[id]; return copy })
    addToast(t('jt.job_deleted'), 'success')
  }
  function openAddModal(colId) {
    setAddToColumn(colId)
    setEditingJob(null)
    setModalOpen(true)
  }
  function openEditModal(job) {
    setEditingJob(job)
    setModalOpen(true)
  }

  // ── Drag & Drop ──
  function onDragStart(e, job) {
    setDraggedJob(job)
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('text/plain', job.id)
    requestAnimationFrame(() => { if (e.target) e.target.classList.add('jt-card-dragging') })
  }
  function onDragEnd(e) {
    e.target.classList.remove('jt-card-dragging')
    setDraggedJob(null)
    setDragOverCol(null)
  }
  function onDragOver(e, colId) {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    setDragOverCol(colId)
  }
  function onDragLeave() { setDragOverCol(null) }
  function onDrop(e, colId) {
    e.preventDefault()
    setDragOverCol(null)
    if (!draggedJob) return
    if (draggedJob.status === colId) return
    const updatedJob = { ...draggedJob, status: colId, order: getColumnJobs(colId).length }
    setJobs(prev => ({
      ...prev,
      [draggedJob.id]: updatedJob
    }))
    // Toast for status change
    if (colId === 'offer') addToast(`🎉 ${t('jt.congrats_offer')}`, 'success')
    else if (colId === 'interview') addToast(`📞 ${t('jt.moved_interview')}`, 'success')
    else addToast(t('jt.job_moved'), 'success')
    if (['interview', 'offer'].includes(colId) && !draggedJob.reminderDate) {
      setEditingJob({
        ...updatedJob,
        reminderEnabled: true,
        reminderType: reminderTypeFromStatus(colId),
        reminderEmail: draggedJob.reminderEmail || userEmail,
      })
      setModalOpen(true)
    }
    setDraggedJob(null)
  }

  async function handleSendReminderTest(job) {
    if (!token || !job.reminderId) return
    try {
      await sendReminderTest(token, job.reminderId)
      addToast(copy(lang, 'Test hatırlatma maili gönderildi', 'Test reminder email sent'), 'success')
    } catch (err) {
      addToast(err.message || copy(lang, 'Test maili gönderilemedi', 'Test email could not be sent'), 'error')
    }
  }

  const dragHandlers = { onDragStart, onDragEnd }

  return (
    <div className="app-layout">
      <Navbar />
      <main className="main-content" id="main-content">
        <motion.div initial="hidden" animate="show" variants={containerVariants}>

          {/* Header */}
          <motion.div className="jt-header" variants={itemVariants}>
            <div className="jt-header-icon">
              <Briefcase size={28} strokeWidth={1.6} />
              <div className="jt-header-icon-glow" />
            </div>
            <div>
              <h1 className="jt-title">{t('jt.title')}</h1>
              <p className="jt-subtitle">{t('jt.subtitle')}</p>
            </div>
          </motion.div>

          {/* Gamification Stats */}
          <motion.div className="jt-stats" variants={itemVariants}>
            <div className="jt-stat">
              <div className="jt-stat-icon" style={{ '--stat-color': '#a78bfa' }}><Target size={18} /></div>
              <div><span className="jt-stat-value">{totalApps}</span><span className="jt-stat-label">{t('jt.total_applied')}</span></div>
            </div>
            <div className="jt-stat">
              <div className="jt-stat-icon" style={{ '--stat-color': '#fbbf24' }}><Briefcase size={18} /></div>
              <div><span className="jt-stat-value">{interviews}</span><span className="jt-stat-label">{t('jt.interviews')}</span></div>
            </div>
            <div className="jt-stat">
              <div className="jt-stat-icon" style={{ '--stat-color': '#34d399' }}><Trophy size={18} /></div>
              <div><span className="jt-stat-value">{offers}</span><span className="jt-stat-label">{t('jt.offers')}</span></div>
            </div>
            <div className="jt-stat">
              <div className="jt-stat-icon" style={{ '--stat-color': '#60a5fa' }}><TrendingUp size={18} /></div>
              <div><span className="jt-stat-value">{interviewRate}%</span><span className="jt-stat-label">{t('jt.interview_rate')}</span></div>
            </div>
            <div className="jt-stat">
              <div className="jt-stat-icon" style={{ '--stat-color': '#f97316' }}><Flame size={18} /></div>
              <div><span className="jt-stat-value">{thisWeekApps}</span><span className="jt-stat-label">{t('jt.this_week')}</span></div>
            </div>
          </motion.div>

          {upcomingReminders.length > 0 && (
            <motion.div className="jt-reminder-panel" variants={itemVariants}>
              <div className="jt-reminder-panel-head">
                <div>
                  <h3><Bell size={16} /> {copy(lang, 'Yaklaşan hatırlatmalar', 'Upcoming reminders')}</h3>
                  <p>{copy(lang, 'Mülakat, teklif ve takip tarihleri için mail hatırlatmaları açık.', 'Email reminders are active for interviews, offers, and follow-ups.')}</p>
                </div>
                <span>{upcomingReminders.length}</span>
              </div>
              <div className="jt-reminder-list">
                {upcomingReminders.map(job => {
                  const remaining = daysUntil(job.reminderDate)
                  return (
                    <button key={job.id} type="button" className="jt-reminder-chip" onClick={() => openEditModal(job)}>
                      <Bell size={14} />
                      <span>
                        <strong>{job.company}</strong>
                        <small>{job.role}</small>
                      </span>
                      <em>{formatReminderDate(job.reminderDate, lang)}</em>
                      {remaining !== null && <b>{remaining <= 0 ? copy(lang, 'bugün', 'today') : `${remaining}d`}</b>}
                    </button>
                  )
                })}
              </div>
            </motion.div>
          )}

          {/* Kanban Board */}
          <motion.div className="jt-board" variants={itemVariants}>
            {COLUMNS.map(col => {
              const Icon = col.icon
              const colJobs = getColumnJobs(col.id)
              const isOver = dragOverCol === col.id
              return (
                <div key={col.id} className={`jt-column ${isOver ? 'jt-column-dragover' : ''}`}
                  onDragOver={e => onDragOver(e, col.id)} onDragLeave={onDragLeave} onDrop={e => onDrop(e, col.id)}>
                  <div className="jt-column-header" style={{ '--col-color': col.color }}>
                    <div className="jt-column-header-left">
                      <Icon size={16} />
                      <span className="jt-column-title">{t(`jt.col_${col.id}`)}</span>
                      <span className="jt-column-count">{colJobs.length}</span>
                    </div>
                    <button className="jt-column-add" onClick={() => openAddModal(col.id)} title={t('jt.add_job')}>
                      <Plus size={15} />
                    </button>
                  </div>
                  <div className="jt-column-body">
                    <AnimatePresence>
                      {colJobs.map(job => (
                        <JobCard key={job.id} job={job} onEdit={openEditModal} onDelete={handleDeleteJob}
                          onSendReminderTest={handleSendReminderTest}
                          dragHandlers={dragHandlers} isDragging={draggedJob?.id === job.id} />
                      ))}
                    </AnimatePresence>
                    {colJobs.length === 0 && (
                      <div className="jt-column-empty">
                        <p>{t('jt.empty_column')}</p>
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </motion.div>

          {/* Empty overall state */}
          {allJobs.length === 0 && (
            <motion.div className="jt-empty-state" variants={itemVariants}>
              <Briefcase size={40} strokeWidth={1.2} />
              <h3>{t('jt.empty_title')}</h3>
              <p>{t('jt.empty_desc')}</p>
              <button className="jt-btn-primary" onClick={() => openAddModal('wishlist')}>
                <Plus size={16} /> {t('jt.add_first')}
              </button>
            </motion.div>
          )}

        </motion.div>

        {/* Modal */}
        <AnimatePresence>
          {modalOpen && (
            <JobModal
              job={editingJob}
              initialStatus={editingJob?.status || addToColumn}
              userEmail={userEmail}
              onSave={editingJob ? handleEditJob : handleAddJob}
              onClose={() => { setModalOpen(false); setEditingJob(null) }}
              t={t}
              lang={lang}
            />
          )}
        </AnimatePresence>
      </main>
    </div>
  )
}
