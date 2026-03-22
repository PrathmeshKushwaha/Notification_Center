from locust import HttpUser, task, between

class NotificationUser(HttpUser):
    wait_time = between(0.5, 2)

    @task(3)
    def send_email_notification(self):
        self.client.post("/notify", json={
            "user_id": f"user-{self.user_id}",
            "channel": "email",
            "template_id": "tmpl-001",
            "variables": {"name": "Load Test User"},
            "idempotency_key": f"load-{self.user_id}-{self.environment.runner.user_count}"
        })

    @task(1)
    def check_status(self):
        self.client.get("/notify/history")