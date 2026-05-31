"""Expone la app de Celery al importar el paquete config.

Garantiza que Celery se inicialice cuando arranca Django.
"""
from .celery import app as celery_app

__all__ = ("celery_app",)
