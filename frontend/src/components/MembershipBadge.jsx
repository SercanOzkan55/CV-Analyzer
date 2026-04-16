import React from 'react';

export default function MembershipBadge({ plan, role }) {
  let color = '#aaa', label = 'Üye';
  if (role === 'admin') {
    color = '#eab308'; label = 'Admin';
  } else if (role === 'recruiter') {
    color = '#38bdf8'; label = 'Recruiter';
  } else if (plan === 'premium') {
    color = '#c084fc'; label = 'Premium';
  } else if (plan === 'free') {
    color = '#64748b'; label = 'Free';
  }
  return (
    <span style={{
      background: color,
      color: '#fff',
      borderRadius: '8px',
      padding: '2px 8px',
      fontSize: '0.85rem',
      fontWeight: 600,
      marginLeft: 8,
      display: 'inline-block'
    }}>{label}</span>
  );
}
