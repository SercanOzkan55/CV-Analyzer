.pragma library

// Shared, pure-JS weight-redistribution helpers for the AnalyzePage "Scoring
// criteria" budget UI (Phase 3). Used at BOTH levels of the two-level
// budget — the 4 top-level category sliders and each category's own member
// sliders — so the "always sums to a fixed total" invariant lives in one
// place instead of being reimplemented per level.
//
// Every function here is pure (no QML/backend access) and works on plain
// {key, value, locked} entry lists so it's trivially testable and reusable.
// `locked` marks an entry that must never change and never absorbs part of
// a redistributed delta (used for the reserved "Background" category and
// its 3 not-yet-scored members — see local_worker/scoring/criteria.py's
// RESERVED_CRITERIA).

// ── Internal helpers ─────────────────────────────────────────────────

function _clamp(value, lo, hi) {
    return Math.max(lo, Math.min(hi, value))
}

// Rounds an array of (possibly fractional) values to integers that sum to
// EXACTLY `targetSum`, using the largest-remainder method: floor everything,
// then hand out the leftover +1's to the entries with the largest fractional
// remainder first. Keeps proportions as close to the fractional shares as
// integer values allow, with no drift in the total.
function _roundPreservingSum(values, targetSum) {
    var floors = values.map(function (v) { return Math.floor(v) })
    var remainders = values.map(function (v, i) { return v - floors[i] })
    var flooredSum = floors.reduce(function (a, b) { return a + b }, 0)
    var need = Math.max(0, Math.round(targetSum - flooredSum))

    var order = values.map(function (_, i) { return i })
    order.sort(function (a, b) { return remainders[b] - remainders[a] })

    var result = floors.slice()
    for (var i = 0; i < need && i < order.length; i++) {
        result[order[i]] += 1
    }
    return result
}

// ── Public API ────────────────────────────────────────────────────────

// The "disk usage budget bar" interaction: one entry (`changedKey`) was
// just dragged to `newValueRaw`; every OTHER, non-locked entry absorbs the
// delta proportionally to its current value (or split evenly across them
// if they're all currently 0, to avoid a divide-by-zero / stuck-at-0 trap).
// Locked entries are excluded from the absorbing pool and keep their value
// unchanged, but their value still counts against `total`'s budget.
//
// entries: Array<{ key, value, locked? }> — `value` is each entry's
//   CURRENT weight.
// total: fixed sum every returned entry must add up to.
// changedKey: the entry the user just moved.
// newValueRaw: the slider's raw new value for changedKey (clamped here).
//
// Returns Array<{ key, value }> — new integer values for every entry
// (including changedKey and any locked entries), summing to exactly
// `total`.
function redistribute(entries, total, changedKey, newValueRaw) {
    var changedIndex = -1
    var lockedTotal = 0
    for (var i = 0; i < entries.length; i++) {
        if (entries[i].key === changedKey) changedIndex = i
        else if (entries[i].locked) lockedTotal += entries[i].value
    }

    var result = entries.map(function (e) { return { key: e.key, value: e.value } })
    if (changedIndex === -1) return result // defensive: unknown key, no-op

    var available = Math.max(0, total - lockedTotal)
    var newChangedValue = Math.round(_clamp(newValueRaw, 0, available))

    var others = []
    for (var j = 0; j < entries.length; j++) {
        if (j === changedIndex || entries[j].locked) continue
        others.push({ index: j, value: entries[j].value })
    }

    result[changedIndex].value = newChangedValue

    if (others.length === 0) return result

    var otherOldTotal = others.reduce(function (a, o) { return a + o.value }, 0)
    var otherNewTotal = available - newChangedValue

    var shares
    if (otherOldTotal > 0) {
        shares = others.map(function (o) { return o.value * (otherNewTotal / otherOldTotal) })
    } else {
        // All other entries are already 0 — split evenly instead of
        // proportionally (proportional-to-0 would just stay 0 forever).
        shares = others.map(function () { return otherNewTotal / others.length })
    }

    var rounded = _roundPreservingSum(shares, otherNewTotal)
    for (var k = 0; k < others.length; k++) {
        result[others[k].index].value = rounded[k]
    }
    return result
}

// Proportionally rescales a WHOLE group of entries (e.g. one category's
// member criteria) so they sum to `newTotal`, preserving each entry's
// relative share of the group (or splitting evenly if the group currently
// sums to 0). Used when a category's own aggregate slider moves: every
// member scales together, rather than one member absorbing the change.
//
// entries: Array<{ key, value, locked? }>. Locked entries are excluded
//   from scaling and keep their value; that value still counts against
//   `newTotal`'s budget.
// newTotal: target sum for the whole group.
//
// Returns Array<{ key, value }> — new integer values summing to exactly
// `newTotal`.
function scaleGroup(entries, newTotal) {
    var lockedTotal = 0
    var unlocked = []
    for (var i = 0; i < entries.length; i++) {
        if (entries[i].locked) lockedTotal += entries[i].value
        else unlocked.push({ index: i, value: entries[i].value })
    }

    var result = entries.map(function (e) { return { key: e.key, value: e.value } })
    if (unlocked.length === 0) return result

    var available = Math.max(0, newTotal - lockedTotal)
    var oldTotal = unlocked.reduce(function (a, u) { return a + u.value }, 0)

    var shares
    if (oldTotal > 0) {
        shares = unlocked.map(function (u) { return u.value * (available / oldTotal) })
    } else {
        shares = unlocked.map(function () { return available / unlocked.length })
    }

    var rounded = _roundPreservingSum(shares, available)
    for (var k = 0; k < unlocked.length; k++) {
        result[unlocked[k].index].value = rounded[k]
    }
    return result
}

// Orders a batch of {key, value} target updates so they can be pushed
// through a `clamp_scoring_weight(value, other_total)`-style single-key
// setter (Python's `LocalWorkerBackend.setScoringWeight`) and land exactly
// on target, however many keys move at once.
//
// Why order matters: that setter clamps a key's new value to
// `total - sum(OTHER keys' CURRENT values)`. If an increase is applied
// before the decreases that make room for it, it gets truncated. Applying
// every decrease first (any order among themselves), then every increase
// (any order among themselves), is always safe — see WeightAllocator's
// module tests / AnalyzePage.qml usage for the invariant this relies on:
// entries and updates always share the same fixed total.
//
// oldByKey: { [key]: currentValue } — current values before this update.
// updates: Array<{ key, value }> — target values (e.g. from redistribute
//   or scaleGroup).
//
// Returns Array<{ key, value }> — the same updates, reordered.
function orderForApply(oldByKey, updates) {
    var withDelta = updates.map(function (u) {
        var old = (oldByKey[u.key] !== undefined) ? oldByKey[u.key] : 0
        return { key: u.key, value: u.value, delta: u.value - old }
    })
    withDelta.sort(function (a, b) { return a.delta - b.delta })
    return withDelta.map(function (u) { return { key: u.key, value: u.value } })
}
