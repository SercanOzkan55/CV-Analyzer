---
name: frontend-ui-polish
description: SaaS UI polish workflow for React/Vite frontends. Use when Codex needs to improve a large production app's visual quality through safe, centralized design-system, light-theme, component, animation, responsive, and accessibility improvements without redesigning the product or changing business logic.
---

# Frontend UI Polish

Act as a combined Design System Agent, Motion Design Agent, and senior frontend implementer. Improve the product through shared foundations first, then targeted high-impact screens.

## Operating Rules

- Preserve business logic, routing, authentication, API behavior, and existing features.
- Do not introduce new dependencies unless the repo lacks a needed capability and the user approves.
- Prefer existing tokens, CSS variables, classes, components, Framer Motion, and lucide icons.
- Improve light theme quality while preserving dark theme parity.
- Make central changes in shared CSS/components before one-off page changes.
- Keep the first pass incremental: tokens, forms, buttons, cards, tables, modals, toasts, loading states, navigation, and page transitions.

## Foundation Checklist

1. Inspect framework, routes, theme context, global CSS, shared components, and animation usage.
2. Expand or normalize design tokens for color, spacing, typography, radius, shadows, borders, focus, and motion.
3. Add or improve global reduced-motion behavior.
4. Standardize default, hover, active, focus, disabled, loading, error, success, warning, and info states.
5. Prefer `transform` and `opacity` for animation.
6. Avoid heavy blur, excessive gradients, playful effects, or noisy per-item animation.

## Implementation Order

1. Update project instructions and skills when the workflow changes.
2. Improve global tokens and base styles.
3. Polish shared components and common classes.
4. Improve high-impact screens only when the change is small and follows existing patterns.
5. Run available validation from `AGENTS.md`.

## Output

Report:

- Foundation changes.
- Component and screen polish.
- Motion changes and reduced-motion behavior.
- Validation commands and results.
- Remaining recommendations and risks.
