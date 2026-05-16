# UI Product Preservation Skill

Use this skill when changing navigation, routes, public pages, authenticated product screens, shared UI components, styles, or restored legacy features.

## Mission

Improve UI quality without removing or hiding important product functionality.

## Features To Preserve

Do not remove or bury these features without explicit user approval:
- Blog.
- Cover Letter.
- Career Studio.
- Compare.
- CV Builder.
- Template Marketplace.
- Dashboard.
- Analyze.
- Recruiter.
- Recruiter Hub.
- Job Tracker.
- My CVs.
- Data Center.
- Settings.
- Profile.
- Pricing/Premium.
- Auth pages.

## Navigation Rules

The top navbar must not become crowded.

Prefer:
- Primary nav for the most frequent workflows.
- Grouped menus for secondary tools.
- Authenticated product navigation for signed-in screens.
- Footer or secondary links for public/legal/support pages.

Do not:
- Add every route as a top-level navbar item.
- Remove important routes to reduce clutter.
- Make route discoverability depend only on direct URL entry.

## API/UI Consistency

If the UI exposes a feature, the backend contract must exist or the UI must show a clear unavailable state.

Avoid:
- Buttons that trigger 404s.
- Pages that parse HTML as JSON.
- Empty states that look like crashes.
- Console noise caused by missing local API base.

## Shared UI Rules

Use shared utilities and components for:
- File type acceptance.
- Score/status colors.
- Badges.
- Cards.
- Buttons.
- Tables/lists.
- Loading and empty states.
- Toasts and modals.

Do not duplicate hard-coded colors or accepted file extensions page-by-page.

## Visual Quality Rules

The app should feel:
- Professional.
- Calm.
- Modern.
- Trustworthy.
- Clear.
- Responsive.

Prefer:
- Light theme with soft surfaces.
- Consistent spacing.
- Readable typography.
- Subtle borders.
- Restrained shadows.
- Visible focus states.
- Short, useful transitions.

Avoid:
- Overly decorative gradients.
- Heavy blur/glass effects everywhere.
- Nested cards.
- Low contrast text.
- Text overflow.
- Animated noise.

## Browser QA Rules

For visual or route changes, check:
- Desktop around `1440x900`.
- Mobile around `390x844`.
- Console errors.
- Network 404/500.
- Route reload behavior.
- Auth redirects.
- Empty/loading/error states.

Use the in-app browser when available.

## Verification

Run:

```bash
cd frontend
npm test
npm run build
```

If backend contracts are touched:

```bash
python -m pytest
```

## Output Requirement

Final response must include:
- Which screens/features were preserved.
- Which UI/API mismatch was fixed.
- Files changed.
- Browser QA result if performed.
- Remaining visual or route risks.
