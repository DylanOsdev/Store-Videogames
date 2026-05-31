from django import forms
from django.contrib import admin, messages

from .fulfillment import (
    AlreadyDelivered,
    complete_manual_delivery,
    mark_record_delivered,
)
from .models import DeliveryRecord, DeliveryStatus, DigitalKey


class DigitalKeyForm(forms.ModelForm):
    """Form que permite cargar la clave en texto plano; se cifra al guardar.

    El campo real `encrypted_value` nunca se muestra. El admin escribe el valor
    en `raw_value`, y en save() se cifra con Fernet. Si se deja vacío al editar,
    la clave existente no se modifica.
    """

    raw_value = forms.CharField(
        label="Valor de la clave (texto plano)",
        required=False,
        widget=forms.TextInput(attrs={"size": 70, "autocomplete": "off"}),
        help_text="Se cifra al guardar. Déjalo vacío al editar para conservar la actual.",
    )

    class Meta:
        model = DigitalKey
        fields = ["product", "status", "order_item"]

    def save(self, commit=True):
        instance = super().save(commit=False)
        raw = self.cleaned_data.get("raw_value")
        if raw:
            instance.set_value(raw)
        if commit:
            instance.save()
        return instance


@admin.register(DigitalKey)
class DigitalKeyAdmin(admin.ModelAdmin):
    form = DigitalKeyForm
    list_display = ("id", "product", "status", "order_item", "created_at", "delivered_at")
    list_filter = ("status", "product__platform")
    search_fields = ("product__title",)
    readonly_fields = ("created_at", "reserved_at", "delivered_at")
    autocomplete_fields = ("product",)


class DeliveryRecordAdminForm(forms.ModelForm):
    """Form de fulfillment manual.

    El admin carga el contenido a entregar en texto plano (`raw_payload`); se
    cifra al guardar. Marcar `mark_delivered` cierra la entrega: cifra, pasa a
    SUCCESS, sincroniza el pedido y notifica al cliente. El estado no se edita
    a mano para forzar ese único camino correcto de completado.
    """

    raw_payload = forms.CharField(
        label="Contenido a entregar (texto plano)",
        required=False,
        widget=forms.Textarea(attrs={"rows": 4, "cols": 70, "autocomplete": "off"}),
        help_text=(
            "Credenciales de la cuenta, código de recarga o instrucciones. "
            "Se cifra al guardar. Déjalo vacío para conservar el contenido actual."
        ),
    )
    mark_delivered = forms.BooleanField(
        label="Marcar como entregada y notificar al cliente",
        required=False,
        help_text=(
            "Completa la entrega: cifra el contenido, marca el registro como "
            "entregado, actualiza el estado del pedido y envía el correo."
        ),
    )

    class Meta:
        model = DeliveryRecord
        fields = ["public_message", "error_detail"]


@admin.register(DeliveryRecord)
class DeliveryRecordAdmin(admin.ModelAdmin):
    """Bandeja de fulfillment: completa las entregas que esperan al admin.

    Para cuentas compartidas, recargas y entregas manuales, el admin abre el
    registro (estado "Esperando acción del admin"), pega el contenido a
    entregar y marca la casilla de completar. El contenido se guarda cifrado;
    el cliente recibe el correo y lo ve en su cuenta.
    """

    form = DeliveryRecordAdminForm
    list_display = (
        "id",
        "order_item",
        "delivery_type",
        "status",
        "has_payload",
        "created_at",
        "completed_at",
    )
    list_filter = ("status", "delivery_type")
    search_fields = ("order_item__order__id", "order_item__product__title")
    readonly_fields = (
        "order_item",
        "delivery_type",
        "status",
        "has_payload",
        "created_at",
        "completed_at",
    )
    fields = (
        "order_item",
        "delivery_type",
        "status",
        "has_payload",
        "public_message",
        "raw_payload",
        "mark_delivered",
        "error_detail",
        "created_at",
        "completed_at",
    )
    actions = ("action_mark_delivered",)

    @admin.display(description="¿Tiene contenido?", boolean=True)
    def has_payload(self, obj):
        return bool(obj.encrypted_payload)

    def save_model(self, request, obj, form, change):
        raw_payload = form.cleaned_data.get("raw_payload", "")
        mark = form.cleaned_data.get("mark_delivered", False)

        if mark:
            try:
                order = complete_manual_delivery(
                    obj,
                    raw_payload=raw_payload,
                    public_message=obj.public_message or None,
                    notify=True,
                )
            except AlreadyDelivered:
                self.message_user(
                    request,
                    "Esta entrega ya estaba completada; no se reprocesó.",
                    messages.WARNING,
                )
                return
            self.message_user(
                request,
                f"Entrega completada. Pedido #{order.id} actualizado "
                f"({order.get_status_display()}) y cliente notificado.",
                messages.SUCCESS,
            )
            return

        # Sin completar: guarda ediciones de mensaje/error y, si se cargó
        # contenido, lo cifra (sin cambiar el estado todavía).
        if raw_payload:
            obj.set_payload(raw_payload)
        super().save_model(request, obj, form, change)

    @admin.action(
        description="Marcar entregas seleccionadas como completadas y notificar"
    )
    def action_mark_delivered(self, request, queryset):
        done = 0
        skipped = 0
        for record in queryset:
            result = mark_record_delivered(record, notify=True)
            if result is None:
                skipped += 1
            else:
                done += 1
        self.message_user(
            request,
            f"Entregas completadas: {done}. "
            f"Ya estaban entregadas (omitidas): {skipped}.",
            messages.SUCCESS,
        )
