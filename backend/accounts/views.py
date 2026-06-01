from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .emails import send_password_reset_email
from .serializers import (
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    UserSerializer,
)

User = get_user_model()


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


class PasswordResetRequestView(APIView):
    """Solicita un enlace de restablecimiento de contraseña.

    Responde 200 SIEMPRE, exista o no la cuenta, para no revelar qué correos
    están registrados (anti-enumeración). Si existe, genera un enlace firmado
    y lo envía por correo. El scope 'password_reset' frena el abuso.
    """

    permission_classes = [permissions.AllowAny]
    throttle_scope = "password_reset"
    throttle_classes = [ScopedRateThrottle]

    _ok_message = (
        "Si existe una cuenta con ese correo, te enviamos un enlace para "
        "restablecer tu contraseña."
    )

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        # No filtramos si existe o no: buscamos y, si está, enviamos.
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user is not None:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            base = settings.FRONTEND_URL.rstrip("/")
            reset_url = f"{base}/restablecer/?uid={uid}&token={token}"
            send_password_reset_email(user, reset_url)

        return Response({"detail": self._ok_message}, status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    """Confirma el restablecimiento: fija la nueva contraseña.

    Valida uid + token (firmado y con caducidad) y aplica la nueva contraseña
    pasando por los validadores del proyecto. Mismo scope de throttling que la
    solicitud para frenar fuerza bruta sobre tokens.
    """

    permission_classes = [permissions.AllowAny]
    throttle_scope = "password_reset"
    throttle_classes = [ScopedRateThrottle]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"detail": "Tu contraseña se actualizó. Ya puedes iniciar sesión."},
            status=status.HTTP_200_OK,
        )
