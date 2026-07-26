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
  {
    slug: 'resume-builder',
    path: '/en/resume-builder/',
    trPath: '/rehber/cv-nasil-hazirlanir/',
    eyebrow: 'Free AI-assisted resume builder',
    title: 'Free AI Resume Builder: Create an ATS-Friendly CV Online',
    seoTitle: 'Free AI Resume Builder | Create Your CV Online | CV Analyzer',
    description: 'Build your resume with a guided, step-by-step editor, AI-assisted summary suggestions, ATS tips, and instant PDF or DOCX export.',
    intro: 'Instead of starting from a blank page or wrestling with a rigid template, the builder walks you through your experience, education, and skills one step at a time, then exports a clean file — with an AI assist for the hardest part: your summary.',
    updatedAt: '2026-07-27',
    readingTime: '5 min read',
    highlights: [
      'A guided 3-step process: personal details & summary, experience/education/skills, ATS tips & export',
      'AI-suggested summary options tailored to a job description you paste in',
      'Reorderable sections — experience, education, skills, certifications, projects, languages, social links — via drag-and-drop',
      'A live preview as you edit, with multiple templates (classic on the free plan, more on paid plans)',
      'Built-in ATS tips shown before you export',
      'Direct export to PDF or DOCX',
    ],
    sections: [
      {
        heading: 'How it works',
        paragraphs: [
          'The builder is a guided editor, not a blank canvas.',
        ],
        bullets: [
          'Start from scratch, or open a CV you already saved or analyzed directly in the builder.',
          'Fill in your personal details and let AI suggest a summary based on a job description.',
          'Add and reorder experience, education, skills, and other sections.',
          'Review the ATS tips checklist before you export.',
          'Export your finished resume as PDF or DOCX.',
        ],
      },
      {
        heading: 'Who it is for',
        paragraphs: [
          'For anyone who wants structure and guidance rather than a blank document to fight with.',
        ],
        bullets: [
          'Candidates who want a fast, template-based starting point instead of formatting in a word processor.',
          'Anyone who has already analyzed a CV and wants to rebuild it cleanly.',
          'People who find writing a professional summary the hardest part of a resume.',
        ],
      },
      {
        heading: 'What the builder does — and does not — cover',
        paragraphs: [
          'Templates and export are the builder’s job — for real hiring-system readability testing, pair the result with the ATS Resume Checker. Template availability depends on your plan; the free plan includes one classic template.',
          'AI-suggested summaries are starting points, not final text. Review and personalize every suggestion before you export — the same rule applies here as everywhere else: don’t claim experience or skills you don’t have.',
        ],
      },
    ],
    faq: [
      { question: 'Is the resume builder free?', answer: 'The free plan includes one classic template. More templates are available on paid plans.' },
      { question: 'Can I import an existing CV?', answer: 'You can open a CV you have already saved or analyzed directly in the builder. There is no separate raw file re-upload inside the builder itself.' },
      { question: 'Does it check ATS compatibility?', answer: 'It shows ATS tips before you export. For a full readability check, run the exported file through the ATS Resume Checker.' },
      { question: 'What file formats can I export?', answer: 'PDF or DOCX.' },
    ],
    ctaLabel: 'Build My Resume Free',
    ctaHref: '/register',
  },
  {
    slug: 'cover-letter-generator',
    path: '/en/cover-letter-generator/',
    trPath: '/rehber/on-yazi-nasil-yazilir/',
    eyebrow: 'AI-generated, editable cover letters',
    title: 'Free AI Cover Letter Generator: Draft a Letter From Your CV',
    seoTitle: 'Free AI Cover Letter Generator | CV Analyzer',
    description: 'Generate a role-specific cover letter draft from your CV and a job description, choose a tone and persona, then edit and copy it in seconds.',
    intro: 'Paste your CV and the job description you are targeting, and the generator drafts a cover letter that connects the two — in a tone and voice you choose. You edit and finalize it before sending.',
    updatedAt: '2026-07-27',
    readingTime: '5 min read',
    highlights: [
      'Works from pasted CV text or an uploaded CV file, plus a job description',
      '5 tone options: professional, enthusiastic, confident, creative, formal',
      '5 role-context modes: junior, senior, manager, technical, academic',
      'Fully editable output with a live word count',
      'Copy to clipboard or download as a text file',
    ],
    sections: [
      {
        heading: 'How it works',
        paragraphs: [
          'A draft takes a few steps, and you stay in control of the final wording.',
        ],
        bullets: [
          'Paste or upload your CV.',
          'Add the job description and, optionally, the company name.',
          'Pick a tone and a mode that matches the role.',
          'Generate a draft.',
          'Edit it directly, then copy it or download it as a text file.',
        ],
      },
      {
        heading: 'Who it is for',
        paragraphs: [
          'For anyone who finds the blank page the hardest part of writing a cover letter.',
        ],
        bullets: [
          'Candidates applying to multiple similar roles who want a fast, tailored starting draft each time.',
          'Anyone who wants a specific tone to match a company’s culture.',
          'People who have a strong CV but struggle to summarize it into a short letter.',
        ],
      },
      {
        heading: 'What the draft can — and cannot — guarantee',
        paragraphs: [
          'The draft is a starting point built only from what you provide — it will not invent experience, employers, or results you have not mentioned. Verify every claim, company name, and detail before sending, the same way you would review any AI-assisted writing.',
          'It does not check your CV’s ATS readability. Pair it with the ATS Resume Checker if you have not already verified your CV parses correctly.',
        ],
      },
    ],
    faq: [
      { question: 'Is the cover letter generator free?', answer: 'Yes, you can generate drafts after creating a free account. Current usage limits are shown in the product.' },
      { question: 'Will it invent experience I don’t have?', answer: 'No. It works from the CV and job description you provide — always verify the final text before sending.' },
      { question: 'Can I export as PDF?', answer: 'You can copy the text or download it as a text file today, then format it in your own document if you need PDF.' },
      { question: 'Do I need to provide a job description?', answer: 'Yes. The letter connects your background to a specific role, so a job description produces a far stronger result than a generic letter.' },
    ],
    ctaLabel: 'Generate My Cover Letter',
    ctaHref: '/register',
  },
  {
    slug: 'job-application-tracker',
    path: '/en/job-application-tracker/',
    eyebrow: 'Job search organization',
    title: 'Free Job Application Tracker: Manage Your Search in One Board',
    seoTitle: 'Free Job Application Tracker | CV Analyzer',
    description: 'Track every application on a kanban board — wishlist to offer — with reminders, notes, and priority so nothing falls through the cracks.',
    intro: 'Once you are applying to more than a couple of roles, a spreadsheet or your memory stops being enough. The tracker gives every application a place on a board, with reminders so follow-ups do not get missed.',
    updatedAt: '2026-07-27',
    readingTime: '5 min read',
    highlights: [
      'A kanban board with 5 stages: wishlist, applied, interview, offer, rejected',
      'Drag and drop applications between stages as your search progresses',
      'Per-application fields: company, role, location, date applied, job URL, salary, priority, and notes',
      'Email reminders for interviews, offers, and follow-ups, sent automatically ahead of the date',
      'At-a-glance stats: total applied, interviews, offers, interview rate, and weekly activity',
    ],
    sections: [
      {
        heading: 'How it works',
        paragraphs: [
          'The board follows the natural stages of a job search.',
        ],
        bullets: [
          'Add a job as soon as you are considering it (wishlist).',
          'Move it to applied, interview, offer, or rejected as things progress.',
          'Fill in company, role, dates, salary, priority, and notes.',
          'Turn on an email reminder for an upcoming interview or follow-up.',
          'Check your stats to see your search’s overall momentum.',
        ],
      },
      {
        heading: 'Who it is for',
        paragraphs: [
          'For anyone whose job search has outgrown a spreadsheet or their memory.',
        ],
        bullets: [
          'Candidates applying to more than a few roles at once.',
          'Anyone juggling multiple interview stages who needs one source of truth.',
          'People who want a nudge before they forget to follow up.',
        ],
      },
      {
        heading: 'What the tracker does — and does not — do',
        paragraphs: [
          'It is an organization tool, not a job-matching or application-automation service — you still find, apply to, and communicate with employers yourself.',
          'Reminders are sent by email, so keep your account’s notification email current if you rely on them.',
        ],
      },
    ],
    faq: [
      { question: 'Is the job tracker free?', answer: 'Yes, it is available after creating a free account.' },
      { question: 'Does it apply to jobs for me?', answer: 'No. It organizes applications you make yourself; it does not submit applications automatically.' },
      { question: 'Can I set reminders?', answer: 'Yes, per application, for interviews, offers, or follow-ups, with automatic emails sent ahead of the date.' },
      { question: 'Is my board private to my account?', answer: 'Yes, your board and its data are tied to your account.' },
    ],
    ctaLabel: 'Track My Applications Free',
    ctaHref: '/register',
  },
]

export const EN_SEO_PAGE_BY_PATH = Object.fromEntries(EN_SEO_PAGES.map((page) => [page.path, page]))

export function findEnSeoPage(pathname) {
  const normalized = pathname.endsWith('/') ? pathname : `${pathname}/`
  return EN_SEO_PAGE_BY_PATH[normalized] || null
}

export const EN_EQUIVALENT_BY_TR_PATH = Object.fromEntries(
  EN_SEO_PAGES.filter((page) => page.trPath).map((page) => [page.trPath, page.path]),
)
