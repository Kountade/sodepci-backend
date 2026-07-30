# finances/views.py

from users.permissions import IsAdmin, IsGestionnaire, IsComptable
from produits_stocks.models import Product, Stock
from achats_fournisseurs.models import SupplierInvoice, PurchaseOrder, Supplier
from ventes_clients.models import Vente, Facture, Paiement, Client
from .serializers import RapportFinancierSerializer, RapportFinancierCreateSerializer
from .models import RapportFinancier
from django.core.files.base import ContentFile
from django.db.models import Sum, Count, Q
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from datetime import datetime
from django.http import FileResponse
from django.conf import settings
import os
import io
from django.http import HttpResponse, FileResponse
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from io import BytesIO
import json

from .models import (
    CompteComptable,
    EcritureComptable,
    Tresorerie,
    MouvementTresorerie,
    Depense,
    Budget,
    BudgetCategorie,
    BudgetLigne,
    RapportFinancier,
    ConfigurationFinanciere
)
from .serializers import (
    CompteComptableSerializer,
    CompteComptableListSerializer,
    EcritureComptableSerializer,
    EcritureComptableCreateSerializer,
    TresorerieSerializer,
    TresorerieListSerializer,
    MouvementTresorerieSerializer,
    MouvementTresorerieCreateSerializer,
    DepenseSerializer,
    DepenseCreateSerializer,
    DepenseApproveSerializer,
    BudgetSerializer,
    BudgetCreateSerializer,
    BudgetCategorieSerializer,
    BudgetLigneSerializer,
    RapportFinancierSerializer,
    RapportFinancierCreateSerializer,
    ConfigurationFinanciereSerializer,
    FinancesStatsSerializer,
    FinancesDashboardSerializer
)
from users.permissions import IsAdmin, IsGestionnaire, IsComptable, IsCaissier
from ventes_clients.models import Vente, Facture, Paiement
from achats_fournisseurs.models import SupplierInvoice, PurchaseOrder


# ==================== COMPTE COMPTABLE VIEWSET ====================
class CompteComptableViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des comptes comptables
    """
    queryset = CompteComptable.objects.all()
    permission_classes = [permissions.IsAuthenticated,
                          IsAdmin | IsGestionnaire | IsComptable]

    def get_serializer_class(self):
        if self.action == 'list':
            return CompteComptableListSerializer
        return CompteComptableSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(numero__icontains=search) |
                Q(nom__icontains=search) |
                Q(nom_complet__icontains=search)
            )

        type_filter = self.request.query_params.get('type')
        if type_filter:
            queryset = queryset.filter(type=type_filter)

        classe = self.request.query_params.get('classe')
        if classe:
            queryset = queryset.filter(classe=classe)

        is_active = self.request.query_params.get('is_active')
        if is_active == 'true':
            queryset = queryset.filter(is_active=True)

        parent = self.request.query_params.get('parent')
        if parent == 'null':
            queryset = queryset.filter(parent__isnull=True)
        elif parent:
            queryset = queryset.filter(parent_id=parent)

        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def update_solde(self, request, pk=None):
        """Met à jour le solde du compte"""
        compte = self.get_object()
        compte.update_solde()
        return Response({
            'id': compte.id,
            'solde': str(compte.solde),
            'message': 'Solde mis à jour avec succès'
        })

    @action(detail=True, methods=['get'])
    def ecritures(self, request, pk=None):
        """Récupère les écritures liées au compte"""
        compte = self.get_object()
        ecritures = EcritureComptable.objects.filter(
            Q(compte_debit=compte) | Q(compte_credit=compte)
        ).order_by('-date_ecriture')
        serializer = EcritureComptableSerializer(ecritures, many=True)
        return Response(serializer.data)


# ==================== ÉCRITURE COMPTABLE VIEWSET ====================
# finances/views.py - Modifier EcritureComptableViewSet

class EcritureComptableViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des écritures comptables
    """
    queryset = EcritureComptable.objects.all()
    permission_classes = [permissions.IsAuthenticated,
                          IsAdmin | IsGestionnaire | IsComptable]

    def get_serializer_class(self):
        if self.action == 'create':
            return EcritureComptableCreateSerializer
        return EcritureComptableSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(numero__icontains=search) |
                Q(reference__icontains=search) |
                Q(description__icontains=search)
            )

        type_filter = self.request.query_params.get('type')
        if type_filter:
            queryset = queryset.filter(type=type_filter)

        statut = self.request.query_params.get('statut')
        if statut:
            queryset = queryset.filter(statut=statut)

        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(date_ecriture__gte=date_from)

        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(date_ecriture__lte=date_to)

        compte = self.request.query_params.get('compte')
        if compte:
            queryset = queryset.filter(
                Q(compte_debit_id=compte) | Q(compte_credit_id=compte)
            )

        return queryset

    # ✅ SUPPRIMER cette méthode car le serializer s'occupe déjà de created_by
    # def perform_create(self, serializer):
    #     serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def valider(self, request, pk=None):
        """Valide une écriture comptable"""
        ecriture = self.get_object()
        if ecriture.statut == 'valide':
            return Response(
                {"error": "Cette écriture est déjà validée"},
                status=status.HTTP_400_BAD_REQUEST
            )
        ecriture.valider(request.user)
        return Response({
            'id': ecriture.id,
            'statut': ecriture.statut,
            'message': 'Écriture validée avec succès'
        })

    @action(detail=True, methods=['post'])
    def annuler(self, request, pk=None):
        """Annule une écriture comptable"""
        ecriture = self.get_object()
        if ecriture.statut == 'valide':
            return Response(
                {"error": "Les écritures validées ne peuvent pas être annulées"},
                status=status.HTTP_400_BAD_REQUEST
            )
        ecriture.statut = 'annulee'
        ecriture.save()
        return Response({
            'id': ecriture.id,
            'statut': ecriture.statut,
            'message': 'Écriture annulée avec succès'
        })

