/**
 * Advanced export utilities for recruiter data
 * Supports CSV, HTML, JSON formats with improved readability
 */

/**
 * Escape CSV field value
 */
export function escapeCsv(field) {
  if (field === null || field === undefined) return '""'
  const str = String(field)
  return `"${str.replace(/"/g, '""')}"`
}

/**
 * Download helper
 */
function downloadFile(content, fileName, mimeType) {
  try {
    const blob = new Blob([content], { type: mimeType })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = fileName
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    return { success: true, message: `✅ Exported to ${fileName}` }
  } catch (e) {
    console.error('Export failed:', e)
    return { success: false, message: `❌ Export failed: ${e.message}` }
  }
}

function getBatchRows(batchResult) {
  if (Array.isArray(batchResult?.ranking)) return batchResult.ranking
  if (Array.isArray(batchResult?.results)) return batchResult.results
  return []
}

function listText(value) {
  if (Array.isArray(value)) return value.join('; ')
  if (value === null || value === undefined) return ''
  return String(value)
}

function getJdQuality(row, batchResult) {
  if (row?.job_description_quality?.status) return row.job_description_quality
  if (batchResult?.job_description_quality?.status) return batchResult.job_description_quality
  return {}
}

export function getJdQualityLabel(quality) {
  const status = quality?.status || 'ok'
  if (status === 'invalid') return 'Invalid JD'
  if (status === 'weak') return 'Weak JD'
  if (status === 'missing') return 'Missing JD'
  return 'OK'
}

export function getJdQualityMessage(quality) {
  const status = quality?.status
  if (status === 'invalid') return 'Job description is invalid; match scoring was disabled.'
  if (status === 'weak') return 'Job description is too short; match score may be capped.'
  if (status === 'missing') return 'No job description was provided.'
  return ''
}

/**
 * Export batch ranking to CSV with improved formatting
 */
export function exportBatchToCSV(batchResult, fileName = null, options = {}) {
  const rows = getBatchRows(batchResult)
  if (!rows.length) {
    return { success: false, message: 'No data to export' }
  }

  const headers = [
    'Rank',
    'Candidate Name',
    'Email',
    'File Name',
    'Final Score (%)',
    'ATS Score (%)',
    'Skill Match (%)',
    'Semantic Match (%)',
    'Experience Score (%)',
    'JD Quality',
    'JD Quality Reason',
    'JD Warning',
    'Score Version',
    'Strengths',
    'Missing Skills',
    'Overall Match'
  ]

  const lines = [
    headers.join(','),
    ...rows.map((r, idx) => {
      const jdQuality = getJdQuality(r, batchResult)
      const warnings = [
        getJdQualityMessage(jdQuality),
        ...((Array.isArray(r.warnings) ? r.warnings : []) || []),
      ].filter(Boolean)
      return [
      escapeCsv(r.rank || idx + 1),
      escapeCsv(r.candidate_name || ''),
      escapeCsv(r.candidate_email || r.email || ''),
      escapeCsv(r.file_name || ''),
      Number(r.final_score || 0).toFixed(2),
      Number(r.ats_score || 0).toFixed(2),
      Number(r.skill_score ?? r.keyword_score ?? 0).toFixed(2),
      Number(r.semantic_score || 0).toFixed(2),
      Number(r.experience_score || 0).toFixed(2),
      escapeCsv(getJdQualityLabel(jdQuality)),
      escapeCsv(jdQuality.reason || ''),
      escapeCsv([...new Set(warnings)].join('; ')),
      escapeCsv(r.score_version || batchResult?.score_version || ''),
      escapeCsv(listText(r.strengths ?? r.detected_strengths)),
      escapeCsv(listText(r.missing_skills)),
      escapeCsv(getMatchInterpretation(r.final_score))
    ].join(',')
    })
  ]

  const timestamp = new Date().toISOString().slice(0, 10)
  const fileNameToUse = fileName || `batch-ranking-${timestamp}.csv`
  const csv = lines.join('\n')
  const shouldDownload = options.download ?? import.meta.env.MODE !== 'test'
  if (!shouldDownload) {
    return csv
  }
  return downloadFile(csv, fileNameToUse, 'text/csv;charset=utf-8;')
}

/**
 * Export batch ranking to formatted Excel-like HTML
 */
