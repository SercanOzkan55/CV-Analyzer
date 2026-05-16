import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { GripVertical, Plus, Trash2, Eye, Download, ChevronLeft, ChevronRight, FileText, Sparkles, Check, Link2 } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { useToast } from '../components/Toast'
import { generateCV, previewCV, suggestSummary, fetchFonts } from '../api'
import Navbar from '../components/Navbar'
import CVLivePreview from '../components/CVLivePreview'

const EMPTY_EXP  = { title: '', company: '', location: '', start_date: '', end_date: '', bullets: [''] }
const EMPTY_EDU  = { degree: '', school: '', location: '', start_date: '', end_date: '', gpa: '', field: '' }
const EMPTY_CERT = { name: '', issuer: '', date: '' }
const EMPTY_PROJ = { name: '', description: '', bullets: [''] }
const EMPTY_LANG = { name: '', writing: '', listening: '', speaking: '' }
const EMPTY_SOCIAL = { platform: '', url: '' }
const CEFR_LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2', 'Native']

const DEFAULT_SECTION_ORDER = ['experience', 'education', 'skills', 'certifications', 'projects', 'languages']

const PLAN_TEMPLATES = {
  free:       ['classic'],
  pro:        ['classic', 'modern', 'executive', 'professional', 'creative'],
  enterprise: ['classic', 'modern', 'executive', 'professional', 'creative', 'corporate', 'tech', 'consulting'],
  admin:      ['classic', 'modern', 'executive', 'professional', 'creative', 'corporate', 'tech', 'consulting'],
}

function extractNonEmptyTitles(experiences) {
  return (Array.isArray(experiences) ? experiences : [])
    .map(e => e?.title || e?.company || '').filter(Boolean).slice(0, 3)
}
function extractNonEmptyNames(items, key = 'name') {
  return (Array.isArray(items) ? items : [])
    .map(item => item?.[key] || '').filter(Boolean).slice(0, 3)
}

