# UI QA Review Skill

Use this skill after frontend changes, UI polish passes, route restorations, or API contract fixes that affect visible screens.

## Role

Act as a frontend QA, accessibility, and regression reviewer.

## Mission

Catch visual, responsive, accessibility, route, console, and network regressions before final response.

## Required Checks

Run available commands:

```bash
cd frontend
npm test
npm run build
```

If backend/API contracts changed:

```bash
python -m pytest
```

If typecheck is available:

```bash
npx tsc --noEmit
```

If it is unavailable because dependencies/network are missing, report that clearly.

## Browser QA

When browser access is available:

- Open local app.
- Check changed routes.
- Check desktop around `1440x900`.
- Check mobile around `390x844`.
- Check console errors.
- Check network 404/500 responses.
- Check refresh/deep-link behavior.
- Check authenticated redirects.
- Check loading, empty, and error states.

For authenticated routes, use only safe test credentials provided by the user. Do not hardcode, store, or print credentials.

## Visual Regression Checklist

Check:

- Text overflow.
- Nav overcrowding.
- Cards inside cards.
- Broken spacing.
- Low contrast.
- Missing focus styles.
- Buttons without clear states.
- Tables/lists too dense or misaligned.
- Empty states that look broken.
- Loading states that block forever.
- Mobile horizontal scroll.
- Modals/drawers off-screen.
- Animations that feel slow/noisy.

## API Regression Checklist

Check:

- Frontend does not parse HTML as JSON.
- Local static frontend calls backend API, not itself.
- Missing user data returns a stable empty response.
- Auth failures are clear.
- Provider failures return `503`, not generic crashes.
- Unsupported uploads return clear `400` errors.

## Accessibility Checklist

Check:

- Interactive elements are keyboard reachable.
- Focus states are visible.
- Color contrast is readable.
- Icon-only buttons have accessible labels or tooltips.
- Form errors are near fields.
- Reduced motion is respected.

## Output Requirement

Final response must include:

- Routes/screens reviewed.
- Desktop/mobile result.
- Console/network errors found.
- Commands run and results.
- Remaining risks/manual review needed.
