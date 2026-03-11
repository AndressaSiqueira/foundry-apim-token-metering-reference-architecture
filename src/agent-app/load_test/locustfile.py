from __future__ import annotations

import json
import random

from locust import HttpUser, between, task

SAMPLE_MESSAGES = [
    "Explain the concept of token metering in Azure AI Foundry in two sentences.",
    "What is the difference between prompt tokens and completion tokens?",
    "How does APIM enforce token-per-minute limits?",
    "Give me a brief summary of showback vs chargeback for cloud AI services.",
    "What are the benefits of using Managed Identity over API keys?",
]


class AgentAppUser(HttpUser):
    """
    Simulates concurrent tenants sending chat requests to the agent app.

    Run with:
        locust -f load_test/locustfile.py --headless -u 10 -r 2 --run-time 60s \
               --host http://localhost:8000
    """

    wait_time = between(1, 3)

    @task(10)
    def chat_request(self) -> None:
        payload = {
            "messages": [
                {"role": "user", "content": random.choice(SAMPLE_MESSAGES)}
            ]
        }
        with self.client.post(
            "/chat",
            json=payload,
            headers={"Content-Type": "application/json"},
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                data = response.json()
                total_tokens = data.get("usage", {}).get("total_tokens", 0)
                response.success()
            elif response.status_code == 429:
                # Expected under quota; do not count as failure
                response.success()
            else:
                response.failure(f"Unexpected status {response.status_code}: {response.text[:200]}")

    @task(1)
    def health_check(self) -> None:
        with self.client.get("/healthz", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")
