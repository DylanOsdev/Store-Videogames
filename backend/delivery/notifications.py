"""Notificaciones por correo al cliente sobre el estado de su entrega.

Construye y envía el correo según el resultado de la entrega de un pedido.
En desarrollo usa el backend de consola (los correos se imprimen en stdout),
así funciona sin servidor SMTP. En producción se configura SMTP por env.
"""
from __future__ import annotations

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from .models import DeliveryStatus


def _render_order_email(order) -> tuple[str, str]:
    """Devuelve (texto_plano, html) para el correo de un pedido entregado."""
    lines = [
        f"¡Hola!",
        "",
        f"Gracias por tu compra en GameStore. Pedido #{order.id}.",
        "",
    ]
    html_parts = [
        "<h2>¡Gracias por tu compra en GameStore!</h2>",
        f"<p>Pedido <strong>#{order.id}</strong></p>",
    ]

    for item in order.items.all():
        lines.append(f"• {item.quantity}× {item.product.title}")
        html_parts.append(f"<h3>{item.quantity}× {item.product.title}</h3>")

        for rec in item.delivery_records.all():
            if rec.status == DeliveryStatus.SUCCESS:
                content = rec.get_payload()
                lines.append(f"  {rec.public_message}")
                lines.append(f"  {content}")
                html_parts.append(f"<p>{rec.public_message}</p>")
                html_parts.append(
                    f"<pre style='background:#f4f4f5;padding:12px;"
                    f"border-radius:8px;font-size:15px;'>{content}</pre>"
                )
            elif rec.status == DeliveryStatus.AWAITING_ADMIN:
                lines.append(f"  {rec.public_message}")
                html_parts.append(f"<p>{rec.public_message}</p>")
            elif rec.status == DeliveryStatus.FAILED:
                msg = (
                    "Tuvimos un inconveniente al entregar este producto. "
                    "Nuestro equipo te contactará pronto."
                )
                lines.append(f"  {msg}")
                html_parts.append(f"<p style='color:#c0392b;'>{msg}</p>")
        lines.append("")

    lines.append("Puedes ver tu pedido en cualquier momento desde tu cuenta.")
    html_parts.append(
        "<p>Puedes ver tu pedido en cualquier momento desde tu cuenta.</p>"
    )

    return "\n".join(lines), "\n".join(html_parts)


def send_order_delivery_email(order) -> bool:
    """Envía al cliente el correo con el resultado de la entrega.

    Devuelve True si se envió (o se encoló en el backend de consola).
    No lanza si el envío falla: registra y devuelve False, para no romper la
    entrega por un problema de correo.
    """
    if not order.contact_email:
        return False

    subject = f"Tu pedido #{order.id} en GameStore"
    text_body, html_body = _render_order_email(order)
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@gamestore.local")

    try:
        msg = EmailMultiAlternatives(
            subject, text_body, from_email, [order.contact_email]
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send()
        return True
    except Exception:
        # El correo no debe tumbar la entrega; el contenido ya está en la cuenta.
        return False
