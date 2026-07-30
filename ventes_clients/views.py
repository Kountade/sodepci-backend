# apps/ventes_clients/views.py
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q, Sum, Count
from django.utils import timezone
from datetime import date, timedelta
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER
# apps/ventes_clients/views.py

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q, Sum, Count
from django.utils import timezone
from datetime import date, timedelta
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER
from io import BytesIO
from PIL import Image as PILImage
import json

from .models import (
    Client, Vente, LigneVente, Paiement, Facture,
    Avoir, Taxe, Remise, Devis, LigneDevis
)
from .serializers import (
    ClientSerializer, ClientListSerializer,
    VenteListSerializer, VenteDetailSerializer,
    VenteCreateSerializer, VenteUpdateSerializer,
    VenteStatusUpdateSerializer,
    LigneVenteSerializer, LigneVenteCreateSerializer,
    PaiementSerializer, PaiementCreateSerializer,
    FactureSerializer, FactureCreateSerializer,
    AvoirSerializer, AvoirCreateSerializer,
    TaxeSerializer, RemiseSerializer,
    DevisListSerializer, DevisDetailSerializer,
    DevisCreateSerializer, DevisUpdateSerializer,
    DevisStatusUpdateSerializer,
    LigneDevisSerializer, LigneDevisCreateSerializer
)
from users.permissions import IsAdmin, IsGestionnaire, IsCaissier
from produits_stocks.models import Stock, StockMovement, Warehouse

from io import BytesIO
from PIL import Image as PILImage
import json

from .models import (
    Client, Vente, LigneVente, Paiement, Facture,
    Avoir, Taxe, Remise, Devis, LigneDevis
)
from .serializers import (
    ClientSerializer, ClientListSerializer,
    VenteListSerializer, VenteDetailSerializer,
    VenteCreateSerializer, VenteUpdateSerializer,
    VenteStatusUpdateSerializer,
    LigneVenteSerializer, LigneVenteCreateSerializer,
    PaiementSerializer, PaiementCreateSerializer,
    FactureSerializer, FactureCreateSerializer,
    AvoirSerializer, AvoirCreateSerializer,
    TaxeSerializer, RemiseSerializer,
    DevisListSerializer, DevisDetailSerializer,
    DevisCreateSerializer, DevisUpdateSerializer,
    DevisStatusUpdateSerializer,
    LigneDevisSerializer, LigneDevisCreateSerializer
)
from users.permissions import IsAdmin, IsGestionnaire, IsCaissier
from produits_stocks.models import Stock, StockMovement, Warehouse


