export const EN_PAGE_ENHANCEMENTS = {
  'ai-cv-analyzer': {
    readingTime: '8 min read',
    sections: [
      {
        heading: 'A worked example: from extracted text to a useful revision',
        paragraphs: [
          'Imagine a CV whose visual layout looks polished, but whose extracted text places project dates before employer names and separates skills from the experience that proves them. The first useful finding is not a low score. It is the broken reading order. Correct the export or template, extract the text again, and only then evaluate wording and role relevance.',
          'Next, compare the target vacancy with evidence already present in the CV. If the role asks for stakeholder reporting and the candidate has prepared weekly delivery updates, that evidence can be described more clearly. If the experience is not real, the term should not be added merely to improve a match indicator.',
        ],
        bullets: ['Verify the extracted contact details and headings.', 'Fix document-order problems before rewriting content.', 'Connect relevant terms to evidence you can explain.', 'Review the final PDF visually and as plain text.'],
      },
      {
        heading: 'How to interpret the analysis responsibly',
        paragraphs: [
          'Treat each category as a prompt for review. Readability findings concern what the document exposes to software. Content findings concern clarity and evidence. Job-fit findings compare selected language with one vacancy. Combining them into a score is convenient, but the number cannot represent every recruiter, employer or ATS configuration.',
          'A useful revision should make the CV easier for a person and software to understand without changing the truth. Keep a copy of the submitted version and the vacancy so that you can explain every statement consistently during an interview.',
        ],
      },
      {
        heading: 'European context and personal information',
        paragraphs: [
          'CV conventions vary across Europe. Photographs, dates of birth, nationality, marital status and full addresses are treated differently by country and employer. CV Analyzer does not treat any of these items as a universal European requirement. Follow the vacancy instructions and consider whether each personal detail is necessary for the application.',
          'Upload only a document you are authorised to process. Remove unnecessary identifiers before testing a sample CV, and use the account data controls when you no longer need a saved analysis. The analysis supports your review; it does not make an employer’s hiring decision.',
        ],
      },
    ],
    faq: [
      { question: 'Is there one CV format for all of Europe?', answer: 'No. Expectations differ by country, sector and employer. Use a clear structure, then follow the instructions for the specific vacancy.' },
    ],
  },
  'ats-resume-checker': {
    readingTime: '8 min read',
    sections: [
      {
        heading: 'Run a manual parsing test before relying on a score',
        paragraphs: [
          'Open the final PDF, select all text and paste it into a plain-text editor. Check whether the name, contact details, headings, employers, job titles and dates appear in a sensible order. A two-column layout is not automatically unreadable, but it should be replaced when the exported reading order mixes unrelated lines.',
          'Repeat the test after every material design change. A source document may look unchanged while a font, text box, icon or PDF export option alters extraction. Scanned PDFs need optical character recognition and should be checked especially carefully for missing characters and dates.',
        ],
        bullets: ['Keep essential details in normal selectable text.', 'Use familiar section headings.', 'Check special characters, bullets and links.', 'Follow the employer’s requested file format.'],
      },
      {
        heading: 'Diagnose common failures without keyword stuffing',
        paragraphs: [
          'A parser warning and a relevance warning are different problems. Missing dates, scrambled lines or invisible headings are document issues. A missing role term may instead mean that the CV does not show the relevant experience clearly. Fix the document first, then decide whether truthful evidence should be rewritten.',
          'Do not hide keywords, repeat vacancy text in white, or add skills you have not used. Those tactics reduce trust and do not solve extraction quality. A readable CV with specific evidence is more useful than a document optimised for one speculative score.',
        ],
      },
      {
        heading: 'Limits across European employers and ATS products',
        paragraphs: [
          'There is no single European ATS engine or universal pass threshold. Employers configure different products, questions and review stages, and some applications are reviewed manually. The checker is therefore a risk-reduction tool, not a simulation of a particular employer’s system.',
          'Local application practices also differ. Use the language and file type requested by the vacancy, and avoid unnecessary sensitive information. If an employer provides its own form, complete it accurately even when the same details already appear in the CV.',
        ],
      },
    ],
    faq: [
      { question: 'Does an ATS checker reproduce the employer’s system?', answer: 'No. It can identify common extraction and structure risks, but products and employer configurations differ.' },
    ],
  },
  'ai-interview-simulator': {
    readingTime: '7 min read',
    sections: [
      {
        heading: 'Build a practice set from the role and your real evidence',
        paragraphs: [
          'Start with the vacancy’s responsibilities and select four or five experiences you can discuss in detail. For each one, note the situation, your own responsibility, the action you took, the result and what you would change. The simulator can turn those themes into practice questions, but the source material should remain your real work.',
          'Record a first answer without trying to sound perfect. Review whether the response explains your contribution, gives enough context and answers the question directly. A second attempt should be clearer, not memorised word for word.',
        ],
        bullets: ['Prepare examples for delivery, conflict, learning and failure.', 'Separate your contribution from the team result.', 'Keep confidential employer and customer information out.', 'Prepare questions for the interviewer as well.'],
      },
      {
        heading: 'Use feedback as a rehearsal aid, not an assessment result',
        paragraphs: [
          'Automated feedback can point to long openings, missing outcomes or answers that do not address the question. It cannot judge the full context, communication norms, accessibility needs or expectations of a particular interviewer. Review suggestions critically and keep wording natural for you.',
          'Do not infer a hiring probability from a practice score. Interview decisions can include role-specific expertise, team needs, work authorisation, location, salary expectations and human judgement that are outside a simulator’s view.',
        ],
      },
      {
        heading: 'European and cross-border interview context',
        paragraphs: [
          'Interview formats and lawful or appropriate questions vary across European jurisdictions. The simulator does not provide jurisdiction-specific legal advice. If a question requests sensitive personal information that appears unrelated to the role, pause before answering and consult reliable local guidance where needed.',
          'For cross-border roles, confirm the interview time zone, working language, location expectations and whether the role is remote, hybrid or tied to a particular country. These practical checks prevent avoidable misunderstandings and are more useful than trying to predict every question.',
        ],
      },
    ],
    faq: [
      { question: 'Can interview practice predict whether I will be hired?', answer: 'No. It can improve preparation and clarity, but it cannot reproduce an employer’s full decision process.' },
    ],
  },
  'resume-builder': {
    readingTime: '8 min read',
    sections: [
      {
        heading: 'Create a verified master CV before choosing a layout',
        paragraphs: [
          'Collect accurate dates, role titles, responsibilities, projects, education and skills in one working document. For each experience, record the problem, your contribution, the method and an outcome you can support. This master file reduces contradictions when you later create shorter versions for different roles.',
          'Choose content before styling. A template cannot decide which evidence matters for a vacancy, and an attractive layout cannot repair vague or invented claims. Start with the most recent and relevant information, then remove material that does not help the intended reader.',
        ],
        bullets: ['Use consistent date and heading formats.', 'Write achievements only when the evidence is real.', 'Keep contact details current and necessary.', 'Save a separate copy for each submitted application.'],
      },
      {
        heading: 'A safe build-and-export workflow',
        paragraphs: [
          'Enter the content, preview the reading order, export the requested file type and reopen the final file. Check page breaks, links, bullet characters and selectable text. Paste the exported content into a plain-text editor to find columns or decorative elements that disrupt extraction.',
          'Ask another person to locate the target role, recent experience and strongest evidence within a short scan. If they cannot, improve hierarchy and wording before adding decoration. Keep the final file name professional and avoid including unnecessary identifiers.',
        ],
      },
      {
        heading: 'Country conventions and Europass',
        paragraphs: [
          'There is no layout that every European employer requires. Europass can be useful when a vacancy or programme requests it, but it is not a universal requirement for private-sector applications. Photographs, personal profiles and personal details also vary by market.',
          'Follow the vacancy and local expectations rather than adding information solely because a template offers a field. CV Analyzer provides structure and export assistance; the user remains responsible for accuracy, relevance and the decision to include personal data.',
        ],
      },
    ],
    faq: [
      { question: 'Is Europass required for European applications?', answer: 'Not generally. Use it when the employer, institution or programme requests it; otherwise follow the specific vacancy and local norms.' },
    ],
  },
}
