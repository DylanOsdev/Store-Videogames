"""Configuración de Celery para tareas asíncronas.

Las entregas, el envío de correos y el procesamiento de webhooks de pago se
ejecutan como tareas Celery para no bloquear la petición HTTP del cliente.
"""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("videojuegos")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
