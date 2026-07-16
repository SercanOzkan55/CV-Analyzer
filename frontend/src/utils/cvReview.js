export function reviewDecisionMap(operations = []) {
  return Object.fromEntries(
    operations.map((operation) => [operation.id, operation.accepted !== false]),
  )
}

export function applyReviewDecisions(operations = [], decisions = {}) {
  const lines = []

  operations.forEach((operation) => {
    const before = Array.isArray(operation.before_lines) ? operation.before_lines : []
    const after = Array.isArray(operation.after_lines) ? operation.after_lines : []
    const accepted = decisions[operation.id] ?? operation.accepted !== false

    if (operation.kind === 'equal') {
      lines.push(...before)
    } else {
      lines.push(...(accepted ? after : before))
    }
  })

  return lines.join('\n')
}
