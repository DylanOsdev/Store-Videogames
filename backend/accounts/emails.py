"""Correos relacionados con la cuenta del usuario.

En desarrollo usa el backend de consola (los correos se imprimen en stdout),
así funciona sin servidor SMTP. En producción se configura SMTP por entorno.
"""
from __future__ import annotations

from django.conf import settings
from django.core.mail import EmailMultiAlternatives


def send_password_reset_email(user, reset_url: str) -> bool:
    """Envía al usuario el enlace para restablecer su contraseña.

    No lanza si el envío falla: registra implícitamente y devuelve False, para
    que la vista pueda responder de forma uniforme (anti-enumeración) sin
    filtrar si el correo existe ni si el envío tuvo problemas.
    """
    nombre = user.full_name or "hola"
    subject = "Restablece tu contraseña en GameStore"
    from_email = getattr(
        settings, "DEFAULT_FROM_EMAIL", "no-reply@gamestore.local"
    )

    text_body = "\n".join(
        [
            f"¡{nombre}!",
            "",
            "Recibimos una solicitud para restablecer la contraseña de tu "
            "cuenta en GameStore.",
            "",
            "Abre este enlace para crear una contraseña nueva:",
            reset_url,
            "",
            "Si no fuiste tú, ignora este correo: tu contraseña no cambiará.",
            "El enlace caduca por seguridad pasado un tiempo.",
            "",
            "— El equipo de GameStore",
        ]
    )

    html_body = "\n".join(
        [
            f"<h2>Restablece tu contraseña</h2>",
            f"<p>¡{nombre}!</p>",
            "<p>Recibimos una solicitud para restablecer la contraseña de tu "
            "cuenta en GameStore.</p>",
            f'<p><a href="{reset_url}" style="display:inline-block;'
            "background:#6d28d9;color:#fff;padding:12px 20px;border-radius:8px;"
            'text-decoration:none;font-weight:600;">Crear contraseña nueva</a></p>',
            "<p style='color:#71717a;font-size:0.9rem;'>O copia y pega este "
            f"enlace en tu navegador:<br>{reset_url}</p>",
            "<p style='color:#71717a;font-size:0.9rem;'>Si no fuiste tú, ignora "
            "este correo: tu contraseña no cambiará. El enlace caduca por "
            "seguridad pasado un tiempo.</p>",
        ]
    )

    try:
        msg = EmailMultiAlternatives(
            subject, text_body, from_email, [user.email]
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send()
        return True
    except Exception:
        # El correo no debe romper el flujo; la vista responde igual.
        return False
