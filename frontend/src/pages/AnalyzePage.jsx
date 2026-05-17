import React, { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { useToast } from '../components/Toast'
import { analyzePdf, autoFixCv, buildSkillRoadmap, exportAutoFixedCV, fetchScoreBreakdown } from '../api'
import { addHistoryItem } from '../utils/historyStorage'
import Navbar from '../components/Navbar'
import DragDropUpload from '../components/DragDropUpload'
import ScoreCircle from '../components/ScoreCircle'
import ScoreBars from '../components/ScoreBars'
import ScoreBreakdown from '../components/ScoreBreakdown'
import SkillTags from '../components/SkillTags'
import GlobalBenchmark from '../components/GlobalBenchmark'
import QuotaWarningBanner from '../components/QuotaWarningBanner'
import JDTemplateSelector from '../components/JDTemplateSelector'

function localizedValue(value, lang) {
  if (!value) return ''
  if (typeof value === 'string') return value
  return value[lang] || value.en || value.tr || ''
}

function uiCopy(lang, tr, en) {
  return lang === 'tr' ? tr : en
}

const STATUS_COLOR = {
  success: 'var(--status-success)',
  warning: 'var(--status-warning)',
  danger: 'var(--status-danger)',
  info: 'var(--status-info)',
  accent: 'var(--status-accent)',
}

const STATUS_BG = {
  success: 'var(--status-success-bg)',
  warning: 'var(--status-warning-bg)',
  danger: 'var(--status-danger-bg)',
  info: 'var(--status-info-bg)',
  accent: 'var(--status-accent-bg)',
}

const STATUS_BORDER = {
  success: 'var(--status-success-border)',
  warning: 'var(--status-warning-border)',
  danger: 'var(--status-danger-border)',
  info: 'var(--status-info-border)',
  accent: 'var(--status-accent-border)',
}

const SUPPORTED_CV_TYPES = new Set([
  'application/pdf',
  'text/plain',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
])

function isSupportedCvFile(file) {
  if (!file) return false
  const ext = String(file.name || '').split('.').pop()?.toLowerCase()
  return SUPPORTED_CV_TYPES.has(file.type) || ['pdf', 'txt', 'docx'].includes(ext)
}

function scoreStatus(score, mid = 50, high = 70) {
  const value = Number(score) || 0
  if (value >= high) return 'success'
  if (value >= mid) return 'warning'
  return 'danger'
}

function scoreColor(score, mid = 50, high = 70) {
  return STATUS_COLOR[scoreStatus(score, mid, high)]
}

function scoreToneStyle(score, mid = 50, high = 70) {
  const status = scoreStatus(score, mid, high)
  return {
    background: STATUS_BG[status],
    border: `1px solid ${STATUS_BORDER[status]}`,
  }
}

function scoreGradient(score, mid = 50, high = 70) {
  const status = scoreStatus(score, mid, high)
  return `linear-gradient(90deg, ${STATUS_COLOR[status]}, color-mix(in srgb, ${STATUS_COLOR[status]} 70%, white))`
}

function normalizeForMatch(value) {
  return String(value || '').toLocaleLowerCase('tr-TR')
}

function compactTextList(values) {
  const seen = new Set()
  return values
    .map((value) => String(value || '').trim())
    .filter((value) => {
      if (!value || seen.has(value)) return false
      seen.add(value)
      return true
    })
}

function getSectionKey(section) {
  const label = `${section?.name || ''} ${localizedValue(section?.label, 'tr')} ${localizedValue(section?.label, 'en')}`
  const text = normalizeForMatch(label)

  if (text.includes('contact') || text.includes('ileti') || text.includes('mail') || text.includes('phone')) return 'contact'
  if (text.includes('summary') || text.includes('profile') || text.includes('özet') || text.includes('profil')) return 'summary'
  if (text.includes('experience') || text.includes('deneyim') || text.includes('work')) return 'experience'
  if (text.includes('project') || text.includes('proje')) return 'projects'
  if (text.includes('education') || text.includes('eğitim') || text.includes('academic')) return 'education'
  if (text.includes('skill') || text.includes('yetenek') || text.includes('beceri')) return 'skills'
  if (text.includes('language') || text.includes('dil')) return 'languages'
  if (text.includes('format') || text.includes('layout') || text.includes('ats')) return 'format'
  return 'generic'
}

function getSectionCopy(key, lang) {
  const copy = {
    contact: {
      where: ['CV başlığı ve iletişim satırı', 'CV header and contact line'],
      why: [
        'İşe alımcı ve ATS ilk olarak ad, e-posta, telefon, şehir ve portfolyo/link bilgilerini arar. Eksik ya da dağınık iletişim bilgisi adayın bulunmasını zorlaştırır.',
        'Recruiters and ATS tools first look for name, email, phone, location, and portfolio/profile links. Missing or scattered contact data makes the candidate harder to reach.',
      ],
      steps: [
        ['Ad soyadı en üstte net yaz; hemen altına e-posta, telefon, şehir ve varsa LinkedIn/GitHub/portfolyo ekle.', 'Linkleri tek satırda sade tut ve gereksiz kişisel bilgileri çıkar.', 'E-posta ve telefonun kopyalanabilir düz metin olduğundan emin ol.'],
        ['Put the full name at the top, then email, phone, location, and LinkedIn/GitHub/portfolio if available.', 'Keep links in one clean line and remove unnecessary personal details.', 'Make sure email and phone are selectable plain text.'],
      ],
    },
    summary: {
      where: ['Profesyonel özet / profil bölümü', 'Professional summary / profile section'],
      why: [
        'Özet bölümü CV’nin yönünü anlatır. Rol, seviye, temel teknoloji/uzmanlık ve ölçülebilir etki yoksa analiz motoru CV’nin hedefini zayıf algılar.',
        'The summary tells the reader what the CV is aiming for. Without role, seniority, core skills, and measurable impact, the analysis reads the CV as less focused.',
      ],
      steps: [
        ['2-4 satırlık kısa bir özet yaz.', 'Hedef rolü, deneyim seviyesini ve 3-5 ana yetkinliği belirt.', 'Varsa proje, başarı veya ölçülebilir sonucu tek cümleyle ekle.'],
        ['Write a concise 2-4 line summary.', 'Mention target role, seniority, and 3-5 core strengths.', 'Add one sentence with a project, achievement, or measurable outcome if available.'],
      ],
    },
    experience: {
      where: ['Deneyim / staj / çalışma geçmişi', 'Experience / internship / work history'],
      why: [
        'Deneyim maddeleri sadece görev anlatırsa zayıf kalır. ATS ve recruiter, sorumluluk + kullanılan araç + sonuç formatını daha güçlü değerlendirir.',
        'Experience bullets are weaker when they only list duties. ATS and recruiters value responsibility + tools + outcome more highly.',
      ],
      steps: [
        ['Her deneyimde şirket, rol ve tarih bilgisini aynı düzende ver.', 'Maddeleri fiille başlat: geliştirdim, analiz ettim, optimize ettim gibi.', 'Araç/teknoloji ve sonucu aynı maddede bağla.'],
        ['Use the same order for company, role, and dates in every entry.', 'Start bullets with action verbs such as developed, analyzed, optimized.', 'Connect tools/technologies with outcomes in the same bullet.'],
      ],
    },
    projects: {
      where: ['Projeler bölümü', 'Projects section'],
      why: [
        'Projelerde başlık, teknoloji satırı ve açıklama karışınca CV okunabilirliği düşer. Her proje ayrı blok olmalı; teknoloji listesi alta kaymadan kısa ve düzenli durmalı.',
        'Projects become hard to read when titles, technology lines, and descriptions run together. Each project should be its own block with a short, stable technology line.',
      ],
      steps: [
        ['Her proje için önce proje adını yaz.', 'Alt satıra sadece teknolojileri kısa liste halinde koy.', 'Sonra 2-3 maddeyle ne yaptığını, hangi problemi çözdüğünü ve sonucu anlat.'],
        ['Write the project name first.', 'Put only the technologies on the next short line.', 'Then use 2-3 bullets for what you built, what problem it solved, and the result.'],
      ],
    },
    education: {
      where: ['Eğitim bölümü', 'Education section'],
      why: [
        'Eğitim bilgisi tekrarlandığında veya okul/bölüm/tarih ayrımı belirsiz olduğunda CV gereksiz kalabalık görünür.',
        'Education looks noisy when the same school is repeated or school, degree, and dates are not separated clearly.',
      ],
      steps: [
        ['Okul, bölüm/derece ve tarih bilgisini tek blokta ver.', 'Aynı bilgiyi tekrar eden satırları kaldır.', 'Devam ediyorsa “Devam ediyor” bilgisini tarih satırında göster.'],
        ['Keep school, degree/department, and dates in one block.', 'Remove repeated lines with the same information.', 'If ongoing, show that on the date line.'],
      ],
    },
    skills: {
      where: ['Yetenekler / teknik beceriler', 'Skills / technical skills'],
      why: [
        'Beceri listesi çok uzun, karışık veya kategori dışı olursa güçlü anahtar kelimeler kaybolur.',
        'If the skills list is too long, mixed, or uncategorized, the strongest keywords get buried.',
      ],
      steps: [
        ['Teknik becerileri kategoriye ayır: diller, framework, veritabanı, araçlar.', 'Sadece gerçekten bildiğin becerileri yaz.', 'İş tanımındaki ifadeyi birebir kopyalamadan doğal biçimde eşleştir.'],
        ['Group technical skills by category: languages, frameworks, databases, tools.', 'List only skills you can actually defend.', 'Mirror the job description naturally without blindly copying it.'],
      ],
    },
    languages: {
      where: ['Diller bölümü', 'Languages section'],
      why: [
        'Dil bölümü yoksa veya seviye belirsizse uluslararası/çok dilli roller için önemli bir sinyal eksik kalır.',
        'When languages are missing or levels are unclear, international or multilingual roles lose an important signal.',
      ],
      steps: [
        ['Her dili ayrı yaz ve mümkünse seviye ekle: İngilizce B2/C1 gibi.', 'Ana dil ile yabancı dili karıştırmadan belirt.', 'Dil bölümü çok kısaysa CV’nin en altına sade bir satır olarak koy.'],
        ['List each language separately and add level if possible, such as English B2/C1.', 'Separate native and foreign languages clearly.', 'If the section is short, keep it as a clean line near the bottom.'],
      ],
    },
    format: {
      where: ['Genel sayfa düzeni ve ATS okunabilirliği', 'Overall layout and ATS readability'],
      why: [
        'Çok kolonlu veya yoğun düzenler bazı PDF ayrıştırıcılarda satır sırasını bozabilir. Bu da isim, proje veya beceri gibi alanların yanlış yere taşınmasına neden olur.',
        'Dense or multi-column layouts can break reading order in PDF parsers. That can move names, projects, or skills into the wrong place.',
      ],
      steps: [
        ['Tek kolonlu, net başlıklı ve basit çizgilerle ayrılmış düzen kullan.', 'Tablo, metin kutusu ve ikon içinde kritik bilgi tutma.', 'Başlıkları standart kullan: Deneyim, Eğitim, Projeler, Yetenekler, Diller.'],
        ['Use a single-column layout with clear headings and simple dividers.', 'Avoid putting critical information in tables, text boxes, or icons.', 'Use standard headings: Experience, Education, Projects, Skills, Languages.'],
      ],
    },
    keywords: {
      where: ['İş tanımı eşleşmesi ve anahtar kelimeler', 'Job match and keywords'],
      why: [
        'İş tanımındaki kritik beceriler CV’de kanıtlanmazsa eşleşme puanı düşer. Burada amaç kelime doldurmak değil, gerçek deneyimi doğru ifadeyle göstermek.',
        'If critical job-description skills are not evidenced in the CV, match score drops. The goal is not keyword stuffing, but proving real experience with the right wording.',
      ],
      steps: [
        ['Eksik becerileri önce gerçekten sahip oldukların arasından seç.', 'Bu becerileri yetenek listesine eklemekle kalma; proje veya deneyim maddesinde kanıtla.', 'Her eklediğin anahtar kelimeyi bağlam içinde kullan.'],
        ['Only choose missing skills you truly have.', 'Do not only add them to the skills list; prove them in project or experience bullets.', 'Use every added keyword in context.'],
      ],
    },
    warning: {
      where: ['Analiz uyarısı', 'Analysis warning'],
      why: [
        'Bu uyarı, CV metninin okunması veya puanlanması sırasında güvenilirliği etkileyebilecek bir noktayı gösterir.',
        'This warning points to something that can affect extraction or scoring reliability.',
      ],
      steps: [
        ['Uyarıdaki bölümü CV üzerinde bul.', 'Bilgiyi daha standart bir başlık veya sade satır yapısıyla yeniden yaz.', 'Tekrar analiz edip uyarının kaybolup kaybolmadığını kontrol et.'],
        ['Find the referenced area in the CV.', 'Rewrite it with a standard heading or simpler line structure.', 'Analyze again and confirm the warning disappears.'],
      ],
    },
    generic: {
      where: ['İlgili CV bölümü', 'Relevant CV section'],
      why: [
        'Bu bölüm okunabilirlik, içerik netliği veya ATS sinyali açısından geliştirilebilir görünüyor.',
        'This section can likely be improved for readability, clarity, or ATS signal.',
      ],
      steps: [
        ['Başlığı standartlaştır.', 'Uzun paragrafları kısa maddelere böl.', 'Somut araç, sorumluluk ve sonuç bilgisini birlikte yaz.'],
        ['Standardize the heading.', 'Break long paragraphs into short bullets.', 'Combine tool, responsibility, and outcome in the same context.'],
      ],
    },
  }

  const selected = copy[key] || copy.generic
  return {
    where: selected.where[lang === 'tr' ? 0 : 1],
    why: selected.why[lang === 'tr' ? 0 : 1],
    steps: selected.steps[lang === 'tr' ? 0 : 1],
  }
}

function buildDiagnosticItems(result, jobDesc, lang) {
  if (!result) return []

  const items = []
  const sectionScores = Array.isArray(result.ats?.section_scores) ? result.ats.section_scores : []

  sectionScores.forEach((section, index) => {
    const score = Number(section.score ?? 0)
    const status = section.status || (score >= 70 ? 'pass' : score >= 50 ? 'warning' : 'fail')
    const evidence = compactTextList([
      localizedValue(section.message, lang),
      ...((Array.isArray(section.recommendations) ? section.recommendations : []).map((rec) => localizedValue(rec, lang))),
    ]).slice(0, 4)

    if (status === 'pass' && score >= 85 && evidence.length === 0) return

    const key = getSectionKey(section)
    const copy = getSectionCopy(key, lang)
    const label = localizedValue(section.label, lang) || section.name || uiCopy(lang, 'Bu bölüm', 'This section')
    const severity = status === 'fail' || score < 50 ? 'high' : status === 'warning' || score < 75 ? 'medium' : 'low'

    items.push({
      id: `section-${key}-${index}`,
      markerKey: key,
      severity,
      score,
      title: uiCopy(lang, `${label} bölümünü daha net hale getir`, `Make the ${label} section clearer`),
      where: copy.where,
      why: copy.why,
      steps: copy.steps,
      evidence,
    })
  })

  const warnings = Array.isArray(result.warnings) ? result.warnings : []
  warnings.forEach((warning, index) => {
    const copy = getSectionCopy('warning', lang)
    items.push({
      id: `warning-${index}`,
      markerKey: 'warning',
      severity: 'medium',
      score: 55,
      title: uiCopy(lang, 'Analiz uyarısını kontrol et', 'Check this analysis warning'),
      where: copy.where,
      why: copy.why,
      steps: copy.steps,
      evidence: [localizedValue(warning, lang) || String(warning)],
    })
  })

  const missingSkills = Array.isArray(result.missing_skills) ? compactTextList(result.missing_skills).slice(0, 14) : []
  if (jobDesc?.trim() && missingSkills.length > 0) {
    const copy = getSectionCopy('keywords', lang)
    items.push({
      id: 'missing-skills',
      markerKey: 'keywords',
      severity: missingSkills.length > 5 ? 'high' : 'medium',
      score: Math.max(30, 90 - missingSkills.length * 7),
      title: uiCopy(lang, 'İş tanımına göre eksik görünen becerileri kanıtla', 'Evidence skills that look missing for this job'),
      where: copy.where,
      why: copy.why,
      steps: copy.steps,
      evidence: [uiCopy(lang, `Eksik görünenler: ${missingSkills.join(', ')}`, `Missing-looking skills: ${missingSkills.join(', ')}`)],
    })
  }

  const suggestions = Array.isArray(result.score_suggestions) ? result.score_suggestions : []
  if (jobDesc?.trim() && suggestions.length > 0) {
    const suggestionEvidence = compactTextList(
      suggestions.slice(0, 5).map((suggestion) => {
        const impact = Number(suggestion.impact || 0)
        const action = localizedValue(suggestion.action, lang) || localizedValue(suggestion.keyword, lang) || suggestion.action || suggestion.keyword || ''
        return `${action}${impact ? ` (+${impact.toFixed(1)} pts)` : ''}`
      }),
    )

    if (suggestionEvidence.length > 0) {
      const copy = getSectionCopy('keywords', lang)
      items.push({
        id: 'score-suggestions',
        markerKey: 'keywords',
        severity: 'low',
        score: 72,
        title: uiCopy(lang, 'Puanı artırabilecek yüksek etkili eklemeler', 'High-impact additions that can improve the score'),
        where: copy.where,
        why: copy.why,
        steps: copy.steps,
        evidence: suggestionEvidence,
      })
    }
  }

  if (items.length === 0) {
    items.push({
      id: 'healthy-cv',
      markerKey: 'summary',
      severity: 'success',
      score: 100,
      title: uiCopy(lang, 'CV genel olarak okunabilir görünüyor', 'The CV looks generally readable'),
      where: uiCopy(lang, 'Genel CV yapısı', 'Overall CV structure'),
      why: uiCopy(lang, 'Temel bölümler algılandı ve kritik bir eksik görünmüyor. Yine de hedef role göre anahtar kelime ve ölçülebilir başarı eklemek puanı artırabilir.', 'Core sections were detected and no critical gap stands out. Adding role-specific keywords and measurable achievements can still improve the score.'),
      steps: [
        uiCopy(lang, 'Hedef işe göre özet ve beceri listesini gözden geçir.', 'Review the summary and skills list for the target job.'),
        uiCopy(lang, 'Deneyim ve projelerde sonuç/etki cümlelerini güçlendir.', 'Strengthen outcome/impact wording in experience and projects.'),
      ],
      evidence: [],
    })
  }

  const severityRank = { high: 0, medium: 1, low: 2, success: 3 }
  return items.sort((a, b) => (severityRank[a.severity] ?? 9) - (severityRank[b.severity] ?? 9) || (a.score ?? 100) - (b.score ?? 100))
}

function getMarkerTop(markerKey, index) {
  const positions = {
    contact: 9,
    summary: 20,
    experience: 36,
    projects: 50,
    education: 66,
    skills: 78,
    languages: 88,
    format: 44,
    keywords: 58,
    warning: 32,
    generic: 48,
  }
  return positions[markerKey] || Math.min(88, 18 + index * 12)
}

function toScore(value) {
  const score = Number(value)
  return Number.isFinite(score) ? score : 0
}

function getScoreStatus(score) {
  if (score >= 70) return 'pass'
  if (score >= 50) return 'warning'
  return 'fail'
}

function sectionFound(sectionsFound, key) {
  const aliases = {
    contact: ['contact', 'ileti', 'email', 'phone'],
    summary: ['summary', 'professional summary', 'profile', 'özet', 'profil'],
    experience: ['experience', 'work', 'employment', 'deneyim', 'staj'],
    projects: ['project', 'projects', 'proje'],
    education: ['education', 'academic', 'eğitim'],
    skills: ['skills', 'skill', 'yetenek', 'beceri'],
    languages: ['language', 'languages', 'dil'],
  }
  const wanted = aliases[key] || [key]
  return sectionsFound.some((section) => wanted.some((alias) => section.includes(alias)))
}

function buildCvMapSections(result, lang) {
  if (!result) return []

  const sectionScores = Array.isArray(result.ats?.section_scores) ? result.ats.section_scores : []
  const sectionsFound = Array.isArray(result.ats?.layout?.sections_found)
    ? result.ats.layout.sections_found.map((section) => normalizeForMatch(section))
    : []

  const byKey = new Map()
  sectionScores.forEach((section) => {
    const key = getSectionKey(section)
    const existing = byKey.get(key)
    if (!existing || toScore(section.score) < toScore(existing.score)) {
      byKey.set(key, section)
    }
  })

  const order = [
    { key: 'contact', tr: 'İletişim', en: 'Contact' },
    { key: 'summary', tr: 'Özet', en: 'Summary' },
    { key: 'experience', tr: 'Deneyim', en: 'Experience' },
    { key: 'projects', tr: 'Projeler', en: 'Projects' },
    { key: 'education', tr: 'Eğitim', en: 'Education' },
    { key: 'skills', tr: 'Yetenekler', en: 'Skills' },
    { key: 'languages', tr: 'Diller', en: 'Languages' },
  ]

  return order.map((item) => {
    const section = byKey.get(item.key)
    const found = Boolean(section) || sectionFound(sectionsFound, item.key)
    const score = section ? toScore(section.score) : found ? 72 : 0
    const status = section?.status || (found ? getScoreStatus(score) : 'missing')
    const note = localizedValue(section?.message, lang) || (
      found
        ? uiCopy(lang, 'Bölüm algılandı.', 'Section detected.')
        : uiCopy(lang, 'Bu bölüm net algılanmadı.', 'This section was not clearly detected.')
    )

    return {
      ...item,
      label: uiCopy(lang, item.tr, item.en),
      found,
      score,
      status,
      note,
    }
  })
}

function compactDisplayList(values, limit = 8) {
  const list = compactTextList(Array.isArray(values) ? values : [])
  const visible = list.slice(0, limit)
  const remaining = Math.max(0, list.length - visible.length)
  return { visible, remaining, total: list.length }
}

function getDomainLabel(result, lang) {
  const specialization = result?.specialization?.name
  const industry = result?.industry?.industry_name || result?.industry?.name
  const domain = result?.domain?.label || result?.domain?.name
  return localizedValue(specialization, lang) || localizedValue(industry, lang) || localizedValue(domain, lang) || specialization || industry || domain || ''
}

function buildParserSnapshot(result, jobDesc, lang) {
  if (!result) return []

  const layout = result.ats?.layout || {}
  const sections = Array.isArray(layout.sections_found) ? layout.sections_found : []
  const detectedSkills = compactDisplayList(result.detected_skills, 10)
  const missingSkills = compactDisplayList(result.missing_skills, 8)
  const jobSkills = compactDisplayList(result.job_skills, 8)

  const empty = uiCopy(lang, 'API cevabında yok', 'Not returned by API')
  const none = uiCopy(lang, 'Yok / algılanmadı', 'None / not detected')

  return [
    {
      title: uiCopy(lang, 'Kimlik ve dil', 'Identity and language'),
      rows: [
        { label: uiCopy(lang, 'Ad', 'Name'), value: result.candidate_name || result.name || empty, state: result.candidate_name || result.name ? 'good' : 'muted' },
        { label: 'Email', value: result.candidate_email || result.email || empty, state: result.candidate_email || result.email ? 'good' : 'muted' },
        { label: uiCopy(lang, 'Algılanan dil', 'Detected language'), value: result.detected_language || none, state: result.detected_language ? 'good' : 'warn' },
        { label: uiCopy(lang, 'Alan/uzmanlık', 'Domain/specialization'), value: getDomainLabel(result, lang) || none, state: getDomainLabel(result, lang) ? 'good' : 'muted' },
      ],
    },
    {
      title: uiCopy(lang, 'Yapı ve okunabilirlik', 'Structure and readability'),
      rows: [
        { label: uiCopy(lang, 'Algılanan bölümler', 'Detected sections'), values: sections.length ? sections : [none], state: sections.length ? 'good' : 'warn' },
        { label: uiCopy(lang, 'İletişim sinyali', 'Contact signal'), value: `${Math.round(toScore(layout.contact_score))}/100`, state: toScore(layout.contact_score) >= 70 ? 'good' : 'warn' },
        { label: uiCopy(lang, 'Sayfa düzeni', 'Layout quality'), value: `${Math.round(toScore(result.layout_score || layout.layout_score))}/100`, state: toScore(result.layout_score || layout.layout_score) >= 70 ? 'good' : 'warn' },
        { label: 'ATS', value: `${Math.round(toScore(result.ats_score))}/100`, state: toScore(result.ats_score) >= 70 ? 'good' : 'warn' },
      ],
    },
    {
      title: uiCopy(lang, 'Beceri ve eşleşme', 'Skills and match'),
      rows: [
        { label: uiCopy(lang, 'CV’de bulunan beceriler', 'Skills found in CV'), values: detectedSkills.visible, overflow: detectedSkills.remaining, state: detectedSkills.total ? 'good' : 'warn' },
        ...(jobDesc?.trim() ? [
          { label: uiCopy(lang, 'İş tanımı becerileri', 'Job skills'), values: jobSkills.visible, overflow: jobSkills.remaining, state: jobSkills.total ? 'good' : 'muted' },
          { label: uiCopy(lang, 'Eksik görünen beceriler', 'Missing-looking skills'), values: missingSkills.visible.length ? missingSkills.visible : [uiCopy(lang, 'Kritik eksik beceri görünmüyor', 'No critical missing skill detected')], overflow: missingSkills.remaining, state: missingSkills.total ? 'warn' : 'good' },
        ] : []),
        { label: uiCopy(lang, 'Anahtar kelime skoru', 'Keyword score'), value: `${Math.round(toScore(result.keyword_score))}/100`, state: toScore(result.keyword_score) >= 70 ? 'good' : 'warn' },
        { label: uiCopy(lang, 'Skill skoru', 'Skill score'), value: `${Math.round(toScore(result.skill_score))}/100`, state: toScore(result.skill_score) >= 70 ? 'good' : 'warn' },
      ],
    },
  ]
}

function buildImpactItems(result, diagnosticItems, lang) {
  if (!result) return []

  const fromSuggestions = (Array.isArray(result.score_suggestions) ? result.score_suggestions : [])
    .map((suggestion, index) => {
      const action = localizedValue(suggestion.action, lang)
        || localizedValue(suggestion.keyword, lang)
        || String(suggestion.action || suggestion.keyword || '').trim()
      const impact = toScore(suggestion.impact)
      return action && impact > 0
        ? {
            id: `suggestion-${index}`,
            label: action,
            impact,
            source: uiCopy(lang, 'İş tanımı eşleşmesi', 'Job match'),
          }
        : null
    })
    .filter(Boolean)

  const fromDiagnostics = (Array.isArray(diagnosticItems) ? diagnosticItems : [])
    .filter((item) => item.severity !== 'success')
    .map((item, index) => {
      const missingPoints = Math.max(0, 85 - toScore(item.score))
      const impact = item.severity === 'high'
        ? Math.max(5, missingPoints * 0.28)
        : item.severity === 'medium'
          ? Math.max(3, missingPoints * 0.18)
          : Math.max(1.5, missingPoints * 0.1)
      return {
        id: `diagnostic-${index}`,
        label: item.title,
        impact,
        source: item.where,
      }
    })

  const merged = [...fromSuggestions, ...fromDiagnostics]
    .sort((a, b) => b.impact - a.impact)
    .slice(0, 6)

  if (merged.length > 0) return merged

  return [{
    id: 'stable-score',
    label: uiCopy(lang, 'Hedef role göre özet, beceri ve proje kanıtlarını ince ayarla', 'Fine-tune summary, skills, and project proof for the target role'),
    impact: 2,
    source: uiCopy(lang, 'Genel optimizasyon', 'General optimization'),
  }]
}

function DiagnosticCard({ item, index, lang }) {
  return (
    <article className={`analysis-diagnostic-item analysis-diagnostic-${item.severity}`}>
      <div className="analysis-diagnostic-item-head">
        <span className="analysis-diagnostic-index">{index + 1}</span>
        <div>
          <h3>{item.title}</h3>
          <div className="analysis-diagnostic-meta-row">
            <span>
              {item.severity === 'success'
                ? uiCopy(lang, 'İyi durumda', 'Looks good')
                : item.severity === 'high'
                  ? uiCopy(lang, 'Öncelik: yüksek', 'Priority: high')
                  : item.severity === 'medium'
                    ? uiCopy(lang, 'Öncelik: orta', 'Priority: medium')
                    : uiCopy(lang, 'Öncelik: düşük', 'Priority: low')}
            </span>
            {item.severity !== 'success' && (
              <span>{uiCopy(lang, 'Bölüm skoru', 'Section score')}: {Math.round(item.score || 0)}</span>
            )}
          </div>
        </div>
      </div>

      <div className="analysis-diagnostic-detail-grid">
        <div>
          <strong>{uiCopy(lang, 'Nerede?', 'Where?')}</strong>
          <p>{item.where}</p>
        </div>
        <div>
          <strong>{uiCopy(lang, 'Neden önemli?', 'Why it matters?')}</strong>
          <p>{item.why}</p>
        </div>
      </div>

      {item.steps?.length > 0 && (
        <div className="analysis-diagnostic-steps">
          <strong>{uiCopy(lang, 'Ne yapmalısın?', 'What to do?')}</strong>
          <ol>
            {item.steps.map((step, stepIndex) => (
              <li key={`${item.id}-step-${stepIndex}`}>{step}</li>
            ))}
          </ol>
        </div>
      )}

      {item.evidence?.length > 0 && (
        <div className="analysis-diagnostic-evidence">
          <strong>{uiCopy(lang, 'Analizden gelen kanıt', 'Evidence from analysis')}</strong>
          <ul>
            {item.evidence.map((evidence, evidenceIndex) => (
              <li key={`${item.id}-evidence-${evidenceIndex}`}>{evidence}</li>
            ))}
          </ul>
        </div>
      )}
    </article>
  )
}

function saveToHistory(result, fileName, jobDesc, user) {
  try {
    addHistoryItem(user, {
      id: Date.now(),
      analysis_id: result.analysis_id || null,
      date: new Date().toISOString(),
      fileName,
      jobTitle: jobDesc.slice(0, 60),
      score: result.final_score,
      interpretation: result.interpretation,
      hasJobDesc: !!(jobDesc && jobDesc.trim()),
      result,
    })
  } catch { /* ignore storage errors */ }
}

export default function AnalyzePage() {
  const { user, token, canAnalyze, recordAnalysis, refreshUsage, signOut } = useAuth()
  const { t, lang } = useLanguage()
  const { addToast } = useToast()
  const navigate = useNavigate()

  const [file, setFile] = useState(null)
  const [jobDesc, setJobDesc] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState(null)
  const [saved, setSaved] = useState(false)
  const [activeTab, setActiveTab] = useState('overview')
  const [autoFixResult, setAutoFixResult] = useState(null)
  const [autoFixLoading, setAutoFixLoading] = useState(false)
  const [autoFixError, setAutoFixError] = useState(null)
  const [exportLoading, setExportLoading] = useState(null)
  const [editedText, setEditedText] = useState('')
  const [scoreBreakdown, setScoreBreakdown] = useState(null)
  const [breakdownLoading, setBreakdownLoading] = useState(false)
  const [cvPreviewUrl, setCvPreviewUrl] = useState('')
  const [skillRoadmap, setSkillRoadmap] = useState(null)
  const [skillRoadmapLoading, setSkillRoadmapLoading] = useState(false)
  const [skillRoadmapError, setSkillRoadmapError] = useState(null)

  useEffect(() => {
    if (!file) {
      setCvPreviewUrl('')
      return undefined
    }

    const nextUrl = URL.createObjectURL(file)
    setCvPreviewUrl(nextUrl)
    return () => URL.revokeObjectURL(nextUrl)
  }, [file])

  const diagnosticItems = useMemo(
    () => buildDiagnosticItems(result, jobDesc, lang),
    [result, jobDesc, lang],
  )

  const splitDiagnosticItems = useMemo(() => {
    const columns = { left: [], right: [] }
    diagnosticItems.forEach((item, index) => {
      const entry = { item, index }
      if (index % 2 === 0) columns.left.push(entry)
      else columns.right.push(entry)
    })
    return columns
  }, [diagnosticItems])

  const markerItems = useMemo(() => diagnosticItems.slice(0, 6), [diagnosticItems])
  const cvMapSections = useMemo(() => buildCvMapSections(result, lang), [result, lang])
  const parserSnapshot = useMemo(() => buildParserSnapshot(result, jobDesc, lang), [result, jobDesc, lang])
  const impactItems = useMemo(() => buildImpactItems(result, diagnosticItems, lang), [result, diagnosticItems, lang])
  const maxImpact = useMemo(
    () => Math.max(1, ...impactItems.map((item) => toScore(item.impact))),
    [impactItems],
  )

  // Helper: pick current language from bilingual {en, tr} objects
  const L = (val) => {
    if (!val) return val
    if (typeof val === 'string') return val
    return val[lang] || val.en || val.tr || ''
  }

  async function handleAnalyze(e) {
    e.preventDefault()
    setError(null)
    setResult(null)
    setSaved(false)
    setSkillRoadmap(null)
    setSkillRoadmapError(null)

    if (!file) return setError(t('analyze.no_file'))
    if (!isSupportedCvFile(file)) return setError(uiCopy(lang, 'Lütfen PDF, DOCX veya TXT CV dosyası seçin', 'Please select a PDF, DOCX, or TXT CV file'))
    if (file.size > 10 * 1024 * 1024) return setError(t('analyze.file_too_large'))
    // Job description is optional for ATS-focused checks

    if (!canAnalyze()) {
      addToast(t('toast.limit_reached'), 'warning')
      return
    }

    try {
      setLoading(true)
      // Simulate progress
      setProgress(10)
      const progressInterval = setInterval(() => {
        setProgress((p) => Math.min(p + 15, 85))
      }, 500)

      const data = await analyzePdf(token, file, jobDesc, { lang })

      clearInterval(progressInterval)
      setProgress(100)
      setResult(data)
      setActiveTab('overview')
      setAutoFixResult(null)
      setAutoFixError(null)
      setEditedText('')
      setSkillRoadmap(null)
      setSkillRoadmapError(null)
      recordAnalysis()
      saveToHistory(data, file.name, jobDesc, user)
      addToast(t('toast.analysis_complete'), 'success')
    } catch (err) {
      if (err.message.includes('403')) {
        addToast(t('toast.limit_reached'), 'warning')
        refreshUsage(token, { background: true })
      } else if (err.message.includes('401')) {
        addToast(t('toast.session_expired'), 'error')
        await signOut()
        navigate('/login')
        return
      } else {
        setError(err.message || t('toast.error_generic'))
      }
    } finally {
      setLoading(false)
      setTimeout(() => setProgress(0), 500)
    }
  }

  async function handleAutoFix(useAi = true) {
    if (!file) {
      setAutoFixError(t('analyze.no_file'))
      return
    }

    try {
      setAutoFixLoading(true)
      setAutoFixError(null)

      const data = await autoFixCv(token, file, jobDesc, { lang, useAi })

      setAutoFixResult(data)
      setEditedText(data.optimized_cv_text || '')
      addToast(t('toast.analysis_complete'), 'success')
    } catch (err) {
      console.error('Auto-fix error:', err)
      const msg = err.message || t('toast.error_generic')
      setAutoFixError(msg)
    } finally {
      setAutoFixLoading(false)
    }
  }

  async function handleBuildSkillRoadmap() {
    if (!result || !jobDesc.trim()) {
      setSkillRoadmapError(uiCopy(lang, 'Roadmap icin is tanimi ve analiz sonucu gerekli.', 'A job description and analysis result are required for a roadmap.'))
      return
    }

    try {
      setSkillRoadmapLoading(true)
      setSkillRoadmapError(null)
      const data = await buildSkillRoadmap(token, {
        cv_text: result.cv_text || '',
        job_description: jobDesc,
        lang,
      })
      setSkillRoadmap(data)
    } catch (err) {
      setSkillRoadmapError(err.message || t('toast.error_generic'))
    } finally {
      setSkillRoadmapLoading(false)
    }
  }

  async function handleExportAutoFix(format) {
    if (!autoFixResult || !editedText.trim()) {
      setAutoFixError(t('analyze.no_file'))
      return
    }

    try {
      setExportLoading(format)
      setAutoFixError(null)

      const response = await exportAutoFixedCV(token, {
        optimized_cv_text: editedText,
        output_format: format,
      })

      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      const baseName = (file?.name || 'optimized_cv').replace(/\.pdf$/i, '')
      a.href = url
      a.download = `${baseName}_optimized.${format}`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      setAutoFixError(err.message || t('toast.error_generic'))
    } finally {
      setExportLoading(null)
    }
  }

  function handleReset() {
    setFile(null)
    setJobDesc('')
    setResult(null)
    setError(null)
    setSaved(false)
    setActiveTab('overview')
    setAutoFixResult(null)
    setAutoFixError(null)
    setExportLoading(null)
    setEditedText('')
    setSkillRoadmap(null)
    setSkillRoadmapError(null)
  }

  function getInterpretation(text) {
    const lower = (text || '').toLowerCase()
    if (lower.includes('strong') || lower.includes('güçlü') || lower.includes('forte') || lower.includes('stark') || lower.includes('fuerte') || lower.includes('قوي')) return t('results.strong_match')
    if (lower.includes('moderate') || lower.includes('orta') || lower.includes('modér') || lower.includes('moderat') || lower.includes('moderada') || lower.includes('متوسط')) return t('results.moderate_match')
    return t('results.weak_match')
  }

  function getRiskLabel(text) {
    const lower = (text || '').toLowerCase()
    if (lower.includes('low') || lower.includes('düşük') || lower.includes('faible') || lower.includes('niedrig') || lower.includes('bajo') || lower.includes('منخفض')) return t('results.low_risk')
    if (lower.includes('medium') || lower.includes('orta') || lower.includes('moyen') || lower.includes('mittel') || lower.includes('medio') || lower.includes('متوسط')) return t('results.medium_risk')
    return t('results.high_risk')
  }

  function getRiskColor(level) {
    const lower = (level || '').toLowerCase()
    // Support multiple languages: "low risk", "düşük risk", "risque faible", etc.
    if (lower.includes('low') || lower.includes('düşük') || lower.includes('faible') || lower.includes('bajo') || lower.includes('منخفضة') || lower.includes('baixo') || lower.includes('basso') || lower.includes('laag') || lower.includes('низкий') || lower.includes('低')) return STATUS_COLOR.success
    if (lower.includes('medium') || lower.includes('orta') || lower.includes('moyen') || lower.includes('medio') || lower.includes('متوسطة') || lower.includes('médio') || lower.includes('gemiddeld') || lower.includes('средний') || lower.includes('中')) return STATUS_COLOR.warning
    return STATUS_COLOR.danger
  }

  return (
    <div className="app-layout">
      <Navbar />
      <main className="main-content" id="main-content">
        <QuotaWarningBanner />
        <motion.div
          className="page-header"
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <h1>{t('analyze.title')}</h1>
          {result && (
            <motion.button
              className="btn-outline"
              onClick={handleReset}
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
            >
              {t('analyze.new_analysis')}
            </motion.button>
          )}
        </motion.div>

        <AnimatePresence mode="wait">
        {!result ? (
          <motion.form
            key="form"
            onSubmit={handleAnalyze}
            className="analyze-form"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.4 }}
          >
            <div className="analyze-grid">
              {/* Upload Section */}
              <motion.div
                className="card"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.1 }}
              >
                <h2>{t('analyze.upload_title')}</h2>
                <DragDropUpload
                  file={file}
                  onFileSelect={setFile}
                  onRemove={() => setFile(null)}
                />
              </motion.div>

              {/* Job Description */}
              <motion.div
                className="card"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.15 }}
              >
                <h2>{t('analyze.job_desc_title')}</h2>
                <JDTemplateSelector
                  onSelect={(desc) => setJobDesc(desc)}
                  currentText={jobDesc}
                />
                <textarea
                  className="job-desc-input"
                  rows={12}
                  placeholder={t('analyze.job_desc_placeholder')}
                  value={jobDesc}
                  onChange={(e) => setJobDesc(e.target.value)}
                />
              </motion.div>
            </div>

            {/* Progress */}
            <AnimatePresence>
            {loading && (
              <motion.div
                className="progress-wrapper"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.3 }}
              >
                <div className="progress-track">
                  <motion.div
                    className="progress-fill"
                    animate={{ width: `${progress}%` }}
                    transition={{ duration: 0.3, ease: 'easeOut' }}
                  />
                </div>
                <span className="progress-text">{t('analyze.upload_progress')}</span>
              </motion.div>
            )}
            </AnimatePresence>

            {error && <p className="error">{error}</p>}

            <motion.button
              type="submit"
              className="btn-primary btn-lg btn-full"
              disabled={loading}
              whileHover={!loading ? { scale: 1.01 } : undefined}
              whileTap={!loading ? { scale: 0.99 } : undefined}
            >
              {loading ? t('analyze.analyzing') : t('analyze.analyze_btn')}
            </motion.button>
          </motion.form>
        ) : (
          <motion.div
            key="results"
            className="results-layout"
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.5 }}
          >
            {/* File info header */}
            <div style={{ marginBottom: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.25rem' }}>
                <span style={{ fontSize: '1.1rem', fontWeight: 600 }}>{file?.name || 'CV'}</span>
                {jobDesc?.trim() ? (
                  /* JD provided → show match level */
                  result.final_score >= 75 ? (
                    <span className="status-pill status-pill-success">
                      {t('results.strong_match')}
                    </span>
                  ) : result.final_score >= 50 ? (
                    <span className="status-pill status-pill-warning">
                      {t('results.moderate_match')}
                    </span>
                  ) : (
                    <span className="status-pill status-pill-danger">
                      {t('results.weak_match')}
                    </span>
                  )
                ) : (
                  /* No JD → show CV quality level */
                  result.final_score >= 75 ? (
                    <span className="status-pill status-pill-success">
                      {t('results.excellent_quality')}
                    </span>
                  ) : result.final_score >= 50 ? (
                    <span className="status-pill status-pill-warning">
                      {t('results.good_quality')}
                    </span>
                  ) : (
                    <span className="status-pill status-pill-danger">
                      {t('results.needs_improvement')}
                    </span>
                  )
                )}
              </div>
              <p className="text-muted text-xs">{new Date().toLocaleDateString(lang, { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</p>
            </div>

            {/* Resume Analysis Results header card */}
            <div className="card" style={{ marginBottom: '1.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
                <div>
                  <h2 style={{ margin: '0 0 0.5rem 0' }}>{t('results.title')}</h2>
                  <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
                    <span className="status-count status-count-success">✓ {result.ats?.passed_checks ?? 0} {t('results.passed_checks')}</span>
                    <span className="status-count status-count-warning">⚠ {result.ats?.warning_checks ?? 0} {t('results.warnings')}</span>
                    <span className="status-count status-count-danger">✕ {result.ats?.failed_checks ?? 0} {t('results.issues')}</span>
                  </div>
                </div>
                <ScoreCircle score={result.final_score} size={100} label={jobDesc?.trim() ? t('results.final_score') : t('results.analysis_score')} />
              </div>

              {/* Score Decomposition: ATS Quality vs Job Match */}
              {jobDesc?.trim() && result.score_decomposition && (
                <div style={{
                  marginTop: '1.25rem',
                  paddingTop: '1.25rem',
                  borderTop: '1px solid rgba(148,163,184,0.15)',
                }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '0.75rem' }}>
                    {/* CV Quality */}
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                        <span style={{ fontSize: '0.82rem', color: 'var(--color-text-secondary)', fontWeight: 500 }}>
                          📄 {t('results.cv_quality') || 'CV Quality'}
                        </span>
                        <span style={{
                          fontSize: '1rem', fontWeight: 700,
                          color: scoreColor(result.score_decomposition.ats_quality || 0),
                          fontFamily: "'JetBrains Mono', monospace",
                        }}>
                          {Math.round(result.score_decomposition.ats_quality || 0)}%
                        </span>
                      </div>
                      <div style={{ width: '100%', height: '6px', background: 'var(--bg-input)', borderRadius: '3px', overflow: 'hidden' }}>
                        <div style={{
                          width: `${Math.min(100, result.score_decomposition.ats_quality || 0)}%`,
                          height: '100%', borderRadius: '3px',
                          background: 'linear-gradient(90deg, var(--status-info), color-mix(in srgb, var(--status-info) 70%, white))',
                          transition: 'width 0.8s ease',
                        }} />
                      </div>
                    </div>
                    {/* Job Match */}
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                        <span style={{ fontSize: '0.82rem', color: 'var(--color-text-secondary)', fontWeight: 500 }}>
                          🎯 {t('results.job_match') || 'Job Match'}
                        </span>
                        <span style={{
                          fontSize: '1rem', fontWeight: 700,
                          color: scoreColor(result.score_decomposition.job_match || 0, 40),
                          fontFamily: "'JetBrains Mono', monospace",
                        }}>
                          {Math.round(result.score_decomposition.job_match || 0)}%
                        </span>
                      </div>
                      <div style={{ width: '100%', height: '6px', background: 'var(--bg-input)', borderRadius: '3px', overflow: 'hidden' }}>
                        <div style={{
                          width: `${Math.min(100, result.score_decomposition.job_match || 0)}%`,
                          height: '100%', borderRadius: '3px',
                          background: scoreGradient(result.score_decomposition.job_match || 0, 40),
                          transition: 'width 0.8s ease',
                        }} />
                      </div>
                    </div>
                  </div>
                  {/* Interpretation message */}
                  <div style={{
                    ...scoreToneStyle(result.score_decomposition.job_match || 0, 40),
                    borderRadius: '0.5rem',
                    padding: '0.5rem 0.75rem',
                    fontSize: '0.82rem',
                    color: 'var(--color-text-secondary)',
                  }}>
                    {result.score_decomposition.interpretation}
                  </div>
                </div>
              )}
            </div>

            {/* Info banner when no job description */}
            {!jobDesc?.trim() && (
              <div style={{
                background: 'var(--status-info-bg)',
                border: '1px solid var(--status-info-border)',
                borderRadius: '0.75rem',
                padding: '0.75rem 1rem',
                marginBottom: '1rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                fontSize: '0.85rem',
                color: 'var(--status-info)',
              }}>
                <span style={{ fontSize: '1.1rem' }}>ℹ️</span>
                {t('results.no_jd_info')}
              </div>
            )}

            {/* Analysis warnings */}
            {result.warnings?.length > 0 && (
              <div className="alert alert-warning" style={{ marginBottom: '1rem' }}>
                <strong>⚠ {t('results.warnings')}</strong>
                <ul style={{ margin: '0.5rem 0 0', paddingLeft: '1.25rem' }}>
                  {result.warnings.map((w, i) => <li key={i} style={{ marginBottom: '0.25rem' }}>{w}</li>)}
                </ul>
              </div>
            )}

            {/* Tabs */}
            <div className="analysis-tabs">
              {[
                { id: 'overview', icon: '📊', label: t('analyze.tab_overview') },
                { id: 'detailed', icon: '📋', label: t('analyze.tab_detailed') },
                { id: 'recommendations', icon: '💡', label: t('analyze.tab_recommendations') },
                { id: 'nextsteps', icon: '◎', label: t('analyze.tab_next_steps') },
                { id: 'scorebreakdown', icon: '🎯', label: t('analyze.tab_score_breakdown') },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`analysis-tab ${activeTab === tab.id ? 'active' : ''}`}
                  type="button"
                >
                  {tab.icon} {tab.label}
                </button>
              ))}
            </div>

            {/* OVERVIEW TAB */}
            {activeTab === 'overview' && (
              <>
                <section className="analysis-diagnostic-section">
                  <div className="analysis-diagnostic-header">
                    <div>
                      <span className="analysis-diagnostic-eyebrow">
                        {uiCopy(lang, 'Detaylı CV Tanısı', 'Detailed CV diagnosis')}
                      </span>
                      <h2 className="analysis-diagnostic-title">
                        {uiCopy(lang, 'Eksikleri nerede ve nasıl düzeltmen gerektiğini adım adım gör', 'See exactly where and how to improve the CV')}
                      </h2>
                      <p className="analysis-diagnostic-subtitle">
                        {uiCopy(
                          lang,
                          'Bu bölüm sadece açıklama ve kontrol amaçlıdır. AI ile düzeltme akışı aşağıdaki Otomatik Düzeltme bölümünden bağımsız çalışır.',
                          'This section is only for explanation and review. The AI fix flow remains separate in the Auto Fix section below.',
                        )}
                      </p>
                    </div>
                    <span className="analysis-diagnostic-count">
                      {diagnosticItems.length} {uiCopy(lang, 'kontrol maddesi', 'checks')}
                    </span>
                  </div>

                  <div className="analysis-diagnostic-layout">
                    <div className="analysis-diagnostic-list analysis-diagnostic-list-left">
                      {splitDiagnosticItems.left.map(({ item, index }) => (
                        <DiagnosticCard key={item.id} item={item} index={index} lang={lang} />
                      ))}
                    </div>

                    <div className="cv-preview-panel">
                      <div className="cv-preview-toolbar">
                        <div>
                          <strong>{uiCopy(lang, 'CV Önizleme', 'CV preview')}</strong>
                          <span>{uiCopy(lang, 'İşaretler yaklaşık bölüm konumlarını gösterir.', 'Markers show approximate section locations.')}</span>
                        </div>
                        {cvPreviewUrl && (
                          <button
                            type="button"
                            className="cv-preview-open"
                            onClick={() => window.open(cvPreviewUrl, '_blank', 'noopener,noreferrer')}
                          >
                            {uiCopy(lang, 'PDF Aç', 'Open PDF')}
                          </button>
                        )}
                      </div>

                      <div className="cv-preview-canvas">
                        {cvPreviewUrl ? (
                          <object
                            className="cv-preview-object"
                            data={`${cvPreviewUrl}#toolbar=0&navpanes=0&scrollbar=0`}
                            type="application/pdf"
                            aria-label={uiCopy(lang, 'Yüklenen CV önizlemesi', 'Uploaded CV preview')}
                          >
                            <div className="cv-preview-fallback">
                              {uiCopy(lang, 'Tarayıcı PDF önizlemeyi desteklemedi. PDF Aç düğmesiyle ayrı sekmede görüntüleyebilirsin.', 'The browser could not render the PDF preview. Use Open PDF to view it in a new tab.')}
                            </div>
                          </object>
                        ) : (
                          <div className="cv-preview-fallback">
                            {uiCopy(lang, 'CV önizlemesi için analiz edilen PDF bekleniyor.', 'Waiting for the analyzed PDF preview.')}
                          </div>
                        )}

                        <div className="cv-marker-layer" aria-hidden="true">
                          {markerItems.map((item, index) => (
                            <div
                              key={`marker-${item.id}`}
                              className={`cv-marker cv-marker-${item.severity}`}
                              style={{ top: `${getMarkerTop(item.markerKey, index)}%` }}
                            >
                              <span className="cv-marker-dot">{index + 1}</span>
                              <span className="cv-marker-line" />
                              <span className="cv-marker-label">
                                {item.severity === 'success'
                                  ? uiCopy(lang, 'İyi', 'Good')
                                  : item.severity === 'high'
                                    ? uiCopy(lang, 'Eksik', 'Gap')
                                    : uiCopy(lang, 'Kontrol', 'Check')}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>

                      <p className="cv-preview-note">
                        {uiCopy(
                          lang,
                          'Not: PDF içinden kesin koordinat gelmediği için oklar bölüm seviyesinde yaklaşık konum verir; sağ ve soldaki maddeler asıl düzeltme listesidir.',
                          'Note: exact PDF coordinates are not available, so arrows point to approximate section areas; the lists on both sides are the source of truth.',
                        )}
                      </p>
                    </div>

                    <div className="analysis-diagnostic-list analysis-diagnostic-list-right">
                      {splitDiagnosticItems.right.map(({ item, index }) => (
                        <DiagnosticCard key={item.id} item={item} index={index} lang={lang} />
                      ))}
                    </div>
                  </div>

                  <div className="analysis-visual-grid">
                    <section className="cv-map-panel">
                      <div className="analysis-visual-head">
                        <span>{uiCopy(lang, 'CV mini harita', 'CV mini map')}</span>
                        <strong>{uiCopy(lang, 'Bölüm sağlık durumu', 'Section health')}</strong>
                      </div>
                      <div className="cv-mini-sheet" aria-label={uiCopy(lang, 'CV bölüm haritası', 'CV section map')}>
                        {cvMapSections.map((section) => (
                          <div key={section.key} className={`cv-map-row cv-map-${section.status}`}>
                            <div className="cv-map-row-top">
                              <span>{section.label}</span>
                              <strong>
                                {section.found
                                  ? `${Math.round(section.score)}`
                                  : uiCopy(lang, 'Yok', 'Missing')}
                              </strong>
                            </div>
                            <div className="cv-map-track">
                              <span style={{ width: `${section.found ? Math.max(8, Math.min(100, section.score)) : 8}%` }} />
                            </div>
                            <p>{section.note}</p>
                          </div>
                        ))}
                      </div>
                    </section>

                    <section className="parser-snapshot-panel">
                      <div className="analysis-visual-head">
                        <span>{uiCopy(lang, 'ATS parser görünümü', 'ATS parser view')}</span>
                        <strong>{uiCopy(lang, 'Sistem CV’ni böyle okudu', 'How the system read your CV')}</strong>
                      </div>
                      <div className="parser-group-list">
                        {parserSnapshot.map((group) => (
                          <div key={group.title} className="parser-group">
                            <h3>{group.title}</h3>
                            {group.rows.map((row) => (
                              <div key={`${group.title}-${row.label}`} className="parser-row">
                                <span className="parser-label">{row.label}</span>
                                {row.values ? (
                                  <span className="parser-chip-wrap">
                                    {row.values.length > 0 ? row.values.map((value) => (
                                      <span key={`${row.label}-${value}`} className={`parser-chip parser-${row.state || 'muted'}`}>{value}</span>
                                    )) : (
                                      <span className="parser-muted">{uiCopy(lang, 'Yok / algılanmadı', 'None / not detected')}</span>
                                    )}
                                    {row.overflow > 0 && <span className="parser-chip parser-muted">+{row.overflow}</span>}
                                  </span>
                                ) : (
                                  <strong className={`parser-value parser-${row.state || 'muted'}`}>{row.value}</strong>
                                )}
                              </div>
                            ))}
                          </div>
                        ))}
                      </div>
                    </section>

                    <section className="impact-panel">
                      <div className="analysis-visual-head">
                        <span>{uiCopy(lang, 'Puan etki grafiği', 'Score impact chart')}</span>
                        <strong>{uiCopy(lang, 'Önce neyi düzeltmeli?', 'What to fix first?')}</strong>
                      </div>
                      <div className="impact-list">
                        {impactItems.map((item) => (
                          <div key={item.id} className="impact-row">
                            <div className="impact-row-copy">
                              <strong>{item.label}</strong>
                              <span>{item.source}</span>
                            </div>
                            <div className="impact-meter">
                              <span style={{ width: `${Math.max(10, Math.min(100, (toScore(item.impact) / maxImpact) * 100))}%` }} />
                            </div>
                            <b>+{toScore(item.impact).toFixed(1)}</b>
                          </div>
                        ))}
                      </div>
                      <p className="impact-note">
                        {uiCopy(
                          lang,
                          'Etki değerleri tahminidir; aynı bilgiyi gerçek deneyim/proje kanıtıyla eklemek gerekir.',
                          'Impact values are estimates; additions should be backed by real experience or project evidence.',
                        )}
                      </p>
                    </section>
                  </div>
                </section>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
                  {(result.ats?.section_scores || []).map((section, idx) => (
                    <div key={idx} className="card" style={{ margin: 0, padding: '1rem 1.25rem' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '0.5rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span>{section.icon}</span>
                          <strong>{section.label?.[lang] || section.label?.en || section.name}</strong>
                        </div>
                        <span style={{ fontSize: '1.25rem', fontWeight: 700, color: scoreColor(section.score) }}>
                          {Math.round(section.score)}
                        </span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem' }}>
                        {section.status === 'pass' && <span style={{ color: STATUS_COLOR.success, fontSize: '0.8rem' }}>✓ {t('results.status_pass')}</span>}
                        {section.status === 'warning' && <span style={{ color: STATUS_COLOR.warning, fontSize: '0.8rem' }}>⚠ {t('results.status_warning')}</span>}
                        {section.status === 'fail' && <span style={{ color: STATUS_COLOR.danger, fontSize: '0.8rem' }}>✕ {t('results.status_fail')}</span>}
                      </div>
                      {/* Score bar */}
                      <div style={{ width: '100%', height: '4px', background: 'var(--bg-input)', borderRadius: '2px', marginBottom: '0.5rem' }}>
                        <div style={{
                          width: `${Math.min(100, section.score)}%`,
                          height: '100%',
                          borderRadius: '2px',
                          background: scoreColor(section.score),
                          transition: 'width 0.5s ease',
                        }} />
                      </div>
                      <p className="text-muted" style={{ fontSize: '0.8rem', margin: 0 }}>{L(section.message) || (section.score >= 70 ? t('results.looking_good') : t('results.improvements_recommended'))}</p>
                    </div>
                  ))}
                </div>

                {/* Skills & Keyword overview */}
                <div className="results-details">
                  {result.detected_skills?.length > 0 && (
                    <div className="card">
                      <h3>{t('results.detected_skills')}</h3>
                      <SkillTags skills={result.detected_skills} variant="detected" />
                    </div>
                  )}

                  {jobDesc?.trim() && result.missing_skills?.length > 0 && (
                    <div className="card">
                      <h3>{t('results.missing_skills')}</h3>
                      <SkillTags skills={result.missing_skills} variant="missing" />
                    </div>
                  )}

                  {/* Score Suggestions — actionable improvement tips */}
                  {jobDesc?.trim() && result.missing_skills?.length > 0 && (
                    <div className="card" style={{ borderLeft: '3px solid var(--status-info)' }}>
                      <div style={{ display: 'flex', alignItems: 'start', justifyContent: 'space-between', gap: '1rem', marginBottom: '0.75rem' }}>
                        <div>
                          <h3 style={{ marginTop: 0 }}>{uiCopy(lang, 'Beceri yol haritasi', 'Skill gap roadmap')}</h3>
                          <p className="text-muted" style={{ margin: 0, fontSize: '0.84rem' }}>
                            {uiCopy(lang, 'Eksik becerileri kanitlanabilir CV aksiyonlarina donustur.', 'Turn missing skills into provable CV actions.')}
                          </p>
                        </div>
                        <button
                          type="button"
                          className="btn-outline btn-sm"
                          onClick={handleBuildSkillRoadmap}
                          disabled={skillRoadmapLoading}
                        >
                          {skillRoadmapLoading ? uiCopy(lang, 'Hazirlaniyor...', 'Building...') : uiCopy(lang, 'Roadmap uret', 'Build roadmap')}
                        </button>
                      </div>
                      {skillRoadmapError && <p className="error" style={{ marginTop: 0 }}>{skillRoadmapError}</p>}
                      {skillRoadmap?.roadmap?.length > 0 && (
                        <div style={{ display: 'grid', gap: '0.65rem' }}>
                          {skillRoadmap.roadmap.map((item, idx) => (
                            <div key={`${item.skill}-${idx}`} style={{
                              padding: '0.75rem',
                              border: '1px solid var(--color-border)',
                              borderRadius: '0.75rem',
                              background: 'var(--bg-card-hover)',
                            }}>
                              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem', marginBottom: '0.4rem' }}>
                                <strong>{item.skill}</strong>
                                <span className={`status-pill ${item.priority === 'high' ? 'status-pill-danger' : 'status-pill-warning'}`}>
                                  {item.priority}
                                </span>
                              </div>
                              <ul style={{ margin: 0, paddingLeft: '1.1rem', color: 'var(--color-text-secondary)', fontSize: '0.84rem' }}>
                                <li>{item.cv_action}</li>
                                <li>{item.proof}</li>
                                <li>{item.practice}</li>
                              </ul>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {jobDesc?.trim() && result.score_suggestions?.length > 0 && (
                    <div className="card" style={{ borderLeft: '3px solid var(--status-accent)' }}>
                      <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: 0, color: 'var(--status-accent)' }}>
                        💡 {t('results.suggestions_title') || 'How to Improve Your Score'}
                      </h3>
                      <p style={{ fontSize: '0.82rem', color: 'var(--color-text-secondary)', margin: '0 0 0.75rem 0' }}>
                        {t('results.suggestions_desc') || 'Add these to your CV for the highest impact:'}
                      </p>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                        {result.score_suggestions.map((s, i) => (
                          <div key={i} style={{
                            display: 'flex', alignItems: 'center', gap: '0.75rem',
                            background: 'rgba(168,85,247,0.06)',
                            borderRadius: '0.5rem',
                            padding: '0.6rem 0.75rem',
                          }}>
                            <span style={{
                              fontSize: '1rem',
                              minWidth: '24px', textAlign: 'center',
                            }}>
                              {s.category === 'skill' ? '🎯' : s.category === 'keyword' ? '🔑' : '📄'}
                            </span>
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <span style={{ fontSize: '0.85rem', color: '#e2e8f0' }}>{s.action}</span>
                            </div>
                            <span style={{
                              background: 'var(--gradient-accent)',
                              color: '#fff',
                              padding: '2px 8px',
                              borderRadius: '999px',
                              fontSize: '0.75rem',
                              fontWeight: 700,
                              fontFamily: "'JetBrains Mono', monospace",
                              whiteSpace: 'nowrap',
                              flexShrink: 0,
                            }}>
                              +{s.impact.toFixed(1)} pts
                            </span>
                          </div>
                        ))}
                      </div>
                      <p style={{ fontSize: '0.72rem', color: '#64748b', margin: '0.75rem 0 0 0', fontStyle: 'italic' }}>
                        {t('results.suggestions_disclaimer') || '* Point estimates are approximate and based on current scoring weights.'}
                      </p>
                    </div>
                  )}
                </div>
              </>
            )}

            {/* DETAILED RESULTS TAB */}
            {activeTab === 'detailed' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {(result.ats?.section_scores || []).map((section, idx) => (
                  <div
                    key={idx}
                    className="card"
                    style={{
                      margin: 0,
                      padding: '1rem 1.25rem',
                      borderLeft: `3px solid ${section.status === 'pass' ? STATUS_COLOR.success : section.status === 'warning' ? STATUS_COLOR.warning : STATUS_COLOR.danger}`,
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        {section.status === 'pass' && <span style={{ color: STATUS_COLOR.success }}>✓</span>}
                        {section.status === 'warning' && <span style={{ color: STATUS_COLOR.warning }}>⚠</span>}
                        {section.status === 'fail' && <span style={{ color: STATUS_COLOR.danger }}>✕</span>}
                        <span>{section.icon}</span>
                        <strong>{section.label?.[lang] || section.label?.en || section.name}</strong>
                      </div>
                      <span style={{ fontSize: '1.1rem', fontWeight: 700, color: scoreColor(section.score) }}>
                        {Math.round(section.score)}
                      </span>
                    </div>
                    <p style={{ margin: '0.25rem 0 0.5rem 0', fontSize: '0.9rem', color: 'var(--color-text-secondary)' }}>{L(section.message)}</p>
                    {section.recommendations?.length > 0 && (
                      <div>
                        <strong style={{ fontSize: '0.85rem', color: '#cbd5e1' }}>{t('results.recommendations')}:</strong>
                        <ul style={{ margin: '0.25rem 0 0', paddingLeft: '1.25rem', fontSize: '0.85rem', color: 'var(--color-text-secondary)' }}>
                          {section.recommendations.map((rec, i) => <li key={i} style={{ marginBottom: '2px' }}>{L(rec)}</li>)}
                        </ul>
                      </div>
                    )}
                  </div>
                ))}

                {/* Score components breakdown */}
                <div className="card" style={{ margin: 0 }}>
                  <h3>{t('results.breakdown_title')}</h3>
                  <ScoreBars items={[
                    { label: t('results.semantic'), value: result.semantic_score },
                    { label: t('results.keyword'), value: result.keyword_score },
                    { label: t('results.skill'), value: result.skill_score },
                    { label: t('results.experience'), value: result.experience_score },
                    { label: t('results.ats'), value: result.ats_score },
                    { label: t('results.soft_skills') || 'Soft Skills', value: result.soft_skills_score ?? 0 },
                  ]} />
                </div>

                {/* Global ATS Benchmark */}
                {result.global_benchmark && (
                  <GlobalBenchmark data={result.global_benchmark} />
                )}
              </div>
            )}

            {/* RECOMMENDATIONS TAB */}
            {activeTab === 'recommendations' && (
              <>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
                  {/* High Priority */}
                  {result.ats?.priority_recommendations?.high?.length > 0 && (
                    <div className="card" style={{ margin: 0, borderLeft: '3px solid var(--status-danger)' }}>
                      <h3 style={{ color: 'var(--status-danger)', display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: 0 }}>
                        ◎ {t('results.high_priority')}
                      </h3>
                      <ul style={{ margin: 0, paddingLeft: '1rem', listStyle: 'none' }}>
                        {result.ats.priority_recommendations.high.map((rec, i) => (
                          <li key={i} style={{ marginBottom: '0.5rem', fontSize: '0.9rem', color: 'var(--status-danger)' }}>→ {L(rec)}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Medium Priority */}
                  {result.ats?.priority_recommendations?.medium?.length > 0 && (
                    <div className="card" style={{ margin: 0, borderLeft: '3px solid var(--status-warning)' }}>
                      <h3 style={{ color: 'var(--status-warning)', display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: 0 }}>
                        🔶 {t('results.medium_priority')}
                      </h3>
                      <ul style={{ margin: 0, paddingLeft: '1rem', listStyle: 'none' }}>
                        {result.ats.priority_recommendations.medium.map((rec, i) => (
                          <li key={i} style={{ marginBottom: '0.5rem', fontSize: '0.9rem', color: 'var(--status-warning)' }}>→ {L(rec)}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Low Priority */}
                  {result.ats?.priority_recommendations?.low?.length > 0 && (
                    <div className="card" style={{ margin: 0, borderLeft: '3px solid var(--status-accent)' }}>
                      <h3 style={{ color: 'var(--status-accent)', display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: 0 }}>
                        💡 {t('results.low_priority')}
                      </h3>
                      <ul style={{ margin: 0, paddingLeft: '1rem', listStyle: 'none' }}>
                        {result.ats.priority_recommendations.low.map((rec, i) => (
                          <li key={i} style={{ marginBottom: '0.5rem', fontSize: '0.9rem', color: 'var(--status-accent)' }}>→ {L(rec)}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                {/* Industry-Specific Tips */}
                {result.ats?.industry_tips?.length > 0 && (
                  <div className="card" style={{ borderLeft: '3px solid var(--status-accent)' }}>
                    <h3 style={{ color: 'var(--status-accent)', display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: 0 }}>
                      ☆ {t('results.industry_tips')}
                    </h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      {result.ats.industry_tips.map((tip, i) => (
                        <div key={i} style={{ background: 'rgba(168,85,247,0.08)', borderRadius: '0.5rem', padding: '0.75rem 1rem', fontSize: '0.9rem', color: '#cbd5e1' }}>
                          {L(tip)}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}

            {/* NEXT STEPS TAB */}
            {activeTab === 'nextsteps' && (
              <>
                <div className="card">
                  <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: 0 }}>
                    ◎ {t('results.next_steps_title')}
                  </h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {(result.ats?.next_steps || []).map((step, i) => (
                      <div key={i} style={{
                        display: 'flex', alignItems: 'start', gap: '0.75rem',
                        background: 'rgba(192,132,252,0.06)', borderRadius: '0.5rem',
                        padding: '0.75rem 1rem',
                      }}>
                        <span style={{
                          background: '#1e40af', color: '#93c5fd', borderRadius: '0.375rem',
                          minWidth: '28px', height: '28px', display: 'flex', alignItems: 'center',
                          justifyContent: 'center', fontWeight: 700, fontSize: '0.85rem', flexShrink: 0,
                        }}>{i + 1}</span>
                        <span style={{ fontSize: '0.9rem', color: '#cbd5e1', paddingTop: '3px' }}>{L(step)}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Download report section */}
                <div className="card" style={{ textAlign: 'center', marginTop: '1rem' }}>
                  <h3 style={{ marginTop: 0 }}>{t('results.download_report_title')}</h3>
                  <button
                    type="button"
                    className="btn-primary"
                    onClick={() => setActiveTab('autofix')}
                  >
                    ⬇ {t('results.download_report_btn')}
                  </button>
                  <p className="text-muted text-xs" style={{ marginTop: '0.5rem' }}>{t('results.download_report_desc')}</p>
                </div>
              </>
            )}

            {/* SCORE BREAKDOWN TAB */}
            {activeTab === 'scorebreakdown' && (
              <>
                {!scoreBreakdown && !breakdownLoading && (
                  <div className="card" style={{ textAlign: 'center' }}>
                    <p className="text-muted" style={{ marginBottom: '1rem' }}>
                      {t('analyze.score_breakdown_desc')}
                    </p>
                    <button
                      type="button"
                      className="btn-primary"
                      onClick={async () => {
                        try {
                          setBreakdownLoading(true)
                          const data = await fetchScoreBreakdown(token, {
                            cv_text: result.cv_text || '',
                            job_description: jobDesc || '',
                            lang,
                          })
                          setScoreBreakdown(data)
                        } catch (err) {
                          addToast(err.message, 'error')
                        } finally {
                          setBreakdownLoading(false)
                        }
                      }}
                    >
                      {breakdownLoading ? t('analyze.score_breakdown_loading') : t('analyze.score_breakdown_btn')}
                    </button>
                  </div>
                )}

                {breakdownLoading && (
                  <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--color-text-secondary)' }}>
                    {t('analyze.scores_calculating')}
                  </div>
                )}

                {scoreBreakdown && (
                  <ScoreBreakdown
                    atsScores={scoreBreakdown.ats_scores}
                    jobMatch={jobDesc?.trim() ? scoreBreakdown.job_match : null}
                    recruiter={scoreBreakdown.recruiter}
                    feedback={scoreBreakdown.feedback}
                    lang={lang}
                  />
                )}
              </>
            )}

            {/* AUTOFIX TAB (kept from original) */}
            {activeTab === 'autofix' && (
              <div className="card">
                <h3>{t('analyze.autofix_title')}</h3>
                <p className="text-muted" style={{ marginBottom: '1rem' }}>
                  {t('analyze.autofix_desc')}
                </p>

                {autoFixError && <p className="error">{autoFixError}</p>}

                <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
                  <button type="button" className="btn-primary" onClick={() => handleAutoFix(true)} disabled={autoFixLoading}>
                    {autoFixLoading ? t('analyze.autofix_processing') : t('analyze.autofix_ai_fix')}
                  </button>
                  <button type="button" className="btn-outline" onClick={() => handleAutoFix(false)} disabled={autoFixLoading}>
                    {autoFixLoading ? t('analyze.autofix_processing') : t('analyze.autofix_quick_fix')}
                  </button>
                </div>

                {autoFixResult && (
                  <>
                    <div className="autofix-result-shell">
                      <div className="autofix-score-strip">
                        <div>
                          <span>{t('analyze.autofix_before_ats')}</span>
                          <strong>{autoFixResult.before_ats?.overall_score ?? 0}</strong>
                        </div>
                        <div>
                          <span>{t('analyze.autofix_after_ats')}</span>
                          <strong className="autofix-score-good">{autoFixResult.after_ats?.overall_score ?? 0}</strong>
                        </div>
                        <div>
                          <span>{uiCopy(lang, 'Net değişim', 'Net change')}</span>
                          <strong className={Number(autoFixResult.score_delta || 0) >= 0 ? 'autofix-score-good' : 'autofix-score-bad'}>
                            {Number(autoFixResult.score_delta || 0) >= 0 ? '+' : ''}{Number(autoFixResult.score_delta || 0).toFixed(1)}
                          </strong>
                        </div>
                      </div>

                      <div className="autofix-preview-layout">
                        <section className="autofix-preview-panel">
                          <div className="autofix-panel-head">
                            <span>{uiCopy(lang, 'AI sonrası önizleme', 'Post-fix preview')}</span>
                            <strong>{uiCopy(lang, 'Düzenlenebilir CV metni', 'Editable CV text')}</strong>
                          </div>
                          <textarea
                            className="job-desc-input autofix-preview-textarea"
                            rows={18}
                            value={editedText}
                            onChange={(e) => setEditedText(e.target.value)}
                          />
                        </section>

                        <aside className="autofix-changes-panel">
                          <div className="autofix-panel-head">
                            <span>{uiCopy(lang, 'Düzeltme özeti', 'Fix summary')}</span>
                            <strong>{uiCopy(lang, 'Neleri düzelttik?', 'What changed?')}</strong>
                          </div>
                          {Array.isArray(autoFixResult.applied_changes) && autoFixResult.applied_changes.length > 0 ? (
                            <ul className="autofix-change-list">
                              {autoFixResult.applied_changes.map((change, idx) => (
                                <li key={`change-${idx}`}>
                                  <b>{idx + 1}</b>
                                  <span>{change}</span>
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <p className="text-muted" style={{ margin: 0 }}>{t('analyze.autofix_changes_empty')}</p>
                          )}
                          {Array.isArray(autoFixResult.warnings) && autoFixResult.warnings.length > 0 && (
                            <div className="autofix-warning-box">
                              <strong>{uiCopy(lang, 'Kontrol notu', 'Review note')}</strong>
                              {autoFixResult.warnings.map((warning, idx) => (
                                <p key={`autofix-warning-${idx}`}>{warning}</p>
                              ))}
                            </div>
                          )}
                        </aside>
                      </div>
                    </div>

                    <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', flexWrap: 'wrap' }}>
                      <button
                        type="button"
                        className="btn-primary"
                        onClick={() => handleExportAutoFix('pdf')}
                        disabled={exportLoading === 'pdf'}
                      >
                        {exportLoading === 'pdf' ? t('analyze.autofix_exporting') : t('analyze.autofix_export_pdf')}
                      </button>
                      <button
                        type="button"
                        className="btn-outline"
                        onClick={() => handleExportAutoFix('docx')}
                        disabled={exportLoading === 'docx'}
                      >
                        {exportLoading === 'docx' ? t('analyze.autofix_exporting') : t('analyze.autofix_export_docx')}
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}
          </motion.div>
        )}
        </AnimatePresence>

      </main>
    </div>
  )
}
