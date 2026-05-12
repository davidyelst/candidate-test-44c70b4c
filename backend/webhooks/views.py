from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


# --- Stub endpoints ---
# These exist so the wired developer-settings UI behaves correctly. Real
# endpoint configuration and webhook delivery are part of Task C.

class WebhookEndpointListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response([])

    def post(self, request):
        url = request.data.get('url', '')
        return Response({'id': 'stub', 'url': url, 'active': True}, status=status.HTTP_200_OK)


class WebhookEndpointDestroyView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        return Response(status=status.HTTP_204_NO_CONTENT)
