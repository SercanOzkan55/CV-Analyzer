from services.cv_autofix_service import auto_fix_cv_text, structured_text_to_builder_payload


def test_turkish_certification_heading_does_not_leak_into_experience():
    cv = """Ayse Kaya
ayse@example.com

Özet
Veri analisti.

Deneyim
Veri Analisti
Satış raporlarını otomatikleştirdi.

Sertifikalar
Google Data Analytics Certificate

Eğitim
İstatistik Lisans

Beceriler
Python, SQL, Power BI
"""

    payload = structured_text_to_builder_payload(cv, lang="auto")

    experience_text = " ".join(
        bullet
        for item in payload["experiences"]
        for bullet in item.get("bullets", [])
    )
    certifications = " ".join(item["name"] for item in payload["certifications"])

    assert "Google Data Analytics" not in experience_text
    assert "Google Data Analytics" in certifications
    assert payload["professional_profile"] == ""


def test_spanish_and_german_section_aliases_are_canonicalized():
    cv = """Maria Lopez
maria@example.com

Perfil
Project manager.

Experiencia laboral
Managed rollout across three teams.

Zertifikate
PMP

Ausbildung
MBA

Habilidades
Agile, Jira
"""

    result = auto_fix_cv_text(cv, job_description="Project manager", use_ai=False)

    assert "CERTIFICATIONS" in result["optimized_cv_text"]
    assert "PMP" in result["optimized_cv_text"]
    assert "experience" in result["structured_sections"]
    assert "certifications" in result["structured_sections"]


def test_professional_profile_field_is_not_limited_to_linkedin():
    cv = """John Doe
john@example.com | github.com/johndoe

Experience
Built APIs.

Education
BSc Computer Science

Skills
Python
"""

    payload = structured_text_to_builder_payload(cv, lang="auto")

    assert payload["professional_profile"] == "john@example.com | github.com/johndoe"
    assert payload["linkedin"] == payload["professional_profile"]
