# apps/achats_fournisseurs/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SupplierViewSet, PurchaseOrderViewSet, ReceiptViewSet,
    PurchaseReturnViewSet, SupplierInvoiceViewSet, DashboardViewSet,
    PurchaseAlertViewSet  # Ajouter cet import
)

router = DefaultRouter()
router.register('suppliers', SupplierViewSet, basename='suppliers')
router.register('purchase-orders', PurchaseOrderViewSet,
                basename='purchase-orders')
router.register('receipts', ReceiptViewSet, basename='receipts')
router.register('purchase-returns', PurchaseReturnViewSet,
                basename='purchase-returns')
router.register('supplier-invoices', SupplierInvoiceViewSet,
                basename='supplier-invoices')
router.register('purchase-alerts', PurchaseAlertViewSet,
                basename='purchase-alerts')

urlpatterns = [
    path('', include(router.urls)),

    # Dashboard statistics
    path('dashboard/statistics/',
         DashboardViewSet.as_view({'get': 'statistics'}), name='dashboard-statistics'),
]