# ==================== TRÉSORERIE VIEWSET ====================


class TresorerieViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion de la trésorerie
    """
    queryset = Tresorerie.objects.all()
    permission_classes = [permissions.IsAuthenticated,
                          IsAdmin | IsGestionnaire | IsComptable]

    def get_serializer_class(self):
        if self.action == 'list':
            return TresorerieListSerializer
        return TresorerieSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(nom__icontains=search) |
                Q(code__icontains=search) |
                Q(banque__icontains=search)
            )

        type_filter = self.request.query_params.get('type')
        if type_filter:
            queryset = queryset.filter(type=type_filter)

        is_active = self.request.query_params.get('is_active')
        if is_active == 'true':
            queryset = queryset.filter(is_active=True)

        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def update_solde(self, request, pk=None):
        """Met à jour le solde de la trésorerie"""
        tresorerie = self.get_object()
        tresorerie.update_solde()
        return Response({
            'id': tresorerie.id,
            'solde_actuel': str(tresorerie.solde_actuel),
            'message': 'Solde mis à jour avec succès'
        })

    @action(detail=True, methods=['get'])
    def mouvements(self, request, pk=None):
        """Récupère les mouvements de la trésorerie"""
        tresorerie = self.get_object()
        mouvements = tresorerie.mouvements.all().order_by('-date_mouvement')
        serializer = MouvementTresorerieSerializer(mouvements, many=True)
        return Response(serializer.data)


# ==================== MOUVEMENT TRÉSORERIE VIEWSET ====================
# finances/views.py - MouvementTresorerieViewSet

class MouvementTresorerieViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des mouvements de trésorerie
    """
    queryset = MouvementTresorerie.objects.all()
    permission_classes = [permissions.IsAuthenticated,
                          IsAdmin | IsGestionnaire | IsComptable]

    def get_serializer_class(self):
        if self.action == 'create':
            return MouvementTresorerieCreateSerializer
        return MouvementTresorerieSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        tresorerie = self.request.query_params.get('tresorerie')
        if tresorerie:
            queryset = queryset.filter(tresorerie_id=tresorerie)

        type_filter = self.request.query_params.get('type')
        if type_filter:
            queryset = queryset.filter(type=type_filter)

        categorie = self.request.query_params.get('categorie')
        if categorie:
            queryset = queryset.filter(categorie=categorie)

        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(date_valeur__gte=date_from)

        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(date_valeur__lte=date_to)

        return queryset

    def get_serializer_context(self):
        """Ajoute la requête au contexte du serializer"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    # ✅ SUPPRIMER cette méthode car le serializer gère déjà created_by
    # def perform_create(self, serializer):
    #     serializer.save(created_by=self.request.user)S

# ==================== DÉPENSE VIEWSET ====================
# finances/views.py - DepenseViewSet


class DepenseViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des dépenses
    """
    queryset = Depense.objects.all()
    permission_classes = [permissions.IsAuthenticated,
                          IsAdmin | IsGestionnaire | IsComptable]

    def get_serializer_class(self):
        if self.action == 'create':
            return DepenseCreateSerializer
        return DepenseSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(reference__icontains=search) |
                Q(description__icontains=search) |
                Q(supplier_name__icontains=search)
            )

        categorie = self.request.query_params.get('categorie')
        if categorie:
            queryset = queryset.filter(categorie=categorie)

        statut = self.request.query_params.get('statut')
        if statut:
            queryset = queryset.filter(statut=statut)

        supplier = self.request.query_params.get('supplier')
        if supplier:
            queryset = queryset.filter(supplier_id=supplier)

        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(date_depense__gte=date_from)

        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(date_depense__lte=date_to)

        min_amount = self.request.query_params.get('min_amount')
        if min_amount:
            queryset = queryset.filter(montant__gte=min_amount)

        max_amount = self.request.query_params.get('max_amount')
        if max_amount:
            queryset = queryset.filter(montant__lte=max_amount)

        return queryset

    def get_serializer_context(self):
        """Ajoute la requête au contexte du serializer"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    # ✅ SUPPRIMER cette méthode car le serializer gère déjà created_by
    # def perform_create(self, serializer):
    #     serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def approuver(self, request, pk=None):
        """Approuve une dépense"""
        depense = self.get_object()
        if depense.statut != 'en_attente':
            return Response(
                {"error": f"La dépense est déjà {depense.get_statut_display()}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        depense.approuver(request.user)
        return Response({
            'id': depense.id,
            'statut': depense.statut,
            'message': 'Dépense approuvée avec succès'
        })

    @action(detail=True, methods=['post'])
    def payer(self, request, pk=None):
        """Marque une dépense comme payée"""
        depense = self.get_object()
        if depense.statut == 'paye':
            return Response(
                {"error": "Cette dépense est déjà payée"},
                status=status.HTTP_400_BAD_REQUEST
            )
        depense.payer(request.user)
        return Response({
            'id': depense.id,
            'statut': depense.statut,
            'message': 'Dépense payée avec succès'
        })

    @action(detail=True, methods=['post'])
    def rejeter(self, request, pk=None):
        """Rejette une dépense"""
        depense = self.get_object()
        if depense.statut != 'en_attente':
            return Response(
                {"error": f"La dépense est déjà {depense.get_statut_display()}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        depense.statut = 'rejete'
        depense.save()
        return Response({
            'id': depense.id,
            'statut': depense.statut,
            'message': 'Dépense rejetée'
        })

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        """Génère un PDF pour une dépense"""
        # ... votre code PDF existant ...

# ==================== BUDGET VIEWSET ====================
# finances/views.py - BudgetViewSet


class BudgetViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des budgets
    """
    queryset = Budget.objects.all()
    permission_classes = [permissions.IsAuthenticated,
                          IsAdmin | IsGestionnaire | IsComptable]

    def get_serializer_class(self):
        if self.action == 'create':
            return BudgetCreateSerializer
        return BudgetSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(nom__icontains=search)
            )

        type_filter = self.request.query_params.get('type')
        if type_filter:
            queryset = queryset.filter(type=type_filter)

        statut = self.request.query_params.get('statut')
        if statut:
            queryset = queryset.filter(statut=statut)

        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(date_debut__gte=date_from)

        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(date_fin__lte=date_to)

        return queryset

    def get_serializer_context(self):
        """Ajoute la requête au contexte du serializer"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    # ✅ SUPPRIMER cette méthode car le serializer gère déjà created_by
    # def perform_create(self, serializer):
    #     serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def update_utilise(self, request, pk=None):
        """Met à jour le montant utilisé du budget"""
        budget = self.get_object()
        budget.update_utilise()
        return Response({
            'id': budget.id,
            'montant_utilise': str(budget.montant_utilise),
            'montant_restant': str(budget.montant_restant),
            'message': 'Budget mis à jour'
        })

# ==================== BUDGET CATÉGORIE VIEWSET ====================


class BudgetCategorieViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des catégories de budget
    """
    queryset = BudgetCategorie.objects.all()
    serializer_class = BudgetCategorieSerializer
    permission_classes = [permissions.IsAuthenticated,
                          IsAdmin | IsGestionnaire | IsComptable]

    def get_queryset(self):
        queryset = super().get_queryset()

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(nom__icontains=search) |
                Q(code__icontains=search)
            )

        is_active = self.request.query_params.get('is_active')
        if is_active == 'true':
            queryset = queryset.filter(is_active=True)

        return queryset


