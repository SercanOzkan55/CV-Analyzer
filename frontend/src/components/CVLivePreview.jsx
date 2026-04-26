import React from 'react'

const TEMPLATE_COLORS = {
  classic:      { header: '#4b5563', accent: '#1f2937', bg: '#ffffff', sideAccent: '#e5e7eb', headerBg: 'linear-gradient(135deg, #f9fafb, #f3f4f6)' },
  modern:       { header: '#2b6cb0', accent: '#63b3ed', bg: '#ffffff', sideAccent: '#dbeafe', headerBg: 'linear-gradient(135deg, #eff6ff, #dbeafe)' },
  executive:    { header: '#8b4513', accent: '#a0522d', bg: '#fdfaf7', sideAccent: '#fde68a', headerBg: 'linear-gradient(135deg, #fefce8, #fef3c7)' },
  professional: { header: '#2f4f4f', accent: '#5f8a8a', bg: '#ffffff', sideAccent: '#ccfbf1', headerBg: 'linear-gradient(135deg, #f0fdfa, #ccfbf1)' },
  creative:     { header: '#9b59b6', accent: '#c39bd3', bg: '#ffffff', sideAccent: '#f3e8ff', headerBg: 'linear-gradient(135deg, #faf5ff, #f3e8ff)' },
  corporate:    { header: '#1f4e79', accent: '#3a7cbd', bg: '#f8fafc', sideAccent: '#bfdbfe', headerBg: 'linear-gradient(135deg, #eff6ff, #bfdbfe)' },
  tech:         { header: '#007acc', accent: '#00d4aa', bg: '#fafeff', sideAccent: '#a7f3d0', headerBg: 'linear-gradient(135deg, #ecfdf5, #d1fae5)' },
  consulting:   { header: '#5d4e75', accent: '#8e7daa', bg: '#ffffff', sideAccent: '#e9d5ff', headerBg: 'linear-gradient(135deg, #faf5ff, #e9d5ff)' },
}

/**
 * Live CV preview — renders current form data as a styled CV.
 */
