# apps/achats_fournisseurs/views.py
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from datetime import date, timedelta
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from io import BytesIO
import json

from .models import (
    Supplier, SupplierContact, SupplierProduct, PurchaseOrder,
    PurchaseOrderLine, Receipt, ReceiptLine, PurchaseReturn,
    PurchaseReturnLine, SupplierInvoice, FournisseurPaiement
)
from .serializers import (
    SupplierListSerializer, SupplierDetailSerializer, SupplierWriteSerializer,
    SupplierContactSerializer, SupplierProductSerializer,
    PurchaseOrderListSerializer, PurchaseOrderDetailSerializer,
    PurchaseOrderCreateSerializer, PurchaseOrderUpdateSerializer,
    PurchaseOrderApproveSerializer, 
    ReceiptListSerializer, ReceiptDetailSerializer, ReceiptCreateSerializer,
    PurchaseReturnSerializer, PurchaseReturnCreateSerializer,
    SupplierInvoiceListSerializer, SupplierInvoiceDetailSerializer,
    SupplierInvoiceCreateSerializer, SupplierInvoicePaymentSerializer,
    FournisseurPaiementSerializer, FournisseurPaiementCreateSerializer
)
from users.permissions import IsAdmin, IsGestionnaire, IsMagasinier


# ============================================================
# FOURNISSEUR VIEWSET
# ============================================================

