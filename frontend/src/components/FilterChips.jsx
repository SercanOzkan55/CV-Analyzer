import React from 'react'
import { X } from 'lucide-react'

/**
 * Filter chip row.
 * chips: [{ id, label, variant? ('high'|'medium'|'low') }]
 * active: currently active chip id
 * onChange: (id) => void
 * onClear: optional clear handler
 * label: optional row label
 */
export default function FilterChips({ chips = [], active = 'all', onChange, onClear, label }) {
  return (
    <div className="filter-chips">
      {label && <span className="filter-chips-label">{label}</span>}
      {chips.map((chip) => (
        <button
          key={chip.id}
          className={`filter-chip ${chip.variant || ''} ${active === chip.id ? 'active' : ''}`}
          onClick={() => onChange(chip.id)}
          type="button"
        >
          {chip.label}
          {chip.count !== undefined && (
            <span style={{ opacity: 0.7 }}>({chip.count})</span>
          )}
        </button>
      ))}
      {onClear && active !== 'all' && (
        <button
          className="filter-chip"
          onClick={onClear}
          type="button"
          style={{ gap: 4 }}
        >
          <X size={12} />
          Clear
        </button>
      )}
    </div>
  )
}
