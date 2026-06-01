"""Envía un correo de prueba para verificar la configuración SMTP.

Útil para validar credenciales y conectividad en producción SIN tener que
crear un pedido real ni disparar correos a clientes.

Uso:
    python manage.py send_test_email --to admin@tudominio.com

Muestra la configuración activa (sin revelar la contraseña) y reporta si el
envío tuvo éxito o el error exacto del servidor SMTP.
"""
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Envía un correo de prueba para verificar la configuración SMTP."

    def add_arguments(self, parser):
        parser.add_argument(
            "--to",
            required=True,
            help="Dirección de correo destino para la prueba.",
        )

    def handle(self, *args, **options):
        destino = options["to"]

        # Resumen de la config activa (la contraseña NO se imprime).
        self.stdout.write("Configuración de correo activa:")
        self.stdout.write(f"  EMAIL_BACKEND   = {settings.EMAIL_BACKEND}")
        self.stdout.write(f"  EMAIL_HOST      = {settings.EMAIL_HOST or '(vacío)'}")
        self.stdout.write(f"  EMAIL_PORT      = {settings.EMAIL_PORT}")
        self.stdout.write(f"  EMAIL_HOST_USER = {settings.EMAIL_HOST_USER or '(vacío)'}")
        self.stdout.write(
            f"  EMAIL_HOST_PASSWORD = {'(definida)' if settings.EMAIL_HOST_PASSWORD else '(vacía)'}"
        )
        self.stdout.write(f"  EMAIL_USE_TLS   = {settings.EMAIL_USE_TLS}")
        self.stdout.write(f"  EMAIL_USE_SSL   = {getattr(settings, 'EMAIL_USE_SSL', False)}")
        self.stdout.write(f"  EMAIL_TIMEOUT   = {getattr(settings, 'EMAIL_TIMEOUT', None)}")
        self.stdout.write(f"  DEFAULT_FROM_EMAIL = {settings.DEFAULT_FROM_EMAIL}")

        if "console" in settings.EMAIL_BACKEND:
            self.stdout.write(
                self.style.WARNING(
                    "\nAviso: EMAIL_BACKEND usa el backend de consola. El correo "
                    "se imprimirá abajo en vez de enviarse por SMTP. Para una "
                    "prueba real, define EMAIL_BACKEND=django.core.mail.backends."
                    "smtp.EmailBackend y las credenciales SMTP."
                )
            )

        subject = "Correo de prueba — GameStore"
        text_body = (
            "Este es un correo de prueba de GameStore.\n\n"
            "Si lo recibes, tu configuración SMTP funciona correctamente."
        )
        html_body = (
            "<h2>Correo de prueba — GameStore</h2>"
            "<p>Si lo recibes, tu configuración SMTP funciona correctamente.</p>"
        )

        msg = EmailMultiAlternatives(
            subject, text_body, settings.DEFAULT_FROM_EMAIL, [destino]
        )
        msg.attach_alternative(html_body, "text/html")

        try:
            enviados = msg.send()
        except Exception as exc:
            # Reporta el error real del servidor SMTP para diagnosticar.
            raise CommandError(f"Fallo al enviar el correo: {exc!r}")

        if enviados:
            self.stdout.write(
                self.style.SUCCESS(f"\nCorreo de prueba enviado a {destino}.")
            )
        else:
            raise CommandError(
                "El backend reportó 0 correos enviados. Revisa la configuración."
            )
