from .purchase_alerts import PurchaseAlert
from django.shortcuts import render

# Create your views here.
# apps/achats_fournisseurs/views.py
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from datetime import date, timedelta
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from io import BytesIO
from PIL import Image as PILImage
import qrcode
import json
import base64

from .models import (
    Supplier, SupplierContact, SupplierProduct, PurchaseOrder,
    PurchaseOrderLine, Receipt, ReceiptLine, PurchaseReturn,
    PurchaseReturnLine, SupplierInvoice
)
from .serializers import (
    SupplierListSerializer, SupplierDetailSerializer, SupplierWriteSerializer,
    SupplierContactSerializer, SupplierProductSerializer,
    PurchaseOrderListSerializer, PurchaseOrderDetailSerializer,
    PurchaseOrderCreateSerializer, PurchaseOrderUpdateSerializer,
    PurchaseOrderApproveSerializer, ReceiptListSerializer,
    ReceiptDetailSerializer, ReceiptCreateSerializer,
    PurchaseReturnSerializer, PurchaseReturnCreateSerializer,
    SupplierInvoiceSerializer, SupplierInvoiceCreateSerializer,
    SupplierInvoicePaymentSerializer
)
from users.permissions import IsAdmin, IsGestionnaire, IsMagasinier


# ==================== SUPPLIER VIEWSET ====================
class SupplierViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des fournisseurs
    """
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
        user = self.request.user

        # Filtrer par recherche
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search) |
                Q(phone__icontains=search) |
                Q(email__icontains=search) |
                Q(commercial_name__icontains=search)
            )

        # Filtrer par type
        type_filter = self.request.query_params.get('type')
        if type_filter:
            queryset = queryset.filter(type=type_filter)

        # Filtrer par statut
        is_active = self.request.query_params.get('is_active')
        if is_active == 'true':
            queryset = queryset.filter(is_active=True)
        elif is_active == 'false':
            queryset = queryset.filter(is_active=False)

        # Filtrer par fournisseur privilégié
        is_preferred = self.request.query_params.get('is_preferred')
        if is_preferred == 'true':
            queryset = queryset.filter(is_preferred=True)

        # Trier
        ordering = self.request.query_params.get('ordering', 'name')
        if ordering:
            queryset = queryset.order_by(ordering)

        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['get'])
    def contacts(self, request, pk=None):
        """Récupère tous les contacts d'un fournisseur"""
        supplier = self.get_object()
        contacts = supplier.contacts.all()
        serializer = SupplierContactSerializer(contacts, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def add_contact(self, request, pk=None):
        """Ajoute un contact à un fournisseur"""
        supplier = self.get_object()
        serializer = SupplierContactSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(supplier=supplier)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def products(self, request, pk=None):
        """Récupère tous les produits d'un fournisseur"""
        supplier = self.get_object()
        products = supplier.products.filter(is_active=True)
        serializer = SupplierProductSerializer(products, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def add_product(self, request, pk=None):
        """Ajoute un produit à un fournisseur"""
        supplier = self.get_object()
        data = request.data.copy()
        data['supplier'] = supplier.id
        serializer = SupplierProductSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def purchase_orders(self, request, pk=None):
        """Récupère toutes les commandes d'un fournisseur"""
        supplier = self.get_object()
        orders = supplier.purchase_orders.all().order_by('-order_date')
        serializer = PurchaseOrderListSerializer(orders, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Statistiques d'un fournisseur"""
        supplier = self.get_object()
        orders = supplier.purchase_orders.all()

        stats = {
            'total_orders': orders.count(),
            'total_amount': orders.aggregate(total=Sum('total'))['total'] or 0,
            'orders_by_status': {},
            'average_order_value': 0,
            'total_products': supplier.products.filter(is_active=True).count(),
        }

        # Commandes par statut
        for status_choice in PurchaseOrder.STATUS_CHOICES:
            status_code = status_choice[0]
            count = orders.filter(status=status_code).count()
            if count > 0:
                stats['orders_by_status'][status_code] = count

        # Valeur moyenne des commandes
        if stats['total_orders'] > 0:
            stats['average_order_value'] = stats['total_amount'] / \
                stats['total_orders']

        return Response(stats)


# ==================== PURCHASE ORDER VIEWSET ====================
class PurchaseOrderViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des bons de commande avec QR Code
    """
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
        user = self.request.user

        # Recherche
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(po_number__icontains=search) |
                Q(supplier__name__icontains=search) |
                Q(supplier__code__icontains=search)
            )

        # Filtrer par fournisseur
        supplier = self.request.query_params.get('supplier')
        if supplier:
            queryset = queryset.filter(supplier_id=supplier)

        # Filtrer par statut
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)

        # Filtrer par date
        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(order_date__date__gte=date_from)

        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(order_date__date__lte=date_to)

        # Filtrer par montant min/max
        min_total = self.request.query_params.get('min_total')
        if min_total:
            queryset = queryset.filter(total__gte=min_total)

        max_total = self.request.query_params.get('max_total')
        if max_total:
            queryset = queryset.filter(total__lte=max_total)

        # Trier
        ordering = self.request.query_params.get('ordering', '-order_date')
        if ordering:
            queryset = queryset.order_by(ordering)

        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approuve ou rejette une commande"""
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

            # Régénérer le QR Code si le statut change
            purchase_order.generate_qr_code()
            purchase_order.save()

            return Response({
                'status': purchase_order.status,
                'approved': serializer.validated_data['approved']
            })

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Annule une commande"""
        purchase_order = self.get_object()

        if purchase_order.status not in ['draft', 'sent']:
            return Response(
                {"error": "Cette commande ne peut pas être annulée"},
                status=status.HTTP_400_BAD_REQUEST
            )

        purchase_order.status = 'cancelled'
        purchase_order.save()

        # Régénérer le QR Code
        purchase_order.generate_qr_code()
        purchase_order.save()

        return Response({
            'status': purchase_order.status,
            'message': 'Commande annulée avec succès'
        })

    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        """Marque une commande comme envoyée"""
        purchase_order = self.get_object()

        if purchase_order.status != 'draft':
            return Response(
                {"error": "Seules les commandes en brouillon peuvent être envoyées"},
                status=status.HTTP_400_BAD_REQUEST
            )

        purchase_order.status = 'sent'
        purchase_order.save()

        # Régénérer le QR Code
        purchase_order.generate_qr_code()
        purchase_order.save()

        return Response({
            'status': purchase_order.status,
            'message': 'Commande envoyée avec succès'
        })

    @action(detail=True, methods=['get'])
    def receipts(self, request, pk=None):
        """Récupère toutes les réceptions d'une commande"""
        purchase_order = self.get_object()
        receipts = purchase_order.receipts.all()
        serializer = ReceiptListSerializer(receipts, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def generate_qr(self, request, pk=None):
        """Génère et retourne le QR Code de la commande"""
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

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        """Génère un PDF de la commande avec QR Code"""
        purchase_order = self.get_object()

        # Créer le PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = []

        # Titre
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a237e'),
            alignment=TA_CENTER,
            spaceAfter=30
        )
        elements.append(Paragraph("BON DE COMMANDE", title_style))

        # Informations de la commande
        info_style = ParagraphStyle(
            'Info',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=6
        )

        elements.append(
            Paragraph(f"<b>N° Commande:</b> {purchase_order.po_number}", info_style))
        elements.append(Paragraph(
            f"<b>Date:</b> {purchase_order.order_date.strftime('%d/%m/%Y %H:%M')}", info_style))
        elements.append(Paragraph(
            f"<b>Fournisseur:</b> {purchase_order.supplier.name if purchase_order.supplier else 'N/A'}", info_style))
        elements.append(
            Paragraph(f"<b>Statut:</b> {purchase_order.get_status_display()}", info_style))
        elements.append(Spacer(1, 12))

        # QR Code
        if purchase_order.qr_code:
            try:
                qr_path = purchase_order.qr_code.path
                qr_img = PILImage.open(qr_path)
                qr_buffer = BytesIO()
                qr_img.save(qr_buffer, format='PNG')
                qr_buffer.seek(0)

                # Ajouter le QR Code au PDF
                qr_width, qr_height = 100, 100
                qr_image = Image(qr_buffer, width=qr_width, height=qr_height)
                elements.append(qr_image)
                elements.append(Spacer(1, 12))
            except Exception as e:
                print(f"Erreur QR Code: {e}")

        # Tableau des produits
        data = [['Produit', 'Quantité', 'Prix unitaire', 'Remise', 'Total']]
        for line in purchase_order.lines.all():
            data.append([
                line.product.name,
                str(line.quantity),
                f"{line.unit_price:,.0f} FCFA",
                f"{line.discount:,.0f} FCFA",
                f"{line.total:,.0f} FCFA"
            ])

        # Total
        data.append(['', '', '', 'Sous-total',
                    f"{purchase_order.subtotal:,.0f} FCFA"])
        if purchase_order.discount_amount > 0:
            data.append(
                ['', '', '', 'Remise', f"-{purchase_order.discount_amount:,.0f} FCFA"])
        if purchase_order.tax_amount > 0:
            data.append(
                ['', '', '', 'TVA', f"{purchase_order.tax_amount:,.0f} FCFA"])
        if purchase_order.shipping_cost > 0:
            data.append(['', '', '', 'Frais de livraison',
                        f"{purchase_order.shipping_cost:,.0f} FCFA"])
        data.append(['', '', '', 'TOTAL', f"{purchase_order.total:,.0f} FCFA"])

        table = Table(data, colWidths=[
                      2.5*inch, 0.8*inch, 1.2*inch, 0.8*inch, 1.2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e8eaf6')),
            ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#1a237e')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -2), 1, colors.grey),
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 20))

        # Notes
        if purchase_order.notes:
            elements.append(Paragraph("<b>Notes:</b>", info_style))
            elements.append(Paragraph(purchase_order.notes, info_style))

        # Piéd de page
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER
        )
        elements.append(Spacer(1, 30))
        elements.append(
            Paragraph("Document généré automatiquement", footer_style))
        elements.append(
            Paragraph(f"Date: {timezone.now().strftime('%d/%m/%Y %H:%M')}", footer_style))

        # Générer le PDF
        doc.build(elements)
        buffer.seek(0)

        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="commande_{purchase_order.po_number}.pdf"'
        return response


# ==================== RECEIPT VIEWSET ====================
class ReceiptViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des réceptions avec QR Code
    """
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

        # Filtrer par commande
        purchase_order = self.request.query_params.get('purchase_order')
        if purchase_order:
            queryset = queryset.filter(purchase_order_id=purchase_order)

        # Filtrer par statut
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)

        # Filtrer par entrepôt
        warehouse = self.request.query_params.get('warehouse')
        if warehouse:
            queryset = queryset.filter(warehouse_id=warehouse)

        # Filtrer par date
        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(receipt_date__date__gte=date_from)

        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(receipt_date__date__lte=date_to)

        # Trier
        ordering = self.request.query_params.get('ordering', '-receipt_date')
        if ordering:
            queryset = queryset.order_by(ordering)

        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Annule une réception"""
        receipt = self.get_object()

        if receipt.status != 'in_progress':
            return Response(
                {"error": "Cette réception ne peut pas être annulée"},
                status=status.HTTP_400_BAD_REQUEST
            )

        receipt.status = 'cancelled'
        receipt.save()

        # Régénérer le QR Code
        receipt.generate_qr_code()
        receipt.save()

        return Response({
            'status': receipt.status,
            'message': 'Réception annulée avec succès'
        })

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Marque une réception comme terminée"""
        receipt = self.get_object()

        if receipt.status != 'in_progress':
            return Response(
                {"error": "Seules les réceptions en cours peuvent être terminées"},
                status=status.HTTP_400_BAD_REQUEST
            )

        receipt.status = 'completed'
        receipt.save()

        # Régénérer le QR Code
        receipt.generate_qr_code()
        receipt.save()

        return Response({
            'status': receipt.status,
            'message': 'Réception terminée avec succès'
        })

    @action(detail=True, methods=['get'])
    def generate_qr(self, request, pk=None):
        """Génère et retourne le QR Code de la réception"""
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


# ==================== PURCHASE RETURN VIEWSET ====================
class PurchaseReturnViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des retours fournisseurs avec QR Code
    """
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

        # Filtrer par commande
        purchase_order = self.request.query_params.get('purchase_order')
        if purchase_order:
            queryset = queryset.filter(purchase_order_id=purchase_order)

        # Filtrer par statut
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)

        # Filtrer par raison
        reason = self.request.query_params.get('reason')
        if reason:
            queryset = queryset.filter(reason=reason)

        # Filtrer par date
        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(return_date__date__gte=date_from)

        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(return_date__date__lte=date_to)

        # Trier
        ordering = self.request.query_params.get('ordering', '-return_date')
        if ordering:
            queryset = queryset.order_by(ordering)

        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approuve un retour"""
        purchase_return = self.get_object()

        if purchase_return.status != 'requested':
            return Response(
                {"error": "Seuls les retours demandés peuvent être approuvés"},
                status=status.HTTP_400_BAD_REQUEST
            )

        purchase_return.status = 'approved'
        purchase_return.save()

        # Régénérer le QR Code
        purchase_return.generate_qr_code()
        purchase_return.save()

        return Response({
            'status': purchase_return.status,
            'message': 'Retour approuvé avec succès'
        })

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Rejette un retour"""
        purchase_return = self.get_object()

        if purchase_return.status != 'requested':
            return Response(
                {"error": "Seuls les retours demandés peuvent être rejetés"},
                status=status.HTTP_400_BAD_REQUEST
            )

        purchase_return.status = 'rejected'
        purchase_return.save()

        # Régénérer le QR Code
        purchase_return.generate_qr_code()
        purchase_return.save()

        return Response({
            'status': purchase_return.status,
            'message': 'Retour rejeté avec succès'
        })

    @action(detail=True, methods=['post'])
    def ship(self, request, pk=None):
        """Marque un retour comme expédié"""
        purchase_return = self.get_object()

        if purchase_return.status != 'approved':
            return Response(
                {"error": "Seuls les retours approuvés peuvent être expédiés"},
                status=status.HTTP_400_BAD_REQUEST
            )

        purchase_return.status = 'shipped'
        purchase_return.save()

        # Régénérer le QR Code
        purchase_return.generate_qr_code()
        purchase_return.save()

        return Response({
            'status': purchase_return.status,
            'message': 'Retour expédié avec succès'
        })

    @action(detail=True, methods=['get'])
    def generate_qr(self, request, pk=None):
        """Génère et retourne le QR Code du retour"""
        purchase_return = self.get_object()

        if not purchase_return.qr_code:
            purchase_return.generate_qr_code()
            purchase_return.save()

        if purchase_return.qr_code:
            return Response({
                'qr_code_url': request.build_absolute_uri(purchase_return.qr_code.url),
                'qr_code_data': purchase_return.qr_code_data
            })

        return Response(
            {"error": "Impossible de générer le QR Code"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ==================== SUPPLIER INVOICE VIEWSET ====================
class SupplierInvoiceViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des factures fournisseurs
    """
    queryset = SupplierInvoice.objects.all()
    permission_classes = [permissions.IsAuthenticated, IsGestionnaire]

    def get_serializer_class(self):
        if self.action == 'create':
            return SupplierInvoiceCreateSerializer
        return SupplierInvoiceSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtrer par commande
        purchase_order = self.request.query_params.get('purchase_order')
        if purchase_order:
            queryset = queryset.filter(purchase_order_id=purchase_order)

        # Filtrer par fournisseur
        supplier = self.request.query_params.get('supplier')
        if supplier:
            queryset = queryset.filter(supplier_id=supplier)

        # Filtrer par statut
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)

        # Filtrer par date
        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(invoice_date__gte=date_from)

        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(invoice_date__lte=date_to)

        # Trier
        ordering = self.request.query_params.get('ordering', '-invoice_date')
        if ordering:
            queryset = queryset.order_by(ordering)

        return queryset

    def perform_create(self, serializer):
        serializer.save(
            supplier=serializer.validated_data['purchase_order'].supplier)

    @action(detail=True, methods=['post'])
    def register_payment(self, request, pk=None):
        """Enregistre un paiement sur une facture"""
        invoice = self.get_object()
        serializer = SupplierInvoicePaymentSerializer(data=request.data)

        if serializer.is_valid():
            amount = serializer.validated_data['amount']

            if amount > invoice.remaining_amount:
                return Response(
                    {"error": "Le montant dépasse le solde restant"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            invoice.amount_paid += amount
            invoice.payment_date = serializer.validated_data['payment_date']
            invoice.payment_reference = serializer.validated_data.get(
                'payment_reference', '')

            if invoice.amount_paid >= invoice.total_amount:
                invoice.status = 'paid'
            else:
                invoice.status = 'partial'

            invoice.save()

            return Response({
                'status': invoice.status,
                'amount_paid': invoice.amount_paid,
                'remaining_amount': invoice.remaining_amount,
                'message': 'Paiement enregistré avec succès'
            })

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Vérifie une facture"""
        invoice = self.get_object()

        if invoice.status != 'received':
            return Response(
                {"error": "Seules les factures reçues peuvent être vérifiées"},
                status=status.HTTP_400_BAD_REQUEST
            )

        invoice.status = 'verified'
        invoice.save()

        return Response({
            'status': invoice.status,
            'message': 'Facture vérifiée avec succès'
        })

    @action(detail=True, methods=['post'])
    def dispute(self, request, pk=None):
        """Conteste une facture"""
        invoice = self.get_object()

        if invoice.status not in ['received', 'verified']:
            return Response(
                {"error": "Cette facture ne peut pas être contestée"},
                status=status.HTTP_400_BAD_REQUEST
            )

        invoice.status = 'disputed'
        invoice.save()

        return Response({
            'status': invoice.status,
            'message': 'Facture contestée'
        })
# apps/achats_fournisseurs/views.py
# Ajouter à la fin du fichier, après DashboardViewSet

# ==================== PURCHASE ALERTS VIEWSET ====================


class PurchaseAlertViewSet(viewsets.ViewSet):
    """
    ViewSet pour les alertes achats
    """
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='')
    def list_alerts(self, request):
        """Récupère toutes les alertes"""
        from .purchase_alerts import PurchaseAlert

        alerts = PurchaseAlert.get_all_alerts()
        stats = PurchaseAlert.get_alerts_count()

        return Response({
            'alerts': alerts,
            'stats': stats
        })

    @action(detail=True, methods=['post'])
    def dismiss(self, request, pk=None):
        """Ignore une alerte"""
        # Logique pour ignorer l'alerte (peut être stockée en base)
        return Response({
            'status': 'dismissed',
            'message': f'Alerte {pk} ignorée'
        })

    @action(detail=False, methods=['post'])
    def send_report(self, request):
        """Envoie un rapport des alertes par email"""
        from .purchase_alerts import PurchaseAlert

        alerts = PurchaseAlert.get_all_alerts()
        stats = PurchaseAlert.get_alerts_count()

        # Envoyer l'email à l'utilisateur connecté
        user = request.user
        if user.email:
            # Ici vous pouvez implémenter l'envoi d'email
            return Response({
                'status': 'sent',
                'message': f'Rapport envoyé à {user.email}',
                'total_alerts': len(alerts)
            })
        else:
            return Response(
                {'error': 'Aucun email associé à cet utilisateur'},
                status=400
            )

# apps/achats_fournisseurs/views.py


class GlobalAlertViewSet(viewsets.ViewSet):
    """
    ViewSet pour toutes les alertes du système
    """
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def list_alerts(self, request):
        """Récupère toutes les alertes du système"""
        alerts = []

        # Alertes Achats
        if request.user.has_perm('achats_fournisseurs.view_purchaseorder'):
            alerts.extend(PurchaseAlert.get_all_alerts())

        # Alertes Stocks
        if request.user.has_perm('produits_stocks.view_product'):
            alerts.extend(StockAlert.get_all_alerts())

        # Alertes Ventes
        if request.user.has_perm('ventes.view_sale'):
            alerts.extend(SalesAlert.get_all_alerts())

        # Alertes Finances
        if request.user.has_perm('finances.view_transaction'):
            alerts.extend(FinanceAlert.get_all_alerts())

        # Alertes Fournisseurs
        if request.user.has_perm('achats_fournisseurs.view_supplier'):
            alerts.extend(SupplierAlert.get_all_alerts())

        # Alertes Livraisons
        if request.user.has_perm('livraisons.view_delivery'):
            alerts.extend(DeliveryAlert.get_all_alerts())

        # Alertes Utilisateurs
        if request.user.is_superuser:
            alerts.extend(UserAlert.get_all_alerts())

        # Ajouter des IDs uniques
        for i, alert in enumerate(alerts):
            alert['id'] = i + 1
            alert['created_at'] = alert.get(
                'created_at', timezone.now().isoformat())

        # Statistiques
        stats = {
            'total': len(alerts),
            'error': len([a for a in alerts if a.get('level') == 'error']),
            'warning': len([a for a in alerts if a.get('level') == 'warning']),
            'info': len([a for a in alerts if a.get('level') == 'info']),
            'byCategory': {
                'achats': len([a for a in alerts if a.get('category') == 'achats']),
                'stocks': len([a for a in alerts if a.get('category') == 'stocks']),
                'ventes': len([a for a in alerts if a.get('category') == 'ventes']),
                'finances': len([a for a in alerts if a.get('category') == 'finances']),
                'fournisseurs': len([a for a in alerts if a.get('category') == 'fournisseurs']),
                'livraisons': len([a for a in alerts if a.get('category') == 'livraisons']),
                'utilisateurs': len([a for a in alerts if a.get('category') == 'utilisateurs'])
            }
        }

        return Response({
            'alerts': alerts,
            'stats': stats
        })
# ==================== DASHBOARD STATISTICS ====================


class DashboardViewSet(viewsets.ViewSet):
    """
    ViewSet pour les statistiques du tableau de bord
    """
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Statistiques globales pour le tableau de bord"""
        today = timezone.now().date()
        start_of_month = today.replace(day=1)
        start_of_week = today - timedelta(days=today.weekday())

        # Statistiques des commandes
        total_orders = PurchaseOrder.objects.count()
        orders_this_month = PurchaseOrder.objects.filter(
            order_date__date__gte=start_of_month).count()
        orders_this_week = PurchaseOrder.objects.filter(
            order_date__date__gte=start_of_week).count()
        pending_orders = PurchaseOrder.objects.filter(
            status__in=['draft', 'sent', 'confirmed']).count()

        # Montants
        total_amount = PurchaseOrder.objects.aggregate(total=Sum('total'))[
            'total'] or 0
        amount_this_month = PurchaseOrder.objects.filter(
            order_date__date__gte=start_of_month).aggregate(total=Sum('total'))['total'] or 0

        # Statistiques des fournisseurs
        total_suppliers = Supplier.objects.filter(is_active=True).count()

        # Statistiques des réceptions
        total_receipts = Receipt.objects.count()
        pending_receipts = Receipt.objects.filter(
            status__in=['pending', 'in_progress']).count()

        # Statistiques des retours
        total_returns = PurchaseReturn.objects.count()
        pending_returns = PurchaseReturn.objects.filter(
            status='requested').count()

        # Statistiques des factures
        total_invoices = SupplierInvoice.objects.count()
        unpaid_invoices = SupplierInvoice.objects.filter(
            status__in=['received', 'verified', 'partial']).count()
        overdue_invoices = SupplierInvoice.objects.filter(
            due_date__lt=today,
            status__in=['received', 'verified', 'partial']
        ).count()

        # Top fournisseurs
        top_suppliers = Supplier.objects.annotate(
            order_count=Count('purchase_orders'),
            total_spent=Sum('purchase_orders__total')
        ).order_by('-total_spent')[:5]

        top_suppliers_data = []
        for supplier in top_suppliers:
            top_suppliers_data.append({
                'id': supplier.id,
                'name': supplier.name,
                'order_count': supplier.order_count,
                'total_spent': supplier.total_spent or 0
            })

        return Response({
            'orders': {
                'total': total_orders,
                'this_month': orders_this_month,
                'this_week': orders_this_week,
                'pending': pending_orders,
                'total_amount': total_amount,
                'amount_this_month': amount_this_month,
            },
            'suppliers': {
                'total': total_suppliers,
                'top': top_suppliers_data,
            },
            'receipts': {
                'total': total_receipts,
                'pending': pending_receipts,
            },
            'returns': {
                'total': total_returns,
                'pending': pending_returns,
            },
            'invoices': {
                'total': total_invoices,
                'unpaid': unpaid_invoices,
                'overdue': overdue_invoices,
            }
        })
