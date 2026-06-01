"""Tests del flujo de recuperación de contraseña.

Cubre la solicitud (anti-enumeración) y la confirmación con token firmado.
Usa el backend de correo en memoria para inspeccionar lo que se envía.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()

# Correo en memoria + URL de front fija para inspeccionar el enlace generado.
# Nota: las rates de throttling NO se pueden cambiar con override_settings
# (SimpleRateThrottle.THROTTLE_RATES se fija al importar la clase). Por eso cada
# test limpia la caché en setUp para resetear el historial de peticiones; así
# las rates reales (5/min) no se agotan entre tests.
TEST_SETTINGS = {
    "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
    "FRONTEND_URL": "http://testserver",
}


@override_settings(**TEST_SETTINGS)
class PasswordResetRequestTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.url = "/api/auth/password/reset/"
        self.user = User.objects.create_user(
            email="ana@example.com", password="ClaveVieja123", full_name="Ana"
        )

    def test_email_existente_envia_correo_y_responde_200(self):
        resp = self.client.post(self.url, {"email": "ana@example.com"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("ana@example.com", mail.outbox[0].to)
        # El correo lleva el enlace con uid y token.
        self.assertIn("uid=", mail.outbox[0].body)
        self.assertIn("token=", mail.outbox[0].body)

    def test_email_inexistente_responde_200_sin_enviar(self):
        # Anti-enumeración: misma respuesta, pero no se manda correo.
        resp = self.client.post(self.url, {"email": "nadie@example.com"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 0)

    def test_email_existente_e_inexistente_dan_misma_respuesta(self):
        r1 = self.client.post(self.url, {"email": "ana@example.com"})
        r2 = self.client.post(self.url, {"email": "nadie@example.com"})
        self.assertEqual(r1.data, r2.data)

    def test_email_invalido_es_rechazado(self):
        resp = self.client.post(self.url, {"email": "no-es-correo"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


@override_settings(**TEST_SETTINGS)
class PasswordResetConfirmTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.url = "/api/auth/password/reset/confirm/"
        self.login_url = "/api/auth/login/"
        self.user = User.objects.create_user(
            email="ana@example.com", password="ClaveVieja123", full_name="Ana"
        )
        self.uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        self.token = default_token_generator.make_token(self.user)

    def test_token_valido_cambia_contrasena_y_permite_login(self):
        resp = self.client.post(
            self.url,
            {
                "uid": self.uid,
                "token": self.token,
                "new_password": "ClaveNueva456",
            },
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("ClaveNueva456"))

        # La nueva contraseña permite iniciar sesión.
        login = self.client.post(
            self.login_url,
            {"email": "ana@example.com", "password": "ClaveNueva456"},
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.assertIn("access", login.data)

    def test_token_invalido_es_rechazado(self):
        resp = self.client.post(
            self.url,
            {
                "uid": self.uid,
                "token": "token-falso-123",
                "new_password": "ClaveNueva456",
            },
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("ClaveVieja123"))

    def test_uid_invalido_es_rechazado(self):
        resp = self.client.post(
            self.url,
            {
                "uid": "uid-basura",
                "token": self.token,
                "new_password": "ClaveNueva456",
            },
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_token_no_se_puede_reutilizar(self):
        # Primer uso: cambia la contraseña.
        first = self.client.post(
            self.url,
            {
                "uid": self.uid,
                "token": self.token,
                "new_password": "ClaveNueva456",
            },
        )
        self.assertEqual(first.status_code, status.HTTP_200_OK)

        # Segundo uso del mismo token: ya no sirve (el hash cambió).
        second = self.client.post(
            self.url,
            {
                "uid": self.uid,
                "token": self.token,
                "new_password": "OtraClave789",
            },
        )
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("ClaveNueva456"))

    def test_contrasena_debil_es_rechazada(self):
        resp = self.client.post(
            self.url,
            {"uid": self.uid, "token": self.token, "new_password": "123"},
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
