import React from 'react'

export default function SkillTags({ skills, variant = 'default' }) {
  if (!skills?.length) return null

  const cls = variant === 'missing' ? 'tag tag-red' : variant === 'detected' ? 'tag tag-green' : 'tag'

  return (
    <div className="tag-list">
      {skills.map((skill, i) => (
        <span key={i} className={cls}>{skill}</span>
      ))}
    </div>
  )
}
