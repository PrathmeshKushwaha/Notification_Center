from locust import HttpUser, task, between
import random
import uuid


class NotificationUser(HttpUser):
    wait_time = between(0.5, 2)
    template_id = "743ca962-82be-4c04-91b1-afc9e0ad6eb7"

    def on_start(self):
        self.user_id = f"loadtest-user-{uuid.uuid4().hex[:8]}"
        self.client.put(
            f"/preferences/{self.user_id}",
            json={
                "email_enabled": True,
                "websocket_enabled": True,
                "webhook_enabled": False,
                "timezone": "Asia/Kolkata"
            }
        )

    @task(5)
    def send_email_notification(self):
        self.client.post("/notify", json={
            "user_id": self.user_id,
            "channel": "email",
            "priority": random.choice(["normal", "high"]),
            "template_id": self.template_id,
            "variables": {"name": "LoadTest"},
            "idempotency_key": f"load-{uuid.uuid4().hex}"
        })

    @task(3)
    def send_websocket_notification(self):
        self.client.post("/notify", json={
            "user_id": self.user_id,
            "channel": "websocket",
            "priority": "normal",
            "variables": {"message": "load test"},
            "idempotency_key": f"load-{uuid.uuid4().hex}"
        })

    @task(1)
    def check_history(self):
        self.client.get(f"/notify/history?user_id={self.user_id}")

    @task(1)
    def check_health(self):
        self.client.get("/health")