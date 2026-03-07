from rest_framework.routers import DefaultRouter
from .views import TemplatesViewSet

router = DefaultRouter()
router.register(r'', TemplatesViewSet, basename='templates')

urlpatterns = router.urls