export default function CVBuilderPage() {
  const { token, plan, planLoading, canAnalyze, recordAnalysis, refreshUsage } = useAuth()
  const { t, lang } = useLanguage()
  const { addToast } = useToast()
  const routeLocation = useLocation()
  const prefillAppliedRef = useRef(false)
  const premium = !planLoading && (plan === 'pro' || plan === 'enterprise' || plan === 'admin')

  // ── Form state ──────────────────────────────────────────────────────────────
  const [fullName,       setFullName]       = useState('')
  const [email,          setEmail]          = useState('')
  const [phone,          setPhone]          = useState('')
  const [location,       setLocation]       = useState('')
  const [linkedin,       setLinkedin]       = useState('')
  const [summary,        setSummary]        = useState('')
  const [jobDescription, setJobDescription] = useState('')
  const [experiences,    setExperiences]    = useState([{ ...EMPTY_EXP, bullets: [''] }])
  const [education,      setEducation]      = useState([{ ...EMPTY_EDU }])
  const [skills,         setSkills]         = useState([''])
  const [certifications, setCertifications] = useState([])
  const [projects,       setProjects]       = useState([])
  const [languages,      setLanguages]      = useState([{ ...EMPTY_LANG }])
  const [socialLinks,     setSocialLinks]    = useState([])

  // ── Settings ─────────────────────────────────────────────────────────────────
  const [template,      setTemplate]      = useState('classic')
  const [outputFormat,  setOutputFormat]  = useState('docx')
  const [fontFamily,    setFontFamily]    = useState('')
  const [availableFonts, setAvailableFonts] = useState([])
  const [defaultFont,   setDefaultFont]   = useState('Arial')
  const resolvedPlan       = planLoading ? 'free' : plan
  const availableTemplates = PLAN_TEMPLATES[resolvedPlan] || PLAN_TEMPLATES.free

  // ── UI state ─────────────────────────────────────────────────────────────────
  const [loading,           setLoading]           = useState(false)
  const [previewData,       setPreviewData]        = useState(null)
  const [step,              setStep]               = useState(1)
  const [showPrefillBanner, setShowPrefillBanner]  = useState(false)
  const [prefillSummary,    setPrefillSummary]     = useState(null)
  const [sectionOrder,      setSectionOrder]       = useState(DEFAULT_SECTION_ORDER)
  const [dragSection,       setDragSection]        = useState(null)
  const [dragOverSection,   setDragOverSection]    = useState(null)
  const [suggestions,       setSuggestions]         = useState([])
  const [suggestLoading,    setSuggestLoading]      = useState(false)
  const [suggestError,      setSuggestError]        = useState('')

  useEffect(() => {
    document.title = `${t('nav.cv_builder')} — CV Analyzer`
  }, [t])

  // ── Fetch available fonts ─────────────────────────────────────────────────────
  useEffect(() => {
    fetchFonts()
      .then(data => {
        setAvailableFonts(data.fonts || [])
        setDefaultFont(data.default || 'Arial')
      })
      .catch(() => {})
  }, [])

  // ── Prefill from route state ──────────────────────────────────────────────────
  useEffect(() => {
    const prefill = routeLocation.state?.prefill
    if (!prefill || prefillAppliedRef.current) return
    prefillAppliedRef.current = true

    setFullName(prefill.full_name || '')
    setEmail(prefill.email || '')
    setPhone(prefill.phone || '')
    setLocation(prefill.location || '')
    setLinkedin(prefill.linkedin || '')
    setSummary(prefill.summary || '')
    setJobDescription(prefill.job_description || '')
    setExperiences(
      Array.isArray(prefill.experiences) && prefill.experiences.length > 0
        ? prefill.experiences.map(exp => ({ ...EMPTY_EXP, ...exp, bullets: Array.isArray(exp?.bullets) && exp.bullets.length > 0 ? exp.bullets : [''] }))
        : [{ ...EMPTY_EXP, bullets: [''] }]
    )
    setEducation(
      Array.isArray(prefill.education) && prefill.education.length > 0
        ? prefill.education.map(edu => ({ ...EMPTY_EDU, ...edu }))
        : [{ ...EMPTY_EDU }]
    )
    setSkills(Array.isArray(prefill.skills) && prefill.skills.length > 0 ? prefill.skills.map(s => String(s || '')) : [''])
    setCertifications(Array.isArray(prefill.certifications) ? prefill.certifications.map(c => ({ ...EMPTY_CERT, ...c })) : [])
    setProjects(Array.isArray(prefill.projects) ? prefill.projects.map(p => ({ ...EMPTY_PROJ, ...p, bullets: Array.isArray(p?.bullets) && p.bullets.length > 0 ? p.bullets : [''] })) : [])
    setLanguages(Array.isArray(prefill.languages) && prefill.languages.length > 0 ? prefill.languages.map(entry => typeof entry === 'string' ? { ...EMPTY_LANG, name: entry } : { ...EMPTY_LANG, ...entry }) : [{ ...EMPTY_LANG }])
    setSocialLinks(Array.isArray(prefill.social_links) && prefill.social_links.length > 0 ? prefill.social_links.map(s => ({ ...EMPTY_SOCIAL, ...s })) : [])
    setTemplate(prefill.template || 'classic')
    setOutputFormat(prefill.output_format || 'docx')
    setPreviewData(null)
    setShowPrefillBanner(true)
    setPrefillSummary({
      experiences: Array.isArray(prefill.experiences) ? prefill.experiences.length : 0,
      experienceTitles: extractNonEmptyTitles(prefill.experiences),
      education: Array.isArray(prefill.education) ? prefill.education.length : 0,
      educationNames: extractNonEmptyNames(prefill.education, 'school'),
      skills: Array.isArray(prefill.skills) ? prefill.skills.length : 0,
      skillNames: extractNonEmptyNames(prefill.skills),
      certifications: Array.isArray(prefill.certifications) ? prefill.certifications.length : 0,
      projects: Array.isArray(prefill.projects) ? prefill.projects.length : 0,
      languages: Array.isArray(prefill.languages) ? prefill.languages.length : 0,
    })
    setStep(1)
    addToast(t('cv_builder.prefill_loaded'), 'success')
  }, [routeLocation.state, addToast, t])

  // ── Array helpers ─────────────────────────────────────────────────────────────
  function updateArrayItem(arr, setArr, idx, field, value) {
    const copy = [...arr]; copy[idx] = { ...copy[idx], [field]: value }; setArr(copy)
  }
  function addArrayItem(arr, setArr, tmpl) { setArr([...arr, { ...tmpl }]) }
  function removeArrayItem(arr, setArr, idx) { if (arr.length <= 1) return; setArr(arr.filter((_, i) => i !== idx)) }
  function updateBullet(arr, setArr, expIdx, bulletIdx, value) {
    const copy = [...arr]; const bullets = [...(copy[expIdx].bullets || [])]
    bullets[bulletIdx] = value; copy[expIdx] = { ...copy[expIdx], bullets }; setArr(copy)
  }
  function addBullet(arr, setArr, expIdx) {
    const copy = [...arr]; copy[expIdx] = { ...copy[expIdx], bullets: [...(copy[expIdx].bullets || []), ''] }; setArr(copy)
  }
  function removeBullet(arr, setArr, expIdx, bulletIdx) {
    const copy = [...arr]; let bullets = (copy[expIdx].bullets || []).filter((_, i) => i !== bulletIdx)
    if (!bullets.length) bullets = ['']
    copy[expIdx] = { ...copy[expIdx], bullets }; setArr(copy)
  }

  // ── Drag-and-drop section reordering ─────────────────────────────────────────
  function handleDragStart(sectionId) { setDragSection(sectionId) }
  function handleDragOver(e, sectionId) { e.preventDefault(); setDragOverSection(sectionId) }
  function handleDrop(sectionId) {
    if (!dragSection || dragSection === sectionId) { setDragSection(null); setDragOverSection(null); return }
    const newOrder = [...sectionOrder]
    const fromIdx = newOrder.indexOf(dragSection)
    const toIdx   = newOrder.indexOf(sectionId)
    if (fromIdx === -1 || toIdx === -1) { setDragSection(null); setDragOverSection(null); return }
    newOrder.splice(fromIdx, 1)
    newOrder.splice(toIdx, 0, dragSection)
    setSectionOrder(newOrder)
    setDragSection(null)
    setDragOverSection(null)
  }
  function handleDragEnd() { setDragSection(null); setDragOverSection(null) }

  // ── Build payload ─────────────────────────────────────────────────────────────
  function buildPayload() {
    return {
      full_name: fullName.trim(), email: email.trim(), phone: phone.trim(),
      location: location.trim(), linkedin: linkedin.trim(), summary: summary.trim(),
      job_description: jobDescription.trim(),
      experiences: experiences.map(e => ({ ...e, bullets: (e.bullets || []).filter(b => b.trim()) })).filter(e => e.title.trim() || e.company.trim()),
      education: education.filter(e => e.degree.trim() || e.school.trim()),
      skills: skills.filter(s => s.trim()),
      certifications: certifications.filter(c => c.name.trim()),
      projects: projects.map(p => ({ ...p, bullets: (p.bullets || []).filter(b => b.trim()) })).filter(p => p.name.trim()),
      languages: languages.filter(l => l.name.trim()),
      social_links: socialLinks.filter(s => s.platform.trim() && s.url.trim()),
      template, output_format: outputFormat, lang,
      font_family: fontFamily || '',
    }
  }

  // Live data for preview (includes partial data)
  const livePreviewData = {
    fullName, email, phone, location, linkedin, summary,
    experiences, education, skills, certifications, projects, languages, socialLinks,
  }

  // ── Preview & Generate ────────────────────────────────────────────────────────
  async function handlePreview() {
    if (!fullName.trim()) { addToast(t('cv_builder.name_required'), 'error'); return }
    setLoading(true)
    try {
      const data = await previewCV(token, buildPayload())
      setPreviewData(data.enhanced_data)
      addToast(t('cv_builder.preview_ready'), 'success')
    } catch (err) {
      addToast(err.message || t('toast.error_generic'), 'error')
    } finally {
      setLoading(false)
    }
  }

  async function handleGenerate() {
    if (!fullName.trim()) { addToast(t('cv_builder.name_required'), 'error'); return }
    if (!canAnalyze()) { addToast(t('toast.limit_reached'), 'warning'); return }
    setLoading(true)
    try {
      const res = await generateCV(token, buildPayload())
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      const safeName = fullName.trim().replace(/\s+/g, '_').replace(/[^a-zA-Z0-9_-]/g, '') || 'CV'
      a.href = url; a.download = `${safeName}_CV.${outputFormat}`
      document.body.appendChild(a); a.click(); document.body.removeChild(a)
      URL.revokeObjectURL(url)
      recordAnalysis()
      addToast(t('cv_builder.download_success'), 'success')
    } catch (err) {
      if (err.message?.includes('403')) refreshUsage(token, { background: true })
      addToast(err.message || t('toast.error_generic'), 'error')
    } finally {
      setLoading(false)
    }
  }

  // ── AI Summary Suggestions ────────────────────────────────────────────────────
  async function handleSuggestSummary() {
    if (summary.trim().length < 20) {
      addToast(t('cv_builder.suggest_min_chars'), 'warning')
      return
    }
    setSuggestLoading(true)
    setSuggestError('')
    setSuggestions([])
    try {
      const data = await suggestSummary(token, {
        summary: summary.trim(),
        job_description: jobDescription.trim(),
        lang,
      })
      setSuggestions(data.suggestions || [])
    } catch (err) {
      setSuggestError(err.message || t('cv_builder.suggest_error'))
    } finally {
      setSuggestLoading(false)
    }
  }

  function handlePickSuggestion(text) {
    setSummary(text)
    setSuggestions([])
    addToast('✓', 'success')
  }

  // ── Section renderers for step 2 ──────────────────────────────────────────────
  function renderSectionCard(sectionId) {
    const isDragOver = dragOverSection === sectionId
    const isDragging = dragSection === sectionId

    const wrapSection = (title, addBtn, content) => (
      <div
        key={sectionId}
        className={`card cv-section-card ${isDragOver ? 'drag-over' : ''} ${isDragging ? 'dragging' : ''}`}
        draggable
        onDragStart={() => handleDragStart(sectionId)}
        onDragOver={e => handleDragOver(e, sectionId)}
        onDrop={() => handleDrop(sectionId)}
        onDragEnd={handleDragEnd}
      >
        <div className="cv-section-header">
          <div className="cv-section-header-left">
            <span className="cv-drag-handle" title={t('cv_builder.drag_to_reorder')}>
              <GripVertical size={16} />
            </span>
            <h3>{title}</h3>
          </div>
          {addBtn}
        </div>
        {content}
      </div>
    )

    switch (sectionId) {
      case 'experience':
        return wrapSection(
          t('cv_builder.experience_title'),
          <button className="btn-ghost btn-sm" onClick={() => addArrayItem(experiences, setExperiences, { ...EMPTY_EXP, bullets: [''] })}>
            <Plus size={14} /> {t('cv_builder.add_experience')}
          </button>,
          <>
            {experiences.map((exp, i) => (
              <div key={i} className="cv-entry-card">
                <div className="cv-entry-header">
                  <span className="cv-entry-num">#{i + 1}</span>
                  {experiences.length > 1 && (
                    <button className="btn-ghost btn-sm danger" onClick={() => removeArrayItem(experiences, setExperiences, i)}>
                      <Trash2 size={13} />
                    </button>
                  )}
                </div>
                <div className="cv-form-grid">
                  <div className="form-group">
                    <label>{t('cv_builder.job_title')}</label>
                    <input value={exp.title} onChange={e => updateArrayItem(experiences, setExperiences, i, 'title', e.target.value)} placeholder={t('cv_builder.ph_job_title')} />
                  </div>
                  <div className="form-group">
                    <label>{t('cv_builder.company')}</label>
                    <input value={exp.company} onChange={e => updateArrayItem(experiences, setExperiences, i, 'company', e.target.value)} placeholder="Google" />
                  </div>
                  <div className="form-group">
                    <label>{t('cv_builder.location_label')}</label>
                    <input value={exp.location} onChange={e => updateArrayItem(experiences, setExperiences, i, 'location', e.target.value)} placeholder={t('cv_builder.ph_location')} />
                  </div>
                  <div className="form-group">
                    <label>{t('cv_builder.start_date')}</label>
                    <input value={exp.start_date} onChange={e => updateArrayItem(experiences, setExperiences, i, 'start_date', e.target.value)} placeholder={t('cv_builder.ph_start_date')} />
                  </div>
                  <div className="form-group">
                    <label>{t('cv_builder.end_date')}</label>
                    <input value={exp.end_date} onChange={e => updateArrayItem(experiences, setExperiences, i, 'end_date', e.target.value)} placeholder={t('cv_builder.ph_end_date')} />
                  </div>
                </div>
                <div className="cv-bullets">
                  <label>{t('cv_builder.bullets_label')}</label>
                  <p className="form-hint">{t('cv_builder.bullets_hint')}</p>
                  {(exp.bullets || ['']).map((b, bi) => (
                    <div key={bi} className="cv-bullet-row">
                      <span className="bullet-dot">•</span>
                      <input value={b} onChange={e => updateBullet(experiences, setExperiences, i, bi, e.target.value)} placeholder={t('cv_builder.bullet_placeholder')} />
                      <button className="btn-ghost btn-xs" onClick={() => removeBullet(experiences, setExperiences, i, bi)}><Trash2 size={11} /></button>
                    </div>
                  ))}
                  <button className="btn-ghost btn-xs" onClick={() => addBullet(experiences, setExperiences, i)}>
                    <Plus size={11} /> {t('cv_builder.add_bullet')}
                  </button>
                </div>
              </div>
            ))}
          </>
        )

      case 'education':
        return wrapSection(
          t('cv_builder.education_title'),
          <button className="btn-ghost btn-sm" onClick={() => addArrayItem(education, setEducation, { ...EMPTY_EDU })}>
            <Plus size={14} /> {t('cv_builder.add_education')}
          </button>,
          <>
            {education.map((edu, i) => (
              <div key={i} className="cv-entry-card">
                <div className="cv-entry-header">
                  <span className="cv-entry-num">#{i + 1}</span>
                  {education.length > 1 && (
                    <button className="btn-ghost btn-sm danger" onClick={() => removeArrayItem(education, setEducation, i)}><Trash2 size={13} /></button>
                  )}
                </div>
                <div className="cv-form-grid">
                  <div className="form-group">
                    <label>{t('cv_builder.degree')}</label>
                    <input value={edu.degree} onChange={e => updateArrayItem(education, setEducation, i, 'degree', e.target.value)} placeholder={t('cv_builder.ph_degree')} />
                  </div>
                  <div className="form-group">
                    <label>{t('cv_builder.field_of_study')}</label>
                    <input value={edu.field} onChange={e => updateArrayItem(education, setEducation, i, 'field', e.target.value)} placeholder={t('cv_builder.ph_field')} />
                  </div>
                  <div className="form-group">
                    <label>{t('cv_builder.school')}</label>
                    <input value={edu.school} onChange={e => updateArrayItem(education, setEducation, i, 'school', e.target.value)} placeholder="MIT" />
                  </div>
                  <div className="form-group">
                    <label>{t('cv_builder.start_date')}</label>
                    <input value={edu.start_date} onChange={e => updateArrayItem(education, setEducation, i, 'start_date', e.target.value)} placeholder={t('cv_builder.ph_edu_start')} />
                  </div>
                  <div className="form-group">
                    <label>{t('cv_builder.end_date')}</label>
                    <input value={edu.end_date} onChange={e => updateArrayItem(education, setEducation, i, 'end_date', e.target.value)} placeholder={t('cv_builder.ph_edu_end')} />
                  </div>
                  <div className="form-group">
                    <label>GPA</label>
                    <input value={edu.gpa} onChange={e => updateArrayItem(education, setEducation, i, 'gpa', e.target.value)} placeholder="3.8/4.0" />
                  </div>
                </div>
              </div>
            ))}
          </>
        )

      case 'skills':
        return wrapSection(
          t('cv_builder.skills_title'),
          <button className="btn-ghost btn-sm" onClick={() => setSkills([...skills, ''])}>
            <Plus size={14} /> {t('cv_builder.add_skill')}
          </button>,
          <>
            <p className="form-hint">{t('cv_builder.skills_hint')}</p>
            <div className="cv-skills-list">
              {skills.map((s, i) => (
                <div key={i} className="cv-skill-row">
                  <input value={s} onChange={e => { const copy = [...skills]; copy[i] = e.target.value; setSkills(copy) }} placeholder={t('cv_builder.skill_placeholder')} />
                  {skills.length > 1 && (
                    <button className="btn-ghost btn-xs" onClick={() => setSkills(skills.filter((_, j) => j !== i))}><Trash2 size={11} /></button>
                  )}
                </div>
              ))}
            </div>
          </>
        )

      case 'certifications':
        return wrapSection(
          t('cv_builder.certifications_title'),
          <button className="btn-ghost btn-sm" onClick={() => addArrayItem(certifications, setCertifications, { ...EMPTY_CERT })}>
            <Plus size={14} /> {t('cv_builder.add_certification')}
          </button>,
          <>
            {certifications.map((cert, i) => (
              <div key={i} className="cv-entry-card">
                <div className="cv-entry-header">
                  <span className="cv-entry-num">#{i + 1}</span>
                  <button className="btn-ghost btn-sm danger" onClick={() => removeArrayItem(certifications, setCertifications, i)}><Trash2 size={13} /></button>
                </div>
                <div className="cv-form-grid">
                  <div className="form-group">
                    <label>{t('cv_builder.cert_name')}</label>
                    <input value={cert.name} onChange={e => updateArrayItem(certifications, setCertifications, i, 'name', e.target.value)} placeholder="AWS Solutions Architect" />
                  </div>
                  <div className="form-group">
                    <label>{t('cv_builder.cert_issuer')}</label>
                    <input value={cert.issuer} onChange={e => updateArrayItem(certifications, setCertifications, i, 'issuer', e.target.value)} placeholder="Amazon Web Services" />
                  </div>
                  <div className="form-group">
                    <label>{t('cv_builder.cert_date')}</label>
                    <input value={cert.date} onChange={e => updateArrayItem(certifications, setCertifications, i, 'date', e.target.value)} placeholder={t('cv_builder.ph_cert_date')} />
                  </div>
                </div>
              </div>
            ))}
            {certifications.length === 0 && <p className="empty-hint">{t('cv_builder.no_certs_hint')}</p>}
          </>
        )

      case 'projects':
        return wrapSection(
          t('cv_builder.projects_title'),
          <button className="btn-ghost btn-sm" onClick={() => addArrayItem(projects, setProjects, { ...EMPTY_PROJ, bullets: [''] })}>
            <Plus size={14} /> {t('cv_builder.add_project')}
          </button>,
          <>
            {projects.map((proj, i) => (
              <div key={i} className="cv-entry-card">
                <div className="cv-entry-header">
                  <span className="cv-entry-num">#{i + 1}</span>
                  <button className="btn-ghost btn-sm danger" onClick={() => removeArrayItem(projects, setProjects, i)}><Trash2 size={13} /></button>
                </div>
                <div className="cv-form-grid">
                  <div className="form-group full-width">
                    <label>{t('cv_builder.project_name')}</label>
                    <input value={proj.name} onChange={e => updateArrayItem(projects, setProjects, i, 'name', e.target.value)} placeholder="E-commerce Platform" />
                  </div>
                  <div className="form-group full-width">
                    <label>{t('cv_builder.project_desc')}</label>
                    <input value={proj.description} onChange={e => updateArrayItem(projects, setProjects, i, 'description', e.target.value)} placeholder={t('cv_builder.ph_project_desc')} />
                  </div>
                </div>
                <div className="cv-bullets">
                  {(proj.bullets || ['']).map((b, bi) => (
                    <div key={bi} className="cv-bullet-row">
                      <span className="bullet-dot">•</span>
                      <input value={b} onChange={e => updateBullet(projects, setProjects, i, bi, e.target.value)} placeholder={t('cv_builder.bullet_placeholder')} />
                      <button className="btn-ghost btn-xs" onClick={() => removeBullet(projects, setProjects, i, bi)}><Trash2 size={11} /></button>
                    </div>
                  ))}
                  <button className="btn-ghost btn-xs" onClick={() => addBullet(projects, setProjects, i)}>
                    <Plus size={11} /> {t('cv_builder.add_bullet')}
                  </button>
                </div>
              </div>
            ))}
            {projects.length === 0 && <p className="empty-hint">{t('cv_builder.no_projects_hint')}</p>}
          </>
        )

      case 'languages':
        return wrapSection(
          t('cv_builder.languages_title'),
          <button className="btn-ghost btn-sm" onClick={() => addArrayItem(languages, setLanguages, { ...EMPTY_LANG })}>
            <Plus size={14} /> {t('cv_builder.add_language')}
          </button>,
          <>
            {languages.map((l, i) => (
              <div key={i} className="cv-entry-card cv-lang-entry">
                <div className="cv-entry-header">
                  <div className="form-group" style={{ flex: 1, marginBottom: 0 }}>
                    <label>{t('cv_builder.language_name')}</label>
                    <input value={l.name} onChange={e => updateArrayItem(languages, setLanguages, i, 'name', e.target.value)} placeholder="English" />
                  </div>
                  {languages.length > 1 && (
                    <button className="btn-ghost btn-xs danger" onClick={() => removeArrayItem(languages, setLanguages, i)}><Trash2 size={11} /></button>
                  )}
                </div>
                <div className="cv-lang-skills-grid">
                  {['writing', 'listening', 'speaking'].map(skill => (
                    <div key={skill} className="form-group">
                      <label>{t(`cv_builder.lang_${skill}`)}</label>
                      <select value={l[skill] || ''} onChange={e => updateArrayItem(languages, setLanguages, i, skill, e.target.value)}>
                        <option value="">{t('cv_builder.select_level')}</option>
                        {CEFR_LEVELS.map(lv => (
                          <option key={lv} value={lv}>{lv === 'Native' ? t('cv_builder.level_native') : lv}</option>
                        ))}
                      </select>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </>
        )

      default:
        return null
    }
  }

  const SECTION_LABELS = {
    experience: t('cv_builder.experience_title'),
    education:  t('cv_builder.education_title'),
    skills:     t('cv_builder.skills_title'),
    certifications: t('cv_builder.certifications_title'),
    projects:   t('cv_builder.projects_title'),
    languages:  t('cv_builder.languages_title'),
  }

  return (
    <div className="app-layout">
      <Navbar />
      <main style={{ flex: 1 }} id="main-content">
        <div className="cv-builder-page" style={{ maxWidth: 1400, margin: '0 auto', padding: '24px 24px 48px' }}>

          {/* Page header with decorative orbs */}
          <motion.div
            className="cv-builder-hero"
            initial={{ opacity: 0, y: -16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            {/* Decorative floating orbs */}
            <div className="cv-hero-orb cv-hero-orb-1" />
            <div className="cv-hero-orb cv-hero-orb-2" />
            <div className="cv-hero-orb cv-hero-orb-3" />

            {/* Geometric shapes */}
            <div className="cv-hero-shape cv-hero-shape-ring" />
            <div className="cv-hero-shape cv-hero-shape-dots" />

            <div className="cv-hero-content">
              <div className="cv-hero-icon-wrap">
                <FileText size={26} />
                <div className="cv-hero-icon-glow" />
              </div>
              <div>
                <h1 className="cv-hero-title">{t('cv_builder.title')}</h1>
                <p className="cv-hero-subtitle">{t('cv_builder.subtitle')}</p>
              </div>
            </div>
          </motion.div>

          {/* Prefill banner */}
          {showPrefillBanner && (
            <div className="alert alert-warning" style={{ marginBottom: 16 }}>
              <span className="alert-icon">ℹ</span>
              <div>
                <strong>{t('cv_builder.prefill_review_title')}</strong>
                <p>{t('cv_builder.prefill_review_desc')}</p>
                {prefillSummary && (
                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.65rem' }}>
                    {prefillSummary.experiences > 0 && <span className="skill-tag">{t('cv_builder.prefill_summary_experiences')}: {prefillSummary.experiences}</span>}
                    {prefillSummary.education > 0 && <span className="skill-tag">{t('cv_builder.prefill_summary_education')}: {prefillSummary.education}</span>}
                    {prefillSummary.skills > 0 && <span className="skill-tag">{t('cv_builder.prefill_summary_skills')}: {prefillSummary.skills}</span>}
                  </div>
                )}
              </div>
              <button className="btn-ghost btn-sm" onClick={() => setShowPrefillBanner(false)}>✕</button>
            </div>
          )}

          {/* Split-pane layout */}
          <div className="cv-split-layout">

            {/* ── Left: Editor pane ─────────────────────────────── */}
            <div className="cv-editor-pane">

              {/* Step indicator with connector */}
              <div className="cv-steps-wrapper">
                <div className="cv-steps-connector">
                  <div className="cv-steps-connector-fill" style={{ width: step === 1 ? '0%' : step === 2 ? '50%' : '100%' }} />
                </div>
                <div className="cv-steps">
                  {[1, 2, 3].map(s => (
                    <motion.button
                      key={s}
                      className={`cv-step-btn ${step === s ? 'active' : ''} ${step > s ? 'done' : ''}`}
                      onClick={() => setStep(s)}
                      whileHover={{ scale: 1.04 }}
                      whileTap={{ scale: 0.97 }}
                    >
                      <span className="cv-step-num">{step > s ? '✓' : s}</span>
                      <span className="cv-step-label">
                        {s === 1 ? t('cv_builder.step_info') : s === 2 ? t('cv_builder.step_details') : t('cv_builder.step_generate')}
                      </span>
                    </motion.button>
                  ))}
                </div>
              </div>

              <AnimatePresence mode="wait">

              {/* STEP 1: Personal Info */}
              {step === 1 && (
                <motion.div
                  key="step-1"
                  className="cv-builder-section"
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 20 }}
                  transition={{ duration: 0.3 }}
                >
                  <div className="card">
                    <h3>{t('cv_builder.personal_info')}</h3>
                    <div className="cv-form-grid">
                      <div className="form-group">
                        <label>{t('cv_builder.full_name')} *</label>
                        <input type="text" value={fullName} onChange={e => setFullName(e.target.value)} placeholder={t('cv_builder.ph_full_name')} />
                      </div>
                      <div className="form-group">
                        <label>{t('cv_builder.email_label')}</label>
                        <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="john@example.com" />
                      </div>
                      <div className="form-group">
                        <label>{t('cv_builder.phone_label')}</label>
                        <input type="tel" value={phone} onChange={e => setPhone(e.target.value)} placeholder={t('cv_builder.ph_phone')} />
                      </div>
                      <div className="form-group">
                        <label>{t('cv_builder.location_label')}</label>
                        <input type="text" value={location} onChange={e => setLocation(e.target.value)} placeholder={t('cv_builder.ph_location')} />
                      </div>
                      <div className="form-group full-width">
                        <label>LinkedIn</label>
                        <input type="text" value={linkedin} onChange={e => setLinkedin(e.target.value)} placeholder="linkedin.com/in/johndoe" />
                      </div>
                    </div>
                  </div>

                  {/* Social Links */}
                  <div className="card">
                    <div className="cv-section-header" style={{ marginBottom: 8 }}>
                      <h3 style={{ display: 'flex', alignItems: 'center', gap: 8 }}><Link2 size={16} /> {t('cv_builder.social_links_title')}</h3>
                      <button className="btn-ghost btn-sm" onClick={() => setSocialLinks([...socialLinks, { ...EMPTY_SOCIAL }])}>
                        <Plus size={14} /> {t('cv_builder.add_social')}
                      </button>
                    </div>
                    <p className="form-hint">{t('cv_builder.social_links_hint')}</p>
                    {socialLinks.length === 0 && <p className="empty-hint">{t('cv_builder.no_social_hint')}</p>}
                    {socialLinks.map((s, i) => (
                      <div key={i} className="cv-social-row">
                        <select value={s.platform} onChange={e => { const copy = [...socialLinks]; copy[i] = { ...copy[i], platform: e.target.value }; setSocialLinks(copy) }}>
                          <option value="">{t('cv_builder.select_platform')}</option>
                          <option value="GitHub">GitHub</option>
                          <option value="Portfolio">{t('cv_builder.platform_portfolio')}</option>
                          <option value="Twitter / X">Twitter / X</option>
                          <option value="Kaggle">Kaggle</option>
                          <option value="Stack Overflow">Stack Overflow</option>
                          <option value="Behance">Behance</option>
                          <option value="Dribbble">Dribbble</option>
                          <option value="Medium">Medium</option>
                          <option value="YouTube">YouTube</option>
                          <option value="Other">{t('cv_builder.platform_other')}</option>
                        </select>
                        <input value={s.url} onChange={e => { const copy = [...socialLinks]; copy[i] = { ...copy[i], url: e.target.value }; setSocialLinks(copy) }} placeholder="https://github.com/username" />
                        <button className="btn-ghost btn-xs danger" onClick={() => setSocialLinks(socialLinks.filter((_, j) => j !== i))}><Trash2 size={11} /></button>
                      </div>
                    ))}
                  </div>

                  <div className="card">
                    <h3>{t('cv_builder.summary_title')}</h3>
                    <p className="form-hint">{t('cv_builder.summary_hint')}</p>
                    <textarea className="cv-textarea" rows={4} value={summary} onChange={e => { setSummary(e.target.value); if (suggestions.length) setSuggestions([]) }} placeholder={t('cv_builder.summary_placeholder')} />

                    {/* AI Suggest button */}
                    <div className="cv-suggest-row">
                      <motion.button
                        className="btn-outline btn-sm cv-suggest-btn"
                        onClick={handleSuggestSummary}
                        disabled={suggestLoading || summary.trim().length < 20}
                        whileHover={{ scale: 1.03 }}
                        whileTap={{ scale: 0.97 }}
                      >
                        <Sparkles size={14} />
                        {suggestLoading ? t('cv_builder.suggest_loading') : t('cv_builder.suggest_btn')}
                      </motion.button>
                    </div>

                    {/* Suggestions panel */}
                    <AnimatePresence>
                      {suggestions.length > 0 && (
                        <motion.div
                          className="cv-suggestions-panel"
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: 'auto' }}
                          exit={{ opacity: 0, height: 0 }}
                          transition={{ duration: 0.3 }}
                        >
                          <p className="cv-suggestions-label">{t('cv_builder.suggest_pick')}</p>
                          {suggestions.map((s, i) => (
                            <motion.div
                              key={i}
                              className="cv-suggestion-card"
                              initial={{ opacity: 0, y: 10 }}
                              animate={{ opacity: 1, y: 0 }}
                              transition={{ delay: i * 0.1 }}
                            >
                              <div className="cv-suggestion-header">
                                <span className="cv-suggestion-num">{t('cv_builder.suggest_option')} {i + 1}</span>
                              </div>
                              <p className="cv-suggestion-text">{s}</p>
                              <button className="btn-ghost btn-sm cv-suggestion-use" onClick={() => handlePickSuggestion(s)}>
                                <Check size={13} /> {t('cv_builder.suggest_use')}
                              </button>
                            </motion.div>
                          ))}
                        </motion.div>
                      )}
                    </AnimatePresence>

                    {suggestError && <p className="form-error">{suggestError}</p>}
                  </div>

                  <div className="card">
                    <h3>{t('cv_builder.job_desc_title')}</h3>
                    <p className="form-hint">{t('cv_builder.job_desc_hint')}</p>
                    <textarea className="cv-textarea" rows={5} value={jobDescription} onChange={e => setJobDescription(e.target.value)} placeholder={t('cv_builder.job_desc_placeholder')} />
                  </div>

                  <div className="cv-nav-buttons">
                    <div />
                    <button className="btn-primary" onClick={() => setStep(2)}>
                      {t('common.next')} <ChevronRight size={16} />
                    </button>
                  </div>
                </motion.div>
              )}

              {/* STEP 2: Experience, Education, Skills — draggable */}
              {step === 2 && (
                <motion.div
                  key="step-2"
                  className="cv-builder-section"
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 20 }}
                  transition={{ duration: 0.3 }}
                >
                  <p className="form-hint" style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
                    <GripVertical size={14} /> {t('cv_builder.drag_to_reorder')}
                  </p>
                  {sectionOrder.map(sectionId => renderSectionCard(sectionId))}
                  <div className="cv-nav-buttons">
                    <button className="btn-outline" onClick={() => setStep(1)}>
                      <ChevronLeft size={16} /> {t('common.back')}
                    </button>
                    <button className="btn-primary" onClick={() => setStep(3)}>
                      {t('common.next')} <ChevronRight size={16} />
                    </button>
                  </div>
                </motion.div>
              )}

              {/* STEP 3: ATS Tips + Actions */}
              {step === 3 && (
                <motion.div
                  key="step-3"
                  className="cv-builder-section"
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 20 }}
                  transition={{ duration: 0.3 }}
                >
                  {/* AI-enhanced preview if available */}
                  {previewData && (
                    <div className="card cv-preview-card">
                      <h3>{t('cv_builder.preview_title')}</h3>
                      <div className="cv-preview-content">
                        {previewData.full_name && <div className="cv-preview-name">{previewData.full_name}</div>}
                        {previewData.summary && (
                          <div className="cv-preview-section">
                            <h4>{t('cv_builder.preview_summary')}</h4>
                            <p>{previewData.summary}</p>
                          </div>
                        )}
                        {previewData.experiences?.length > 0 && (
                          <div className="cv-preview-section">
                            <h4>{t('cv_builder.preview_experience')}</h4>
                            {previewData.experiences.map((exp, i) => (
                              <div key={i} className="cv-preview-entry">
                                <strong>{exp.title}</strong> — {exp.company}
                                <ul>{exp.bullets?.map((b, bi) => <li key={bi}>{b}</li>)}</ul>
                              </div>
                            ))}
                          </div>
                        )}
                        {previewData.skills_categorized && Object.keys(previewData.skills_categorized).length > 0 && (
                          <div className="cv-preview-section">
                            <h4>{t('cv_builder.preview_skills')}</h4>
                            {Object.entries(previewData.skills_categorized).map(([cat, items]) => (
                              <p key={cat}><strong>{cat}:</strong> {Array.isArray(items) ? items.join(', ') : items}</p>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  <div className="card cv-tips-card">
                    <h3>{t('cv_builder.ats_tips_title')}</h3>
                    <ul className="cv-tips-list">
                      <li>{t('cv_builder.ats_tip_1')}</li>
                      <li>{t('cv_builder.ats_tip_2')}</li>
                      <li>{t('cv_builder.ats_tip_3')}</li>
                      <li>{t('cv_builder.ats_tip_4')}</li>
                      <li>{t('cv_builder.ats_tip_5')}</li>
                    </ul>
                  </div>

                  <div className="cv-nav-buttons">
                    <button className="btn-outline" onClick={() => setStep(2)}>
                      <ChevronLeft size={16} /> {t('common.back')}
                    </button>
                    <div className="cv-action-group">
                      <button className="btn-outline" onClick={handlePreview} disabled={loading}>
                        <Eye size={15} />
                        {loading ? t('common.loading') : t('cv_builder.preview_btn')}
                      </button>
                      <button className="btn-primary btn-lg" onClick={handleGenerate} disabled={loading || !fullName.trim()}>
                        <Download size={15} />
                        {loading ? t('common.loading') : t('cv_builder.generate_btn')}
                      </button>
                    </div>
                  </div>
                </motion.div>
              )}

              </AnimatePresence>
            </div>

            {/* ── Right: Preview pane ────────────────────────────── */}
            <motion.div
              className="cv-preview-pane"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.45, delay: 0.15 }}
            >

              {/* Header */}
              <div className="cv-preview-header">
                <h4>
                  <Eye size={14} />
                  {t('cv_builder.live_preview')}
                  <span className="preview-live-badge">
                    <span className="preview-live-dot" />
                    LIVE
                  </span>
                </h4>
              </div>

              {/* Template thumbnail selector */}
              <div className="cv-template-thumb-row" style={{ padding: '8px 12px', background: 'var(--bg-card)', border: '1px solid var(--color-border)', borderTop: 'none' }}>
                {availableTemplates.map(tpl => (
                  <button
                    key={tpl}
                    className={`cv-template-thumb-btn ${template === tpl ? 'active' : ''}`}
                    onClick={() => setTemplate(tpl)}
                    title={t(`cv_builder.template_${tpl}`)}
                  >
                    <div className={`cv-template-mini ${tpl}`} style={{ width: 44, height: 58, flexShrink: 0 }}>
                      <div className="mini-header-bar" />
                      <div className="mini-name-line" />
                      <div className="mini-contact-line" />
                      <div className="mini-section-line" />
                      <div className="mini-text-block">
                        <div className="mini-line full" /><div className="mini-line med" />
                      </div>
                    </div>
                    <span style={{ fontSize: '0.65rem' }}>{t(`cv_builder.template_${tpl}`)?.split(' ')[0]}</span>
                  </button>
                ))}
                {!premium && (
                  <div className="cv-template-thumb-btn" style={{ opacity: 0.5, cursor: 'default' }}>
                    <div style={{ fontSize: '1.2rem' }}>🔒</div>
                    <span style={{ fontSize: '0.65rem' }}>PRO</span>
                  </div>
                )}
              </div>

              {/* Font selector */}
              <div style={{ padding: '6px 12px', background: 'var(--bg-card)', border: '1px solid var(--color-border)', borderTop: 'none', display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 600, opacity: 0.7 }}>{t('cv_builder.choose_font')}</span>
                {premium ? (
                  <select
                    value={fontFamily}
                    onChange={e => setFontFamily(e.target.value)}
                    style={{
                      fontSize: '0.75rem',
                      padding: '3px 8px',
                      borderRadius: 4,
                      border: '1px solid var(--color-border)',
                      background: 'var(--bg-card)',
                      color: 'var(--text-primary)',
                      fontFamily: fontFamily || 'inherit',
                      cursor: 'pointer',
                    }}
                  >
                    <option value="">{t('cv_builder.font_default')} ({defaultFont})</option>
                    {availableFonts.map(f => (
                      <option key={f.id} value={f.id} style={{ fontFamily: f.label }}>{f.label}</option>
                    ))}
                  </select>
                ) : (
                  <span style={{ fontSize: '0.7rem', opacity: 0.5 }}>🔒 {t('cv_builder.font_pro_only')}</span>
                )}
              </div>

              {/* Live preview */}
              <div className="cv-live-preview-wrapper">
                <div className="cv-preview-paper-shadow" />
                <CVLivePreview data={livePreviewData} template={template} sectionOrder={sectionOrder} fontFamily={fontFamily} />
                <div className="clp-label">
                  <span className="clp-label-dot" />
                  {t('cv_builder.preview_updates')}
                  {t(`cv_builder.template_${template}`)}
                </div>
              </div>

              {/* Format + Generate actions */}
              <div className="cv-preview-actions">
                <div className="cv-format-mini">
                  <button
                    className={`cv-format-mini-btn ${outputFormat === 'docx' ? 'active' : ''}`}
                    onClick={() => setOutputFormat('docx')}
                    type="button"
                  >
                    DOCX
                    <div style={{ fontSize: '0.62rem', fontWeight: 400, color: 'inherit', opacity: 0.7 }}>
                      {t('cv_builder.docx_desc')}
                    </div>
                  </button>
                  <button
                    className={`cv-format-mini-btn ${outputFormat === 'pdf' ? 'active' : ''}`}
                    onClick={() => setOutputFormat('pdf')}
                    type="button"
                  >
                    PDF
                    <div style={{ fontSize: '0.62rem', fontWeight: 400, color: 'inherit', opacity: 0.7 }}>
                      {t('cv_builder.pdf_desc')}
                    </div>
                  </button>
                </div>
                <button
                  className="btn-primary btn-full"
                  onClick={handleGenerate}
                  disabled={loading || !fullName.trim()}
                >
                  <Download size={15} />
                  {loading ? t('common.loading') : t('cv_builder.generate_btn')}
                </button>
              </div>

            </motion.div>
          </div>
        </div>
      </main>
    </div>
  )
}
