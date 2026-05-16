# Multi-Agent UI Workflow

Use this repository guide when working on UI changes. The goal is to simulate a senior multi-agent UI team while keeping changes incremental, production-safe, and aligned with the existing React/Vite design system.

## Tool Setup

- Prefer Figma MCP when a Figma file, node, or design reference is provided. Review design intent before editing.
- Prefer browser/Playwright MCP when available for live screenshots, keyboard checks, and responsive viewport checks.
- If those MCP tools are not available, continue using the codebase as the source of truth and document the limitation in the final response.
- To enable richer UI review later, install/configure:
  - Figma MCP with access to the relevant team/file.
  - Browser or Playwright MCP with permission to open `http://localhost:<port>`.

Project-level Playwright MCP setup is stored in `.codex/config.toml`:

```toml
[mcp_servers.playwright]
command = "npx"
args = ["-y", "@playwright/mcp@latest"]
```

Project-level Figma MCP setup is also stored in `.codex/config.toml`:

```toml
[mcp_servers.figma]
url = "http://127.0.0.1:3845/mcp"
```

Start the Figma Desktop MCP server before launching Codex, then restart Codex after changing MCP server config so the new browser and Figma tools are loaded.

When a Figma frame link is provided, use it as the source design, compare it with the current implementation, then run the Product Designer, Frontend Implementation, and QA Review agents. Apply only safe differences needed to match the design.

## Specialized Agents

### Product Designer Agent

Use `.codex/skills/design-review/SKILL.md`.

Responsibilities:
- Review Figma/design intent when available; otherwise use the live app and codebase as source of truth.
- Check visual hierarchy, spacing, alignment, typography, contrast, color usage, responsive layout, empty/loading/error states, accessibility, and design consistency.
- Categorize issues as Critical Must Fix, High Impact UI Polish, Animation Opportunity, Theme/Design Token Issue, Responsive Issue, Accessibility Issue, Nice To Have, or Avoid/risky changes.
- Identify only high-confidence improvements that preserve the current product direction.
- Defer broad redesigns, new branding, and speculative layout changes.

Output:
- High-confidence improvements.
- Risks or deferred design questions.
- Validation notes for viewports and states.

### Design System Agent

Use `.codex/skills/frontend-ui-polish/SKILL.md`.

Responsibilities:
- Improve shared tokens and visual foundations before one-off page styling.
- Preserve the existing CV Analyzer brand direction while making the product feel more professional, clean, modern, and trustworthy.
- Standardize colors, spacing, radius, shadows, typography, focus states, semantic statuses, and light theme surfaces.
- Prefer central CSS variables, utility classes, and shared component classes.

Output:
- Token/foundation changes.
- Component or screen surfaces affected.
- Risks or compatibility notes.

### Motion Design Agent

Use `.codex/skills/frontend-ui-polish/SKILL.md`.

Responsibilities:
- Use existing Framer Motion and CSS transitions; do not add animation dependencies without approval.
- Add subtle, fast, professional motion for page transitions, cards, buttons, menus, modals, tabs, loading states, and empty states.
- Respect `prefers-reduced-motion`.
- Prefer opacity and transform over layout-heavy animation.

Output:
- Animation changes.
- Reduced-motion behavior.
- Interactions or screens to verify.

### Frontend Implementation Agent

Use `.codex/skills/frontend-implementation/SKILL.md`.

Responsibilities:
- Implement only safe, scoped UI changes.
- Prefer existing CSS variables, components, routes, icons, Framer Motion, lucide icons, and layout patterns.
- Avoid broad rewrites, new dependencies, unrelated refactors, or redesigning whole screens.
- Add focused tests only when behavior or contracts change.

Output:
- Files changed.
- Why changes are safe.
- Validation run.
- Deferred questions.

### QA Review Agent

Use `.codex/skills/ui-qa-review/SKILL.md`.

Responsibilities:
- Review regression risk, accessibility, responsive behavior, and validation coverage.
- Run or recommend build, test, lint/typecheck, and browser checks.
- Check keyboard access, focus states, landmarks, skip links, forms, modals, upload flows, and navigation.

Output:
- Blockers.
- Non-blocking risks.
- Validation evidence.
- Ship recommendation.

## UI Workflow

1. Product Designer Agent reviews the target screen or flow.
2. Design System Agent identifies the safest central foundation changes.
3. Motion Design Agent proposes tasteful motion using existing tools.
4. Frontend Implementation Agent applies only high-confidence improvements.
5. QA Review Agent validates the change and calls out residual risk.
6. The coordinator summarizes what changed and what was intentionally deferred.

## Main Frontend Surfaces

Primary screens:
- `frontend/src/pages/LandingPage.jsx`
- `frontend/src/pages/DashboardPage.jsx`
- `frontend/src/pages/AnalyzePage.jsx`
- `frontend/src/pages/RecruiterPage.jsx`

Shared UI:
- `frontend/src/components/Navbar.jsx`
- `frontend/src/components/Footer.jsx`
- `frontend/src/components/Toast.jsx`
- `frontend/src/components/Modal.jsx`
- `frontend/src/components/LoadingScreen.jsx`
- `frontend/src/components/PageTransition.jsx`
- `frontend/src/components/SkeletonLoader.jsx`
- `frontend/src/style.css`

## Permanent UI Quality Rules

- Prefer central tokens and shared classes over one-off page styles.
- Prioritize an excellent light theme: soft backgrounds, clear surfaces, subtle borders, restrained shadows, and readable text hierarchy.
- Keep dark theme parity when changing tokens or shared components.
- Use consistent semantic colors for primary, secondary, destructive, warning, success, and info states.
- Keep typography professional: no viewport-scaled font sizes, no negative letter spacing in compact controls, and no oversized headings inside dense app surfaces.
- Keep motion subtle and useful: micro interactions 120-200ms, section/page entrances 200-400ms, modals/drawers 180-300ms.
- Respect `prefers-reduced-motion` globally.
- Prefer `transform` and `opacity` for animation performance.
- Do not overuse gradients, glass, blur, shadows, decorative blobs, or playful effects in operational app screens.
- Keep cards at `8px` radius or less only when the established component style calls for it; otherwise preserve current tokenized radius.
- Make keyboard focus, hover, active, disabled, loading, empty, and error states visible and consistent.
- Do not remove features, change business logic, break API/auth/routing behavior, or introduce new dependencies for visual polish without explicit approval.

## Validation Commands

Run from `frontend/` when UI files change:

```bash
npm run build
npm run test
npx tsc --noEmit
```

There is no dedicated lint script in `frontend/package.json` at the time of writing. If one is added, run it during QA.

For browser verification:

```bash
npm run dev
```

Then inspect at least:
- Desktop: `1440 x 900`
- Tablet: `1024 x 768`
- Mobile: `390 x 844`

Check key routes:
- `/`
- `/dashboard`
- `/analyze`
- `/recruiter`

## Guardrails

- Do not redesign the whole product.
- Do not introduce new UI libraries unless explicitly requested.
- Do not replace established tokens, layout primitives, or navigation patterns without approval.
- Do not hide functionality to make a screen look cleaner.
- Prefer fixing accessibility, responsive overflow, spacing inconsistencies, and broken states over aesthetic restyling.
- Keep cards, panels, and controls consistent with existing radius, border, shadow, and color tokens.
