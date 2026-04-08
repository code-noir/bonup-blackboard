from rest_framework.routers import DefaultRouter
from .views import PaymentTemplatesViewSet

router = DefaultRouter()
router.register(r'', PaymentTemplatesViewSet, basename='payment-templates')

urlpatterns = router.urls
