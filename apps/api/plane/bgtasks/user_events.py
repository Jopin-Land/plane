from celery import shared_task
from django.conf import settings
import json, time, uuid, hmac, hashlib, requests

def _signature(ts: str, body: bytes, secret: str) -> str:
    return f"t={ts},v1=" + hmac.new(secret.encode("utf-8"), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()

def _endpoints():
    raw = getattr(settings, "CUSTOM_USER_CREATED_WEBHOOK_URLS", "")
    return [u.strip() for u in raw.split(",") if u.strip()]

@shared_task(bind=True, max_retries=5, default_retry_delay=10)
def deliver_user_created_webhook(self, payload: dict):
    eps = _endpoints()
    if not eps:
        return

    secret  = getattr(settings, "CUSTOM_USER_WEBHOOK_SECRET", "")
    timeout = getattr(settings, "CUSTOM_USER_WEBHOOK_TIMEOUT", 4)

    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ts   = str(int(time.time()))
    sig  = _signature(ts, body, secret)
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "AppAuthHooks/1.0",
        "X-Event": payload.get("event", "user.created"),
        "X-Webhook-Timestamp": ts,
        "X-Webhook-Signature": sig,
        "X-Idempotency-Key": str(uuid.uuid4()),
    }

    for url in eps:
        try:
            r = requests.post(url, data=body, headers=headers, timeout=timeout)
            if not (200 <= r.status_code < 300):
                raise RuntimeError(f"{url} -> {r.status_code} {r.text[:300]}")
        except Exception as e:
            raise self.retry(exc=e, countdown=min(60, (self.request.retries + 1) * 15))
