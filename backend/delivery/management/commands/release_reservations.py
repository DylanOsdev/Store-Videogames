"""Libera claves reservadas en checkouts que nunca se pagaron.

Uso:
    python manage.py release_reservations            # reservas de +30 min
    python manage.py release_reservations --minutes 60

Pensado para correr periódicamente (cron del sistema o Celery beat). Devuelve
al inventario las claves que quedaron en estado RESERVED por pedidos que no se
completaron, para que vuelvan a estar disponibles para la venta.
"""
from django.core.management.base import BaseCommand

from delivery.inventory import release_expired_reservations


class Command(BaseCommand):
    help = "Libera claves reservadas cuyo checkout nunca se pagó."

    def add_arguments(self, parser):
        parser.add_argument(
            "--minutes",
            type=int,
            default=30,
            help="Antigüedad mínima de la reserva para liberarla (default: 30).",
        )

    def handle(self, *args, **options):
        minutes = options["minutes"]
        freed = release_expired_reservations(older_than_minutes=minutes)
        self.stdout.write(
            self.style.SUCCESS(
                f"Reservas liberadas (> {minutes} min): {freed}."
            )
        )
