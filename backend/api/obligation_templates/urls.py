from rest_framework.routers import DefaultRouter
from .views import ObligationTemplatesViewSet

router = DefaultRouter()
router.register(r'', ObligationTemplatesViewSet, basename='obligation-templates')

urlpatterns = router.urls
