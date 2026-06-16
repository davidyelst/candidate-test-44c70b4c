from rest_framework import serializers

from .models import WebhookDelivery, WebhookEndpoint


class WebhookEndpointSerializer(serializers.ModelSerializer):
    """Endpoint config. `company` is stamped server-side (CompanyScopedMixin), and the
    `secret` is generated server-side and read-only — the client never sets either.
    `last_delivery` is a small at-a-glance summary for the list UI."""

    last_delivery = serializers.ReadOnlyField(source='last_delivery_summary')

    class Meta:
        model = WebhookEndpoint
        fields = ['id', 'url', 'description', 'is_active', 'secret', 'created_at', 'last_delivery']
        read_only_fields = ['id', 'secret', 'created_at']


class WebhookDeliverySerializer(serializers.ModelSerializer):
    """A row of the delivery log — read-only; the worker is the only writer."""

    class Meta:
        model = WebhookDelivery
        fields = ['id', 'event_id', 'event_type', 'status', 'attempt_count',
                  'last_response_code', 'last_error', 'last_attempt_at', 'created_at']
