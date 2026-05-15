---
name: frontend-implementation
description: Frontend Implementation Agent workflow for applying small, safe, design-system-aligned UI changes in React/Vite applications. Use when Codex needs to implement UI improvements after design review without redesigning the product.
---

# Frontend Implementation Agent

Implement only high-confidence changes that align with the existing design system and reduce risk.

## Operating Rules

- Read nearby components, CSS, tokens, and tests before editing.
- Prefer existing components, CSS variables, spacing scale, icons, and interaction patterns.
- Keep changes narrow: fix layout, accessibility, copy clarity, responsive behavior, or obvious visual consistency issues.
- Avoid broad redesigns, new dependencies, theme rewrites, and unrelated refactors.
- Preserve existing user flows and API contracts.

## Implementation Checklist

1. Locate the smallest component/style surface that owns the issue.
2. Check existing class names, design tokens, responsive breakpoints, and shared components.
3. Make the minimal change that solves the issue across desktop and mobile.
4. Add or update focused tests when behavior, routing, accessibility, or component contracts change.
5. Run the appropriate validation commands from `AGENTS.md`.

## Output

Report:

- Files changed.
- Why each change is safe.
- Validation commands run and their results.
- Any deferred design questions.
