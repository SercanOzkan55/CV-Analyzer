# Parser Generalization Review Skill

Use this skill when changing CV parsing, auto-fix parsing, upload extraction, document format support, section classification, scoring inputs, or recruiter batch parsing.

## Mission

Keep CV parsing general. The parser must work for many languages, layouts, formats, and professional backgrounds.

## Do Not Special-Case Narrow Samples

Do not write logic that only works for:
- One language.
- One country.
- One company.
- One certificate name.
- One CV template.
- One visual layout.
- One file from the user's desktop.

Specific samples are useful only as regression tests. The fix must generalize.

## Supported Inputs

The same extraction path should support:
- PDF.
- DOCX.
- TXT.

The same parser behavior should feed:
- Analyze.
- Auto-fix.
- CV builder parse.
- Recruiter batch ranking.
- Recruiter dashboard batch upload.
- JD file parsing.

## Section Integrity Rules

Keep these sections distinct whenever possible:
- Contact.
- Summary/profile.
- Experience.
- Education.
- Skills.
- Certifications.
- Projects.
- Awards.
- Publications.
- Languages.
- Volunteer work.

Known critical regression:
- Certifications must not leak into experience.
- Education must not be parsed as work history.
- Projects must not be parsed as certificates.
- Skills lists must not consume later section headings.

## Layout Rules

Parser changes should consider:
- Multi-page PDFs.
- Multi-column PDFs.
- DOCX tables.
- Text exports with inconsistent line breaks.
- Section headings with punctuation.
- Uppercase headings.
- Mixed-language CVs.
- Missing standard headings.

## Language Rules

Section aliases should be general and multilingual. Favor normalized heading dictionaries over one-off conditionals.

Important languages to consider:
- Turkish.
- English.
- German.
- Spanish.
- French.
- Arabic.
- Unknown/neutral text.

## Testing Rules

Every parser bug fix needs at least one regression test.

Useful test files:
- `tests/test_cv_autofix_parser_generalization.py`
- `tests/test_ats.py`
- `tests/test_language_service_generalization.py`
- `tests/test_recruiter_endpoints.py`
- `tests/test_security_file_upload.py`
- `tests/test_security_file_type.py`

Minimum checks:

```bash
python -m pytest tests/test_cv_autofix_parser_generalization.py
python -m pytest tests/test_ats.py
python -m pytest tests/test_recruiter_endpoints.py
python -m pytest tests/test_security_file_upload.py tests/test_security_file_type.py
```

Run full backend tests before final response when practical:

```bash
python -m pytest
```

## Implementation Placement

Parsing behavior belongs in service modules, not `main.py`.

Expected target modules:
- `services/parsing_service.py`
- `services/upload_service.py`
- `services/cv_autofix_service.py`
- `services/ats_service.py`
- `services/language_service.py`
- `services/skill_service.py`

Route handlers should only call these services.

## Output Requirement

Final response must include:
- What parser/generalization issue was fixed.
- Which formats/languages/layouts were considered.
- Which regression tests were added or updated.
- Any known parser limitations that remain.
