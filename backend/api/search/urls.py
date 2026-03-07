from rest_framework.routers import DefaultRouter
from .views import SearchViewSet

router = DefaultRouter()
router.register(r'', SearchViewSet, basename='search')

urlpatterns = router.urls
