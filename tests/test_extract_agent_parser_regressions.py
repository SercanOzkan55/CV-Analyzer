from agents.extract_agent import extract_structured


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

    assert result["experiences"][0]["title"] == "Accenture"
    assert "Application Development Associate" in result["experiences"][0]["company"]
    assert result["experiences"][0]["bullets"] == [
        "Created SAP master data and configuration documents for clients."
    ]
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