# ==================== RAPPORT FINANCIER VIEWSET ====================
# finances/views.py - RapportFinancierViewSet
# finances/views.py - RapportFinancierViewSet

# finances/views.py - RapportFinancierViewSet avec données réelles


class RapportFinancierViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des rapports financiers
    """
    queryset = RapportFinancier.objects.all()
    permission_classes = [permissions.IsAuthenticated,
                          IsAdmin | IsGestionnaire | IsComptable]

    def get_serializer_class(self):
        if self.action == 'create':
            return RapportFinancierCreateSerializer
        return RapportFinancierSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        type_filter = self.request.query_params.get('type')
        if type_filter:
            queryset = queryset.filter(type=type_filter)

        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(date_debut__gte=date_from)

        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(date_fin__lte=date_to)

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(nom__icontains=search)

        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def _get_bilan_data(self, date_debut, date_fin):
        """Récupère les données pour le bilan comptable"""
        from .models import Tresorerie, Depense

        # Trésorerie
        tresoreries = Tresorerie.objects.filter(is_active=True)
        tresorerie_total = tresoreries.aggregate(
            total=Sum('solde_actuel'))['total'] or 0

        # Créances clients (factures non payées)
        creances = Facture.objects.filter(
            status__in=['sent', 'partial', 'overdue'],
            due_date__lte=date_fin
        )
        creances_total = creances.aggregate(
            total=Sum('remaining_amount'))['total'] or 0

        # Dettes fournisseurs
        dettes = SupplierInvoice.objects.filter(
            status__in=['received', 'verified', 'partial'],
            due_date__lte=date_fin
        )
        dettes_total = dettes.aggregate(
            total=Sum('remaining_amount'))['total'] or 0

        # Dépenses
        depenses = Depense.objects.filter(
            statut='paye',
            date_depense__lte=date_fin
        )
        depenses_total = depenses.aggregate(total=Sum('total'))['total'] or 0

        # Ventes payées
        ventes = Vente.objects.filter(
            status='paid',
            sale_date__date__lte=date_fin
        )
        ventes_total = ventes.aggregate(total=Sum('total'))['total'] or 0

        return {
            'tresorerie': {
                'total': tresorerie_total,
                'details': [{'nom': t.nom, 'solde': t.solde_actuel} for t in tresoreries]
            },
            'creances': {
                'total': creances_total,
                'details': [{
                    'facture': f.invoice_number,
                    'client': f.client.name,
                    'montant': f.remaining_amount,
                    'due_date': f.due_date.strftime('%d/%m/%Y')
                } for f in creances[:20]]
            },
            'dettes': {
                'total': dettes_total,
                'details': [{
                    'facture': d.invoice_number,
                    'fournisseur': d.supplier.name,
                    'montant': d.remaining_amount,
                    'due_date': d.due_date.strftime('%d/%m/%Y')
                } for d in dettes[:20]]
            },
            'depenses_total': depenses_total,
            'ventes_total': ventes_total,
            'resultat': ventes_total - depenses_total
        }

    def _get_compte_resultat_data(self, date_debut, date_fin):
        """Récupère les données pour le compte de résultat"""
        from .models import Depense

        # Ventes sur la période
        ventes = Vente.objects.filter(
            status='paid',
            sale_date__date__gte=date_debut,
            sale_date__date__lte=date_fin
        )
        ventes_total = ventes.aggregate(total=Sum('total'))['total'] or 0

        # Dépenses sur la période
        depenses = Depense.objects.filter(
            statut='paye',
            date_depense__gte=date_debut,
            date_depense__lte=date_fin
        )
        depenses_total = depenses.aggregate(total=Sum('total'))['total'] or 0

        # Dépenses par catégorie
        depenses_par_categorie = {}
        for d in depenses:
            cat = d.get_categorie_display()
            depenses_par_categorie[cat] = depenses_par_categorie.get(
                cat, 0) + d.total

        return {
            'ventes': {
                'total': ventes_total,
                'nombre': ventes.count(),
                'details': [{
                    'invoice': v.invoice_number,
                    'client': v.client_name,
                    'date': v.sale_date.strftime('%d/%m/%Y'),
                    'montant': v.total
                } for v in ventes[:20]]
            },
            'depenses': {
                'total': depenses_total,
                'nombre': depenses.count(),
                'par_categorie': depenses_par_categorie,
                'details': [{
                    'reference': d.reference,
                    'categorie': d.get_categorie_display(),
                    'date': d.date_depense.strftime('%d/%m/%Y'),
                    'montant': d.total
                } for d in depenses[:20]]
            },
            'resultat': ventes_total - depenses_total
        }

    def _get_tresorerie_data(self, date_debut, date_fin):
        """Récupère les données pour le tableau de trésorerie"""
        from .models import Tresorerie, MouvementTresorerie

        tresoreries = Tresorerie.objects.filter(is_active=True)

        # Mouvements sur la période
        mouvements = MouvementTresorerie.objects.filter(
            date_valeur__gte=date_debut,
            date_valeur__lte=date_fin
        )

        entrees = mouvements.filter(type='entree').aggregate(
            total=Sum('montant'))['total'] or 0
        sorties = mouvements.filter(type='sortie').aggregate(
            total=Sum('montant'))['total'] or 0

        return {
            'tresorerie': {
                'total': sum(t.solde_actuel for t in tresoreries),
                'details': [{
                    'nom': t.nom,
                    'solde': t.solde_actuel,
                    'minimum': t.solde_minimum
                } for t in tresoreries]
            },
            'mouvements': {
                'entrees': entrees,
                'sorties': sorties,
                'solde': entrees - sorties,
                'details': [{
                    'date': m.date_valeur.strftime('%d/%m/%Y'),
                    'type': 'Entrée' if m.type == 'entree' else 'Sortie',
                    'montant': m.montant,
                    'description': m.description
                } for m in mouvements[:20]]
            }
        }

    def _get_budget_data(self, date_debut, date_fin):
        """Récupère les données pour le suivi budgétaire"""
        from .models import Budget

        budgets = Budget.objects.filter(
            statut='en_cours',
            date_debut__lte=date_fin,
            date_fin__gte=date_debut
        )

        return {
            'budgets': [{
                'nom': b.nom,
                'type': b.get_type_display(),
                'total': b.montant_total,
                'utilise': b.montant_utilise,
                'restant': b.montant_restant,
                'pourcentage': (b.montant_utilise / b.montant_total * 100) if b.montant_total > 0 else 0
            } for b in budgets]
        }

    def _get_ventes_data(self, date_debut, date_fin):
        """Récupère les données pour le rapport de ventes"""
        ventes = Vente.objects.filter(
            sale_date__date__gte=date_debut,
            sale_date__date__lte=date_fin
        )

        # Par statut
        par_statut = {}
        for v in ventes:
            statut = v.get_status_display()
            par_statut[statut] = par_statut.get(statut, 0) + 1

        # Par client
        par_client = {}
        for v in ventes:
            client = v.client_name
            par_client[client] = par_client.get(client, 0) + v.total

        return {
            'ventes': {
                'total': ventes.aggregate(total=Sum('total'))['total'] or 0,
                'nombre': ventes.count(),
                'par_statut': par_statut,
                'par_client': dict(sorted(par_client.items(), key=lambda x: x[1], reverse=True)[:10]),
                'details': [{
                    'invoice': v.invoice_number,
                    'client': v.client_name,
                    'date': v.sale_date.strftime('%d/%m/%Y'),
                    'montant': v.total,
                    'statut': v.get_status_display()
                } for v in ventes[:20]]
            }
        }

    def _get_depenses_data(self, date_debut, date_fin):
        """Récupère les données pour le rapport de dépenses"""
        from .models import Depense

        depenses = Depense.objects.filter(
            date_depense__gte=date_debut,
            date_depense__lte=date_fin
        )

        # Par catégorie
        par_categorie = {}
        for d in depenses:
            cat = d.get_categorie_display()
            par_categorie[cat] = par_categorie.get(cat, 0) + d.total

        # Par statut
        par_statut = {}
        for d in depenses:
            statut = d.get_statut_display()
            par_statut[statut] = par_statut.get(statut, 0) + 1

        return {
            'depenses': {
                'total': depenses.aggregate(total=Sum('total'))['total'] or 0,
                'nombre': depenses.count(),
                'par_categorie': par_categorie,
                'par_statut': par_statut,
                'details': [{
                    'reference': d.reference,
                    'categorie': d.get_categorie_display(),
                    'date': d.date_depense.strftime('%d/%m/%Y'),
                    'montant': d.total,
                    'statut': d.get_statut_display()
                } for d in depenses[:20]]
            }
        }

    def _generer_contenu_rapport(self, rapport):
        """Génère le contenu du rapport selon le type"""
        date_debut = rapport.date_debut
        date_fin = rapport.date_fin

        if rapport.type == 'bilan':
            data = self._get_bilan_data(date_debut, date_fin)
        elif rapport.type == 'compte_resultat':
            data = self._get_compte_resultat_data(date_debut, date_fin)
        elif rapport.type == 'tresorerie':
            data = self._get_tresorerie_data(date_debut, date_fin)
        elif rapport.type == 'budget':
            data = self._get_budget_data(date_debut, date_fin)
        elif rapport.type == 'ventes':
            data = self._get_ventes_data(date_debut, date_fin)
        elif rapport.type == 'depenses':
            data = self._get_depenses_data(date_debut, date_fin)
        else:
            data = {'message': 'Type de rapport non pris en charge'}

        return {
            'type': rapport.type,
            'date_debut': date_debut.isoformat(),
            'date_fin': date_fin.isoformat(),
            'genere_le': datetime.now().isoformat(),
            'data': data
        }

    def _creer_pdf(self, rapport, contenu):
        """Crée le PDF du rapport avec les données réelles"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = []

        # Styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=20,
            textColor=colors.HexColor('#1a237e'),
            alignment=TA_CENTER,
            spaceAfter=20
        )

        subtitle_style = ParagraphStyle(
            'Subtitle',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#333333'),
            alignment=TA_CENTER,
            spaceAfter=10
        )

        info_style = ParagraphStyle(
            'Info',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=6
        )

        section_style = ParagraphStyle(
            'Section',
            parent=styles['Heading3'],
            fontSize=12,
            textColor=colors.HexColor('#1a237e'),
            spaceAfter=8
        )

        # En-tête
        elements.append(Paragraph(rapport.nom, title_style))
        elements.append(
            Paragraph(f"Type: {rapport.get_type_display()}", subtitle_style))
        elements.append(Spacer(1, 5))

        elements.append(Paragraph(
            f"Période du {rapport.date_debut.strftime('%d/%m/%Y')} au {rapport.date_fin.strftime('%d/%m/%Y')}",
            info_style
        ))
        elements.append(Paragraph(
            f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}",
            info_style
        ))
        elements.append(Spacer(1, 15))

        data = contenu.get('data', {})

        # === BILAN ===
        if rapport.type == 'bilan':
            # Trésorerie
            treso = data.get('tresorerie', {})
            if treso.get('details'):
                elements.append(Paragraph("TRÉSORERIE", section_style))
                table_data = [['Compte', 'Solde']]
                for item in treso['details']:
                    table_data.append(
                        [item['nom'], f"{item['solde']:,.0f} FCFA"])
                table_data.append(
                    ['Total', f"{treso.get('total', 0):,.0f} FCFA"])
                table = Table(table_data, colWidths=[3*inch, 2*inch])
                table.setStyle(self._get_table_style())
                elements.append(table)
                elements.append(Spacer(1, 10))

            # Créances
            creances = data.get('creances', {})
            if creances.get('details'):
                elements.append(Paragraph("CRÉANCES CLIENTS", section_style))
                table_data = [['Facture', 'Client', 'Montant', 'Échéance']]
                for item in creances['details']:
                    table_data.append(
                        [item['facture'], item['client'], f"{item['montant']:,.0f} FCFA", item['due_date']])
                table_data.append(
                    ['Total', '', f"{creances.get('total', 0):,.0f} FCFA", ''])
                table = Table(table_data, colWidths=[
                              1.5*inch, 2*inch, 1.5*inch, 1.2*inch])
                table.setStyle(self._get_table_style())
                elements.append(table)
                elements.append(Spacer(1, 10))

            # Dettes
            dettes = data.get('dettes', {})
            if dettes.get('details'):
                elements.append(
                    Paragraph("DETTES FOURNISSEURS", section_style))
                table_data = [
                    ['Facture', 'Fournisseur', 'Montant', 'Échéance']]
                for item in dettes['details']:
                    table_data.append(
                        [item['facture'], item['fournisseur'], f"{item['montant']:,.0f} FCFA", item['due_date']])
                table_data.append(
                    ['Total', '', f"{dettes.get('total', 0):,.0f} FCFA", ''])
                table = Table(table_data, colWidths=[
                              1.5*inch, 2*inch, 1.5*inch, 1.2*inch])
                table.setStyle(self._get_table_style())
                elements.append(table)

            # Résultat
            resultat = data.get('resultat', 0)
            elements.append(Spacer(1, 10))
            color = colors.HexColor(
                '#22c55e') if resultat >= 0 else colors.HexColor('#ef4444')
            result_style = ParagraphStyle(
                'Result',
                parent=styles['Heading2'],
                textColor=color,
                alignment=TA_CENTER,
                fontSize=16
            )
            elements.append(
                Paragraph(f"RÉSULTAT: {resultat:,.0f} FCFA", result_style))

        # === COMPTE DE RÉSULTAT ===
        elif rapport.type == 'compte_resultat':
            # Ventes
            ventes = data.get('ventes', {})
            if ventes.get('details'):
                elements.append(Paragraph("PRODUITS (VENTES)", section_style))
                table_data = [['Facture', 'Client', 'Date', 'Montant']]
                for item in ventes['details']:
                    table_data.append(
                        [item['invoice'], item['client'], item['date'], f"{item['montant']:,.0f} FCFA"])
                table_data.append(
                    ['Total', f"{ventes.get('nombre', 0)} ventes", '', f"{ventes.get('total', 0):,.0f} FCFA"])
                table = Table(table_data, colWidths=[
                              1.2*inch, 1.8*inch, 1*inch, 1.5*inch])
                table.setStyle(self._get_table_style())
                elements.append(table)
                elements.append(Spacer(1, 10))

            # Dépenses
            depenses = data.get('depenses', {})
            if depenses.get('details'):
                elements.append(Paragraph("CHARGES (DÉPENSES)", section_style))
                table_data = [['Référence', 'Catégorie', 'Date', 'Montant']]
                for item in depenses['details']:
                    table_data.append(
                        [item['reference'], item['categorie'], item['date'], f"{item['montant']:,.0f} FCFA"])
                table_data.append(
                    ['Total', f"{depenses.get('nombre', 0)} dépenses", '', f"{depenses.get('total', 0):,.0f} FCFA"])
                table = Table(table_data, colWidths=[
                              1.2*inch, 1.8*inch, 1*inch, 1.5*inch])
                table.setStyle(self._get_table_style())
                elements.append(table)

            # Résultat
            resultat = data.get('resultat', 0)
            elements.append(Spacer(1, 10))
            color = colors.HexColor(
                '#22c55e') if resultat >= 0 else colors.HexColor('#ef4444')
            result_style = ParagraphStyle(
                'Result',
                parent=styles['Heading2'],
                textColor=color,
                alignment=TA_CENTER,
                fontSize=16
            )
            elements.append(
                Paragraph(f"RÉSULTAT: {resultat:,.0f} FCFA", result_style))

        # === TRÉSORERIE ===
        elif rapport.type == 'tresorerie':
            # Soldes
            treso = data.get('tresorerie', {})
            if treso.get('details'):
                elements.append(Paragraph("SOLDES DES COMPTES", section_style))
                table_data = [['Compte', 'Solde', 'Minimum']]
                for item in treso['details']:
                    table_data.append(
                        [item['nom'], f"{item['solde']:,.0f} FCFA", f"{item['minimum']:,.0f} FCFA"])
                table = Table(table_data, colWidths=[
                              2.5*inch, 1.5*inch, 1.5*inch])
                table.setStyle(self._get_table_style())
                elements.append(table)
                elements.append(Spacer(1, 10))

            # Mouvements
            mouvements = data.get('mouvements', {})
            if mouvements.get('details'):
                elements.append(Paragraph("MOUVEMENTS", section_style))
                elements.append(Paragraph(
                    f"Total entrées: {mouvements.get('entrees', 0):,.0f} FCFA", info_style))
                elements.append(Paragraph(
                    f"Total sorties: {mouvements.get('sorties', 0):,.0f} FCFA", info_style))
                elements.append(
                    Paragraph(f"Solde net: {mouvements.get('solde', 0):,.0f} FCFA", info_style))
                elements.append(Spacer(1, 5))

                table_data = [['Date', 'Type', 'Montant', 'Description']]
                for item in mouvements['details']:
                    table_data.append(
                        [item['date'], item['type'], f"{item['montant']:,.0f} FCFA", item['description']])
                table = Table(table_data, colWidths=[
                              1.2*inch, 1.2*inch, 1.5*inch, 2.5*inch])
                table.setStyle(self._get_table_style())
                elements.append(table)

        # === BUDGET ===
        elif rapport.type == 'budget':
            budgets = data.get('budgets', [])
            if budgets:
                elements.append(Paragraph("SUIVI BUDGÉTAIRE", section_style))
                table_data = [
                    ['Budget', 'Type', 'Total', 'Utilisé', 'Restant', '%']]
                for item in budgets:
                    pourcent = item.get('pourcentage', 0)
                    table_data.append([
                        item['nom'],
                        item['type'],
                        f"{item['total']:,.0f} FCFA",
                        f"{item['utilise']:,.0f} FCFA",
                        f"{item['restant']:,.0f} FCFA",
                        f"{pourcent:.1f}%"
                    ])
                table = Table(table_data, colWidths=[
                              1.2*inch, 1*inch, 1.5*inch, 1.5*inch, 1.5*inch, 0.8*inch])
                table.setStyle(self._get_table_style())
                elements.append(table)

        # === VENTES ===
        elif rapport.type == 'ventes':
            ventes = data.get('ventes', {})
            if ventes.get('details'):
                elements.append(Paragraph("RAPPORT DE VENTES", section_style))
                elements.append(
                    Paragraph(f"Total: {ventes.get('total', 0):,.0f} FCFA", info_style))
                elements.append(
                    Paragraph(f"Nombre de ventes: {ventes.get('nombre', 0)}", info_style))
                elements.append(Spacer(1, 5))

                # Par statut
                par_statut = ventes.get('par_statut', {})
                if par_statut:
                    elements.append(
                        Paragraph("Répartition par statut", styles['Heading4']))
                    table_data = [['Statut', 'Nombre']]
                    for statut, count in par_statut.items():
                        table_data.append([statut, str(count)])
                    table = Table(table_data, colWidths=[2*inch, 1*inch])
                    table.setStyle(self._get_table_style())
                    elements.append(table)
                    elements.append(Spacer(1, 10))

                # Détails
                elements.append(
                    Paragraph("Détails des ventes", styles['Heading4']))
                table_data = [
                    ['Facture', 'Client', 'Date', 'Montant', 'Statut']]
                for item in ventes['details']:
                    table_data.append([item['invoice'], item['client'], item['date'],
                                      f"{item['montant']:,.0f} FCFA", item['statut']])
                table = Table(table_data, colWidths=[
                              1.2*inch, 1.5*inch, 1*inch, 1.5*inch, 1*inch])
                table.setStyle(self._get_table_style())
                elements.append(table)

        # === DÉPENSES ===
        elif rapport.type == 'depenses':
            depenses = data.get('depenses', {})
            if depenses.get('details'):
                elements.append(
                    Paragraph("RAPPORT DE DÉPENSES", section_style))
                elements.append(
                    Paragraph(f"Total: {depenses.get('total', 0):,.0f} FCFA", info_style))
                elements.append(
                    Paragraph(f"Nombre de dépenses: {depenses.get('nombre', 0)}", info_style))
                elements.append(Spacer(1, 5))

                # Par catégorie
                par_categorie = depenses.get('par_categorie', {})
                if par_categorie:
                    elements.append(
                        Paragraph("Répartition par catégorie", styles['Heading4']))
                    table_data = [['Catégorie', 'Montant']]
                    for cat, montant in par_categorie.items():
                        table_data.append([cat, f"{montant:,.0f} FCFA"])
                    table = Table(table_data, colWidths=[2.5*inch, 1.5*inch])
                    table.setStyle(self._get_table_style())
                    elements.append(table)
                    elements.append(Spacer(1, 10))

                # Détails
                elements.append(
                    Paragraph("Détails des dépenses", styles['Heading4']))
                table_data = [
                    ['Référence', 'Catégorie', 'Date', 'Montant', 'Statut']]
                for item in depenses['details']:
                    table_data.append([item['reference'], item['categorie'],
                                      item['date'], f"{item['montant']:,.0f} FCFA", item['statut']])
                table = Table(table_data, colWidths=[
                              1.2*inch, 1.5*inch, 1*inch, 1.5*inch, 1*inch])
                table.setStyle(self._get_table_style())
                elements.append(table)

        # Pied de page
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER
        )
        elements.append(Spacer(1, 20))
        elements.append(
            Paragraph("Document généré automatiquement", footer_style))
        elements.append(
            Paragraph(f"EBSF - {datetime.now().year}", footer_style))

        doc.build(elements)
        buffer.seek(0)
        return buffer

    def _get_table_style(self):
        """Retourne le style par défaut pour les tableaux"""
        return TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -2), 0.5, colors.grey),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e8eaf6')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('ALIGN', (-1, 1), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ])

    @action(detail=True, methods=['post'])
    def generer(self, request, pk=None):
        """Génère le rapport PDF avec données réelles"""
        rapport = self.get_object()

        try:
            # Générer le contenu avec données réelles
            contenu = self._generer_contenu_rapport(rapport)
            rapport.contenu = contenu

            # Générer le PDF
            pdf_buffer = self._creer_pdf(rapport, contenu)

            # Sauvegarder le fichier
            filename = f"{rapport.nom}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            rapport.fichier.save(filename, ContentFile(pdf_buffer.getvalue()))
            rapport.save()

            return Response({
                'id': rapport.id,
                'message': 'Rapport généré avec succès',
                'fichier': rapport.fichier.url if rapport.fichier else None
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response(
                {"error": f"Erreur lors de la génération: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Télécharge le rapport généré"""
        rapport = self.get_object()

        try:
            # Vérifier si le fichier existe
            if rapport.fichier:
                try:
                    response = FileResponse(
                        rapport.fichier.open('rb'),
                        content_type='application/pdf',
                        as_attachment=True,
                        filename=f"{rapport.nom}.pdf"
                    )
                    return response
                except Exception as e:
                    return Response(
                        {"error": f"Erreur lecture fichier: {str(e)}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            else:
                # Si le fichier n'existe pas, générer automatiquement
                return self.generer(request, pk)

        except Exception as e:
            return Response(
                {"error": f"Erreur lors du téléchargement: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# ==================== CONFIGURATION FINANCIÈRE VIEWSET ====================


class ConfigurationFinanciereViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion de la configuration financière
    """
    queryset = ConfigurationFinanciere.objects.all()
    serializer_class = ConfigurationFinanciereSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get_queryset(self):
        return super().get_queryset()[:1]  # Une seule configuration

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


# ==================== STATISTIQUES VIEWSET ====================
class FinancesStatsViewSet(viewsets.ViewSet):
    """
    ViewSet pour les statistiques financières
    """
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Résumé des statistiques financières"""
        today = date.today()
        start_of_month = today.replace(day=1)
        start_of_week = today - timedelta(days=today.weekday())

        # Trésorerie
        tresoreries = Tresorerie.objects.filter(is_active=True)
        tresorerie_total = tresoreries.aggregate(total=Sum('solde_actuel'))[
            'total'] or Decimal('0')
        tresorerie_par_type = {}
        for treso in tresoreries:
            tresorerie_par_type[treso.type] = tresorerie_par_type.get(
                treso.type, 0) + treso.solde_actuel

        # Ventes
        ventes_total = Vente.objects.filter(status='paid').aggregate(
            total=Sum('total'))['total'] or Decimal('0')
        ventes_mois = Vente.objects.filter(
            status='paid',
            sale_date__date__gte=start_of_month
        ).aggregate(total=Sum('total'))['total'] or Decimal('0')
        ventes_jour = Vente.objects.filter(
            status='paid',
            sale_date__date=today
        ).aggregate(total=Sum('total'))['total'] or Decimal('0')

        # Dépenses
        depenses_total = Depense.objects.filter(statut='paye').aggregate(
            total=Sum('total'))['total'] or Decimal('0')
        depenses_mois = Depense.objects.filter(
            statut='paye',
            date_depense__gte=start_of_month
        ).aggregate(total=Sum('total'))['total'] or Decimal('0')

        depenses_par_categorie = {}
        for depense in Depense.objects.filter(statut='paye'):
            depenses_par_categorie[depense.categorie] = depenses_par_categorie.get(
                depense.categorie, 0) + depense.total

        # Budget
        budgets_actifs = Budget.objects.filter(statut='en_cours')
        budget_total = budgets_actifs.aggregate(total=Sum('montant_total'))[
            'total'] or Decimal('0')
        budget_utilise = budgets_actifs.aggregate(total=Sum('montant_utilise'))[
            'total'] or Decimal('0')
        budget_restant = budget_total - budget_utilise

        # Créances / Dettes
        creances_client = Facture.objects.filter(
            Q(status='sent') | Q(status='partial') | Q(status='overdue')
        ).aggregate(total=Sum('remaining_amount'))['total'] or Decimal('0')

        dettes_fournisseurs = SupplierInvoice.objects.filter(
            Q(status='received') | Q(status='verified') | Q(status='partial')
        ).aggregate(total=Sum('remaining_amount'))['total'] or Decimal('0')

        # Marge bénéficiaire
        if ventes_total > 0:
            marge_beneficiaire = (
                (ventes_total - depenses_total) / ventes_total) * 100
        else:
            marge_beneficiaire = 0

        # Ratio de créances
        if ventes_total > 0:
            ratio_creances = (creances_client / ventes_total) * 100
        else:
            ratio_creances = 0

        stats = {
            'tresorerie_total': tresorerie_total,
            'tresorerie_par_type': tresorerie_par_type,
            'ventes_total': ventes_total,
            'ventes_mois': ventes_mois,
            'ventes_jour': ventes_jour,
            'depenses_total': depenses_total,
            'depenses_mois': depenses_mois,
            'depenses_par_categorie': depenses_par_categorie,
            'budget_total': budget_total,
            'budget_utilise': budget_utilise,
            'budget_restant': budget_restant,
            'creances_client': creances_client,
            'dettes_fournisseurs': dettes_fournisseurs,
            'marge_beneficiaire': round(marge_beneficiaire, 2),
            'ratio_creances': round(ratio_creances, 2)
        }

        serializer = FinancesStatsSerializer(stats)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Données pour le dashboard financier"""
        today = date.today()
        start_of_month = today.replace(day=1)

        # Ventes mensuelles (12 mois)
        ventes_mensuelles = []
        for i in range(11, -1, -1):
            mois = today - timedelta(days=30*i)
            debut = mois.replace(day=1)
            if i == 0:
                fin = today
            else:
                fin = (debut + timedelta(days=32)).replace(day=1)
            total = Vente.objects.filter(
                status='paid',
                sale_date__date__gte=debut,
                sale_date__date__lt=fin
            ).aggregate(total=Sum('total'))['total'] or Decimal('0')
            ventes_mensuelles.append({
                'mois': mois.strftime('%Y-%m'),
                'total': total
            })

        # Dépenses mensuelles (12 mois)
        depenses_mensuelles = []
        for i in range(11, -1, -1):
            mois = today - timedelta(days=30*i)
            debut = mois.replace(day=1)
            if i == 0:
                fin = today
            else:
                fin = (debut + timedelta(days=32)).replace(day=1)
            total = Depense.objects.filter(
                statut='paye',
                date_depense__gte=debut,
                date_depense__lt=fin
            ).aggregate(total=Sum('total'))['total'] or Decimal('0')
            depenses_mensuelles.append({
                'mois': mois.strftime('%Y-%m'),
                'total': total
            })

        # Alertes
        alertes_budget = []
        for budget in Budget.objects.filter(statut='en_cours'):
            if budget.montant_total > 0:
                pourcentage = (budget.montant_utilise /
                               budget.montant_total) * 100
                if pourcentage > 80:
                    alertes_budget.append({
                        'budget': budget.nom,
                        'pourcentage': round(pourcentage, 2),
                        'message': f"Budget {budget.nom} utilisé à {pourcentage:.0f}%"
                    })

        alertes_tresorerie = []
        for treso in Tresorerie.objects.filter(is_active=True):
            if treso.solde_actuel < treso.solde_minimum:
                alertes_tresorerie.append({
                    'tresorerie': treso.nom,
                    'solde': treso.solde_actuel,
                    'minimum': treso.solde_minimum,
                    'message': f"Solde de {treso.nom} inférieur au minimum"
                })

        alertes_echeances = []
        echeances = Facture.objects.filter(
            status__in=['sent', 'partial'],
            due_date__lte=today + timedelta(days=7)
        )
        for facture in echeances:
            alertes_echeances.append({
                'facture': facture.invoice_number,
                'client': facture.client.name,
                'due_date': facture.due_date,
                'montant': facture.remaining_amount
            })

        data = {
            'total_ventes': Vente.objects.filter(status='paid').aggregate(total=Sum('total'))['total'] or Decimal('0'),
            'total_depenses': Depense.objects.filter(statut='paye').aggregate(total=Sum('total'))['total'] or Decimal('0'),
            'total_tresorerie': Tresorerie.objects.aggregate(total=Sum('solde_actuel'))['total'] or Decimal('0'),
            'benefice': (Vente.objects.filter(status='paid').aggregate(total=Sum('total'))['total'] or Decimal('0')) -
            (Depense.objects.filter(statut='paye').aggregate(
                total=Sum('total'))['total'] or Decimal('0')),
            'evolution_ventes': 0,
            'evolution_depenses': 0,
            'alertes_budget': alertes_budget,
            'alertes_tresorerie': alertes_tresorerie,
            'alertes_echeances': alertes_echeances,
            'ventes_mensuelles': ventes_mensuelles,
            'depenses_mensuelles': depenses_mensuelles,
            'tresorerie_par_type': {},
            'depenses_par_categorie': {}
        }

        serializer = FinancesDashboardSerializer(data)
        return Response(serializer.data)
