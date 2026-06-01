from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )

    class Meta:
        model = User
        fields = ("id", "email", "full_name", "password")

    def create(self, validated_data):
        return User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            full_name=validated_data.get("full_name", ""),
        )


class UserSerializer(serializers.ModelSerializer):
    """Datos públicos del propio usuario (endpoint /me)."""

    class Meta:
        model = User
        fields = ("id", "email", "full_name", "date_joined")
        read_only_fields = fields


class PasswordResetRequestSerializer(serializers.Serializer):
    """Solicitud de restablecimiento: solo valida el formato del correo.

    La vista responde igual exista o no la cuenta (anti-enumeración), así que
    aquí no comprobamos si el usuario existe.
    """

    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Confirma el restablecimiento con uid + token + nueva contraseña.

    El uid identifica al usuario (base64) y el token lo emite
    ``default_token_generator``: va firmado, caduca con PASSWORD_RESET_TIMEOUT
    y queda invalidado en cuanto cambia la contraseña (porque depende del hash
    actual). Así un enlace no se puede reutilizar.
    """

    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(
        write_only=True, validators=[validate_password]
    )

    # Mensaje único para uid o token malos: no distingue entre "no existe" y
    # "token vencido", para no dar pistas a un atacante.
    _invalid_msg = "El enlace de restablecimiento es inválido o ya caducó."

    def validate(self, attrs):
        try:
            uid = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError({"uid": self._invalid_msg})

        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"token": self._invalid_msg})

        attrs["user"] = user
        return attrs

    def save(self, **kwargs):
        user = self.validated_data["user"]
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user
