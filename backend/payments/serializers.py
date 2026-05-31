from rest_framework import serializers

from .models import Payment


class PaymentInitSerializer(serializers.Serializer):
    """Entrada: el id del pedido a pagar."""

    order_id = serializers.IntegerField()


class PaymentInitResponseSerializer(serializers.Serializer):
    """Datos que el frontend necesita para abrir el checkout de Wompi."""

    reference = serializers.CharField()
    amount_in_cents = serializers.IntegerField()
    currency = serializers.CharField()
    public_key = serializers.CharField()
    integrity_signature = serializers.CharField()


class PaymentSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Payment
        fields = (
            "reference",
            "status",
            "status_display",
            "amount_in_cents",
            "currency",
            "payment_method_type",
            "created_at",
            "finalized_at",
        )
        read_only_fields = fields
