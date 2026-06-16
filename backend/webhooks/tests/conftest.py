"""Webhook-test helpers, layered on the root conftest fixtures (northstar / meridian /
admin_user / admin_client / freelancer_client)."""

import pytest

from webhooks.models import WebhookDelivery, WebhookEndpoint


@pytest.fixture
def make_endpoint(northstar):
    """Factory: a webhook endpoint (active, on `northstar` by default)."""
    def _make(url='http://localhost:8027/hook', is_active=True, company=None):
        return WebhookEndpoint.objects.create(
            company=company or northstar, url=url, is_active=is_active,
        )
    return _make


@pytest.fixture
def delivery(make_endpoint):
    """A pending delivery created directly (bypassing enqueue_for, so no broker call),
    ready to drive `deliver_webhook` through its state machine."""
    return WebhookDelivery.objects.create(
        endpoint=make_endpoint(),
        event_type='invoice.created',
        payload={'id': 'evt', 'type': 'invoice.created', 'api_version': 'v1',
                 'created_at': '2026-06-15T00:00:00+00:00', 'data': {'invoice_id': 1}},
    )
