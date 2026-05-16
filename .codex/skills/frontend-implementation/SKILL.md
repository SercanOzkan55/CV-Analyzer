# Frontend Implementation Skill

Use this skill when implementing frontend UI, routing, shared components, page styles, API wrappers, responsive behavior, or product polish.

## Role

Act as a senior frontend engineer working in an existing production app.

## Mission

Implement safe, design-system-aligned improvements while preserving all existing functionality.

## Core Rules

- Do not remove features.
- Do not rewrite the whole app.
- Do not introduce unnecessary dependencies.
- Use existing React/Vite patterns.
- Keep API calls centralized in `frontend/src/api.js`.
- Keep shared logic in utilities/components.
- Preserve business logic, auth behavior, routing, and backend contracts.
- If backend changes are needed, use the backend modularization skill and do not add feature logic to `main.py`.

## Shared Ownership

Use shared files for repeated behavior:

- File upload types: `frontend/src/utils/fileTypes.js`.
- Score/status colors: shared utility or token file.
- Route/API calls: `frontend/src/api.js`.
- Shared UI states: reusable components.
- Translations: `frontend/src/i18n/*.json`.

Avoid duplicating:

- Accepted file extensions.
- Hard-coded status colors.
- Button/card/table styling.
- Empty/loading/error state markup.

## UI Implementation Checklist

Before editing:

- Identify affected routes/pages.
- Identify shared components.
- Identify existing CSS/tokens.
- Check whether a central fix solves multiple pages.

During editing:

- Keep changes scoped.
- Prefer shared component improvements.
- Keep responsive layouts stable.
- Keep text from overflowing.
- Preserve keyboard focus states.
- Respect `prefers-reduced-motion`.

After editing:

```bash
cd frontend
npm test
npm run build
```

If backend API contracts are touched:

```bash
python -m pytest
```

## Navigation Rules

Do not crowd the top navbar.

Use:
- Primary nav for core workflows.
- Menus/secondary nav for less frequent tools.
- Authenticated layout for product screens.

Do not:
- Add every page as a top-level nav item.
- Remove Blog/Cover Letter/Career Studio/Compare/CV Builder/Recruiter tools to simplify layout.

## Visual Rules

Prefer:

- Clean light theme.
- Consistent spacing.
- Clear card hierarchy.
- Subtle hover/focus/active states.
- Fast, purposeful transitions.
- Accessible contrast.

Avoid:

- Hard-coded one-off colors.
- Excessive gradients.
- Heavy shadows.
- Decorative animations everywhere.
- Nested cards.
- Huge hero-style UI in operational screens.

## Output Requirement

Final response must include:

- Screens/components changed.
- Shared utilities/components updated.
- Commands run and results.
- Remaining UI risks or recommendations.
