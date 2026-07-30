# dashboard/views.py
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, Count, Avg, F
from django.utils import timezone
from datetime import date, timedelta

from produits_stocks.models import Product, Stock, Lot, StockMovement
from ventes_clients.models import Vente, Client, Devis, Facture
from achats_fournisseurs.models import PurchaseOrder, Supplier, Receipt
from tresorerie.models import Caisse, CompteBancaire, MouvementTresorerie

from .serializers import (
    DashboardSummarySerializer,
    StatistiquesFilterSerializer,
    StatistiquesSerializer,
    TendancesSerializer,
    PrevisionsSerializer
)


class DashboardViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        today = timezone.now().date()
        start_of_month = today.replace(day=1)

        # VENTES
        ventes_total = Vente.objects.filter(
            status__in=['confirmed', 'paid', 'delivered'])
        ventes_mois = ventes_total.filter(sale_date__date__gte=start_of_month)
        nb_ventes_total = ventes_total.count()
        montant_ventes_total = ventes_total.aggregate(total=Sum('total'))[
            'total'] or 0
        nb_ventes_mois = ventes_mois.count()
        montant_ventes_mois = ventes_mois.aggregate(
            total=Sum('total'))['total'] or 0

        # ACHATS
        achats_total = PurchaseOrder.objects.filter(status='received')
        achats_mois = achats_total.filter(order_date__date__gte=start_of_month)
        nb_achats_total = achats_total.count()
        montant_achats_total = achats_total.aggregate(total=Sum('total'))[
            'total'] or 0
        nb_achats_mois = achats_mois.count()
        montant_achats_mois = achats_mois.aggregate(
            total=Sum('total'))['total'] or 0

        # STOCKS
        produits_total = Product.objects.filter(status='active').count()
        valeur_stock_total = 0
        for stock in Stock.objects.all():
            lots = stock.product.lots.filter(
                warehouse=stock.warehouse,
                is_blocked=False
            ).exclude(status='expired')
            for lot in lots:
                valeur_stock_total += lot.current_quantity * lot.purchase_price
        ruptures = Stock.objects.filter(quantity=0).count()
        stock_faible = Stock.objects.filter(
            quantity__lte=F('product__min_stock')).count()

        # TRÉSORERIE
        caisses = Caisse.objects.filter(is_active=True)
        total_caisses = caisses.aggregate(
            total=Sum('solde_actuel'))['total'] or 0
        comptes = CompteBancaire.objects.filter(is_active=True)
        total_comptes = comptes.aggregate(
            total=Sum('solde_actuel'))['total'] or 0
        tresorerie_totale = total_caisses + total_comptes

        # CLIENTS & FOURNISSEURS
        nb_clients = Client.objects.filter(statut='actif').count()
        nb_fournisseurs = Supplier.objects.filter(is_active=True).count()

        # ALERTES
        commandes_en_attente = PurchaseOrder.objects.filter(
            status__in=['draft', 'sent', 'confirmed']
        ).count()
        factures_impayees = Facture.objects.filter(
            status__in=['sent', 'partial', 'overdue']
        ).count()
        lots_expirant = Lot.objects.filter(
            expiry_date__lte=date.today() + timedelta(days=7),
            expiry_date__gte=date.today(),
            current_quantity__gt=0
        ).count()

        data = {
            'ventes': {
                'total': nb_ventes_total,
                'mois': nb_ventes_mois,
                'montant_total': montant_ventes_total,
                'montant_mois': montant_ventes_mois,
            },
            'achats': {
                'total': nb_achats_total,
                'mois': nb_achats_mois,
                'montant_total': montant_achats_total,
                'montant_mois': montant_achats_mois,
            },
            'stocks': {
                'produits_total': produits_total,
                'valeur_stock': valeur_stock_total,
                'ruptures': ruptures,
                'stock_faible': stock_faible,
            },
            'tresorerie': {
                'total_caisses': total_caisses,
                'total_comptes': total_comptes,
                'total_global': tresorerie_totale,
            },
            'clients_fournisseurs': {
                'clients_actifs': nb_clients,
                'fournisseurs_actifs': nb_fournisseurs,
            },
            'alertes': {
                'commandes_en_attente': commandes_en_attente,
                'factures_impayees': factures_impayees,
                'lots_expirant': lots_expirant,
            }
        }

        serializer = DashboardSummarySerializer(data)
        return Response(serializer.data)


class StatistiquesViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        filtre_serializer = StatistiquesFilterSerializer(
            data=request.query_params)
        filtre_serializer.is_valid(raise_exception=True)
        filtres = filtre_serializer.validated_data

        date_debut = filtres.get(
            'date_debut', date.today() - timedelta(days=30))
        date_fin = filtres.get('date_fin', date.today())
        entrepot_id = filtres.get('entrepot_id')

        ventes_qs = Vente.objects.filter(
            sale_date__date__gte=date_debut,
            sale_date__date__lte=date_fin,
            status__in=['confirmed', 'paid', 'delivered']
        )
        if entrepot_id:
            ventes_qs = ventes_qs.filter(warehouse_id=entrepot_id)

        stats_ventes = {
            'total_ventes': ventes_qs.count(),
            'montant_total': ventes_qs.aggregate(total=Sum('total'))['total'] or 0,
            'panier_moyen': ventes_qs.aggregate(avg=Avg('total'))['avg'] or 0,
            'par_statut': ventes_qs.values('status').annotate(count=Count('id')),
            'par_mode_paiement': ventes_qs.values('payment_method').annotate(count=Count('id')),
        }

        achats_qs = PurchaseOrder.objects.filter(
            order_date__date__gte=date_debut,
            order_date__date__lte=date_fin,
            status='received'
        )
        if entrepot_id:
            achats_qs = achats_qs.filter(
                receipts__warehouse_id=entrepot_id).distinct()

        stats_achats = {
            'total_achats': achats_qs.count(),
            'montant_total': achats_qs.aggregate(total=Sum('total'))['total'] or 0,
            'par_fournisseur': achats_qs.values('supplier__name').annotate(total=Sum('total')).order_by('-total')[:5],
        }

        mouvs_qs = MouvementTresorerie.objects.filter(
            date_mouvement__date__gte=date_debut,
            date_mouvement__date__lte=date_fin,
            status='effectue'
        )
        if entrepot_id:
            mouvs_qs = mouvs_qs.filter(warehouse_id=entrepot_id)

        stats_tresorerie = {
            'total_entrees': mouvs_qs.filter(type_mouvement='encaissement').aggregate(total=Sum('montant'))['total'] or 0,
            'total_sorties': mouvs_qs.filter(type_mouvement='decaissement').aggregate(total=Sum('montant'))['total'] or 0,
            'solde': (mouvs_qs.filter(type_mouvement='encaissement').aggregate(total=Sum('montant'))['total'] or 0) -
                     (mouvs_qs.filter(type_mouvement='decaissement').aggregate(
                         total=Sum('montant'))['total'] or 0),
        }

        top_produits = StockMovement.objects.filter(
            movement_type='sale_out',
            created_at__date__gte=date_debut,
            created_at__date__lte=date_fin,
        )
        if entrepot_id:
            top_produits = top_produits.filter(from_warehouse_id=entrepot_id)
        top_produits = (top_produits.values('product__name')
                        .annotate(total_vendu=Sum('quantity'))
                        .order_by('-total_vendu')[:10])

        data = {
            'periode': {'debut': date_debut, 'fin': date_fin},
            'ventes': stats_ventes,
            'achats': stats_achats,
            'tresorerie': stats_tresorerie,
            'top_produits': top_produits,
        }

        serializer = StatistiquesSerializer(data)
        return Response(serializer.data)


class AnalysesViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='tendances')
    def tendances(self, request):
        periode = request.query_params.get('periode', 'mois')
        nb_periodes = int(request.query_params.get('nb', 6))
        today = date.today()

        if periode == 'jour':
            dates = [today - timedelta(days=i) for i in range(nb_periodes)]
            dates.reverse()
            format_date = '%Y-%m-%d'
        elif periode == 'semaine':
            dates = [today - timedelta(weeks=i) for i in range(nb_periodes)]
            dates.reverse()
            format_date = '%Y-%W'
        else:
            dates = [today.replace(day=1) - timedelta(days=30*i)
                     for i in range(nb_periodes)]
            dates.reverse()
            format_date = '%Y-%m'

        result = []
        for dt in dates:
            if periode == 'jour':
                start = dt
                end = dt + timedelta(days=1)
            elif periode == 'semaine':
                start = dt - timedelta(days=dt.weekday())
                end = start + timedelta(days=7)
            else:
                start = dt.replace(day=1)
                if dt.month == 12:
                    end = dt.replace(year=dt.year+1, month=1, day=1)
                else:
                    end = dt.replace(month=dt.month+1, day=1)

            ventes = Vente.objects.filter(
                sale_date__date__gte=start,
                sale_date__date__lt=end,
                status__in=['confirmed', 'paid', 'delivered']
            )
            nb_ventes = ventes.count()
            montant = ventes.aggregate(total=Sum('total'))['total'] or 0

            result.append({
                'periode_label': dt.strftime(format_date),
                'total_ventes': nb_ventes,
                'montant_total': montant,
                'panier_moyen': montant / nb_ventes if nb_ventes > 0 else 0,
            })

        serializer = TendancesSerializer(result, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='previsions')
    def previsions(self, request):
        trois_mois = date.today() - timedelta(days=90)
        ventes = Vente.objects.filter(
            sale_date__date__gte=trois_mois,
            status__in=['confirmed', 'paid', 'delivered']
        )
        total_mois = ventes.aggregate(total=Sum('total'))['total'] or 0
        nb_mois = 3
        moyenne_mensuelle = total_mois / nb_mois if nb_mois > 0 else 0

        previsions = {
            'prochain_mois': moyenne_mensuelle,
            'prochain_trimestre': moyenne_mensuelle * 3,
            'prochain_semestre': moyenne_mensuelle * 6,
        }

        mois_dernier = date.today().replace(day=1) - timedelta(days=1)
        mois_dernier_start = mois_dernier.replace(day=1)
        mois_dernier_ventes = Vente.objects.filter(
            sale_date__date__gte=mois_dernier_start,
            sale_date__date__lte=mois_dernier,
            status__in=['confirmed', 'paid', 'delivered']
        )
        montant_mois_dernier = mois_dernier_ventes.aggregate(total=Sum('total'))[
            'total'] or 0
        evolution = ((moyenne_mensuelle - montant_mois_dernier) /
                     montant_mois_dernier * 100) if montant_mois_dernier > 0 else 0

        data = {
            'previsions': previsions,
            'moyenne_mensuelle': moyenne_mensuelle,
            'montant_mois_dernier': montant_mois_dernier,
            'evolution_pourcentage': evolution,
        }

        serializer = PrevisionsSerializer(data)
        return Response(serializer.data)
