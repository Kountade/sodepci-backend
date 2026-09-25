from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    CuveViewSet, MouvementCuveViewSet,
    PompeViewSet, MouvementPompeViewSet,
    VenteCarburantViewSet, ServiceViewSet,
    VenteServiceViewSet, PrixCarburantViewSet,
    StatistiquesStationViewSet
)

router = DefaultRouter()
router.register(r'cuves', CuveViewSet, basename='cuve')
router.register(r'mouvements-cuves', MouvementCuveViewSet, basename='mouvement-cuve')
router.register(r'pompes', PompeViewSet, basename='pompe')
router.register(r'mouvements-pompes', MouvementPompeViewSet, basename='mouvement-pompe')
router.register(r'ventes-carburant', VenteCarburantViewSet, basename='vente-carburant')
router.register(r'services', ServiceViewSet, basename='service')
router.register(r'ventes-services', VenteServiceViewSet, basename='vente-service')
router.register(r'prix-carburant', PrixCarburantViewSet, basename='prix-carburant')
router.register(r'statistiques', StatistiquesStationViewSet, basename='statistiques')

urlpatterns = [
    path('', include(router.urls)),
]