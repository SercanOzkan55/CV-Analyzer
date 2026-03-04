from locust import HttpUser, task, between
import os

JWT = os.getenv("LOCUST_JWT", "testtoken")

class AnalyzeUser(HttpUser):
    wait_time = between(1, 2)

    @task
    def analyze(self):
        self.client.post(
            "/api/v1/analyze",
            json={
                "cv_text": "John Doe\nSkills: Python, SQL",
                "job_description": "Software engineer with Python"
            },
            headers={"Authorization": f"Bearer {JWT}"}
        )
