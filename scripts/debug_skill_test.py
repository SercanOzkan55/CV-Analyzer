from services.skill_service import skill_coverage_score, extract_skills

cv_text = "John Doe\nSkills: Python, React, Docker, AWS\n"
job_text = "Senior Python Developer with React and Docker experience"

print('CV skills:', extract_skills(cv_text))
print('JD skills:', extract_skills(job_text))
print('Coverage:', skill_coverage_score(cv_text, job_text))
