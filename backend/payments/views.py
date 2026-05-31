import logging

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import permissions, status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers

from orders.models import Order
from .gateway import verify_event_signature
from .models import Payment
from .serializers import (
    PaymentInitResponseSerializer,
    PaymentInitSerializer,
    PaymentSerializer,
)
from .services import build_checkout_data, create_payment_for_order, process_wompi_event

logger = logging.getLogger(__name__)


class PaymentInitView(GenericAPIView):
    """Inicia el pago de un pedido del usuario. Devuelve datos para el checkout."""

    serializer_class = PaymentInitSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order_id = serializer.validated_data["order_id"]

        # El pedido debe ser del usuario autenticado.
        try:
            order = Order.objects.get(pk=order_id, user=request.user)
        except Order.DoesNotExist:
            return Response(
                {"detail": "Pedido no encontrado."}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            payment = create_payment_for_order(order)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        data = build_checkout_data(payment)
        return Response(
            PaymentInitResponseSerializer(data).data, status=status.HTTP_201_CREATED
        )


class PaymentStatusView(GenericAPIView):
    """Consulta el estado de un pago por su referencia (solo del propio usuario)."""

    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, reference, *args, **kwargs):
        try:
            payment = Payment.objects.select_related("order").get(
                reference=reference, order__user=request.user
            )
        except Payment.DoesNotExist:
            return Response(
                {"detail": "Pago no encontrado."}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(self.get_serializer(payment).data)


@method_decorator(csrf_exempt, name="dispatch")
class WompiWebhookView(APIView):
    """Recibe eventos de Wompi.

    SEGURIDAD: este endpoint es público (Wompi hace POST sin autenticación).
    Toda su seguridad depende de verify_event_signature. Si la firma no es
    válida, se rechaza con 400 y no se procesa nada. Nunca confiar en el cuerpo
    sin validar el checksum.
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_scope = "webhook"
    throttle_classes = [ScopedRateThrottle]

    @extend_schema(
        tags=["payments"],
        summary="Webhook de eventos de Wompi",
        description=(
            "Endpoint público que recibe los eventos de transacción de Wompi. "
            "La autenticidad se valida por la firma (checksum) del evento, no "
            "por credenciales. Una firma inválida se rechaza con 400."
        ),
        request=inline_serializer(
            name="WompiWebhookEvent",
            fields={
                "event": drf_serializers.CharField(),
                "data": drf_serializers.DictField(),
                "signature": drf_serializers.DictField(),
                "timestamp": drf_serializers.IntegerField(),
            },
        ),
        responses={
            200: inline_serializer(
                name="WompiWebhookAccepted",
                fields={
                    "received": drf_serializers.BooleanField(),
                    "status": drf_serializers.CharField(required=False),
                    "delivered": drf_serializers.BooleanField(required=False),
                },
            ),
            400: OpenApiResponse(description="Firma inválida."),
            404: OpenApiResponse(description="Referencia de pago desconocida."),
        },
    )
    def post(self, request, *args, **kwargs):
        event = request.data if isinstance(request.data, dict) else {}

        if not verify_event_signature(event):
            logger.warning("Webhook Wompi con firma inválida rechazado.")
            return Response(
                {"detail": "Firma inválida."}, status=status.HTTP_400_BAD_REQUEST
            )

        if event.get("event") != "transaction.updated":
            # Otros eventos: los aceptamos pero no hacemos nada por ahora.
            return Response({"received": True}, status=status.HTTP_200_OK)

        payment, delivered = process_wompi_event(event)
        if payment is None:
            return Response(
                {"detail": "Referencia desconocida."}, status=status.HTTP_404_NOT_FOUND
            )

        return Response(
            {"received": True, "status": payment.status, "delivered": delivered},
            status=status.HTTP_200_OK,
        )
