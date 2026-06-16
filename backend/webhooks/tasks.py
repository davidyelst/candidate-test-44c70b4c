"""Async webhook delivery.

`deliver_webhook` IS the delivery state machine — Celery drives the retries, but it
never reads the `WebhookDelivery` row to decide anything. Whether we go again is decided
purely by `self.retry()` vs `return`; the attempt counter rides in the task message, not
a table. The row is *our* log of what happened.

    pending → success (2xx, stop)
            → failed  (attempt failed, retry scheduled) → exhausted (retry cap hit)
"""

import logging

import requests
from celery import shared_task
from django.utils import timezone

from .models import WEBHOOK_API_VERSION, WebhookDelivery
from .signing import canonical_json, hmac_sha256

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10   # seconds — a slow destination must not pin a worker
MAX_BACKOFF = 600      # ceiling on a single backoff (10 min); not reached at max_retries=5


@shared_task(bind=True, max_retries=5)
def deliver_webhook(self, delivery_id):
    """POST one delivery's signed envelope, record the outcome, and drive retries.

    `max_retries=5` → 1 initial attempt + 5 retries = 6 attempts. Success short-circuits
    at any attempt; the cap is only a ceiling on the failure path, never a target.
    """
    delivery = WebhookDelivery.objects.select_related('endpoint').get(pk=delivery_id)
    endpoint = delivery.endpoint

    body = canonical_json(delivery.payload)                 # the exact bytes we sign + send
    signature = hmac_sha256(endpoint.secret, body)          # HMAC of the body, keyed by the endpoint secret
    headers = {
        'Content-Type': 'application/json',
        'X-Webhook-Id': str(delivery.event_id),             # stable across retries → receiver dedupes
        'X-Webhook-Signature': signature,
        'X-Webhook-Version': delivery.payload.get('api_version', WEBHOOK_API_VERSION),
    }

    delivery.attempt_count = self.request.retries + 1
    delivery.last_attempt_at = timezone.now()

    try:
        resp = requests.post(endpoint.url, data=body, headers=headers, timeout=REQUEST_TIMEOUT)
        delivery.last_response_code = resp.status_code
        if 200 <= resp.status_code < 300:                   # 2xx only — a 3xx is not "received"
            delivery.status = WebhookDelivery.Status.SUCCESS
            delivery.last_error = ''
            delivery.save(update_fields=['status', 'attempt_count', 'last_response_code',
                                         'last_error', 'last_attempt_at'])
            logger.info('Webhook delivery %s succeeded (HTTP %s)', delivery.id, resp.status_code)
            return
        delivery.last_error = f'HTTP {resp.status_code}'
    except requests.RequestException as exc:                # timeout / connection refused / DNS
        delivery.last_response_code = None
        delivery.last_error = str(exc)

    delivery.status = WebhookDelivery.Status.FAILED
    delivery.save(update_fields=['status', 'attempt_count', 'last_response_code',
                                 'last_error', 'last_attempt_at'])
    logger.warning('Webhook delivery %s failed (attempt %s): %s',
                   delivery.id, delivery.attempt_count, delivery.last_error)

    try:
        # Exponential backoff between attempts: 10s, 20s, 40s, 80s, 160s.
        raise self.retry(countdown=min(10 * 2 ** self.request.retries, MAX_BACKOFF))
    except self.MaxRetriesExceededError:
        delivery.status = WebhookDelivery.Status.EXHAUSTED
        delivery.save(update_fields=['status'])
        logger.error('Webhook delivery %s exhausted after %s attempts',
                     delivery.id, delivery.attempt_count)