class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    permission_classes = [permissions.IsAuthenticated, IsGestionnaire]

    def get_serializer_class(self):
        if self.action == 'list':
            return SupplierListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return SupplierWriteSerializer
        return SupplierDetailSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search) |
                Q(phone__icontains=search) |
                Q(email__icontains=search)
            )
        
        type_filter = self.request.query_params.get('type')
        if type_filter:
            queryset = queryset.filter(type=type_filter)
        
        is_active = self.request.query_params.get('is_active')
        if is_active == 'true':
            queryset = queryset.filter(is_active=True)
        elif is_active == 'false':
            queryset = queryset.filter(is_active=False)
        
        is_preferred = self.request.query_params.get('is_preferred')
        if is_preferred == 'true':
            queryset = queryset.filter(is_preferred=True)
        
        ordering = self.request.query_params.get('ordering', 'name')
        if ordering:
            queryset = queryset.order_by(ordering)
        
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['get'])
    def debt_status(self, request, pk=None):
        """Statut de la dette du fournisseur"""
        supplier = self.get_object()
        return Response({
            'total_debt': supplier.total_debt,
            'overdue_debt': supplier.overdue_debt,
            'total_invoices': supplier.invoices.count(),
            'overdue_invoices': supplier.invoices.filter(
                due_date__lt=date.today(),
                paiement_status__in=['unpaid', 'partial']
            ).count()
        })

    @action(detail=True, methods=['get'])
    def orders_status(self, request, pk=None):
        """Statut des commandes du fournisseur"""
        supplier = self.get_object()
        orders = supplier.purchase_orders.all()
        
        return Response({
            'total_orders': orders.count(),
            'total_amount': orders.aggregate(total=Sum('total'))['total'] or 0,
            'received_amount': orders.aggregate(total=Sum('total_received_amount'))['total'] or 0,
            'invoiced_amount': orders.aggregate(total=Sum('total_invoiced_amount'))['total'] or 0,
            'paid_amount': orders.aggregate(total=Sum('total_paid_amount'))['total'] or 0,
            'orders_by_status': {
                status_code: orders.filter(status=status_code).count()
                for status_code, _ in PurchaseOrder.STATUS_CHOICES
                if orders.filter(status=status_code).count() > 0
            }
        })

    @action(detail=True, methods=['get'])
    def contacts(self, request, pk=None):
        supplier = self.get_object()
        contacts = supplier.contacts.all()
        serializer = SupplierContactSerializer(contacts, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def add_contact(self, request, pk=None):
        supplier = self.get_object()
        serializer = SupplierContactSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(supplier=supplier)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def products(self, request, pk=None):
        supplier = self.get_object()
        products = supplier.products.filter(is_active=True)
        serializer = SupplierProductSerializer(products, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def purchase_orders(self, request, pk=None):
        supplier = self.get_object()
        orders = supplier.purchase_orders.all().order_by('-order_date')
        serializer = PurchaseOrderListSerializer(orders, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def invoices(self, request, pk=None):
        supplier = self.get_object()
        invoices = supplier.invoices.all().order_by('-invoice_date')
        serializer = SupplierInvoiceListSerializer(invoices, many=True)
        return Response(serializer.data)


# ============================================================
# BON DE COMMANDE VIEWSET
# ============================================================

class PurchaseOrderViewSet(viewsets.ModelViewSet):
    queryset = PurchaseOrder.objects.all()
    permission_classes = [permissions.IsAuthenticated, IsGestionnaire]

    def get_serializer_class(self):
        if self.action == 'list':
            return PurchaseOrderListSerializer
        elif self.action == 'create':
            return PurchaseOrderCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return PurchaseOrderUpdateSerializer
        return PurchaseOrderDetailSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_queryset(self):
        queryset = super().get_queryset()
        
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(po_number__icontains=search) |
                Q(supplier__name__icontains=search) |
                Q(supplier__code__icontains=search)
            )
        
        supplier = self.request.query_params.get('supplier')
        if supplier:
            queryset = queryset.filter(supplier_id=supplier)
        
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(order_date__date__gte=date_from)
        
        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(order_date__date__lte=date_to)
        
        ordering = self.request.query_params.get('ordering', '-order_date')
        if ordering:
            queryset = queryset.order_by(ordering)
        
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        purchase_order = self.get_object()
        serializer = PurchaseOrderApproveSerializer(data=request.data)
        
        if serializer.is_valid():
            if serializer.validated_data['approved']:
                purchase_order.status = 'confirmed'
                purchase_order.approved_by = request.user
                purchase_order.approved_at = timezone.now()
            else:
                purchase_order.status = 'cancelled'
            purchase_order.save()
            purchase_order.generate_qr_code()
            purchase_order.save()
            
            return Response({
                'status': purchase_order.status,
                'approved': serializer.validated_data['approved']
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        purchase_order = self.get_object()
        if purchase_order.status not in ['draft', 'sent']:
            return Response(
                {"error": "Cette commande ne peut pas être annulée"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        purchase_order.status = 'cancelled'
        purchase_order.save()
        purchase_order.generate_qr_code()
        purchase_order.save()
        
        return Response({
            'status': purchase_order.status,
            'message': 'Commande annulée avec succès'
        })

    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        purchase_order = self.get_object()
        if purchase_order.status != 'draft':
            return Response(
                {"error": "Seules les commandes en brouillon peuvent être envoyées"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        purchase_order.status = 'sent'
        purchase_order.save()
        purchase_order.generate_qr_code()
        purchase_order.save()
        
        return Response({
            'status': purchase_order.status,
            'message': 'Commande envoyée avec succès'
        })

    @action(detail=True, methods=['get'])
    def receipts(self, request, pk=None):
        purchase_order = self.get_object()
        receipts = purchase_order.receipts.all()
        serializer = ReceiptListSerializer(receipts, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def invoices(self, request, pk=None):
        purchase_order = self.get_object()
        invoices = purchase_order.invoices.all()
        serializer = SupplierInvoiceListSerializer(invoices, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def payments(self, request, pk=None):
        purchase_order = self.get_object()
        payments = purchase_order.paiements.filter(status='confirmed')
        serializer = FournisseurPaiementSerializer(payments, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def generate_qr(self, request, pk=None):
        purchase_order = self.get_object()
        if not purchase_order.qr_code:
            purchase_order.generate_qr_code()
            purchase_order.save()
        
        if purchase_order.qr_code:
            return Response({
                'qr_code_url': request.build_absolute_uri(purchase_order.qr_code.url),
                'qr_code_data': purchase_order.qr_code_data
            })
        
        return Response(
            {"error": "Impossible de générer le QR Code"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================
# RÉCEPTION VIEWSET
# ============================================================

class ReceiptViewSet(viewsets.ModelViewSet):
    queryset = Receipt.objects.all()
    permission_classes = [permissions.IsAuthenticated, IsMagasinier]

    def get_serializer_class(self):
        if self.action == 'list':
            return ReceiptListSerializer
        elif self.action == 'create':
            return ReceiptCreateSerializer
        return ReceiptDetailSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_queryset(self):
        queryset = super().get_queryset()
        
        purchase_order = self.request.query_params.get('purchase_order')
        if purchase_order:
            queryset = queryset.filter(purchase_order_id=purchase_order)
        
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        warehouse = self.request.query_params.get('warehouse')
        if warehouse:
            queryset = queryset.filter(warehouse_id=warehouse)
        
        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(receipt_date__date__gte=date_from)
        
        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(receipt_date__date__lte=date_to)
        
        ordering = self.request.query_params.get('ordering', '-receipt_date')
        if ordering:
            queryset = queryset.order_by(ordering)
        
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        receipt = self.get_object()
        if receipt.status != 'in_progress':
            return Response(
                {"error": "Cette réception ne peut pas être annulée"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        receipt.status = 'cancelled'
        receipt.save()
        receipt.generate_qr_code()
        receipt.save()
        
        return Response({
            'status': receipt.status,
            'message': 'Réception annulée avec succès'
        })

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        receipt = self.get_object()
        if receipt.status != 'in_progress':
            return Response(
                {"error": "Seules les réceptions en cours peuvent être terminées"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        receipt.status = 'completed'
        receipt.save()
        receipt.generate_qr_code()
        receipt.save()
        
        return Response({
            'status': receipt.status,
            'message': 'Réception terminée avec succès'
        })

    @action(detail=True, methods=['get'])
    def generate_qr(self, request, pk=None):
        receipt = self.get_object()
        if not receipt.qr_code:
            receipt.generate_qr_code()
            receipt.save()
        
        if receipt.qr_code:
            return Response({
                'qr_code_url': request.build_absolute_uri(receipt.qr_code.url),
                'qr_code_data': receipt.qr_code_data
            })
        
        return Response(
            {"error": "Impossible de générer le QR Code"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================
# RETOUR FOURNISSEUR VIEWSET
# ============================================================

class PurchaseReturnViewSet(viewsets.ModelViewSet):
    queryset = PurchaseReturn.objects.all()
    permission_classes = [permissions.IsAuthenticated, IsGestionnaire]

    def get_serializer_class(self):
        if self.action == 'create':
            return PurchaseReturnCreateSerializer
        return PurchaseReturnSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_queryset(self):
        queryset = super().get_queryset()
        
        purchase_order = self.request.query_params.get('purchase_order')
        if purchase_order:
            queryset = queryset.filter(purchase_order_id=purchase_order)
        
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        reason = self.request.query_params.get('reason')
        if reason:
            queryset = queryset.filter(reason=reason)
        
        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(return_date__date__gte=date_from)
        
        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(return_date__date__lte=date_to)
        
        ordering = self.request.query_params.get('ordering', '-return_date')
        if ordering:
            queryset = queryset.order_by(ordering)
        
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# ============================================================
# FACTURE FOURNISSEUR VIEWSET
# ============================================================

# apps/achats_fournisseurs/views.py
# Modifier la méthode perform_create du SupplierInvoiceViewSet

class SupplierInvoiceViewSet(viewsets.ModelViewSet):
    queryset = SupplierInvoice.objects.all()
    permission_classes = [permissions.IsAuthenticated, IsGestionnaire]

    def get_serializer_class(self):
        if self.action == 'list':
            return SupplierInvoiceListSerializer
        elif self.action == 'create':
            return SupplierInvoiceCreateSerializer
        return SupplierInvoiceDetailSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        
        purchase_order = self.request.query_params.get('purchase_order')
        if purchase_order:
            queryset = queryset.filter(purchase_order_id=purchase_order)
        
        supplier = self.request.query_params.get('supplier')
        if supplier:
            queryset = queryset.filter(supplier_id=supplier)
        
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        paiement_status = self.request.query_params.get('paiement_status')
        if paiement_status:
            queryset = queryset.filter(paiement_status=paiement_status)
        
        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(invoice_date__gte=date_from)
        
        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(invoice_date__lte=date_to)
        
        is_overdue = self.request.query_params.get('is_overdue')
        if is_overdue == 'true':
            queryset = queryset.filter(
                due_date__lt=date.today(),
                paiement_status__in=['unpaid', 'partial']
            )
        
        ordering = self.request.query_params.get('ordering', '-invoice_date')
        if ordering:
            queryset = queryset.order_by(ordering)
        
        return queryset

    # ✅ CORRECTION ICI - Supprimer le passage de supplier
    def perform_create(self, serializer):
        # Le supplier est déjà défini dans le serializer create()
        # Ne pas passer supplier ici car ça crée un conflit
        serializer.save()

# ============================================================
# PAIEMENT FOURNISSEUR VIEWSET
# ============================================================

class FournisseurPaiementViewSet(viewsets.ModelViewSet):
    queryset = FournisseurPaiement.objects.all()
    permission_classes = [permissions.IsAuthenticated, IsGestionnaire]

    def get_serializer_class(self):
        if self.action == 'create':
            return FournisseurPaiementCreateSerializer
        return FournisseurPaiementSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_queryset(self):
        queryset = super().get_queryset()
        
        supplier_invoice = self.request.query_params.get('supplier_invoice')
        if supplier_invoice:
            queryset = queryset.filter(supplier_invoice_id=supplier_invoice)
        
        supplier = self.request.query_params.get('supplier')
        if supplier:
            queryset = queryset.filter(supplier_invoice__supplier_id=supplier)
        
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        method = self.request.query_params.get('method')
        if method:
            queryset = queryset.filter(method=method)
        
        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(payment_date__date__gte=date_from)
        
        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(payment_date__date__lte=date_to)
        
        ordering = self.request.query_params.get('ordering', '-payment_date')
        if ordering:
            queryset = queryset.order_by(ordering)
        
        return queryset

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        paiement = self.get_object()
        
        if paiement.status == 'cancelled':
            return Response(
                {"error": "Ce paiement est déjà annulé"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Restaurer les montants
        supplier_invoice = paiement.supplier_invoice
        supplier_invoice.amount_paid -= paiement.amount
        supplier_invoice.update_payment_status()
        
        purchase_order = paiement.purchase_order or supplier_invoice.purchase_order
        if purchase_order:
            purchase_order.update_payment_status()
        
        # Annuler le mouvement de trésorerie
        if paiement.mouvement_tresorerie:
            paiement.mouvement_tresorerie.status = 'cancelled'
            paiement.mouvement_tresorerie.save()
        
        paiement.status = 'cancelled'
        paiement.save()
        
        return Response({
            'status': paiement.status,
            'message': 'Paiement annulé avec succès'
        })

    @action(detail=True, methods=['get'])
    def generate_qr(self, request, pk=None):
        paiement = self.get_object()
        
        if not paiement.qr_code:
            paiement.generate_qr_code()
            paiement.save()
        
        if paiement.qr_code:
            return Response({
                'qr_code_url': request.build_absolute_uri(paiement.qr_code.url),
                'qr_code_data': paiement.qr_code_data
            })
        
        return Response(
            {"error": "Impossible de générer le QR Code"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================
# DASHBOARD STATS VIEWSET
# ============================================================

class AchatsDashboardStatsViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        today = date.today()
        
        # Statistiques des commandes
        total_orders = PurchaseOrder.objects.count()
        pending_orders = PurchaseOrder.objects.filter(
            status__in=['draft', 'sent', 'confirmed']
        ).count()
        orders_this_month = PurchaseOrder.objects.filter(
            order_date__month=today.month,
            order_date__year=today.year
        ).count()
        
        total_amount = PurchaseOrder.objects.aggregate(total=Sum('total'))['total'] or 0
        amount_this_month = PurchaseOrder.objects.filter(
            order_date__month=today.month,
            order_date__year=today.year
        ).aggregate(total=Sum('total'))['total'] or 0
        
        # Statistiques des réceptions
        total_received = Receipt.objects.filter(status='completed').count()
        pending_receipts = Receipt.objects.filter(status__in=['pending', 'in_progress']).count()
        
        received_amount = PurchaseOrder.objects.aggregate(
            total=Sum('total_received_amount')
        )['total'] or 0
        remaining_to_receive = total_amount - received_amount
        
        # Statistiques des factures
        total_invoices = SupplierInvoice.objects.count()
        unpaid_invoices = SupplierInvoice.objects.filter(
            paiement_status__in=['unpaid', 'partial', 'overdue']
        ).count()
        overdue_invoices = SupplierInvoice.objects.filter(
            due_date__lt=today,
            paiement_status__in=['unpaid', 'partial']
        ).count()
        
        total_invoiced = SupplierInvoice.objects.aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        total_paid = SupplierInvoice.objects.aggregate(
            total=Sum('amount_paid')
        )['total'] or 0
        total_remaining_to_pay = total_invoiced - total_paid
        
        # Top fournisseurs
        top_suppliers = Supplier.objects.annotate(
            total_orders=Count('purchase_orders'),
            total_amount=Sum('purchase_orders__total')
        ).order_by('-total_amount')[:5]
        
        top_suppliers_data = []
        for supplier in top_suppliers:
            top_suppliers_data.append({
                'id': supplier.id,
                'name': supplier.name,
                'total_orders': supplier.total_orders,
                'total_amount': supplier.total_amount or 0
            })
        
        # Commandes par statut
        orders_by_status = {}
        for status_code, status_label in PurchaseOrder.STATUS_CHOICES:
            count = PurchaseOrder.objects.filter(status=status_code).count()
            if count > 0:
                orders_by_status[status_code] = count
        
        # Alertes
        alerts = {
            'overdue_invoices': overdue_invoices,
            'pending_receipts': pending_receipts,
            'pending_orders': pending_orders,
        }
        
        return Response({
            'orders': {
                'total': total_orders,
                'pending': pending_orders,
                'this_month': orders_this_month,
                'total_amount': total_amount,
                'amount_this_month': amount_this_month,
                'by_status': orders_by_status,
            },
            'receipts': {
                'total': total_received,
                'pending': pending_receipts,
                'received_amount': received_amount,
                'remaining_to_receive': remaining_to_receive,
            },
            'invoices': {
                'total': total_invoices,
                'unpaid': unpaid_invoices,
                'overdue': overdue_invoices,
                'total_invoiced': total_invoiced,
                'total_paid': total_paid,
                'total_remaining_to_pay': total_remaining_to_pay,
            },
            'suppliers': {
                'total': Supplier.objects.filter(is_active=True).count(),
                'top': top_suppliers_data,
            },
            'alerts': alerts,
        })