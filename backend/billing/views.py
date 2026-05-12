from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


# --- Stub endpoints ---
# These exist so the wired billing UI behaves correctly. The real monthly
# billing run is part of Task B.

class BillingRunView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response({
            'run_id': 'stub',
            'invoices_generated': 0,
            'status': 'completed',
        })


class InvoiceListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response([])


class InvoiceDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
