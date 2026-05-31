"""Serializers de entrega.

Expone al DUEÑO del pedido el resultado de su entrega. Reglas:
- El payload (clave/credenciales) solo se descifra si la entrega fue exitosa.
- error_detail NUNCA se expone al cliente (es información para el admin).
"""
from rest_framework import serializers

from .models import DeliveryRecord, DeliveryStatus


class DeliveryRecordSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    content = serializers.SerializerMethodField()

    class Meta:
        model = DeliveryRecord
        fields = (
            "id",
            "delivery_type",
            "status",
            "status_display",
            "public_message",
            "content",
            "created_at",
            "completed_at",
        )

    def get_content(self, obj) -> str | None:
        """Contenido sensible descifrado, solo si la entrega fue exitosa."""
        if obj.status == DeliveryStatus.SUCCESS:
            return obj.get_payload()
        return None
