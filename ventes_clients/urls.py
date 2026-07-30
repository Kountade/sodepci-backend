# apps/ventes_clients/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ClientViewSet, VenteViewSet, PaiementViewSet,
    FactureViewSet, AvoirViewSet, TaxeViewSet,
    RemiseViewSet, SalesDashboardStatsViewSet, DevisViewSet
)

router = DefaultRouter()

# ✅ Endpoints standards
router.register('clients', ClientViewSet, basename='clients')
router.register('devis', DevisViewSet, basename='devis')
router.register('payments', PaiementViewSet, basename='payments')
router.register('factures', FactureViewSet, basename='factures')
router.register('avoirs', AvoirViewSet, basename='avoirs')
router.register('taxes', TaxeViewSet, basename='taxes')
router.register('remises', RemiseViewSet, basename='remises')
router.register('dashboard-sales-stats', SalesDashboardStatsViewSet, basename='dashboard-sales-stats')

# ✅ DUPLICATION de VenteViewSet avec un basename différent pour le POS
router.register('sales', VenteViewSet, basename='sales')
router.register('pos', VenteViewSet, basename='pos')  # Même vue, URL différente

urlpatterns = [
    path('', include(router.urls)),
]