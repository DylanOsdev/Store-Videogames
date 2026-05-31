"""Cifrado simétrico para secretos en reposo (claves digitales, credenciales).

Usa Fernet (AES-128 en modo CBC + HMAC) de la librería `cryptography`.
La clave maestra se lee de la variable de entorno DJANGO_FERNET_KEY.

Generar una clave nueva (una sola vez, guardar en el .env, NUNCA en git):

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Importante: si rotas la clave, los valores cifrados con la anterior dejan de
poder descifrarse. Para rotación real se necesita MultiFernet (no incluido aquí).
"""
import os

from cryptography.fernet import Fernet, InvalidToken
from django.core.exceptions import ImproperlyConfigured


def _get_fernet() -> Fernet:
    key = os.environ.get("DJANGO_FERNET_KEY")
    if not key:
        raise ImproperlyConfigured(
            "Falta DJANGO_FERNET_KEY. Genera una con: "
            'python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        )
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured(
            "DJANGO_FERNET_KEY no es una clave Fernet válida (urlsafe base64 de 32 bytes)."
        ) from exc


def encrypt_value(raw: str) -> str:
    """Cifra un string y devuelve el token (str) listo para guardar en BD."""
    if raw is None:
        raw = ""
    token = _get_fernet().encrypt(raw.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_value(token: str) -> str:
    """Descifra un token previamente generado por encrypt_value."""
    if not token:
        return ""
    try:
        return _get_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError(
            "No se pudo descifrar el valor: token inválido o clave incorrecta."
        ) from exc
