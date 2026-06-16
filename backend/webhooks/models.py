"""Outbound webhook models: a company's configured endpoints, and the delivery log.

One logical event fans out to **one `WebhookDelivery` per active endpoint** — each row
is both the immutable record of what that endpoint was sent *and* its own retry state
machine. There is deliberately no separate "event" table: with a single event type and
no shared-across-endpoints identity, it would not pay for itself (the same call as the
billing models).
"""

import secrets
import uuid

from django.db import models
from django.utils import timezone

from accounts.models import Company

# Payload envelope version. Lives in the envelope (and the X-Webhook-Version header) so
# consumers can branch on it; bump on a breaking change to the `data` shape.
WEBHOOK_API_VERSION = 'v1'

# Synthetic `data` block for the "send test event" action — shaped exactly like a real
# invoice.created so a consumer can exercise their handler before a real invoice exists.
SAMPLE_INVOICE_DATA = {
    'invoice_id': 0,
    'period': '2026-01',
    'subtotal': '1234.56',
    'freelancer': {'id': 0, 'name': 'Sample Freelancer'},
    'company_id': 0,
    'line_item_count': 3,
}


def generate_secret():
    """A per-endpoint signing secret (URL-safe, ~43 chars). Used as the HMAC key."""
    return secrets.token_urlsafe(32)


class WebhookEndpoint(models.Model):
    """A destination a company configures to receive events. One row per URL."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='webhook_endpoints')
    url = models.URLField()
    secret = models.CharField(max_length=64, default=generate_secret)   # HMAC signing key
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.url} ({"active" if self.is_active else "disabled"})'

    @property
    def last_delivery(self):
        """Most recent delivery for this endpoint, or None.

        Reads the prefetched `deliveries` cache (Meta ordering is -created_at, so row 0
        is newest), so it stays query-free per row when the view prefetches `deliveries`.
        Deliberately `list(...)[0]` and not `.first()` — `.first()` issues its own
        LIMIT 1 query that bypasses the prefetch cache and reintroduces the N+1.
        """
        deliveries = list(self.deliveries.all())
        return deliveries[0] if deliveries else None

    @property
    def last_delivery_summary(self):
        """Compact at-a-glance summary of the most recent delivery for the list UI, or
        None if this endpoint has never been delivered to. Serialised straight onto the
        API by `WebhookEndpointSerializer`."""
        last = self.last_delivery
        if last is None:
            return None
        return {'status': last.status, 'at': last.last_activity_at.isoformat()}

    def send_test_event(self):
        """Send a synthetic invoice.created sample to *this* endpoint through the real
        delivery path (so the test exercises signing, headers, and the retry task)."""
        return WebhookDelivery.enqueue_for(self, 'invoice.created', SAMPLE_INVOICE_DATA)


class WebhookDelivery(models.Model):
    """One (event × endpoint) delivery: the log row AND its retry state machine.

    `payload` is the exact envelope that was sent (immutable). `event_id` is stable
    across every retry of this row, so the receiver can dedupe on it (delivery is
    at-least-once — a lost 2xx is retried, so a consumer may see an event twice).
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SUCCESS = 'success', 'Success'
        FAILED = 'failed', 'Failed'
        EXHAUSTED = 'exhausted', 'Exhausted'

    endpoint = models.ForeignKey(WebhookEndpoint, on_delete=models.CASCADE, related_name='deliveries')
    event_id = models.UUIDField(default=uuid.uuid4, editable=False)   # receiver-dedupe key
    event_type = models.CharField(max_length=50)
    payload = models.JSONField()                                     # immutable envelope snapshot
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    attempt_count = models.PositiveIntegerField(default=0)
    last_response_code = models.PositiveIntegerField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.event_type} → endpoint {self.endpoint_id} ({self.status})'

    @property
    def last_activity_at(self):
        """When this delivery last did something — its last attempt, or its creation
        time if it has not been attempted yet."""
        return self.last_attempt_at or self.created_at

    @classmethod
    def enqueue_for(cls, endpoint, event_type, data):
        """Create the delivery row for one endpoint and enqueue its async send.

        The envelope embeds this row's own `event_id`, so the id the receiver sees is
        identical on every retry of this delivery.
        """
        # Local import: webhooks.models ↔ webhooks.tasks would otherwise cycle.
        from .tasks import deliver_webhook

        event_id = uuid.uuid4()
        delivery = cls.objects.create(
            endpoint=endpoint,
            event_id=event_id,
            event_type=event_type,
            payload={
                'id': str(event_id),
                'type': event_type,
                'api_version': WEBHOOK_API_VERSION,
                'created_at': timezone.now().isoformat(),
                'data': data,
            },
        )
        deliver_webhook.delay(delivery.id)
        return delivery

    @classmethod
    def fan_out(cls, company, event_type, data):
        """Fan a system event out to all of `company`'s ACTIVE endpoints — one delivery
        each, enqueued for signed async delivery; returns the deliveries created.

        This is the single seam every system event flows through. It is called
        *explicitly* from the code path that makes the change — `BillingRun.generate()`'s
        per-invoice `on_commit` calls `fan_out(invoice.company, 'invoice.created', …)` —
        not from a `post_save` signal (which fires on every save and is bypassed by bulk
        ops). For use by Task A too: bulk-approve would call `fan_out(company,
        'timesheet.approved', …)` the same way.
        """
        return [cls.enqueue_for(endpoint, event_type, data)
                for endpoint in company.webhook_endpoints.filter(is_active=True)]
