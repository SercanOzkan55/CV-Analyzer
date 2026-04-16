import React, { useState, useEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { useToast } from '../components/Toast'
import { generateCV, previewCV } from '../api'
import Navbar from '../components/Navbar'

const EMPTY_EXP = { title: '', company: '', location: '', start_date: '', end_date: '', bullets: [''] }
const EMPTY_EDU = { degree: '', school: '', location: '', start_date: '', end_date: '', gpa: '', field: '' }
const EMPTY_CERT = { name: '', issuer: '', date: '' }
const EMPTY_PROJ = { name: '', description: '', bullets: [''] }
const EMPTY_LANG = { name: '', level: '' }

function extractNonEmptyTitles(experiences) {
  return (Array.isArray(experiences) ? experiences : [])
    .map((exp) => exp?.title || exp?.company || '')
    .filter((title) => title.trim())
    .slice(0, 3)
}

function extractNonEmptyNames(items, key = 'name') {
  return (Array.isArray(items) ? items : [])
    .map((item) => item?.[key] || '')
    .filter((name) => name.trim())
    .slice(0, 3)
}

export default function CVBuilderPage() {
  const { token, plan, planLoading, canAnalyze, recordAnalysis } = useAuth()
  const { t, lang } = useLanguage()
  const { addToast } = useToast()
  const routeLocation = useLocation()
  const prefillAppliedRef = useRef(false)
  const premium = !planLoading && (plan === 'pro' || plan === 'enterprise')

  // Form state
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [location, setLocation] = useState('')
  const [linkedin, setLinkedin] = useState('')
  const [summary, setSummary] = useState('')
  const [jobDescription, setJobDescription] = useState('')
  const [experiences, setExperiences] = useState([{ ...EMPTY_EXP, bullets: [''] }])
  const [education, setEducation] = useState([{ ...EMPTY_EDU }])
  const [skills, setSkills] = useState([''])
  const [certifications, setCertifications] = useState([])
  const [projects, setProjects] = useState([])
  const [languages, setLanguages] = useState([{ ...EMPTY_LANG }])

  // Template definitions per plan (all ATS-compliant)
  const PLAN_TEMPLATES = {
    free: ['classic'],
    pro: ['classic', 'modern', 'executive', 'professional', 'creative'],
    enterprise: ['classic', 'modern', 'executive', 'professional', 'creative', 'corporate', 'tech', 'consulting'],
  }

  // Settings
  const [template, setTemplate] = useState('classic')
  const [outputFormat, setOutputFormat] = useState('docx')
  const resolvedPlan = planLoading ? 'free' : plan
  const availableTemplates = PLAN_TEMPLATES[resolvedPlan] || PLAN_TEMPLATES.free

  // UI state
  const [loading, setLoading] = useState(false)
  const [previewData, setPreviewData] = useState(null)
  const [step, setStep] = useState(1)
  const [showPrefillBanner, setShowPrefillBanner] = useState(false)
  const [prefillSummary, setPrefillSummary] = useState(null)

  // -- Array field helpers --
  useEffect(() => {
    document.title = `${t('nav.cv_builder')} — CV Analyzer`
  }, [t])

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
        ? prefill.experiences.map((exp) => ({
          ...EMPTY_EXP,
          ...exp,
          bullets: Array.isArray(exp?.bullets) && exp.bullets.length > 0 ? exp.bullets : [''],
        }))
        : [{ ...EMPTY_EXP, bullets: [''] }]
    )

    setEducation(
      Array.isArray(prefill.education) && prefill.education.length > 0
        ? prefill.education.map((edu) => ({ ...EMPTY_EDU, ...edu }))
        : [{ ...EMPTY_EDU }]
    )

    setSkills(
      Array.isArray(prefill.skills) && prefill.skills.length > 0
        ? prefill.skills.map((skill) => String(skill || ''))
        : ['']
    )

    setCertifications(
      Array.isArray(prefill.certifications)
        ? prefill.certifications.map((cert) => ({ ...EMPTY_CERT, ...cert }))
        : []
    )

    setProjects(
      Array.isArray(prefill.projects)
        ? prefill.projects.map((project) => ({
          ...EMPTY_PROJ,
          ...project,
          bullets: Array.isArray(project?.bullets) && project.bullets.length > 0 ? project.bullets : [''],
        }))
        : []
    )

    setLanguages(
      Array.isArray(prefill.languages) && prefill.languages.length > 0
        ? prefill.languages.map((entry) => (
          typeof entry === 'string'
            ? { ...EMPTY_LANG, name: entry, level: '' }
            : { ...EMPTY_LANG, ...entry }
        ))
        : [{ ...EMPTY_LANG }]
    )

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
      certNames: extractNonEmptyNames(prefill.certifications, 'name'),
      projects: Array.isArray(prefill.projects) ? prefill.projects.length : 0,
      projectNames: extractNonEmptyNames(prefill.projects, 'name'),
      languages: Array.isArray(prefill.languages) ? prefill.languages.length : 0,
      languageNames: extractNonEmptyNames(prefill.languages, 'name'),
    })
    setStep(2)
    addToast(t('cv_builder.prefill_loaded'), 'success')
  }, [routeLocation.state, addToast, t])

  function updateArrayItem(arr, setArr, idx, field, value) {
    const copy = [...arr]
    copy[idx] = { ...copy[idx], [field]: value }
    setArr(copy)
  }

  function addArrayItem(arr, setArr, template) {
    setArr([...arr, { ...template }])
  }

  function removeArrayItem(arr, setArr, idx) {
    if (arr.length <= 1) return
    setArr(arr.filter((_, i) => i !== idx))
  }

  function updateBullet(arr, setArr, expIdx, bulletIdx, value) {
    const copy = [...arr]
    const bullets = [...(copy[expIdx].bullets || [])]
    bullets[bulletIdx] = value
    copy[expIdx] = { ...copy[expIdx], bullets }
    setArr(copy)
  }

  function addBullet(arr, setArr, expIdx) {
    const copy = [...arr]
    copy[expIdx] = { ...copy[expIdx], bullets: [...(copy[expIdx].bullets || []), ''] }
    setArr(copy)
  }

  function removeBullet(arr, setArr, expIdx, bulletIdx) {
    const copy = [...arr]
    const bullets = (copy[expIdx].bullets || []).filter((_, i) => i !== bulletIdx)
    if (bullets.length === 0) bullets.push('')
    copy[expIdx] = { ...copy[expIdx], bullets }
    setArr(copy)
  }

  // -- Build payload --
  function buildPayload() {
    return {
      full_name: fullName.trim(),
      email: email.trim(),
      phone: phone.trim(),
      location: location.trim(),
      linkedin: linkedin.trim(),
      summary: summary.trim(),
      job_description: jobDescription.trim(),
      experiences: experiences.map(e => ({
        ...e,
        bullets: (e.bullets || []).filter(b => b.trim()),
      })).filter(e => e.title.trim() || e.company.trim()),
      education: education.filter(e => e.degree.trim() || e.school.trim()),
      skills: skills.filter(s => s.trim()),
      certifications: certifications.filter(c => c.name.trim()),
      projects: projects.map(p => ({
        ...p,
        bullets: (p.bullets || []).filter(b => b.trim()),
      })).filter(p => p.name.trim()),
      languages: languages.filter(l => l.name.trim()),
      template,
      output_format: outputFormat,
      lang,
    }
  }

  // -- Preview --
  async function handlePreview() {
    if (!fullName.trim()) {
      addToast(t('cv_builder.name_required'), 'error')
      return
    }
    setLoading(true)
    try {
      const data = await previewCV(token, buildPayload())
      setPreviewData(data.enhanced_data)
      setStep(3)
      addToast(t('cv_builder.preview_ready'), 'success')
    } catch (err) {
      addToast(err.message || t('toast.error_generic'), 'error')
    } finally {
      setLoading(false)
    }
  }

  // -- Generate & Download --
  async function handleGenerate() {
    if (!fullName.trim()) {
      addToast(t('cv_builder.name_required'), 'error')
      return
    }
    if (!canAnalyze()) {
      addToast(t('toast.limit_reached'), 'warning')
      return
    }
    setLoading(true)
    try {
      const res = await generateCV(token, buildPayload())
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      const safeName = fullName.trim().replace(/\s+/g, '_').replace(/[^a-zA-Z0-9_-]/g, '') || 'CV'
      a.href = url
      a.download = `${safeName}_CV.${outputFormat}`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      recordAnalysis()
      addToast(t('cv_builder.download_success'), 'success')
    } catch (err) {
      addToast(err.message || t('toast.error_generic'), 'error')
    } finally {
      setLoading(false)
    }
  }

  const totalSteps = 3

  return (
    <div className="page">
      <Navbar />
      <main className="main-content" id="main-content">
        <div className="container">
          <div className="page-header">
            <h1>{t('cv_builder.title')}</h1>
            <p className="subtitle">{t('cv_builder.subtitle')}</p>
          </div>

          {showPrefillBanner && (
            <div className="alert alert-warning" style={{ marginBottom: '1rem' }}>
              <span className="alert-icon">ℹ</span>
              <div>
                <strong>{t('cv_builder.prefill_review_title')}</strong>
                <p>{t('cv_builder.prefill_review_desc')}</p>
                {prefillSummary && (
                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.65rem' }}>
                    <span className="skill-tag">
                      {t('cv_builder.prefill_summary_experiences')}: {prefillSummary.experiences}
                      {prefillSummary.experienceTitles?.length > 0 && (
                        <span style={{ opacity: 0.75 }}> • {prefillSummary.experienceTitles.join(', ')}</span>
                      )}
                    </span>
                    <span className="skill-tag">
                      {t('cv_builder.prefill_summary_education')}: {prefillSummary.education}
                      {prefillSummary.educationNames?.length > 0 && (
                        <span style={{ opacity: 0.75 }}> • {prefillSummary.educationNames.join(', ')}</span>
                      )}
                    </span>
                    <span className="skill-tag">
                      {t('cv_builder.prefill_summary_skills')}: {prefillSummary.skills}
                      {prefillSummary.skillNames?.length > 0 && (
                        <span style={{ opacity: 0.75 }}> • {prefillSummary.skillNames.join(', ')}</span>
                      )}
                    </span>
                    {prefillSummary.certifications > 0 && (
                      <span className="skill-tag">
                        {t('cv_builder.prefill_summary_certifications')}: {prefillSummary.certifications}
                        {prefillSummary.certNames?.length > 0 && (
                          <span style={{ opacity: 0.75 }}> • {prefillSummary.certNames.join(', ')}</span>
                        )}
                      </span>
                    )}
                    {prefillSummary.projects > 0 && (
                      <span className="skill-tag">
                        {t('cv_builder.prefill_summary_projects')}: {prefillSummary.projects}
                        {prefillSummary.projectNames?.length > 0 && (
                          <span style={{ opacity: 0.75 }}> • {prefillSummary.projectNames.join(', ')}</span>
                        )}
                      </span>
                    )}
                    {prefillSummary.languages > 0 && (
                      <span className="skill-tag">
                        {t('cv_builder.prefill_summary_languages')}: {prefillSummary.languages}
                        {prefillSummary.languageNames?.length > 0 && (
                          <span style={{ opacity: 0.75 }}> • {prefillSummary.languageNames.join(', ')}</span>
                        )}
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Step Indicator */}
          <div className="cv-steps">
            {[1, 2, 3].map(s => (
              <button
                key={s}
                className={`cv-step-btn ${step === s ? 'active' : ''} ${step > s ? 'done' : ''}`}
                onClick={() => setStep(s)}
              >
                <span className="cv-step-num">{s}</span>
                <span className="cv-step-label">
                  {s === 1 ? t('cv_builder.step_info') : s === 2 ? t('cv_builder.step_details') : t('cv_builder.step_generate')}
                </span>
              </button>
            ))}
          </div>

          {/* STEP 1: Personal Info & Summary */}
          {step === 1 && (
            <div className="cv-builder-section">
              <div className="card">
                <h3>{t('cv_builder.personal_info')}</h3>
                <div className="cv-form-grid">
                  <div className="form-group">
                    <label>{t('cv_builder.full_name')} *</label>
                    <input type="text" value={fullName} onChange={e => setFullName(e.target.value)} placeholder="John Doe" />
                  </div>
                  <div className="form-group">
                    <label>{t('cv_builder.email_label')}</label>
                    <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="john@example.com" />
                  </div>
                  <div className="form-group">
                    <label>{t('cv_builder.phone_label')}</label>
                    <input type="tel" value={phone} onChange={e => setPhone(e.target.value)} placeholder="+1 555-555-5555" />
                  </div>
                  <div className="form-group">
                    <label>{t('cv_builder.location_label')}</label>
                    <input type="text" value={location} onChange={e => setLocation(e.target.value)} placeholder="New York, NY" />
                  </div>
                  <div className="form-group full-width">
                    <label>LinkedIn</label>
                    <input type="text" value={linkedin} onChange={e => setLinkedin(e.target.value)} placeholder="linkedin.com/in/johndoe" />
                  </div>
                </div>
              </div>

              <div className="card">
                <h3>{t('cv_builder.summary_title')}</h3>
                <p className="form-hint">{t('cv_builder.summary_hint')}</p>
                <textarea
                  className="cv-textarea"
                  rows={4}
                  value={summary}
                  onChange={e => setSummary(e.target.value)}
                  placeholder={t('cv_builder.summary_placeholder')}
                />
              </div>

              <div className="card">
                <h3>{t('cv_builder.job_desc_title')}</h3>
                <p className="form-hint">{t('cv_builder.job_desc_hint')}</p>
                <textarea
                  className="cv-textarea"
                  rows={5}
                  value={jobDescription}
                  onChange={e => setJobDescription(e.target.value)}
                  placeholder={t('cv_builder.job_desc_placeholder')}
                />
              </div>

              <div className="cv-nav-buttons">
                <div />
                <button className="btn-primary" onClick={() => setStep(2)}>
                  {t('common.next')} →
                </button>
              </div>
            </div>
          )}

          {/* STEP 2: Experience, Education, Skills */}
          {step === 2 && (
            <div className="cv-builder-section">
              {/* Experience */}
              <div className="card">
                <div className="card-header-row">
                  <h3>{t('cv_builder.experience_title')}</h3>
                  <button className="btn-ghost btn-sm" onClick={() => addArrayItem(experiences, setExperiences, { ...EMPTY_EXP, bullets: [''] })}>
                    + {t('cv_builder.add_experience')}
                  </button>
                </div>
                {experiences.map((exp, i) => (
                  <div key={i} className="cv-entry-card">
                    <div className="cv-entry-header">
                      <span className="cv-entry-num">#{i + 1}</span>
                      {experiences.length > 1 && (
                        <button className="btn-ghost btn-sm danger" onClick={() => removeArrayItem(experiences, setExperiences, i)}>✕</button>
                      )}
                    </div>
                    <div className="cv-form-grid">
                      <div className="form-group">
                        <label>{t('cv_builder.job_title')}</label>
                        <input value={exp.title} onChange={e => updateArrayItem(experiences, setExperiences, i, 'title', e.target.value)} placeholder="Software Engineer" />
                      </div>
                      <div className="form-group">
                        <label>{t('cv_builder.company')}</label>
                        <input value={exp.company} onChange={e => updateArrayItem(experiences, setExperiences, i, 'company', e.target.value)} placeholder="Google" />
                      </div>
                      <div className="form-group">
                        <label>{t('cv_builder.location_label')}</label>
                        <input value={exp.location} onChange={e => updateArrayItem(experiences, setExperiences, i, 'location', e.target.value)} placeholder="Mountain View, CA" />
                      </div>
                      <div className="form-group">
                        <label>{t('cv_builder.start_date')}</label>
                        <input value={exp.start_date} onChange={e => updateArrayItem(experiences, setExperiences, i, 'start_date', e.target.value)} placeholder="Jan 2020" />
                      </div>
                      <div className="form-group">
                        <label>{t('cv_builder.end_date')}</label>
                        <input value={exp.end_date} onChange={e => updateArrayItem(experiences, setExperiences, i, 'end_date', e.target.value)} placeholder="Present" />
                      </div>
                    </div>
                    <div className="cv-bullets">
                      <label>{t('cv_builder.bullets_label')}</label>
                      <p className="form-hint">{t('cv_builder.bullets_hint')}</p>
                      {(exp.bullets || ['']).map((b, bi) => (
                        <div key={bi} className="cv-bullet-row">
                          <span className="bullet-dot">•</span>
                          <input
                            value={b}
                            onChange={e => updateBullet(experiences, setExperiences, i, bi, e.target.value)}
                            placeholder={t('cv_builder.bullet_placeholder')}
                          />
                          <button className="btn-ghost btn-xs" onClick={() => removeBullet(experiences, setExperiences, i, bi)}>✕</button>
                        </div>
                      ))}
                      <button className="btn-ghost btn-xs" onClick={() => addBullet(experiences, setExperiences, i)}>
                        + {t('cv_builder.add_bullet')}
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              {/* Education */}
              <div className="card">
                <div className="card-header-row">
                  <h3>{t('cv_builder.education_title')}</h3>
                  <button className="btn-ghost btn-sm" onClick={() => addArrayItem(education, setEducation, { ...EMPTY_EDU })}>
                    + {t('cv_builder.add_education')}
                  </button>
                </div>
                {education.map((edu, i) => (
                  <div key={i} className="cv-entry-card">
                    <div className="cv-entry-header">
                      <span className="cv-entry-num">#{i + 1}</span>
                      {education.length > 1 && (
                        <button className="btn-ghost btn-sm danger" onClick={() => removeArrayItem(education, setEducation, i)}>✕</button>
                      )}
                    </div>
                    <div className="cv-form-grid">
                      <div className="form-group">
                        <label>{t('cv_builder.degree')}</label>
                        <input value={edu.degree} onChange={e => updateArrayItem(education, setEducation, i, 'degree', e.target.value)} placeholder="Bachelor of Science" />
                      </div>
                      <div className="form-group">
                        <label>{t('cv_builder.field_of_study')}</label>
                        <input value={edu.field} onChange={e => updateArrayItem(education, setEducation, i, 'field', e.target.value)} placeholder="Computer Science" />
                      </div>
                      <div className="form-group">
                        <label>{t('cv_builder.school')}</label>
                        <input value={edu.school} onChange={e => updateArrayItem(education, setEducation, i, 'school', e.target.value)} placeholder="MIT" />
                      </div>
                      <div className="form-group">
                        <label>{t('cv_builder.location_label')}</label>
                        <input value={edu.location} onChange={e => updateArrayItem(education, setEducation, i, 'location', e.target.value)} placeholder="Cambridge, MA" />
                      </div>
                      <div className="form-group">
                        <label>{t('cv_builder.start_date')}</label>
                        <input value={edu.start_date} onChange={e => updateArrayItem(education, setEducation, i, 'start_date', e.target.value)} placeholder="Sep 2016" />
                      </div>
                      <div className="form-group">
                        <label>{t('cv_builder.end_date')}</label>
                        <input value={edu.end_date} onChange={e => updateArrayItem(education, setEducation, i, 'end_date', e.target.value)} placeholder="Jun 2020" />
                      </div>
                      <div className="form-group">
                        <label>GPA</label>
                        <input value={edu.gpa} onChange={e => updateArrayItem(education, setEducation, i, 'gpa', e.target.value)} placeholder="3.8/4.0" />
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Skills */}
              <div className="card">
                <div className="card-header-row">
                  <h3>{t('cv_builder.skills_title')}</h3>
                  <button className="btn-ghost btn-sm" onClick={() => setSkills([...skills, ''])}>
                    + {t('cv_builder.add_skill')}
                  </button>
                </div>
                <p className="form-hint">{t('cv_builder.skills_hint')}</p>
                <div className="cv-skills-list">
                  {skills.map((s, i) => (
                    <div key={i} className="cv-skill-row">
                      <input
                        value={s}
                        onChange={e => {
                          const copy = [...skills]
                          copy[i] = e.target.value
                          setSkills(copy)
                        }}
                        placeholder={t('cv_builder.skill_placeholder')}
                      />
                      {skills.length > 1 && (
                        <button className="btn-ghost btn-xs" onClick={() => setSkills(skills.filter((_, j) => j !== i))}>✕</button>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Certifications */}
              <div className="card">
                <div className="card-header-row">
                  <h3>{t('cv_builder.certifications_title')}</h3>
                  <button className="btn-ghost btn-sm" onClick={() => addArrayItem(certifications, setCertifications, { ...EMPTY_CERT })}>
                    + {t('cv_builder.add_certification')}
                  </button>
                </div>
                {certifications.map((cert, i) => (
                  <div key={i} className="cv-entry-card">
                    <div className="cv-entry-header">
                      <span className="cv-entry-num">#{i + 1}</span>
                      <button className="btn-ghost btn-sm danger" onClick={() => removeArrayItem(certifications, setCertifications, i)}>✕</button>
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
                        <input value={cert.date} onChange={e => updateArrayItem(certifications, setCertifications, i, 'date', e.target.value)} placeholder="Mar 2023" />
                      </div>
                    </div>
                  </div>
                ))}
                {certifications.length === 0 && (
                  <p className="empty-hint">{t('cv_builder.no_certs_hint')}</p>
                )}
              </div>

              {/* Projects */}
              <div className="card">
                <div className="card-header-row">
                  <h3>{t('cv_builder.projects_title')}</h3>
                  <button className="btn-ghost btn-sm" onClick={() => addArrayItem(projects, setProjects, { ...EMPTY_PROJ, bullets: [''] })}>
                    + {t('cv_builder.add_project')}
                  </button>
                </div>
                {projects.map((proj, i) => (
                  <div key={i} className="cv-entry-card">
                    <div className="cv-entry-header">
                      <span className="cv-entry-num">#{i + 1}</span>
                      <button className="btn-ghost btn-sm danger" onClick={() => removeArrayItem(projects, setProjects, i)}>✕</button>
                    </div>
                    <div className="cv-form-grid">
                      <div className="form-group full-width">
                        <label>{t('cv_builder.project_name')}</label>
                        <input value={proj.name} onChange={e => updateArrayItem(projects, setProjects, i, 'name', e.target.value)} placeholder="E-commerce Platform" />
                      </div>
                      <div className="form-group full-width">
                        <label>{t('cv_builder.project_desc')}</label>
                        <input value={proj.description} onChange={e => updateArrayItem(projects, setProjects, i, 'description', e.target.value)} placeholder="Full-stack e-commerce with microservices" />
                      </div>
                    </div>
                    <div className="cv-bullets">
                      {(proj.bullets || ['']).map((b, bi) => (
                        <div key={bi} className="cv-bullet-row">
                          <span className="bullet-dot">•</span>
                          <input
                            value={b}
                            onChange={e => updateBullet(projects, setProjects, i, bi, e.target.value)}
                            placeholder={t('cv_builder.bullet_placeholder')}
                          />
                          <button className="btn-ghost btn-xs" onClick={() => removeBullet(projects, setProjects, i, bi)}>✕</button>
                        </div>
                      ))}
                      <button className="btn-ghost btn-xs" onClick={() => addBullet(projects, setProjects, i)}>
                        + {t('cv_builder.add_bullet')}
                      </button>
                    </div>
                  </div>
                ))}
                {projects.length === 0 && (
                  <p className="empty-hint">{t('cv_builder.no_projects_hint')}</p>
                )}
              </div>

              {/* Languages */}
              <div className="card">
                <div className="card-header-row">
                  <h3>{t('cv_builder.languages_title')}</h3>
                  <button className="btn-ghost btn-sm" onClick={() => addArrayItem(languages, setLanguages, { ...EMPTY_LANG })}>
                    + {t('cv_builder.add_language')}
                  </button>
                </div>
                {languages.map((l, i) => (
                  <div key={i} className="cv-lang-row">
                    <input
                      value={l.name}
                      onChange={e => updateArrayItem(languages, setLanguages, i, 'name', e.target.value)}
                      placeholder="English"
                    />
                    <select value={l.level} onChange={e => updateArrayItem(languages, setLanguages, i, 'level', e.target.value)}>
                      <option value="">{t('cv_builder.select_level')}</option>
                      <option value="Native">Native</option>
                      <option value="Fluent">Fluent</option>
                      <option value="Advanced">Advanced</option>
                      <option value="Intermediate">Intermediate</option>
                      <option value="Beginner">Beginner</option>
                    </select>
                    {languages.length > 1 && (
                      <button className="btn-ghost btn-xs" onClick={() => removeArrayItem(languages, setLanguages, i)}>✕</button>
                    )}
                  </div>
                ))}
              </div>

              <div className="cv-nav-buttons">
                <button className="btn-outline" onClick={() => setStep(1)}>
                  ← {t('common.back')}
                </button>
                <button className="btn-primary" onClick={() => setStep(3)}>
                  {t('common.next')} →
                </button>
              </div>
            </div>
          )}

          {/* STEP 3: Template, Preview & Generate */}
          {step === 3 && (
            <div className="cv-builder-section">
              {/* Template Selection */}
              <div className="card">
                <h3>{t('cv_builder.choose_template')}</h3>
                <p style={{ fontSize: '0.9rem', color: 'var(--color-text-secondary)', marginBottom: '16px' }}>
                  ✅ Tüm şablonlar ATS (Otomatik Tarama Sistemi) uyumludur
                </p>
                <div className="cv-template-grid">
                  {availableTemplates.map(tpl => (
                    <button
                      key={tpl}
                      className={`cv-template-card ${template === tpl ? 'selected' : ''}`}
                      onClick={() => setTemplate(tpl)}
                    >
                      <div className={`cv-template-mini ${tpl}`}>
                        {/* Mini CV preview showing template style */}
                        <div className="mini-header-bar" />
                        <div className="mini-name-line" />
                        <div className="mini-contact-line" />
                        <div className="mini-section-line" />
                        <div className="mini-text-block">
                          <div className="mini-line full" />
                          <div className="mini-line med" />
                        </div>
                        <div className="mini-section-line" />
                        <div className="mini-text-block">
                          <div className="mini-line full" />
                          <div className="mini-line short" />
                          <div className="mini-line med" />
                        </div>
                      </div>
                      <span className="cv-template-name">{t(`cv_builder.template_${tpl}`)}</span>
                      <span className="cv-template-desc">{t(`cv_builder.template_${tpl}_desc`)}</span>
                    </button>
                  ))}
                  {!premium && (
                    <div className="cv-template-card locked">
                      <div className="cv-template-preview">
                        <div className="cv-template-icon locked">🔒</div>
                      </div>
                      <span className="cv-template-name">{t('cv_builder.more_templates')}</span>
                      <span className="cv-template-badge">PRO</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Output Format */}
              <div className="card">
                <h3>{t('cv_builder.output_format')}</h3>
                <div className="cv-format-options">
                  <label className={`cv-format-option ${outputFormat === 'docx' ? 'selected' : ''}`}>
                    <input
                      type="radio"
                      name="format"
                      value="docx"
                      checked={outputFormat === 'docx'}
                      onChange={() => setOutputFormat('docx')}
                    />
                    <div className="cv-format-info">
                      <strong>DOCX</strong>
                      <span>{t('cv_builder.docx_desc')}</span>
                    </div>
                  </label>
                  <label className={`cv-format-option ${outputFormat === 'pdf' ? 'selected' : ''}`}>
                    <input
                      type="radio"
                      name="format"
                      value="pdf"
                      checked={outputFormat === 'pdf'}
                      onChange={() => setOutputFormat('pdf')}
                    />
                    <div className="cv-format-info">
                      <strong>PDF</strong>
                      <span>{t('cv_builder.pdf_desc')}</span>
                    </div>
                  </label>
                </div>
              </div>

              {/* Preview section */}
              {previewData && (
                <div className="card cv-preview-card">
                  <h3>{t('cv_builder.preview_title')}</h3>
                  <div className="cv-preview-content">
                    {previewData.full_name && (
                      <div className="cv-preview-name">{previewData.full_name}</div>
                    )}
                    {previewData.summary && (
                      <div className="cv-preview-section">
                        <h4>Professional Summary</h4>
                        <p>{previewData.summary}</p>
                      </div>
                    )}
                    {previewData.experiences?.length > 0 && (
                      <div className="cv-preview-section">
                        <h4>Experience</h4>
                        {previewData.experiences.map((exp, i) => (
                          <div key={i} className="cv-preview-entry">
                            <strong>{exp.title}</strong> — {exp.company}
                            <ul>
                              {exp.bullets?.map((b, bi) => <li key={bi}>{b}</li>)}
                            </ul>
                          </div>
                        ))}
                      </div>
                    )}
                    {previewData.skills_categorized && Object.keys(previewData.skills_categorized).length > 0 && (
                      <div className="cv-preview-section">
                        <h4>Skills</h4>
                        {Object.entries(previewData.skills_categorized).map(([cat, items]) => (
                          <p key={cat}><strong>{cat}:</strong> {Array.isArray(items) ? items.join(', ') : items}</p>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* ATS Tips */}
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

              {/* Action Buttons */}
              <div className="cv-nav-buttons">
                <button className="btn-outline" onClick={() => setStep(2)}>
                  ← {t('common.back')}
                </button>
                <div className="cv-action-group">
                  <button
                    className="btn-outline"
                    onClick={handlePreview}
                    disabled={loading}
                  >
                    {loading ? t('common.loading') : t('cv_builder.preview_btn')}
                  </button>
                  <button
                    className="btn-primary btn-lg"
                    onClick={handleGenerate}
                    disabled={loading || !fullName.trim()}
                  >
                    {loading ? t('common.loading') : t('cv_builder.generate_btn')}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