export default function CVLivePreview({ data = {}, template = 'classic', sectionOrder = [], fontFamily = '' }) {
  const colors = TEMPLATE_COLORS[template] || TEMPLATE_COLORS.classic

  const hasAnyData = data.fullName || data.summary ||
    data.experiences?.some(e => e.title || e.company) ||
    data.education?.some(e => e.degree || e.school) ||
    data.skills?.some(s => s.trim())

  const defaultOrder = ['experience', 'education', 'skills', 'certifications', 'projects', 'languages']
  const order = sectionOrder.length > 0 ? sectionOrder : defaultOrder

  if (!hasAnyData) {
    return (
      <div className="clp-empty">
        <div className="clp-empty-inner">
          <div className="clp-empty-icon">
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
              <rect x="8" y="4" width="32" height="40" rx="4" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" opacity="0.3" />
              <rect x="14" y="12" width="20" height="2" rx="1" fill="currentColor" opacity="0.15" />
              <rect x="14" y="18" width="16" height="2" rx="1" fill="currentColor" opacity="0.12" />
              <rect x="14" y="24" width="20" height="2" rx="1" fill="currentColor" opacity="0.1" />
              <rect x="14" y="30" width="12" height="2" rx="1" fill="currentColor" opacity="0.08" />
              <circle cx="36" cy="36" r="8" fill="currentColor" opacity="0.06" />
              <path d="M33 36l2 2 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" opacity="0.2" />
            </svg>
          </div>
          <div className="clp-empty-text">Fill in the form to see your live CV preview</div>
          <div className="clp-empty-hint">Your changes appear here instantly</div>
        </div>
      </div>
    )
  }

  const headerStyle = { color: colors.header, borderColor: colors.header }

  function renderSection(id) {
    switch (id) {
      case 'experience':
        if (!data.experiences?.some(e => e.title || e.company)) return null
        return (
          <div key="experience" className="clp-section">
            <div className="clp-section-title" style={headerStyle}>
              <span className="clp-section-icon">💼</span>
              EXPERIENCE
            </div>
            {data.experiences.filter(e => e.title || e.company).map((exp, i) => (
              <div key={i} className="clp-entry">
                <div className="clp-entry-header">
                  {exp.title && <strong>{exp.title}</strong>}
                  {exp.company && <span> — {exp.company}</span>}
                  {exp.location && <span className="clp-meta"> · {exp.location}</span>}
                </div>
                {(exp.start_date || exp.end_date) && (
                  <div className="clp-dates">
                    {exp.start_date}{exp.end_date ? ` – ${exp.end_date}` : ''}
                  </div>
                )}
                {exp.bullets?.some(b => b.trim()) && (
                  <ul className="clp-bullets">
                    {exp.bullets.filter(b => b.trim()).map((b, bi) => (
                      <li key={bi}>{b}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        )

      case 'education':
        if (!data.education?.some(e => e.degree || e.school)) return null
        return (
          <div key="education" className="clp-section">
            <div className="clp-section-title" style={headerStyle}>
              <span className="clp-section-icon">🎓</span>
              EDUCATION
            </div>
            {data.education.filter(e => e.degree || e.school).map((edu, i) => (
              <div key={i} className="clp-entry">
                <div className="clp-entry-header">
                  {edu.degree && <strong>{edu.degree}{edu.field ? ` in ${edu.field}` : ''}</strong>}
                  {edu.school && <span> — {edu.school}</span>}
                  {edu.location && <span className="clp-meta"> · {edu.location}</span>}
                </div>
                {(edu.start_date || edu.end_date) && (
                  <div className="clp-dates">
                    {edu.start_date}{edu.end_date ? ` – ${edu.end_date}` : ''}
                  </div>
                )}
                {edu.gpa && <div className="clp-dates">GPA: {edu.gpa}</div>}
              </div>
            ))}
          </div>
        )

      case 'skills':
        if (!data.skills?.some(s => s.trim())) return null
        return (
          <div key="skills" className="clp-section">
            <div className="clp-section-title" style={headerStyle}>
              <span className="clp-section-icon">⚡</span>
              SKILLS
            </div>
            <div className="clp-skills-wrap">
              {data.skills.filter(s => s.trim()).map((s, i) => (
                <span key={i} className="clp-skill-chip" style={{ borderColor: `${colors.accent}33`, color: colors.header }}>{s}</span>
              ))}
            </div>
          </div>
        )

      case 'certifications':
        if (!data.certifications?.some(c => c.name)) return null
        return (
          <div key="certifications" className="clp-section">
            <div className="clp-section-title" style={headerStyle}>
              <span className="clp-section-icon">🏆</span>
              CERTIFICATIONS
            </div>
            {data.certifications.filter(c => c.name).map((cert, i) => (
              <div key={i} className="clp-entry">
                <div className="clp-entry-header">
                  <strong>{cert.name}</strong>
                  {cert.issuer && <span> — {cert.issuer}</span>}
                </div>
                {cert.date && <div className="clp-dates">{cert.date}</div>}
              </div>
            ))}
          </div>
        )

      case 'projects':
        if (!data.projects?.some(p => p.name)) return null
        return (
          <div key="projects" className="clp-section">
            <div className="clp-section-title" style={headerStyle}>
              <span className="clp-section-icon">🚀</span>
              PROJECTS
            </div>
            {data.projects.filter(p => p.name).map((proj, i) => (
              <div key={i} className="clp-entry">
                <div className="clp-entry-header">
                  <strong>{proj.name}</strong>
                  {proj.description && <span className="clp-meta"> — {proj.description}</span>}
                </div>
                {proj.bullets?.some(b => b.trim()) && (
                  <ul className="clp-bullets">
                    {proj.bullets.filter(b => b.trim()).map((b, bi) => <li key={bi}>{b}</li>)}
                  </ul>
                )}
              </div>
            ))}
          </div>
        )

      case 'languages':
        if (!data.languages?.some(l => l.name)) return null
        return (
          <div key="languages" className="clp-section">
            <div className="clp-section-title" style={headerStyle}>
              <span className="clp-section-icon">🌍</span>
              LANGUAGES
            </div>
            {data.languages.filter(l => l.name).map((l, i) => {
              const skills = [l.writing && `Writing: ${l.writing}`, l.listening && `Listening: ${l.listening}`, l.speaking && `Speaking: ${l.speaking}`].filter(Boolean)
              return (
                <p key={i} className="clp-text" style={{ marginBottom: 1 }}>
                  <strong>{l.name}</strong>{skills.length > 0 ? ` — ${skills.join(', ')}` : l.level ? ` (${l.level})` : ''}
                </p>
              )
            })}
          </div>
        )

      default:
        return null
    }
  }

  return (
    <div className={`cv-live-preview cv-live-preview--${template}`} style={{ background: colors.bg, fontFamily: fontFamily || undefined }}>
      {/* Template side accent bar */}
      <div className="clp-side-accent" style={{ background: `linear-gradient(180deg, ${colors.header}, ${colors.accent})` }} />

      {/* Header */}
      <div className="clp-header" style={{ background: colors.headerBg, borderBottomColor: colors.header }}>
        {/* Decorative corner shape */}
        <div className="clp-header-shape" style={{ background: colors.header }} />

        {data.fullName && (
          <div className="clp-name" style={{ color: colors.header }}>{data.fullName}</div>
        )}
        {(data.email || data.phone || data.location || data.linkedin) && (
          <div className="clp-contact">
            {[data.email, data.phone, data.location, data.linkedin].filter(Boolean).map((item, i, arr) => (
              <React.Fragment key={i}>
                <span className="clp-contact-item">{item}</span>
                {i < arr.length - 1 && <span className="clp-contact-sep" style={{ color: colors.accent }}>·</span>}
              </React.Fragment>
            ))}
          </div>
        )}
        {data.socialLinks?.some(s => s.platform && s.url) && (
          <div className="clp-contact clp-contact-social">
            {data.socialLinks.filter(s => s.platform && s.url).map((s, i, arr) => (
              <React.Fragment key={i}>
                <span className="clp-contact-item">{s.platform}: {s.url}</span>
                {i < arr.length - 1 && <span className="clp-contact-sep" style={{ color: colors.accent }}>·</span>}
              </React.Fragment>
            ))}
          </div>
        )}
      </div>

      {/* Summary */}
      {data.summary && (
        <div className="clp-section clp-summary-section">
          <div className="clp-section-title" style={headerStyle}>
            <span className="clp-section-icon">📋</span>
            SUMMARY
          </div>
          <p className="clp-text clp-summary-text">{data.summary}</p>
        </div>
      )}

      {/* Dynamic sections in order */}
      {order.map(id => renderSection(id))}

      {/* Bottom decorative line */}
      <div className="clp-footer-line" style={{ background: `linear-gradient(90deg, ${colors.header}, ${colors.accent}, transparent)` }} />
    </div>
  )
}
