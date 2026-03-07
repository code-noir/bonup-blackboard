from rest_framework.routers import DefaultRouter
from .views import UploadsViewSet

router = DefaultRouter()
router.register(r'', UploadsViewSet, basename='uploads')

urlpatterns = router.urls
