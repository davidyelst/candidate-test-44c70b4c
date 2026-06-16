from rest_framework import serializers

from accounts.serializers import CompanySerializer, FreelancerSerializer
from .models import Invoice, InvoiceLineItem


class InvoiceLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLineItem
        fields = ['id', 'date', 'hours', 'rate', 'amount']


class InvoiceListSerializer(serializers.ModelSerializer):
    """The Billing page list — only `id` is read by the wired UI; the rest make
    the list useful on its own."""

    freelancer = FreelancerSerializer(read_only=True)

    class Meta:
        model = Invoice
        fields = ['id', 'period', 'freelancer', 'subtotal', 'email_status', 'created_at']


class InvoiceDetailSerializer(serializers.ModelSerializer):
    """Invoice detail — line items + totals. `InvoiceDetail.tsx` renders this as
    raw JSON, so a clean shape displays as-is."""

    company = CompanySerializer(read_only=True)
    freelancer = FreelancerSerializer(read_only=True)
    line_items = InvoiceLineItemSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = ['id', 'company', 'freelancer', 'period', 'subtotal', 'email_status',
                  'created_at', 'line_items']
