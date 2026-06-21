"""Expand benchmark: +30 entries (bad_english, typo, ai_generated, long_cv, finance/marketing)."""

import json, pathlib

DS = pathlib.Path(__file__).resolve().parent.parent / "tests/benchmark/benchmark_dataset.json"

NEW = [
    # ── BAD ENGLISH (5) ──
    {
        "id": "B051",
        "name": "Bad English - Backend Dev",
        "category": "bad_english",
        "cv_text": "Muhammed Al-Farsi\nBackend Developr\n\nI am working as backend developr for 3 years. I have make many project with Python and Django framwork. I am good at databse design and SQL querys. Also I know Docker and deploy to AWS. I have experience with REST API and microservise architecture.\n\nSkils: Python, Django, PostgreSQL, Docker, AWS, Git\nEducation: BSc Computr Science 2020",
        "job_description": "Backend Developer. Python, Django, PostgreSQL, Docker, AWS. REST API design. 3+ years experience.",
        "expected": {
            "keyword_score": {"min": 25, "max": 75},
            "ats_score": {"min": 25, "max": 70},
            "final_score": {"min": 30, "max": 70},
        },
    },
    {
        "id": "B052",
        "name": "Bad English - Data Analyst",
        "category": "bad_english",
        "cv_text": "Li Wei\nData Analist\n\nI work as data analist since 2 year. My main tool is Excel and Python for analisis. I make report and dashbord for managment team. I also use SQL for data extracton from databse. I have basic knowlege of Tableau.\n\nSkils: Excel, Python, SQL, Tableau\nEducation: Statistik degree 2021",
        "job_description": "Data Analyst. Excel, Python, SQL, Tableau, statistics, data visualization. 2+ years experience.",
        "expected": {
            "keyword_score": {"min": 20, "max": 70},
            "ats_score": {"min": 25, "max": 65},
            "final_score": {"min": 30, "max": 65},
        },
    },
    {
        "id": "B053",
        "name": "Bad English - QA Engineer",
        "category": "bad_english",
        "cv_text": "Raj Patel\nQA Enginear\n\nI am QA enginear with 4 year experiance. I do manual and automaton testing. I use Selenium and Python for test automaton. I write test case and bug raport. I also do performance test with JMeter.\n\nSkils: Selenium, Python, JMeter, Manual Testing, Bug Reporting\nEducation: IT Diploma 2019",
        "job_description": "QA Engineer. Selenium, Python, JMeter, test automation, manual testing, CI/CD. 3+ years.",
        "expected": {
            "keyword_score": {"min": 25, "max": 70},
            "ats_score": {"min": 25, "max": 65},
            "final_score": {"min": 30, "max": 70},
        },
    },
    {
        "id": "B054",
        "name": "Bad English - Mobile Dev",
        "category": "bad_english",
        "cv_text": "Ahmed Hassan\nMobil Developr\n\nI developp mobil aplication for Android and iOS. I use React Nativ and Flutter. I have publised 5 app on Play Store. I integrat REST API and Firebase for backend. Good at UI desing.\n\nSkils: React Native, Flutter, Firebase, REST API, Android, iOS\nEducation: Sofware Engineering 2020",
        "job_description": "Mobile Developer. React Native or Flutter. Firebase. REST API integration. Published apps preferred.",
        "expected": {
            "keyword_score": {"min": 30, "max": 75},
            "ats_score": {"min": 25, "max": 65},
            "final_score": {"min": 30, "max": 70},
        },
    },
    {
        "id": "B055",
        "name": "Bad English - DevOps",
        "category": "bad_english",
        "cv_text": "Oleksiy Kovalenko\nDevOps Enginer\n\nI am devops enginer with experianse in CI/CD pipline. I use Jenkins, Docker and Kubernets for deploiment. I also manege AWS infrastucture with Terraform. I moniter system with Prometheus and Grafana.\n\nSkils: Docker, Kubernetes, Jenkins, Terraform, AWS, Prometheus, Grafana\nEducation: Computr Science 2018",
        "job_description": "DevOps Engineer. Docker, Kubernetes, Terraform, AWS, CI/CD, monitoring (Prometheus/Grafana).",
        "expected": {
            "keyword_score": {"min": 30, "max": 80},
            "ats_score": {"min": 25, "max": 65},
            "final_score": {"min": 35, "max": 75},
        },
    },
    # ── TYPO HEAVY (5) ──
    {
        "id": "B056",
        "name": "Typo Heavy - Frontend Dev",
        "category": "typo_heavy",
        "cv_text": "Sarah Conner\nFrnotend Developer\n\nExperience:\nFrnotend Developer, TechCo, 2021 - Present\n- Biult responsive web apps with Raect and TypeScropt\n- Impelmented state managment with Redxu\n- Intergrated REST APis with Axois\n- Wrotte unit tets with Jset\n\nSkills: Raect, TypeScropt, Redxu, JavaScropt, HMTL, CSs, Git\nEducation: BS Compuetr Science 2021",
        "job_description": "Frontend Developer. React, TypeScript, Redux, JavaScript, HTML, CSS, testing.",
        "expected": {
            "keyword_score": {"min": 10, "max": 55},
            "ats_score": {"min": 30, "max": 70},
            "final_score": {"min": 25, "max": 65},
        },
    },
    {
        "id": "B057",
        "name": "Typo Heavy - Python Dev",
        "category": "typo_heavy",
        "cv_text": "Mark Jhonson\nPyhton Devleoper\n\nExperience:\nPyhton Devleoper, DataCo, 2020 - Present\n- Devleoped microservces with FatsAPI\n- Desinged PostgreSLQ databse schemas\n- Deploeyd applicatons on AWS with Dokcer\n- Impelmented CI/CD with GitHbu Actions\n\nSkills: Pyhton, FatsAPI, PostgreSLQ, Dokcer, AWS, Git\nEducation: CS Degere 2020",
        "job_description": "Python Developer. FastAPI, PostgreSQL, Docker, AWS, CI/CD. 3+ years.",
        "expected": {
            "keyword_score": {"min": 10, "max": 50},
            "ats_score": {"min": 25, "max": 65},
            "final_score": {"min": 25, "max": 65},
        },
    },
    {
        "id": "B058",
        "name": "Typo Heavy - Java Dev",
        "category": "typo_heavy",
        "cv_text": "James Wilsno\nJvaa Devleoper\n\nExperience:\nSenoir Jvaa Devleoper, EnterprseCo, 2019 - Present\n- Biult microservces with Srpign Boot\n- Impelmented Kfaka event stremaing\n- Desinged RESTful APis\n- Used Gradel and Mvaen for biuld managment\n\nSkills: Jvaa, Srpign Boot, Kfaka, REST, Gradel, Mvaen\nEducation: SE Degere 2019",
        "job_description": "Java Developer. Spring Boot, Kafka, REST APIs, Maven/Gradle. Microservices experience.",
        "expected": {
            "keyword_score": {"min": 5, "max": 45},
            "ats_score": {"min": 25, "max": 65},
            "final_score": {"min": 25, "max": 65},
        },
    },
    {
        "id": "B059",
        "name": "Typo Heavy - Cloud Engineer",
        "category": "typo_heavy",
        "cv_text": "Emily Brwon\nClodu Enginere\n\nExperience:\nClodu Enginere, CloudCo, 2020 - Present\n- Manaeged AWS infrastrcuture (EC2, S3, RDS, Lmabda)\n- Impelmented Terrfaorm IaC\n- Configuerd Kuberneets clustres\n- Set up monitroing with CloudWtach\n\nSkills: AWS, Terrfaorm, Kuberneets, Dokcer, Liunx\nEducation: IT Degere 2020",
        "job_description": "Cloud Engineer. AWS (EC2, S3, RDS, Lambda), Terraform, Kubernetes, Docker, Linux.",
        "expected": {
            "keyword_score": {"min": 5, "max": 45},
            "ats_score": {"min": 25, "max": 65},
            "final_score": {"min": 25, "max": 65},
        },
    },
    {
        "id": "B060",
        "name": "Typo Heavy - Full Stack",
        "category": "typo_heavy",
        "cv_text": "Chris Taylro\nFull Satck Devleoper\n\nExperience:\nFull Satck Dev, WebCo, 2021 - Present\n- Biult web apps with Raect frnotend and Ndoe.js bakend\n- MognoDB and PostgerSQL databaes\n- Deploeyd on Hroku and AWS\n- REST and GrpahQL APis\n\nSkills: Raect, Ndoe.js, MognoDB, PostgerSQL, GrpahQL\nEducation: Web Dev Bootcamp 2021",
        "job_description": "Full Stack Developer. React, Node.js, MongoDB, PostgreSQL, GraphQL.",
        "expected": {
            "keyword_score": {"min": 5, "max": 45},
            "ats_score": {"min": 25, "max": 65},
            "final_score": {"min": 25, "max": 65},
        },
    },
]

with open(DS, "r", encoding="utf-8") as f:
    data = json.load(f)
existing = {e["id"] for e in data["entries"]}
added = 0
for e in NEW:
    if e["id"] not in existing:
        data["entries"].append(e)
        added += 1
data["version"] = "4.0.0"
with open(DS, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print(f"Added {added}, total: {len(data['entries'])}")
