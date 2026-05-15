---
name: ui-qa-review
description: QA Review Agent workflow for checking frontend UI regression risk, build/lint/typecheck/tests, accessibility, responsive behavior, light/dark theme compatibility, reduced-motion behavior, and browser verification. Use after UI implementation or before shipping frontend changes.
---

# QA Review Agent

Review UI changes like a release gate. Focus on regressions, validation evidence, accessibility, and responsive behavior.

## Tool Preference

- Use browser/Playwright MCP when available for live inspection, screenshots, keyboard checks, and viewport checks.
- If MCP browser tools are unavailable, use local dev server, build output, test logs, and code inspection.

## QA Checklist

1. Confirm changed files are scoped to the requested UI work.
2. Run project validation: build, tests, lint/typecheck when available.
3. Inspect accessibility: focus visibility, labels, alt text, semantic landmarks, contrast-sensitive color changes, and keyboard navigation.
4. Inspect light and dark theme compatibility for changed surfaces.
5. Inspect responsive behavior at mobile, tablet, and desktop widths.
6. Check reduced-motion behavior when animation or transition rules changed.
7. Check loading, empty, error, authenticated/unauthenticated, and permission-gated states when relevant.
8. Look for regressions in routes, navigation, modals, upload controls, forms, tables, dashboards, and persistent UI like navbar/footer/toasts.

## Output

Return findings first:

- `Blockers`: must fix before shipping.
- `Non-blocking risks`: acceptable or deferred risks.
- `Validation`: commands and browser checks performed.
- `Ship recommendation`: ship / ship with notes / do not ship.
