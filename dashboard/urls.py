# dashboard/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DashboardViewSet, StatistiquesViewSet, AnalysesViewSet   # ✅ noms avec 's'

router = DefaultRouter()
router.register('dashboard', DashboardViewSet, basename='dashboard')
router.register('statistiques', StatistiquesViewSet, basename='statistiques')
router.register('analyses', AnalysesViewSet, basename='analyses')

urlpatterns = [
    path('', include(router.urls)),
]