# ==================== CLIENT VIEWSET ====================
class ClientViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des clients
    """
    queryset = Client.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return ClientListSerializer
        return ClientSerializer

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

        statut = self.request.query_params.get('statut')
        if statut:
            queryset = queryset.filter(statut=statut)

        is_favorite = self.request.query_params.get('is_favorite')
        if is_favorite == 'true':
            queryset = queryset.filter(is_favorite=True)

        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['get'])
    def sales(self, request, pk=None):
        client = self.get_object()
        sales = client.sales.all().order_by('-sale_date')
        serializer = VenteListSerializer(sales, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def devis(self, request, pk=None):
        client = self.get_object()
        devis = client.devis.all().order_by('-devis_date')
        serializer = DevisListSerializer(devis, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        client = self.get_object()
        sales = client.sales.all()

        stats = {
            'total_orders': sales.count(),
            'total_purchases': sales.aggregate(total=Sum('total'))['total'] or 0,
            'orders_by_status': {},
            'average_order_value': 0,
        }

        for status_choice in Vente.STATUS_CHOICES:
            status_code = status_choice[0]
            count = sales.filter(status=status_code).count()
            if count > 0:
                stats['orders_by_status'][status_code] = count

        if stats['total_orders'] > 0:
            stats['average_order_value'] = stats['total_purchases'] / \
                stats['total_orders']

        return Response(stats)


# ==================== DEVIS VIEWSET ====================
class DevisViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des devis
    """
    queryset = Devis.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return DevisListSerializer
        elif self.action == 'create':
            return DevisCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return DevisUpdateSerializer
        return DevisDetailSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_queryset(self):
        queryset = super().get_queryset()

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(devis_number__icontains=search) |
                Q(client__name__icontains=search) |
                Q(client_name__icontains=search)
            )

        client = self.request.query_params.get('client')
        if client:
            queryset = queryset.filter(client_id=client)

        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)

        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(devis_date__date__gte=date_from)

        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(devis_date__date__lte=date_to)

        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        devis = self.get_object()
        serializer = DevisStatusUpdateSerializer(data=request.data)

        if serializer.is_valid():
            old_status = devis.status
            new_status = serializer.validated_data['status']
            notes = serializer.validated_data.get('notes', '')

            devis.status = new_status
            if notes:
                devis.notes = devis.notes + '\n' + notes if devis.notes else notes
            devis.save()

            return Response({
                'status': devis.status,
                'old_status': old_status,
                'message': f'Statut changé de {old_status} à {new_status}',
                'devis_number': devis.devis_number
            })

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def convert_to_sale(self, request, pk=None):
        devis = self.get_object()

        if devis.status != 'accepted':
            return Response(
                {"error": "Seul un devis accepté peut être converti en vente"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if devis.sale:
            return Response(
                {"error": "Ce devis a déjà été converti en vente"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not devis.warehouse:
            return Response(
                {"error": "L'entrepôt doit être défini pour convertir le devis en vente"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            vente = devis.convert_to_sale(user=request.user)

            return Response({
                'message': 'Devis converti en vente avec succès',
                'sale': VenteDetailSerializer(vente, context={'request': request}).data,
                'devis': DevisDetailSerializer(devis, context={'request': request}).data
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {"error": f"Erreur lors de la conversion: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def generate_qr(self, request, pk=None):
        devis = self.get_object()

        if not devis.qr_code:
            devis.generate_qr_code()
            devis.save()

        if devis.qr_code:
            return Response({
                'qr_code_url': request.build_absolute_uri(devis.qr_code.url),
                'qr_code_data': devis.qr_code_data
            })

        return Response(
            {"error": "Impossible de générer le QR Code"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        devis = self.get_object()
        # ... code existant pour PDF ...


# ==================== VENTE VIEWSET ====================

# ==================== VENTE VIEWSET ====================

class VenteViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des ventes
    """
    queryset = Vente.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return VenteListSerializer
        elif self.action == 'create':
            return VenteCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return VenteUpdateSerializer
        return VenteDetailSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_queryset(self):
        queryset = super().get_queryset()

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(invoice_number__icontains=search) |
                Q(client__name__icontains=search) |
                Q(client_name__icontains=search) |
                Q(order_number__icontains=search)
            )

        client = self.request.query_params.get('client')
        if client:
            queryset = queryset.filter(client_id=client)

        status_filter = self.request.query_params.get('status')
        if status_filter:
            status_list = status_filter.split(',')
            queryset = queryset.filter(status__in=status_list)

        payment_status = self.request.query_params.get('payment_status')
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)

        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(sale_date__date__gte=date_from)

        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(sale_date__date__lte=date_to)

        warehouse = self.request.query_params.get('warehouse')
        if warehouse:
            queryset = queryset.filter(warehouse_id=warehouse)

        min_total = self.request.query_params.get('min_total')
        if min_total:
            queryset = queryset.filter(total__gte=min_total)

        max_total = self.request.query_params.get('max_total')
        if max_total:
            queryset = queryset.filter(total__lte=max_total)

        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """
        Confirme une vente et déduit le stock UNE SEULE FOIS
        """
        vente = self.get_object()

        if vente.status != 'draft':
            return Response(
                {"error": "Seule une vente en brouillon peut être confirmée"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not vente.warehouse:
            return Response(
                {"error": "Un entrepôt est requis pour confirmer la vente"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Vérifier le stock pour chaque ligne
            stock_errors = []
            for line in vente.lines.all():
                stock = Stock.objects.filter(
                    product=line.product,
                    warehouse=vente.warehouse
                ).first()

                if not stock or stock.available_quantity < line.quantity:
                    stock_errors.append(
                        f"{line.product.name}: disponible {stock.available_quantity if stock else 0}, demandé {line.quantity}"
                    )

            if stock_errors:
                return Response({
                    "error": "Stock insuffisant pour les produits suivants:",
                    "details": stock_errors
                }, status=status.HTTP_400_BAD_REQUEST)

            # Si pas de client, définir un nom par défaut
            if not vente.client and not vente.client_name:
                vente.client_name = "Client anonyme"
                vente.save(update_fields=['client_name'])

            # ✅ Confirmer la vente - UN SEUL appel à save()
            vente.status = 'confirmed'
            vente.save()

            # Vérifier si la facture a été générée
            facture = Facture.objects.filter(sale=vente).first()

            return Response({
                'status': vente.status,
                'message': 'Vente confirmée avec succès',
                'invoice_number': vente.invoice_number,
                'facture_generée': facture is not None,
                'facture_number': facture.invoice_number if facture else None
            })

        except ValueError as e:
            vente.status = 'draft'
            vente.save(update_fields=['status'])
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": f"Erreur lors de la confirmation: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """
        Met à jour le statut d'une vente
        """
        vente = self.get_object()

        status_value = request.data.get('status')
        notes = request.data.get('notes', '')

        if not status_value:
            return Response(
                {"error": "Le statut est requis"},
                status=status.HTTP_400_BAD_REQUEST
            )

        allowed_statuses = ['draft', 'confirmed',
                            'paid', 'delivered', 'cancelled', 'returned']
        if status_value not in allowed_statuses:
            return Response(
                {"error": f"Statut invalide. Choisir parmi: {', '.join(allowed_statuses)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        old_status = vente.status
        is_confirming = old_status == 'draft' and status_value == 'confirmed'

        if is_confirming:
            if not vente.warehouse:
                return Response(
                    {"error": "Un entrepôt est requis pour confirmer la vente"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            stock_errors = []
            for line in vente.lines.all():
                stock = Stock.objects.filter(
                    product=line.product,
                    warehouse=vente.warehouse
                ).first()

                if not stock or stock.available_quantity < line.quantity:
                    stock_errors.append(
                        f"{line.product.name}: disponible {stock.available_quantity if stock else 0}, demandé {line.quantity}"
                    )

            if stock_errors:
                return Response({
                    "error": "Stock insuffisant pour les produits suivants:",
                    "details": stock_errors
                }, status=status.HTTP_400_BAD_REQUEST)

        try:
            if not vente.client and not vente.client_name:
                vente.client_name = "Client anonyme"
                vente.save(update_fields=['client_name'])

            vente.status = status_value
            if notes:
                vente.notes = vente.notes + '\n' + notes if vente.notes else notes

            vente.save()

            facture_generée = Facture.objects.filter(sale=vente).exists()
            facture = Facture.objects.filter(
                sale=vente).first() if facture_generée else None

            return Response({
                'status': vente.status,
                'old_status': old_status,
                'message': f'Statut changé de {old_status} à {status_value}',
                'facture_generée': facture_generée,
                'facture_number': facture.invoice_number if facture else None,
                'invoice_number': vente.invoice_number
            })

        except ValueError as e:
            if is_confirming:
                vente.status = 'draft'
                vente.save(update_fields=['status'])
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": f"Erreur inattendue: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def mark_paid(self, request, pk=None):
        vente = self.get_object()

        if vente.status not in ['confirmed', 'delivered']:
            return Response(
                {"error": "Seule une vente confirmée ou livrée peut être marquée comme payée"},
                status=status.HTTP_400_BAD_REQUEST
            )

        vente.status = 'paid'
        vente.payment_status = 'paid'
        vente.amount_paid = vente.total
        vente.amount_due = 0
        vente.save()

        return Response({
            'status': vente.status,
            'payment_status': vente.payment_status,
            'message': 'Vente marquée comme payée',
            'invoice_number': vente.invoice_number
        })

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        vente = self.get_object()

        if vente.status in ['paid', 'delivered']:
            return Response(
                {"error": "Cette vente ne peut pas être annulée car elle est déjà payée ou livrée"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            old_status = vente.status

            if old_status == 'confirmed':
                vente.restore_stock()

            vente.status = 'cancelled'
            vente.save()
            vente.generate_qr_code()
            vente.save(update_fields=['qr_code', 'qr_code_data'])

            return Response({
                'status': vente.status,
                'old_status': old_status,
                'message': 'Vente annulée avec succès',
                'stock_restored': old_status == 'confirmed'
            })

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def deliver(self, request, pk=None):
        vente = self.get_object()

        if vente.status != 'confirmed':
            return Response(
                {"error": "Seule une vente confirmée peut être marquée comme livrée"},
                status=status.HTTP_400_BAD_REQUEST
            )

        vente.status = 'delivered'
        vente.delivery_date = timezone.now()
        vente.delivery_status = 'delivered'

        if request.data.get('tracking_number'):
            vente.tracking_number = request.data.get('tracking_number')

        vente.save()

        return Response({
            'status': vente.status,
            'delivery_status': vente.delivery_status,
            'delivery_date': vente.delivery_date,
            'message': 'Vente marquée comme livrée',
            'invoice_number': vente.invoice_number
        })

    @action(detail=True, methods=['post'])
    def return_sale(self, request, pk=None):
        vente = self.get_object()

        if vente.status not in ['delivered', 'paid']:
            return Response(
                {"error": "Seules les ventes livrées ou payées peuvent être retournées"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            vente.restore_stock()
            vente.status = 'returned'
            vente.save()

            return Response({
                'status': vente.status,
                'message': 'Vente retournée avec succès',
                'stock_restored': True,
                'invoice_number': vente.invoice_number
            })

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['get'])
    def payments(self, request, pk=None):
        vente = self.get_object()
        payments = []
        for facture in vente.invoices.all():
            for paiement in facture.paiements.all():
                payments.append(paiement)

        serializer = PaiementSerializer(
            payments, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def invoices(self, request, pk=None):
        vente = self.get_object()
        factures = vente.invoices.all()
        serializer = FactureSerializer(
            factures, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def generate_qr(self, request, pk=None):
        vente = self.get_object()

        if not vente.qr_code:
            vente.generate_qr_code()
            vente.save()

        if vente.qr_code:
            return Response({
                'qr_code_url': request.build_absolute_uri(vente.qr_code.url),
                'qr_code_data': vente.qr_code_data,
                'invoice_number': vente.invoice_number
            })

        return Response(
            {"error": "Impossible de générer le QR Code"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    @action(detail=True, methods=['get'])
    def stock_movements(self, request, pk=None):
        vente = self.get_object()
        movements = StockMovement.objects.filter(
            reference_type='sale',
            reference_id=vente.id
        ).order_by('-created_at')

        from produits_stocks.serializers import StockMovementSerializer
        serializer = StockMovementSerializer(movements, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)

        ventes = Vente.objects.filter(sale_date__gte=start_date)

        total_ventes = ventes.count()
        total_montant = ventes.aggregate(total=Sum('total'))['total'] or 0
        total_paye = ventes.aggregate(total=Sum('amount_paid'))['total'] or 0
        total_due = total_montant - total_paye

        by_status = {}
        for status_choice in Vente.STATUS_CHOICES:
            status_code = status_choice[0]
            count = ventes.filter(status=status_code).count()
            if count > 0:
                by_status[status_code] = count

        by_payment_status = {}
        for status_choice in Vente.PAYMENT_STATUS_CHOICES:
            status_code = status_choice[0]
            count = ventes.filter(payment_status=status_code).count()
            if count > 0:
                by_payment_status[status_code] = count

        avg_amount = total_montant / total_ventes if total_ventes > 0 else 0

        return Response({
            'period': {
                'days': days,
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': timezone.now().strftime('%Y-%m-%d')
            },
            'total_ventes': total_ventes,
            'total_montant': total_montant,
            'total_paye': total_paye,
            'total_due': total_due,
            'avg_amount': avg_amount,
            'by_status': by_status,
            'by_payment_status': by_payment_status
        })
# ==================== FACTURE VIEWSET ====================


class FactureViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des factures clients
    """
    queryset = Facture.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return FactureCreateSerializer
        return FactureSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_queryset(self):
        queryset = super().get_queryset()

        client = self.request.query_params.get('client')
        if client:
            queryset = queryset.filter(client_id=client)

        status = self.request.query_params.get('status')
        if status:
            status_list = status.split(',')
            queryset = queryset.filter(status__in=status_list)

        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(invoice_date__gte=date_from)

        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(invoice_date__lte=date_to)

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(invoice_number__icontains=search) |
                Q(client__name__icontains=search) |
                Q(client__code__icontains=search)
            )

        return queryset

    @action(detail=True, methods=['post'])
    def register_payment(self, request, pk=None):
        from decimal import Decimal
        from django.db import transaction
        from django.db.models import Sum

        facture = self.get_object()

        amount = request.data.get('amount')
        method = request.data.get('method', 'cash')
        reference = request.data.get('reference', '')
        notes = request.data.get('notes', '')

        try:
            amount = Decimal(str(amount))
        except (TypeError, ValueError):
            return Response(
                {"error": "Le montant doit être un nombre valide"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if amount <= 0:
            return Response(
                {"error": "Le montant doit être supérieur à 0"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if amount > facture.remaining_amount:
            return Response(
                {"error": f"Le montant dépasse le solde restant ({facture.remaining_amount:,.0f} FCFA)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            paiement = Paiement.objects.create(
                facture=facture,
                amount=amount,
                method=method,
                reference=reference,
                notes=notes or f"Paiement sur la facture {facture.invoice_number}",
                received_by=request.user
            )

            total_paid = facture.paiements.aggregate(total=Sum('amount'))[
                'total'] or Decimal('0')
            facture.amount_paid = total_paid
            if facture.amount_paid >= facture.total:
                facture.status = 'paid'
            elif facture.amount_paid > 0:
                facture.status = 'partial'
            facture.save()

            sale = facture.sale
            if sale:
                total_paid_sale = Decimal('0')
                for inv in sale.invoices.all():
                    total_paid_sale += inv.amount_paid
                sale.amount_paid = total_paid_sale
                sale.amount_due = sale.total - sale.amount_paid
                if sale.amount_due <= 0:
                    sale.payment_status = 'paid'
                elif sale.amount_paid > 0:
                    sale.payment_status = 'partial'
                else:
                    sale.payment_status = 'pending'
                sale.save()

        serializer = PaiementSerializer(paiement)

        return Response({
            'paiement': serializer.data,
            'facture': FactureSerializer(facture, context={'request': request}).data,
            'remaining_amount': facture.remaining_amount
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def mark_paid(self, request, pk=None):
        from decimal import Decimal
        from django.db import transaction
        from django.db.models import Sum

        facture = self.get_object()

        amount = request.data.get('amount', 0)
        method = request.data.get('method', 'cash')
        reference = request.data.get('reference', '')
        notes = request.data.get('notes', '')

        try:
            amount = Decimal(str(amount))
        except (TypeError, ValueError):
            return Response(
                {"error": "Le montant doit être un nombre valide"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if amount <= 0:
            return Response(
                {"error": "Le montant doit être supérieur à 0"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if amount > facture.remaining_amount:
            return Response(
                {"error": f"Le montant dépasse le solde restant ({facture.remaining_amount:,.0f} FCFA)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            paiement = Paiement.objects.create(
                facture=facture,
                amount=amount,
                method=method,
                reference=reference,
                notes=notes or f"Paiement sur la facture {facture.invoice_number}",
                received_by=request.user
            )

            total_paid = facture.paiements.aggregate(total=Sum('amount'))[
                'total'] or Decimal('0')
            facture.amount_paid = total_paid
            if facture.amount_paid >= facture.total:
                facture.status = 'paid'
            elif facture.amount_paid > 0:
                facture.status = 'partial'
            facture.save()

            sale = facture.sale
            if sale:
                total_paid_sale = Decimal('0')
                for inv in sale.invoices.all():
                    total_paid_sale += inv.amount_paid
                sale.amount_paid = total_paid_sale
                sale.amount_due = sale.total - sale.amount_paid
                if sale.amount_due <= 0:
                    sale.payment_status = 'paid'
                elif sale.amount_paid > 0:
                    sale.payment_status = 'partial'
                else:
                    sale.payment_status = 'pending'
                sale.save()

        return Response({
            'paiement': PaiementSerializer(paiement).data,
            'facture_status': facture.status,
            'remaining_amount': facture.remaining_amount
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        facture = self.get_object()

        if facture.status != 'draft':
            return Response(
                {"error": "Seules les factures en brouillon peuvent être envoyées"},
                status=status.HTTP_400_BAD_REQUEST
            )

        facture.status = 'sent'
        facture.save()
        facture.generate_qr_code()
        facture.save()

        return Response({
            'status': facture.status,
            'message': 'Facture envoyée avec succès'
        })

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        facture = self.get_object()

        if facture.status in ['paid']:
            return Response(
                {"error": "Les factures payées ne peuvent pas être annulées"},
                status=status.HTTP_400_BAD_REQUEST
            )

        facture.status = 'cancelled'
        facture.save()

        return Response({
            'status': facture.status,
            'message': 'Facture annulée avec succès'
        })

    @action(detail=True, methods=['post'])
    def generate_invoice(self, request, pk=None):
        from django.db import transaction

        sale_id = request.data.get('sale_id')
        due_date = request.data.get('due_date')

        if not sale_id:
            return Response(
                {"error": "L'ID de la vente est requis"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            sale = Vente.objects.get(id=sale_id)
        except Vente.DoesNotExist:
            return Response(
                {"error": "Vente non trouvée"},
                status=status.HTTP_404_NOT_FOUND
            )

        if Facture.objects.filter(sale=sale).exists():
            return Response(
                {"error": "Une facture existe déjà pour cette vente"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if due_date:
            try:
                due_date = date.fromisoformat(due_date)
            except ValueError:
                return Response(
                    {"error": "Format de date invalide. Utilisez YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            due_date = date.today() + timedelta(days=30)

        with transaction.atomic():
            last_facture = Facture.objects.order_by('-id').first()
            if last_facture and last_facture.invoice_number:
                try:
                    num = int(last_facture.invoice_number.split('-')[-1]) + 1
                except (ValueError, IndexError):
                    num = 1
            else:
                num = 1
            invoice_number = f"FAC-{date.today().year}-{num:04d}"

            facture = Facture.objects.create(
                invoice_number=invoice_number,
                sale=sale,
                client=sale.client,
                due_date=due_date,
                subtotal=sale.subtotal,
                tax_amount=sale.tax_amount,
                total=sale.total,
                status='sent'
            )

            facture.generate_qr_code()
            facture.save()

        return Response({
            'facture': FactureSerializer(facture, context={'request': request}).data,
            'message': 'Facture générée avec succès'
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def generate_qr(self, request, pk=None):
        facture = self.get_object()

        if not facture.qr_code:
            facture.generate_qr_code()
            facture.save()

        if facture.qr_code:
            return Response({
                'qr_code_url': request.build_absolute_uri(facture.qr_code.url),
                'qr_code_data': facture.qr_code_data
            })

        return Response(
            {"error": "Impossible de générer le QR Code"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    @action(detail=True, methods=['get'])
    def paiements(self, request, pk=None):
        facture = self.get_object()
        paiements = facture.paiements.all()
        serializer = PaiementSerializer(paiements, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        facture = self.get_object()
        # ... code existant pour PDF ...

# ==================== PAIEMENT VIEWSET ====================


class PaiementViewSet(viewsets.ModelViewSet):
    queryset = Paiement.objects.all()
    serializer_class = PaiementSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_queryset(self):
        queryset = super().get_queryset()

        facture_id = self.request.query_params.get('facture')
        if facture_id:
            queryset = queryset.filter(facture_id=facture_id)

        return queryset

    def perform_create(self, serializer):
        paiement = serializer.save(received_by=self.request.user)
        paiement.generate_qr_code()
        paiement.save()

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

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        paiement = self.get_object()
        # ... code existant pour PDF ...


# ==================== AVOIR VIEWSET ====================
class AvoirViewSet(viewsets.ModelViewSet):
    queryset = Avoir.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return AvoirCreateSerializer
        return AvoirSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def get_queryset(self):
        queryset = super().get_queryset()

        client = self.request.query_params.get('client')
        if client:
            queryset = queryset.filter(client_id=client)

        return queryset


# ==================== TAXE VIEWSET ====================
class TaxeViewSet(viewsets.ModelViewSet):
    queryset = Taxe.objects.all()
    serializer_class = TaxeSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]


# ==================== REMISE VIEWSET ====================
class RemiseViewSet(viewsets.ModelViewSet):
    queryset = Remise.objects.all()
    serializer_class = RemiseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()

        is_active = self.request.query_params.get('is_active')
        if is_active == 'true':
            queryset = queryset.filter(is_active=True)

        return queryset


# ==================== DASHBOARD STATS VIEWSET ====================
class SalesDashboardStatsViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def summary(self, request):
        today = date.today()
        start_of_month = today.replace(day=1)
        start_of_week = today - timedelta(days=today.weekday())

        total_sales = Vente.objects.count()
        sales_today = Vente.objects.filter(sale_date__date=today).count()
        sales_this_month = Vente.objects.filter(
            sale_date__date__gte=start_of_month).count()
        sales_this_week = Vente.objects.filter(
            sale_date__date__gte=start_of_week).count()

        total_amount = Vente.objects.aggregate(
            total=Sum('total'))['total'] or 0
        amount_today = Vente.objects.filter(sale_date__date=today).aggregate(
            total=Sum('total'))['total'] or 0
        amount_this_month = Vente.objects.filter(
            sale_date__date__gte=start_of_month).aggregate(total=Sum('total'))['total'] or 0

        pending_payments = Vente.objects.filter(
            payment_status__in=['pending', 'partial']).count()
        pending_amount = Vente.objects.filter(payment_status__in=[
                                              'pending', 'partial']).aggregate(total=Sum('amount_due'))['total'] or 0

        total_clients = Client.objects.filter(statut='actif').count()

        pending_invoices = Facture.objects.filter(
            status__in=['draft', 'sent', 'partial']).count()
        overdue_invoices = Facture.objects.filter(status='overdue').count()

        total_devis = Devis.objects.count()
        devis_en_attente = Devis.objects.filter(status='sent').count()
        devis_acceptes = Devis.objects.filter(status='accepted').count()
        devis_expires = Devis.objects.filter(status='expired').count()
        devis_convertis = Devis.objects.filter(status='converted').count()

        return Response({
            'sales': {
                'total': total_sales,
                'today': sales_today,
                'this_week': sales_this_week,
                'this_month': sales_this_month
            },
            'amounts': {
                'total': total_amount,
                'today': amount_today,
                'this_month': amount_this_month
            },
            'payments': {
                'pending': pending_payments,
                'pending_amount': pending_amount
            },
            'clients': {
                'total': total_clients
            },
            'invoices': {
                'pending': pending_invoices,
                'overdue': overdue_invoices
            },
            'devis': {
                'total': total_devis,
                'en_attente': devis_en_attente,
                'acceptes': devis_acceptes,
                'expires': devis_expires,
                'convertis': devis_convertis
            }
        })
