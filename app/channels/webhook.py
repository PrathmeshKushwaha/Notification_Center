import hmac
import hashlib
import json
import logging
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


def sign_payload(payload: dict) -> str:
    body = json.dumps(payload, separators=(",", ":"))
    return hmac.new(
        settings.secret_key.encode(),
        body.encode(),
        hashlib.sha256
    ).hexdigest()


async def send_webhook(url: str, payload: dict) -> bool:
    signature = sign_payload(payload)
    headers = {
        "Content-Type": "application/json",
        "X-PulseNotify-Signature": signature,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            logger.info(f"Webhook delivered to {url}: {response.status_code}")
            return True
        except httpx.HTTPStatusError as e:
            logger.error(f"Webhook failed {url}: {e.response.status_code}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Webhook request error {url}: {e}")
            raise