"""Tests del comando send_test_email y de la config de correo.

Usa el backend en memoria para verificar el envío sin SMTP real.
"""
from io import StringIO

from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="GameStore <no-reply@gamestore.local>",
)
class SendTestEmailCommandTests(SimpleTestCase):
    def test_envia_correo_al_destino(self):
        out = StringIO()
        call_command("send_test_email", "--to", "destino@example.com", stdout=out)

        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertIn("destino@example.com", msg.to)
        self.assertIn("prueba", msg.subject.lower())
        # Lleva alternativa HTML.
        self.assertTrue(msg.alternatives)
        # No imprime la contraseña en el resumen.
        salida = out.getvalue()
        self.assertIn("EMAIL_BACKEND", salida)
        self.assertIn("enviado", salida.lower())

    def test_requiere_argumento_to(self):
        with self.assertRaises(CommandError):
            call_command("send_test_email")


class EmailSettingsExclusividadTests(SimpleTestCase):
    """TLS y SSL no pueden estar activos a la vez (Django lo prohíbe)."""

    def test_tls_y_ssl_no_son_ambos_true(self):
        from django.conf import settings

        self.assertFalse(
            settings.EMAIL_USE_TLS and settings.EMAIL_USE_SSL,
            "EMAIL_USE_TLS y EMAIL_USE_SSL no pueden ser True simultáneamente.",
        )