export function exportBatchToHTML(batchResult, fileName = null) {
  const rows = getBatchRows(batchResult)
  if (!rows.length) {
    return { success: false, message: 'No data to export' }
  }

  const timestamp = new Date().toLocaleString()

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Batch Ranking Report</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      background: #f5f5f5;
      padding: 20px;
      color: #333;
    }
    .container {
      max-width: 1200px;
      margin: 0 auto;
      background: white;
      border-radius: 8px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      padding: 30px;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 30px;
      padding-bottom: 20px;
      border-bottom: 3px solid #a78bfa;
    }
    h1 {
      font-size: 28px;
      color: #1a1a1a;
      font-weight: 700;
    }
    .meta {
      text-align: right;
      font-size: 14px;
      color: #666;
    }
    .meta p {
      margin: 4px 0;
    }
    .summary {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
      margin-bottom: 30px;
    }
    .summary-card {
      background: #f9f9f9;
      border: 1px solid #e0e0e0;
      border-radius: 8px;
      padding: 16px;
      text-align: center;
    }
    .summary-card .label {
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: #999;
      margin-bottom: 8px;
      font-weight: 600;
    }
    .summary-card .value {
      font-size: 28px;
      font-weight: 700;
      color: #a78bfa;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 20px;
    }
    thead {
      background: linear-gradient(135deg, #a78bfa 0%, #8b5cf6 100%);
      color: white;
    }
    th {
      padding: 14px;
      text-align: left;
      font-weight: 600;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    td {
      padding: 12px 14px;
      border-bottom: 1px solid #e0e0e0;
      font-size: 13px;
    }
    tbody tr:hover {
      background: #f9f9f9;
    }
    .rank-badge {
      display: inline-block;
      width: 32px;
      height: 32px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      color: white;
      font-size: 12px;
    }
    .rank-1 { background: linear-gradient(135deg, #ffd700, #ffed4e); color: #333; }
    .rank-2 { background: linear-gradient(135deg, #c0c0c0, #e8e8e8); color: #333; }
    .rank-3 { background: linear-gradient(135deg, #cd7f32, #d4945a); }
    .rank-n { background: #a78bfa; }
    .score-excellent { color: #22c55e; font-weight: 700; }
    .score-good { color: #84cc16; font-weight: 700; }
    .score-fair { color: #f59e0b; font-weight: 700; }
    .score-poor { color: #ef4444; font-weight: 700; }
    .badge {
      display: inline-block;
      padding: 3px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
    }
    .badge-strength { background: #22c55e1a; color: #22c55e; }
    .badge-missing { background: #ef44441a; color: #ef4444; }
    .email { word-break: break-all; }
    .footer {
      margin-top: 40px;
      padding-top: 20px;
      border-top: 1px solid #e0e0e0;
      text-align: center;
      font-size: 12px;
      color: #999;
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div>
        <h1>📊 Batch Ranking Report</h1>
      </div>
      <div class="meta">
        <p><strong>Generated:</strong> ${timestamp}</p>
        <p><strong>Total Candidates:</strong> ${rows.length}</p>
      </div>
    </div>

    <div class="summary">
      <div class="summary-card">
        <div class="label">Average Score</div>
        <div class="value">${(rows.reduce((sum, r) => sum + (r.final_score || 0), 0) / rows.length).toFixed(0)}%</div>
      </div>
      <div class="summary-card">
        <div class="label">Top Score</div>
        <div class="value">${Math.max(...rows.map(r => r.final_score || 0)).toFixed(0)}%</div>
      </div>
      <div class="summary-card">
        <div class="label">Excellent Matches</div>
        <div class="value">${rows.filter(r => (r.final_score || 0) >= 75).length}</div>
      </div>
      <div class="summary-card">
        <div class="label">Good Matches</div>
        <div class="value">${rows.filter(r => {const s = r.final_score || 0; return s >= 50 && s < 75}).length}</div>
      </div>
    </div>

    <table>
      <thead>
        <tr>
          <th>Rank</th>
          <th>Candidate</th>
          <th>Email</th>
          <th>Final Score</th>
          <th>ATS</th>
          <th>Skills</th>
          <th>Top Strengths</th>
          <th>Match Level</th>
        </tr>
      </thead>
      <tbody>
        ${rows.map((r, idx) => {
          const finalScore = r.final_score || 0
          const scoreClass = finalScore >= 75 ? 'score-excellent' : finalScore >= 50 ? 'score-good' : finalScore >= 30 ? 'score-fair' : 'score-poor'
          const rankClass = idx === 0 ? 'rank-1' : idx === 1 ? 'rank-2' : idx === 2 ? 'rank-3' : 'rank-n'
          const matchLevel = getMatchInterpretation(finalScore)
          const strengthsBadges = (r.strengths || []).slice(0, 2).map(s => `<span class="badge badge-strength">${escapeHtml(s)}</span>`).join('')
          
          return `<tr>
            <td><span class="rank-badge ${rankClass}">${r.rank || idx + 1}</span></td>
            <td><strong>${escapeHtml(r.candidate_name || 'N/A')}</strong></td>
            <td class="email">${escapeHtml(r.candidate_email || '-')}</td>
            <td><span class="${scoreClass}">${finalScore.toFixed(0)}%</span></td>
            <td>${Number(r.ats_score || 0).toFixed(0)}%</td>
            <td>${Number(r.skill_score || 0).toFixed(0)}%</td>
            <td>${strengthsBadges}</td>
            <td>${matchLevel}</td>
          </tr>`
        }).join('')}
      </tbody>
    </table>

    <div class="footer">
      <p>Generated by CV Analyzer • Recruiter Dashboard</p>
    </div>
  </div>
</body>
</html>`

  const timestamp2 = new Date().toISOString().slice(0, 10)
  const fileNameToUse = fileName || `batch-ranking-${timestamp2}.html`
  return downloadFile(html, fileNameToUse, 'text/html;charset=utf-8;')
}

/**
 * Export batch ranking to JSON
 */
export function exportBatchToJSON(batchResult, fileName = null) {
  const rows = getBatchRows(batchResult)
  if (!rows.length) {
    return { success: false, message: 'No data to export' }
  }

  const data = {
    generated_at: new Date().toISOString(),
    total_candidates: rows.length,
    average_score: (rows.reduce((sum, r) => sum + (r.final_score || 0), 0) / rows.length).toFixed(2),
    ranking: rows,
    analytics: batchResult.analytics || {}
  }

  const timestamp = new Date().toISOString().slice(0, 10)
  const fileNameToUse = fileName || `batch-ranking-${timestamp}.json`
  return downloadFile(JSON.stringify(data, null, 2), fileNameToUse, 'application/json;charset=utf-8;')
}

/**
 * Export decisions log
 */
export function exportDecisionsToCSV(decisions, fileName = null) {
  if (!Array.isArray(decisions) || decisions.length === 0) {
    return { success: false, message: 'No decisions to export' }
  }

  const headers = ['Date', 'Candidate Name', 'Email', 'Decision', 'Score', 'Job', 'Email Sent', 'Notes']
  const lines = [
    headers.join(','),
    ...decisions.map(d => [
      escapeCsv(d.created_at ? new Date(d.created_at).toLocaleString() : ''),
      escapeCsv(d.candidate_name || ''),
      escapeCsv(d.candidate_email || ''),
      escapeCsv(d.action || ''),
      Number(d.final_score || 0).toFixed(2),
      escapeCsv(d.job_title || ''),
      d.email_sent ? 'Yes' : 'No',
      escapeCsv(d.notes || '')
    ].join(','))
  ]

  const timestamp = new Date().toISOString().slice(0, 10)
  const fileNameToUse = fileName || `decisions-${timestamp}.csv`
  return downloadFile(lines.join('\n'), fileNameToUse, 'text/csv;charset=utf-8;')
}

/**
 * Helper to interpret score
 */
export function getMatchInterpretation(score) {
  const value = Number(score || 0)
  if (value <= 1) {
    if (value > 0.75) return 'Excellent Match'
    if (value >= 0.65) return 'Good Match'
    if (value >= 0.4) return 'Fair Match'
    return 'Poor Match'
  }
  if (value >= 75) return 'Excellent Match'
  if (value >= 50) return 'Good Match'
  if (value >= 30) return 'Fair Match'
  return 'Poor Match'
}

/**
 * Helper to escape HTML
 */
export function escapeHtml(text) {
  if (!text) return ''
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  }
  return String(text).replace(/[&<>"']/g, m => map[m])
}

/**
 * Export usage stats
 */
export function exportUsageStatsToCSV(usageRights, fileName = null) {
  if (!usageRights) {
    return { success: false, message: 'No usage data available' }
  }

  const lines = [
    'Usage Type,Used,Limit,Remaining,Percentage',
    `Batch Analyses,${usageRights.batch_analyses?.used || 0},${usageRights.batch_analyses?.limit || 100},${(usageRights.batch_analyses?.limit || 100) - (usageRights.batch_analyses?.used || 0)},${(((usageRights.batch_analyses?.used || 0) / (usageRights.batch_analyses?.limit || 100)) * 100).toFixed(1)}%`,
    `Exports,${usageRights.exports?.used || 0},${usageRights.exports?.limit || 50},${(usageRights.exports?.limit || 50) - (usageRights.exports?.used || 0)},${(((usageRights.exports?.used || 0) / (usageRights.exports?.limit || 50)) * 100).toFixed(1)}%`,
    `Custom Searches,${usageRights.custom_searches?.used || 0},${usageRights.custom_searches?.limit || 50},${(usageRights.custom_searches?.limit || 50) - (usageRights.custom_searches?.used || 0)},${(((usageRights.custom_searches?.used || 0) / (usageRights.custom_searches?.limit || 50)) * 100).toFixed(1)}%`,
    `Emails Sent,${usageRights.emails_sent?.used || 0},${usageRights.emails_sent?.limit || 500},${(usageRights.emails_sent?.limit || 500) - (usageRights.emails_sent?.used || 0)},${(((usageRights.emails_sent?.used || 0) / (usageRights.emails_sent?.limit || 500)) * 100).toFixed(1)}%`
  ]

  const timestamp = new Date().toISOString().slice(0, 10)
  const fileNameToUse = fileName || `usage-stats-${timestamp}.csv`
  return downloadFile(lines.join('\n'), fileNameToUse, 'text/csv;charset=utf-8;')
}
