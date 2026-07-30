# finances/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'comptes', views.CompteComptableViewSet, basename='comptes')
router.register(r'ecritures', views.EcritureComptableViewSet,
                basename='ecritures')
router.register(r'tresorerie', views.TresorerieViewSet, basename='tresorerie')
router.register(r'mouvements-tresorerie',
                views.MouvementTresorerieViewSet, basename='mouvements-tresorerie')
router.register(r'depenses', views.DepenseViewSet, basename='depenses')
router.register(r'budgets', views.BudgetViewSet, basename='budgets')
router.register(r'budget-categories',
                views.BudgetCategorieViewSet, basename='budget-categories')
router.register(r'rapports', views.RapportFinancierViewSet,
                basename='rapports')
router.register(r'configuration',
                views.ConfigurationFinanciereViewSet, basename='configuration')
router.register(r'stats', views.FinancesStatsViewSet,
                basename='stats-finances')

urlpatterns = [
    path('', include(router.urls)),
]
