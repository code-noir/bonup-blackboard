from rest_framework.routers import DefaultRouter
from .views import ToolsViewSet

router = DefaultRouter()
router.register(r'', ToolsViewSet, basename='tools')

urlpatterns = router.urls
