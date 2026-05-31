from rest_framework import generics, permissions
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import RegisterSerializer, UserSerializer


class LoginView(TokenObtainPairView):
    """Obtención de tokens JWT con rate limiting anti fuerza bruta.

    El scope 'login' limita los intentos por IP (ver DEFAULT_THROTTLE_RATES).
    Frena ataques de credential stuffing sin afectar el uso normal.
    """

    throttle_scope = "login"
    throttle_classes = [ScopedRateThrottle]


class RegisterView(generics.CreateAPIView):
    """Registro público de usuarios, con rate limiting anti abuso.

    El scope 'register' limita cuántas cuentas puede crear una misma IP por
    minuto, frenando registros masivos automatizados.
    """

    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = "register"
    throttle_classes = [ScopedRateThrottle]


class MeView(generics.RetrieveAPIView):
    """Datos del usuario autenticado."""

    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user
