"""Add same-CV-multi-JD and borderline entries to benchmark dataset."""
import json, pathlib

DS = pathlib.Path(__file__).resolve().parent.parent / "tests/benchmark/benchmark_dataset.json"

BASE_CV = (
    "John Smith\nSenior Python Developer\n\n"
    "Contact: john.smith@email.com | +1 555-1234\n\n"
    "Skills:\nPython, JavaScript, SQL, Django, Flask, React, Node.js, "
    "PostgreSQL, MongoDB, Redis, AWS, Docker, Kubernetes, Terraform, Git, Jenkins, Linux\n\n"
    "Experience:\nSenior Python Developer, TechCorp, 2020 - Present\n"
    "- Led microservices architecture serving 1M+ users\n"
    "- Built ML pipelines using Python, TensorFlow, AWS\n"
    "- Mentored 5 junior developers\n"
    "- Reduced deployment time by 60% through CI/CD\n\n"
    "Python Developer, StartupXYZ, 2017 - 2019\n"
    "- Developed REST APIs serving 500K users\n"
    "- Built data visualization dashboards with React and D3.js\n\n"
    "Education:\nMS Computer Science, Stanford, 2015\n"
    "BS Computer Science, UC Berkeley, 2013\n\n"
    "Certifications:\nAWS Certified Solutions Architect (2022)"
)

NEW = [
    {
        "id": "B031", "name": "Same CV - Frontend React JD", "category": "same_cv_diff_jd",
        "cv_text": BASE_CV,
        "job_description": "Senior React Developer needed. 5+ years React, Redux, TypeScript, Next.js, GraphQL, CSS-in-JS, testing (Jest/Cypress). Experience with design systems and accessibility.",
        "expected": {"keyword_score": {"min": 10, "max": 45}, "ats_score": {"min": 55, "max": 85}, "final_score": {"min": 40, "max": 75}},
        "notes": "Python dev CV vs React JD. React mentioned but missing Redux/TS/Next.js/GraphQL."
    },
    {
        "id": "B032", "name": "Same CV - Security Engineer JD", "category": "same_cv_diff_jd",
        "cv_text": BASE_CV,
        "job_description": "Security Engineer needed. Requirements: penetration testing, OWASP, vulnerability assessment, SIEM, IDS/IPS, compliance (SOC2/ISO27001), Python scripting, network security.",
        "expected": {"keyword_score": {"min": 5, "max": 30}, "ats_score": {"min": 55, "max": 85}, "final_score": {"min": 35, "max": 70}},
        "notes": "Python overlap but missing all security-specific skills."
    },
    {
        "id": "B033", "name": "Same CV - Junior Python JD", "category": "same_cv_diff_jd",
        "cv_text": BASE_CV,
        "job_description": "Junior Python Developer. 0-2 years experience. Python basics, Git, willingness to learn. Nice to have: Django, SQL.",
        "expected": {"keyword_score": {"min": 30, "max": 80}, "ats_score": {"min": 55, "max": 90}, "final_score": {"min": 50, "max": 85}},
        "notes": "Senior CV vs Junior JD. Keywords match but overqualified."
    },
    {
        "id": "B034", "name": "Borderline - QA to Dev", "category": "borderline",
        "cv_text": "Sarah Kim\nQA Engineer\n\nContact: sarah.kim@email.com\n\nExperience:\nSenior QA Engineer, TestCo, 2020 - Present\n- Automated test suites using Python and Selenium\n- Built CI/CD pipelines with Jenkins and Docker\n- Wrote API tests with Postman and pytest\n- SQL queries for test data management\n\nSkills:\nPython, Selenium, pytest, Jenkins, Docker, SQL, Git, Jira, Postman, API Testing\n\nEducation:\nBS Computer Science, 2020",
        "job_description": "Python Developer needed. Python, Django, REST APIs, PostgreSQL, Docker, Git required. Testing experience is a plus.",
        "expected": {"keyword_score": {"min": 20, "max": 55}, "ats_score": {"min": 50, "max": 80}, "final_score": {"min": 35, "max": 70}},
        "notes": "QA with Python/Docker/Git overlap but missing Django/REST/PostgreSQL. Classic borderline."
    },
    {
        "id": "B035", "name": "Borderline - Data Analyst to Data Eng", "category": "borderline",
        "cv_text": "Mike Torres\nData Analyst\n\nContact: mike.t@email.com\n\nExperience:\nSenior Data Analyst, AnalyticsCo, 2021 - Present\n- SQL queries and data modeling in BigQuery\n- Python scripts for data cleaning with pandas\n- Built Tableau dashboards for stakeholders\n- Basic ETL pipelines with Python\n\nSkills:\nSQL, Python, pandas, Tableau, BigQuery, Excel, Git, basic Spark\n\nEducation:\nMS Statistics, 2021",
        "job_description": "Data Engineer needed. Python, SQL, Spark, Airflow, dbt, Kafka, AWS (S3/Redshift/Glue). Experience building data pipelines at scale. Docker, Kubernetes.",
        "expected": {"keyword_score": {"min": 10, "max": 45}, "ats_score": {"min": 45, "max": 80}, "final_score": {"min": 30, "max": 65}},
        "notes": "Analyst with Python/SQL overlap but missing Spark/Airflow/dbt/Kafka. Borderline transition."
    },
    {
        "id": "B036", "name": "Borderline - Mobile to Web Dev", "category": "borderline",
        "cv_text": "Chris Park\niOS Developer\n\nContact: chris.p@email.com\n\nExperience:\niOS Developer, AppCo, 2021 - Present\n- Built iOS apps using Swift and SwiftUI\n- REST API integration and JSON parsing\n- Git, CI/CD with Fastlane\n- Unit testing with XCTest\n\nSkills:\nSwift, SwiftUI, Objective-C, Xcode, REST APIs, Git, Firebase, CocoaPods\n\nEducation:\nBS Computer Science, 2021",
        "job_description": "Full Stack Web Developer. React, Node.js, TypeScript, PostgreSQL, Docker, AWS, REST APIs, Git required.",
        "expected": {"keyword_score": {"min": 5, "max": 40}, "ats_score": {"min": 40, "max": 80}, "final_score": {"min": 25, "max": 65}},
        "notes": "iOS dev vs Web dev. REST/Git overlap but entirely different tech stack."
    },
    {
        "id": "B037", "name": "TR+EN Mixed CV", "category": "multilingual",
        "cv_text": "Ahmet Demir\nYazilim Gelistirici / Software Developer\n\nIletisim: ahmet@email.com | Istanbul\n\nDeneyim:\nSoftware Developer, TeknoFirma, 2021 - Present\n- Python ve Django ile REST API gelistirme\n- PostgreSQL veritabani yonetimi\n- Docker containerization\n- Git version control\n\nBeceriler / Skills:\nPython, Django, PostgreSQL, Docker, Git, Linux, REST APIs, JavaScript\n\nEgitim:\nBilgisayar Muhendisligi, ITU, 2021",
        "job_description": "Python Developer needed. Python, Django, PostgreSQL, Docker, REST APIs, Git required.",
        "expected": {"keyword_score": {"min": 40, "max": 85}, "ats_score": {"min": 40, "max": 80}, "final_score": {"min": 40, "max": 80}},
        "notes": "Mixed TR+EN CV. Technical terms in English should match despite Turkish prose."
    },
]

with open(DS, "r", encoding="utf-8") as f:
    data = json.load(f)

data["entries"].extend(NEW)
data["version"] = "2.1.0"

with open(DS, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("Dataset:", len(data["entries"]), "entries")
