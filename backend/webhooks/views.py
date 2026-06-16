from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import (ListAPIView, ListCreateAPIView,
                                      RetrieveUpdateDestroyAPIView)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import CompanyScopedMixin, IsCompanyAdmin, company_for

from .models import WebhookDelivery, WebhookEndpoint
from .serializers import WebhookDeliverySerializer, WebhookEndpointSerializer

# Every endpoint is company-only (IsCompanyAdmin) and tenant-scoped (CompanyScopedMixin):
# a freelancer/nobody gets 403, and one company never sees another's rows (404, no leak).


class WebhookEndpointListCreateView(CompanyScopedMixin, ListCreateAPIView):
    """GET/POST /api/webhook-endpoints/ — list / create. `perform_create` (mixin) stamps
    the company; the model default generates the signing secret."""

    permission_classes = [IsAuthenticated, IsCompanyAdmin]
    serializer_class = WebhookEndpointSerializer
    queryset = WebhookEndpoint.objects.prefetch_related('deliveries').all()  # for last_delivery
    company_lookup = 'company'


class WebhookEndpointDetailView(CompanyScopedMixin, RetrieveUpdateDestroyAPIView):
    """GET/PATCH/DELETE /api/webhook-endpoints/<id>/ — retrieve / edit (e.g. toggle
    is_active) / delete; another company's endpoint 404s via the scoped queryset."""

    permission_classes = [IsAuthenticated, IsCompanyAdmin]
    serializer_class = WebhookEndpointSerializer
    queryset = WebhookEndpoint.objects.prefetch_related('deliveries').all()  # for last_delivery
    company_lookup = 'company'


class WebhookEndpointTestView(APIView):
    """POST /api/webhook-endpoints/<id>/test/ — send a synthetic invoice.created sample
    through the real delivery path. Returns 202; watch the deliveries log for the result."""

    permission_classes = [IsAuthenticated, IsCompanyAdmin]

    def post(self, request, pk):
        endpoint = get_object_or_404(WebhookEndpoint, pk=pk, company=company_for(request.user))
        delivery = endpoint.send_test_event()
        return Response(WebhookDeliverySerializer(delivery).data, status=status.HTTP_202_ACCEPTED)


class WebhookDeliveryListView(CompanyScopedMixin, ListAPIView):
    """GET /api/webhook-endpoints/<id>/deliveries/ — the delivery log for one endpoint,
    scoped to the caller's company via the endpoint relation."""

    permission_classes = [IsAuthenticated, IsCompanyAdmin]
    serializer_class = WebhookDeliverySerializer
    queryset = WebhookDelivery.objects.all()
    company_lookup = 'endpoint__company'

    def get_queryset(self):
        return super().get_queryset().filter(endpoint_id=self.kwargs['pk'])
