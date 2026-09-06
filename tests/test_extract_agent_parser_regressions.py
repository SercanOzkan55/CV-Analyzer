from agents.extract_agent import _merge_wrapped_lines, extract_structured


def test_wrapped_pdf_word_is_dehyphenated():
    merged = _merge_wrapped_lines(
        "Active project devel-\nopment showcased on GitHub. Seeking a Software Engineering role."
    )

    assert "development showcased" in merged
    assert "devel- opment" not in merged


def test_lettered_bullets_are_not_fused_into_one_line():
    # Single lowercase letters ("b)", "c)", "d)") satisfy the generic
    # "starts lowercase -> wrapped continuation" heuristic used elsewhere in
    # this function, so without an explicit exception a lettered list
    # collapses into one fused sentence before section splitting ever runs.
    text = (
        "KEY RESPONSIBILITIES\n"
        "a) Managed a portfolio of community health projects\n"
        "b) Coordinated with government liaison offices\n"
        "c) Prepared quarterly donor reports\n"
        "d) Supervised a team of field officers\n"
    )
    merged_lines = _merge_wrapped_lines(text).split("\n")

    bullet_lines = [line for line in merged_lines if line.strip()[:2] in ("a)", "b)", "c)", "d)")]
    assert len(bullet_lines) == 4
    assert not any("b)" in line and not line.strip().startswith("b)") for line in bullet_lines)


def test_multi_column_name_rescue_accepts_engineering_title():
    result = extract_structured(
        """multi_col_fixed
SKILLS
Innovator from Govt.

SUKHVINDER SINGH
ELECTRICAL ENGINEERING

EXPERIENCE
Site Engineer
Acme Ltd.
2010 - 2013
"""
    )

    assert result["full_name"] == "SUKHVINDER SINGH"


def test_visual_cv_leading_name_and_work_background_are_not_misrouted():
    text = """
DAVID PHIAST
APPLICATION DEVELOPER

PERSONAL PROFILE
I build software for data-heavy applications.

SKILLS
Python, Docker

PROJECTS
Property Valuation using Machine Learning.

WORK BACKGROUND
Accenture
Application Development Associate. Jan 2019 to Jan 2020
Created SAP master data and configuration documents for clients.

EDUCATION
B.Tech from Jawaharlal Nehru University in 2019.

OTHER ACTIVITIES
AI on the cloud using Google Cloud Platform.
"""

    result = extract_structured(text)

    assert result["full_name"] == "DAVID PHIAST"
    assert result["title"] == "APPLICATION DEVELOPER"
    assert result["section_titles"]["experience"] == "WORK BACKGROUND"
    assert result["section_titles"]["misc"] == "OTHER ACTIVITIES"
    assert not result["interests"]

    assert result["experiences"][0]["title"] == "Application Development Associate"
    assert result["experiences"][0]["company"] == "Accenture"
    assert result["experiences"][0]["bullets"] == ["Created SAP master data and configuration documents for clients."]
    assert len(result["experiences"]) == 1


def test_sidebar_first_cv_rescues_name_after_contact_column():
    text = """
multi_col_fixed
COMMUNICATION
+90 553 802 66 25
ahmet@example.com
SKILLS
SQL
HTML / CSS
JAVA

Ahmet Bugra Kuscu
COMPUTER ENGINEER
PERSONAL INFORMATION
3rd-year Computer Engineering student focused on web development.
PROJECTS
Farm Game
Used Technologies: Java
EDUCATION
COMPUTER ENGINEER
2022-2027
BACHELOR'S DEGREE
"""

    result = extract_structured(text)

    assert result["full_name"] == "Ahmet Bugra Kuscu"
    assert result["title"] == "COMPUTER ENGINEER"
    assert "HTML" in result["skills"]
    assert "CSS" in result["skills"]
    assert "COMPUTER ENGINEER" not in result["interests"]
