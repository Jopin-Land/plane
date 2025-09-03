import json, time, uuid, hmac, hashlib, logging, requests
from django.conf import settings

# log = logging.getLogger(__name__)
log = logging.getLogger("plane.api.request")

def _signature(ts: str, body: bytes, secret: str) -> str:
    mac = hmac.new(secret.encode("utf-8"), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={ts},v1={mac}"

def _endpoints():
    raw = getattr(settings, "CUSTOM_USER_CREATED_WEBHOOK_URLS", "")
    return [u.strip() for u in raw.split(",") if u.strip()]

def send_user_created_event(payload: dict) -> None:
    eps = _endpoints()
    if not eps:
        return
    print("-----------------------------------------> send_user_created_event", eps)

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

    print("---------------------> headers:", headers)
    print("---------------------> body:", body)

    for url in eps:
        print("-----------------> url",url)
        try:
            r = requests.post(url, data=body, headers=headers, timeout=timeout)
            log.info(
                "webhook.post.done",
                extra={
                    "stage": "webhook.post.done",
                    "url": url,
                    "status": r.status_code,
                    "resp_len": len(r.content or b""),
                },
            )
            if not (200 <= r.status_code < 300):
                log.warning("user.created webhook %s -> %s %s", url, r.status_code, r.text[:300])
        except Exception:
            log.exception("user.created webhook error to %s", url)
