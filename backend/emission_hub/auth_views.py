"""Simple session-based auth API endpoints for the React frontend."""
# pyrefly: ignore [missing-import]
from django.contrib.auth import authenticate, login, logout, get_user_model
# pyrefly: ignore [missing-import]
from rest_framework.decorators import api_view, permission_classes
# pyrefly: ignore [missing-import]
from rest_framework.permissions import AllowAny, IsAuthenticated
# pyrefly: ignore [missing-import]
from rest_framework.response import Response

User = get_user_model()


@api_view(['POST'])
@permission_classes([AllowAny])
def api_login(request):
    username = request.data.get('username', '')
    password = request.data.get('password', '')
    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response({'detail': 'Invalid username or password.'}, status=401)
    login(request, user)
    return Response({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'is_staff': user.is_staff,
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def api_logout(request):
    logout(request)
    return Response({'detail': 'Logged out.'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_me(request):
    u = request.user
    return Response({
        'id': u.id,
        'username': u.username,
        'email': u.email,
        'is_staff': u.is_staff,
    })
