"""Focused tests for Task C's graded core: how delivery *fails*.

The brief grades Task C on reasoning about failure, so the coverage concentrates on the
signing contract, the retry state machine (success / transient failure / give-up), and
the fan-out + idempotency key. Broader coverage (endpoint CRUD + the perms matrix, a live
HTTP round-trip) is scoped out for the time-box and noted in CANDIDATE_NOTES.md.

`deliver_webhook` is unit-tested by calling it directly with `requests.post` and
`self.retry` mocked — so we assert the state transitions and that a retry is *scheduled*,
without a broker and without relying on CELERY_TASK_ALWAYS_EAGER.
"""

import hashlib
import hmac
from unittest.mock import Mock, patch

import pytest
import requests
from celery.exceptions import MaxRetriesExceededError, Retry

from webhooks.models import WebhookDelivery
from webhooks.signing import canonical_json, hmac_sha256
from webhooks.tasks import deliver_webhook

# --- Signing: a deterministic body + an HMAC the consumer can recompute ---


def test_canonical_json_is_key_order_independent():
    assert canonical_json({'b': 1, 'a': 2}) == canonical_json({'a': 2, 'b': 1}) == b'{"a":2,"b":1}'


def test_signature_matches_an_independently_computed_hmac():
    secret = 'topsecret'
    message = canonical_json({'hello': 'world'})
    expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    assert hmac_sha256(secret, message) == expected


# --- Retry state machine: pending → success | failed → exhausted ---


@pytest.mark.django_db
@patch('webhooks.tasks.requests.post')
def test_2xx_marks_success_signs_the_request_and_does_not_retry(mock_post, delivery):
    mock_post.return_value = Mock(status_code=200)

    with patch.object(deliver_webhook, 'retry') as mock_retry:
        deliver_webhook.run(delivery.id)

    delivery.refresh_from_db()
    assert delivery.status == WebhookDelivery.Status.SUCCESS
    assert delivery.last_response_code == 200
    assert delivery.attempt_count == 1
    mock_retry.assert_not_called()
    # the real delivery path signs and stamps the idempotency key
    headers = mock_post.call_args.kwargs['headers']
    assert headers['X-Webhook-Id'] == str(delivery.event_id)
    assert headers['X-Webhook-Version'] == 'v1'
    assert headers['X-Webhook-Signature']


@pytest.mark.django_db
@patch('webhooks.tasks.requests.post')
def test_non_2xx_marks_failed_and_schedules_a_backed_off_retry(mock_post, delivery):
    mock_post.return_value = Mock(status_code=503)

    with patch.object(deliver_webhook, 'retry', side_effect=Retry()) as mock_retry:
        with pytest.raises(Retry):
            deliver_webhook.run(delivery.id)

    delivery.refresh_from_db()
    assert delivery.status == WebhookDelivery.Status.FAILED
    assert delivery.last_response_code == 503
    assert delivery.last_error == 'HTTP 503'
    assert mock_retry.call_args.kwargs['countdown'] == 10   # first backoff = 10 * 2**0


@pytest.mark.django_db
@patch('webhooks.tasks.requests.post', side_effect=requests.RequestException('connection refused'))
def test_network_error_marks_failed_and_retries(mock_post, delivery):
    with patch.object(deliver_webhook, 'retry', side_effect=Retry()) as mock_retry:
        with pytest.raises(Retry):
            deliver_webhook.run(delivery.id)

    delivery.refresh_from_db()
    assert delivery.status == WebhookDelivery.Status.FAILED
    assert delivery.last_response_code is None
    assert 'connection refused' in delivery.last_error
    mock_retry.assert_called_once()


@pytest.mark.django_db
@patch('webhooks.tasks.requests.post')
def test_retry_cap_marks_exhausted(mock_post, delivery):
    mock_post.return_value = Mock(status_code=500)

    # When Celery has no retries left, self.retry() raises MaxRetriesExceededError —
    # the task catches it and lands the row in the terminal `exhausted` state.
    with patch.object(deliver_webhook, 'retry', side_effect=MaxRetriesExceededError()):
        deliver_webhook.run(delivery.id)

    delivery.refresh_from_db()
    assert delivery.status == WebhookDelivery.Status.EXHAUSTED


# --- Fan-out: one event → one delivery per ACTIVE endpoint, each with a stable event_id ---


@pytest.mark.django_db
@patch('webhooks.tasks.deliver_webhook.delay')
def test_fan_out_enqueues_only_active_endpoints_with_a_stable_event_id(mock_delay, northstar, make_endpoint):
    active_a = make_endpoint(url='http://localhost:8027/a')
    active_b = make_endpoint(url='http://localhost:8027/b')
    make_endpoint(url='http://localhost:8027/c', is_active=False)

    deliveries = WebhookDelivery.fan_out(northstar, 'invoice.created', {'invoice_id': 1})

    assert {d.endpoint_id for d in deliveries} == {active_a.id, active_b.id}   # inactive excluded
    assert mock_delay.call_count == 2
    for d in deliveries:
        assert d.status == WebhookDelivery.Status.PENDING
        assert d.payload['id'] == str(d.event_id)        # the id the receiver dedupes on
        assert d.payload['type'] == 'invoice.created'
        assert d.payload['api_version'] == 'v1'
