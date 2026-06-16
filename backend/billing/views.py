import logging
from datetime import datetime

from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import CompanyScopedMixin, IsCompanyAdmin, company_for

from .models import BillingRun, Invoice
from .serializers import InvoiceDetailSerializer, InvoiceListSerializer

logger = logging.getLogger(__name__)


def _parse_month(value):
    """'YYYY-MM' → the 1st of that month (a date). Raises ValueError/TypeError on bad input."""
    return datetime.strptime(value, '%Y-%m').date().replace(day=1)


class BillingRunView(APIView):
    """POST /api/billing/runs/ — run billing for the caller's own company,
    synchronously, so the wired UI gets a real `invoices_generated` count back."""

    permission_classes = [IsAuthenticated, IsCompanyAdmin]

    def post(self, request):
        month = request.data.get('month')
        if not month:
            return Response({'month': 'This field is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            period = _parse_month(month)
        except (ValueError, TypeError):
            return Response({'month': 'Expected format YYYY-MM.'}, status=status.HTTP_400_BAD_REQUEST)

        run, count = BillingRun.generate(period, company=company_for(request.user))
        logger.info('Billing run %s triggered by %s for %s', run.id, request.user, month)
        return Response({
            'run_id': run.id,
            'invoices_generated': count,
            'status': run.status,
        })


class InvoiceListView(CompanyScopedMixin, ListAPIView):
    """GET /api/invoices/?month=YYYY-MM — the caller's company invoices for the period."""

    permission_classes = [IsAuthenticated, IsCompanyAdmin]
    serializer_class = InvoiceListSerializer
    queryset = Invoice.objects.select_related('freelancer').all()
    company_lookup = 'company'

    def get_queryset(self):
        qs = super().get_queryset()
        month = self.request.query_params.get('month')
        if month:
            try:
                qs = qs.filter(period=_parse_month(month))
            except (ValueError, TypeError):
                return qs.none()
        return qs.order_by('-created_at')


class InvoiceDetailView(CompanyScopedMixin, RetrieveAPIView):
    """GET /api/invoices/<id>/ — scoped detail; another company's invoice 404s."""

    permission_classes = [IsAuthenticated, IsCompanyAdmin]
    serializer_class = InvoiceDetailSerializer
    queryset = Invoice.objects.select_related('company', 'freelancer').prefetch_related('line_items').all()
    company_lookup = 'company'
