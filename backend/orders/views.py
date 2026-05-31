from rest_framework import mixins, permissions, viewsets
from rest_framework.generics import CreateAPIView
from rest_framework.throttling import ScopedRateThrottle

from .models import Order
from .serializers import CheckoutSerializer, OrderSerializer


class OrderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Lista y detalle de los pedidos DEL usuario autenticado.

    El queryset se filtra siempre por request.user: nadie puede ver pedidos
    ajenos aunque adivine el id.
    """

    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Durante la introspección del schema (drf-spectacular) no hay usuario
        # autenticado; devolvemos un queryset vacío para no romper la generación.
        if getattr(self, "swagger_fake_view", False):
            return Order.objects.none()
        return (
            Order.objects.filter(user=self.request.user)
            .prefetch_related("items__product", "items__delivery_records")
        )


class CheckoutView(CreateAPIView):
    """Crea un pedido (estado pendiente de pago) a partir del carrito.

    Rate limiting (scope 'checkout') para frenar la creación masiva de pedidos
    automatizada sin afectar el uso normal del cliente.
    """

    serializer_class = CheckoutSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "checkout"
    throttle_classes = [ScopedRateThrottle]
