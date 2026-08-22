import React from 'react'

// Renders a policy document from the shared content modules. Bare URLs in the
// source text become real links so the opt-out routes AdSense expects are
// clickable rather than plain text.
const URL_PATTERN = /(https?:\/\/[^\s]+)/g

function linkify(text) {
  // The capture group makes split() keep the URLs, so odd indexes are matches.
  return text.split(URL_PATTERN).map((part, index) => {
    if (index % 2 === 0) return part
    return (
      <a key={`${part}-${index}`} href={part} target="_blank" rel="noopener noreferrer">
        {part}
      </a>
    )
  })
}

export default function LegalDocument({ document: doc, updatedAt, updatedLabel }) {
  return (
    <div className="legal-container">
      <h1>{doc.title}</h1>
      <p className="legal-updated">
        <time dateTime={updatedAt}>
          {updatedLabel}: {updatedAt}
        </time>
      </p>
      <p className="legal-intro">{doc.intro}</p>

      {doc.sections.map((section) => (
        <section key={section.heading}>
          <h2>{section.heading}</h2>
          {section.paragraphs.map((paragraph) => (
            <p key={paragraph}>{linkify(paragraph)}</p>
          ))}
          {section.bullets && (
            <ul>
              {section.bullets.map((item) => (
                <li key={item}>{linkify(item)}</li>
              ))}
            </ul>
          )}
        </section>
      ))}
    </div>
  )
}
