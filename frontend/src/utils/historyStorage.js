const HISTORY_NAMESPACE = 'cv-analyzer-history'
const MAX_USER_HISTORY_ITEMS = 5

function resolveUserId(user) {
  if (user?.id) return String(user.id)
  if (user?.email) return String(user.email).toLowerCase()
  return 'anonymous'
}

export function getHistoryStorageKey(user) {
  return `${HISTORY_NAMESPACE}:${resolveUserId(user)}`
}

export function getHistory(user) {
  try {
    const key = getHistoryStorageKey(user)
    const parsed = JSON.parse(localStorage.getItem(key) || '[]')
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function setHistory(user, items, { limit = MAX_USER_HISTORY_ITEMS } = {}) {
  const normalized = Array.isArray(items) ? items.slice(0, limit) : []
  const key = getHistoryStorageKey(user)
  localStorage.setItem(key, JSON.stringify(normalized))
  return normalized
}

export function addHistoryItem(user, item, { limit = MAX_USER_HISTORY_ITEMS } = {}) {
  const current = getHistory(user)
  current.unshift(item)
  return setHistory(user, current, { limit })
}

export function removeHistoryItem(user, id, { limit = MAX_USER_HISTORY_ITEMS } = {}) {
  const updated = getHistory(user).filter((entry) => entry?.id !== id)
  return setHistory(user, updated, { limit })
}

export function clearHistory(user) {
  const key = getHistoryStorageKey(user)
  localStorage.setItem(key, '[]')
}
