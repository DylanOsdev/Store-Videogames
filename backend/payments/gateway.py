"""Pasarela Wompi: validación de firma de eventos y firma de integridad.

Wompi NO usa la llave privada para firmar los webhooks. Usa un "secreto de
eventos" (WOMPI_EVENTS_SECRET). Cada evento trae un bloque `signature` con:
    - properties: lista de rutas dentro de data cuyos valores se concatenan
    - checksum:   SHA256(concatenación de esos valores + timestamp + secreto)

Validar esa firma es CRÍTICO: sin ella, un atacante podría enviar un webhook
falso de "pago aprobado" y disparar la entrega sin haber pagado.

Doc: https://docs.wompi.co/docs/colombia/eventos/
"""
from __future__ import annotations

import hashlib
import hmac

from django.conf import settings


def _resolve_path(data: dict, dotted_path: str):
    """Obtiene un valor anidado a partir de una ruta tipo 'transaction.status'."""
    current = data
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def compute_event_checksum(event: dict, secret: str | None = None) -> str:
    """Calcula el checksum esperado de un evento Wompi.

    Concatena los valores de signature.properties (en orden), seguido del
    timestamp y el secreto de eventos, y aplica SHA256.
    """
    secret = secret if secret is not None else settings.WOMPI_EVENTS_SECRET
    signature = event.get("signature", {})
    properties = signature.get("properties", [])
    data = event.get("data", {})
    timestamp = event.get("timestamp", "")

    concatenated = ""
    for prop in properties:
        value = _resolve_path(data, prop)
        concatenated += str(value if value is not None else "")
    concatenated += str(timestamp)
    concatenated += str(secret)

    return hashlib.sha256(concatenated.encode("utf-8")).hexdigest()


def verify_event_signature(event: dict, secret: str | None = None) -> bool:
    """Devuelve True si la firma del evento es válida.

    Usa comparación en tiempo constante (hmac.compare_digest) para evitar
    ataques de temporización.
    """
    provided = (event.get("signature", {}) or {}).get("checksum", "")
    if not provided:
        return False
    expected = compute_event_checksum(event, secret)
    return hmac.compare_digest(expected.lower(), str(provided).lower())


def generate_integrity_signature(
    reference: str, amount_in_cents: int, currency: str = "COP",
    secret: str | None = None,
) -> str:
    """Firma de integridad para iniciar una transacción desde el frontend.

    El widget/checkout de Wompi exige firmar: reference + amount + currency +
    integrity_secret con SHA256. Así el monto no puede ser manipulado en el
    navegador.
    """
    secret = secret if secret is not None else settings.WOMPI_INTEGRITY_SECRET
    payload = f"{reference}{amount_in_cents}{currency}{secret}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
