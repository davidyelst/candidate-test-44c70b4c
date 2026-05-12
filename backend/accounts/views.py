from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.views import APIView

from .models import Freelancer
from .serializers import FreelancerSerializer, UserSerializer


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    email = request.data.get('email', '')
    password = request.data.get('password', '')
    user = authenticate(request, username=email, password=password)
    if not user:
        return Response({'detail': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)
    token, _ = Token.objects.get_or_create(user=user)
    return Response({'token': token.key, 'user': UserSerializer(user).data})


class FreelancerListView(APIView):
    """Lists freelancers so the manual contract form can populate its dropdown."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not hasattr(request.user, 'company_admin'):
            return Response(
                {'detail': 'Only company admins can list freelancers.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        qs = Freelancer.objects.order_by('name')
        return Response(FreelancerSerializer(qs, many=True).data)
