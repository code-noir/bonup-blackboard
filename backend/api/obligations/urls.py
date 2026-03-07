from rest_framework.routers import DefaultRouter
from .views import ObligationsViewSet

router = DefaultRouter()
router.register(r'', ObligationsViewSet, basename='obligations')

urlpatterns = router.urls
