export const EN_SEO_PAGES = [
  {
    slug: 'ai-cv-analyzer',
    path: '/en/ai-cv-analyzer/',
    trPath: '/cv-analiz/',
    eyebrow: 'Free AI-powered CV analysis',
    title: 'Free AI CV Analyzer: Check Your Resume Instantly',
    seoTitle: 'Free AI CV Analyzer | Analyze My CV | CV Analyzer',
    description: 'Upload your CV to get an instant AI-powered score, section-by-section feedback, and job-match analysis. Free to start, no design changes required.',
    intro: 'CV Analyzer reads your document the way a hiring system and a recruiter both would. Instead of one opaque number, you get a score, a breakdown of every section, and a view of exactly what text the parser extracted — so you know precisely what to fix and why.',
    updatedAt: '2026-07-27',
    readingTime: '5 min read',
    highlights: [
      'Overall score plus pass, warning, and fail checks for Contact, Summary, Experience, Skills, Education, and Format',
      'An ATS parser view showing the name, email, sections, and skills the system actually detected',
      'A score-impact ranking that orders suggested fixes by estimated point gain',
      'Works with or without a job description — add one for keyword and skill matching',
      'Optional AI Auto-Fix rewrite for weak sections, fully editable before you save it',
      'Upload PDF, DOCX, or TXT files up to 10MB',
    ],
    sections: [
      {
        heading: 'How it works',
        paragraphs: [
          'The analysis runs in a few steps, and you can stop after any of them if that is all you need.',
        ],
        bullets: [
          'Upload your CV as a PDF, DOCX, or TXT file (up to 10MB).',
          'Optionally paste a job description, or import one from a posting URL.',
          'Review your overall score, section-by-section diagnostics, and the ATS parser view.',
          'Work through the score-impact list, which orders fixes by how much they are likely to help.',
          'Use Auto-Fix to get an AI-rewritten version of a weak section, then edit and save it yourself.',
        ],
      },
      {
        heading: 'Who it is for',
        paragraphs: [
          'Useful any time you are about to submit a CV and want a second, structured opinion before you do — not just a spell-check.',
        ],
        bullets: [
          'Job seekers tailoring a CV to a specific posting.',
          'Career changers unsure which experience to foreground.',
          'Students and new graduates who have never had a CV professionally reviewed.',
          'Anyone who suspects their CV formatting might be hiding information from applicant tracking systems.',
        ],
      },
      {
        heading: 'What the score does — and does not — mean',
        paragraphs: [
          'The score summarizes signals extracted from your document and, if provided, a target job description. It is a diagnostic tool, not a hiring prediction: no automated check can see culture fit, interview performance, or an employer’s specific internal criteria.',
          'Suggestions are built to work with information already in your CV. The tool will not invent experience, numbers, or skills you have not provided — verify every AI-rewritten sentence against your real background before saving it.',
        ],
      },
    ],
    faq: [
      { question: 'Is the AI CV Analyzer free?', answer: 'Yes — you can create a free account and analyze your CV. Current usage limits for free and paid plans are shown in the product before you start.' },
      { question: 'Does a high score guarantee I’ll get hired?', answer: 'No. The score reflects document readability, structure, and job-match signals. Hiring decisions depend on many factors an automated tool cannot see.' },
      { question: 'Do I need to add a job description?', answer: 'No. You can run a general CV quality and ATS-readability check without one. Adding a job description unlocks keyword and skill-match scoring against that specific role.' },
      { question: 'What happens to my uploaded CV?', answer: 'Your file and analysis results are tied to your account so you can revisit them later. You can delete saved CVs and analyses from your account at any time.' },
    ],
    ctaLabel: 'Analyze My CV Free',
    ctaHref: '/register',
  },
  {
    slug: 'ats-resume-checker',
    path: '/en/ats-resume-checker/',
    trPath: '/ats-cv-kontrol/',
    eyebrow: 'ATS readability check',
    title: 'Free ATS Resume Checker: See If Your Resume Parses Correctly',
    seoTitle: 'Free ATS Resume Checker | ATS CV Check | CV Analyzer',
    description: 'Check whether applicant tracking systems can correctly read your resume — contact details, sections, dates, and keywords — before you apply.',
    intro: 'Most rejections caused by formatting happen silently: a recruiter never sees the missing phone number or the experience section that got scrambled because it was set in a text box. This check shows you exactly what a parser extracts from your file, not just what it looks like on screen.',
    updatedAt: '2026-07-27',
    readingTime: '5 min read',
    highlights: [
      'An ATS parser view showing the exact name, email, section headings, and skills detected in your file',
      'A dedicated format sub-score alongside semantic, keyword, and experience sub-scores',
      'Keyword and skill matching against a job description, when you provide one',
      'Flags unrecognized section headings, broken character encoding, and out-of-order text',
      'Works with PDF, DOCX, or TXT — no need to convert your file first',
    ],
    sections: [
      {
        heading: 'How it works',
        paragraphs: [
          'The checker extracts your resume the way an applicant tracking system would, then compares that extraction against what a well-structured resume should contain.',
        ],
        bullets: [
          'Upload your resume file (PDF, DOCX, or TXT).',
          'Optionally add the job posting so keyword and skill matching can run.',
          'Open the ATS parser view to see the raw name, contact details, sections, and skills the system read.',
          'Check the format sub-score and section-by-section pass/warning/fail results for anything the parser missed or misread.',
          'Fix flagged issues — inconsistent headings, missing plain-text contact details, or column-based layouts — and re-check.',
        ],
      },
      {
        heading: 'Who it is for',
        paragraphs: [
          'For anyone who has sent out applications and gotten no response, and wants to rule out a formatting problem before assuming it was the content.',
        ],
        bullets: [
          'Candidates using a template with columns, tables, or text boxes.',
          'Anyone applying to large companies that rely heavily on applicant tracking software.',
          'Candidates switching from a designed portfolio-style resume to a text-based one for online applications.',
        ],
      },
      {
        heading: 'What this check can and cannot guarantee',
        paragraphs: [
          'There is no single tool that replicates every commercial ATS product or every employer’s internal ranking rules — those vary by company and are not public. This check reduces the most common, avoidable parsing risks (broken text order, unreadable contact info, unrecognized headings), it does not certify that your resume will rank highly in a specific company’s system.',
          'A two-column resume is not automatically rejected everywhere, but it does carry more reading-order risk. Use the parser view as your evidence, not the visual design alone.',
        ],
      },
    ],
    faq: [
      { question: 'Does a passing score guarantee I’ll pass a specific company’s ATS?', answer: 'No. Employers use different ATS products and rules. This check reduces common, avoidable parsing risks rather than certifying a specific vendor’s outcome.' },
      { question: 'Are two-column resumes always rejected by ATS?', answer: 'Not always, but they carry higher risk of scrambled reading order. Check the parser view on your exported file rather than relying on the visual layout.' },
      { question: 'Is PDF or DOCX better for ATS?', answer: 'Both can work if properly exported as text-based (not scanned image) files. Follow the employer’s stated format if one is specified.' },
      { question: 'Is the ATS check free?', answer: 'Yes, you can run it after creating a free account. Current usage limits are shown in the product.' },
    ],
    ctaLabel: 'Check My Resume Free',
    ctaHref: '/register',
  },
  {
    slug: 'ai-interview-simulator',
    path: '/en/ai-interview-simulator/',
    trPath: '/rehber/mulakat-hazirligi/',
    eyebrow: 'AI-powered interview practice',
    title: 'Free AI Interview Simulator: Practice Job Interviews Online',
    seoTitle: 'Free AI Interview Simulator | Practice Job Interviews | CV Analyzer',
    description: 'Practice role-specific interview questions generated from your CV, answer by typing or speaking, and get scored feedback with a sample answer for each question.',
    intro: 'Instead of generic interview questions, the simulator generates questions from your actual CV and, optionally, the job description you are targeting — then scores your answers and shows you what a stronger answer could look like.',
    updatedAt: '2026-07-27',
    readingTime: '6 min read',
    highlights: [
      'Questions generated from your CV and optional job description, not a generic bank',
      'Choose an interview mode — junior, senior, manager, technical, or academic — and a session length of 3, 5, 7, or 10 questions',
      'Answer by typing or speaking, with an elapsed-time counter and an answer-depth meter while you respond',
      'Per-answer scoring out of 10 with feedback, strengths, areas to improve, and a sample answer',
      'Your session is saved automatically so you can pick up where you left off',
    ],
    sections: [
      {
        heading: 'How it works',
        paragraphs: [
          'A full practice session moves through four short phases.',
        ],
        bullets: [
          'Paste your CV text or upload your CV file, and optionally add a job description.',
          'Pick an interview mode and how many questions you want to practice.',
          'Answer each question by typing or speaking; a timer and answer-depth meter run alongside you.',
          'Review your scored feedback per question — strengths, what to improve, and a sample answer for comparison.',
        ],
      },
      {
        heading: 'Who it is for',
        paragraphs: [
          'Built for practicing the specific interview in front of you, not memorizing generic advice.',
        ],
        bullets: [
          'Anyone with an interview scheduled who wants to rehearse out loud before the real conversation.',
          'Candidates moving into a role type they have not interviewed for before.',
          'People who want deliberate practice on behavioral vs. technical question formats separately.',
          'Anyone who prefers to build confidence privately before a live interview.',
        ],
      },
      {
        heading: 'What practice can — and cannot — do for you',
        paragraphs: [
          'This is a practice tool, not a predictor of a specific interview’s outcome. Feedback is automated and useful for structure and clarity, but it does not replace a human mentor or recruiter’s judgment on tone, chemistry, or company-specific expectations.',
          'Sample answers are illustrative examples of structure, not scripts to memorize. The goal is to practice explaining your own real experience clearly and naturally, so it still sounds like you in the actual interview.',
        ],
      },
    ],
    faq: [
      { question: 'Is the interview simulator free?', answer: 'Yes, you can start practicing after creating a free account. Current usage limits are shown in the product.' },
      { question: 'Can I answer by voice instead of typing?', answer: 'Yes. You can type your answers or use your browser’s microphone for voice input, and have questions read aloud.' },
      { question: 'Does it use my real CV to generate questions?', answer: 'Yes. Questions are generated from the CV text you provide and, if included, the job description — not a generic fixed question bank.' },
      { question: 'Can I redo a session or start over?', answer: 'Yes. Your progress saves automatically as you go, and you can start a new session at any time.' },
    ],
    ctaLabel: 'Start Interview Practice',
    ctaHref: '/register',
  },
]

export const EN_SEO_PAGE_BY_PATH = Object.fromEntries(EN_SEO_PAGES.map((page) => [page.path, page]))

export function findEnSeoPage(pathname) {
  const normalized = pathname.endsWith('/') ? pathname : `${pathname}/`
  return EN_SEO_PAGE_BY_PATH[normalized] || null
}

export const EN_EQUIVALENT_BY_TR_PATH = Object.fromEntries(
  EN_SEO_PAGES.map((page) => [page.trPath, page.path]),
)
