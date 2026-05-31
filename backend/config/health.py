"""Health check para monitoreo (load balancers, uptime, orquestadores).

Verifica que el proceso responde y que la base de datos está accesible.
Público y sin rate limiting: los chequeos de salud son frecuentes y no deben
agotar cuotas ni requerir credenciales.
"""
from django.db import connection
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import extend_schema


class HealthCheckView(APIView):
    """Estado del servicio. 200 si la BD responde, 503 si no."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []  # el monitoreo no debe ser limitado

    @extend_schema(
        tags=["health"],
        summary="Estado del servicio",
        description="Devuelve 200 OK si el proceso y la base de datos responden.",
        responses={200: None, 503: None},
    )
    def get(self, request, *args, **kwargs):
        checks = {"app": "ok"}
        healthy = True

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            checks["database"] = "ok"
        except Exception:
            checks["database"] = "error"
            healthy = False

        http_status = (
            status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        return Response(
            {"status": "ok" if healthy else "unhealthy", "checks": checks},
            status=http_status,
        )
