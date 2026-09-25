from django.shortcuts import render

# Create your views here.
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal

from .models import (
    Cuve, MouvementCuve, Pompe, MouvementPompe,
    VenteCarburant, Service, VenteService,
    PrixCarburant, StatistiquesStation
)
from .serializers import (
    CuveSerializer, CuveListSerializer,
    ApprovisionnementCuveSerializer, RetraitCuveSerializer,
    MouvementCuveSerializer,
    PompeSerializer, PompeListSerializer, VentePompeSerializer,
    MouvementPompeSerializer,
    VenteCarburantSerializer, VenteCarburantListSerializer,
    ServiceSerializer, ServiceListSerializer,
    VenteServiceSerializer,
    PrixCarburantSerializer,
    StatistiquesStationSerializer,
)
from .filters import (
    CuveFilter, PompeFilter, VenteCarburantFilter,
    VenteServiceFilter, MouvementCuveFilter, MouvementPompeFilter
)


# ============================================================
# 1. CUVE
# ============================================================

class CuveViewSet(viewsets.ModelViewSet):
    queryset = Cuve.objects.select_related('warehouse', 'created_by').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend,
                       filters.SearchFilter, filters.OrderingFilter]
    filterset_class = CuveFilter
    search_fields = ['code', 'nom', 'emplacement']
    ordering_fields = ['nom', 'niveau_actuel', 'capacite_max', 'created_at']
    ordering = ['nom']

    def get_serializer_class(self):
        if self.action == 'list':
            return CuveListSerializer
        return CuveSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='approvisionner')
    def approvisionner(self, request, pk=None):
        """Ajouter du carburant dans la cuve"""
        cuve = self.get_object()
        serializer = ApprovisionnementCuveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            nouveau_niveau = cuve.ajouter_stock(
                quantite=serializer.validated_data['quantite'],
                reference=serializer.validated_data.get('reference', ''),
                notes=serializer.validated_data.get('notes', ''),
                created_by=request.user
            )
            return Response({
                'success': True,
                'message': 'Approvisionnement enregistré',
                'nouveau_niveau': nouveau_niveau,
                'cuve': CuveSerializer(cuve).data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='retirer')
    def retirer(self, request, pk=None):
        """Retirer du carburant de la cuve"""
        cuve = self.get_object()
        serializer = RetraitCuveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            nouveau_niveau = cuve.retirer_stock(
                quantite=serializer.validated_data['quantite'],
                reference=serializer.validated_data.get('reference', ''),
                notes=serializer.validated_data.get('notes', ''),
                created_by=request.user
            )
            return Response({
                'success': True,
                'message': 'Retrait enregistré',
                'nouveau_niveau': nouveau_niveau,
                'cuve': CuveSerializer(cuve).data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'], url_path='mouvements')
    def mouvements(self, request, pk=None):
        """Liste des mouvements d'une cuve"""
        cuve = self.get_object()
        mouvements = cuve.mouvements.select_related('created_by').all()
        page = self.paginate_queryset(mouvements)
        if page is not None:
            serializer = MouvementCuveSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = MouvementCuveSerializer(mouvements, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='alertes')
    def alertes(self, request):
        """Cuves en alerte"""
        cuves = self.get_queryset().filter(
            niveau_actuel__lte=models.F('capacite_alerte'),
            est_active=True
        )
        serializer = CuveListSerializer(cuves, many=True)
        return Response(serializer.data)


# ============================================================
# 2. MOUVEMENT DE CUVE
# ============================================================

class MouvementCuveViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MouvementCuve.objects.select_related('cuve', 'created_by').all()
    serializer_class = MouvementCuveSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = MouvementCuveFilter
    ordering_fields = ['created_at', 'quantite']
    ordering = ['-created_at']


# ============================================================
# 3. POMPE
# ============================================================

class PompeViewSet(viewsets.ModelViewSet):
    queryset = Pompe.objects.select_related('cuve', 'created_by').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend,
                       filters.SearchFilter, filters.OrderingFilter]
    filterset_class = PompeFilter
    search_fields = ['code', 'nom', 'emplacement']
    ordering_fields = ['nom', 'prix_litre', 'compteur_actuel', 'created_at']
    ordering = ['nom']

    def get_serializer_class(self):
        if self.action == 'list':
            return PompeListSerializer
        return PompeSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='enregistrer-vente')
    def enregistrer_vente(self, request, pk=None):
        """Enregistrer une vente sur la pompe"""
        pompe = self.get_object()
        serializer = VentePompeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            nouveau_compteur = pompe.enregistrer_vente(
                quantite=serializer.validated_data['quantite'],
                montant=serializer.validated_data['montant'],
                reference=serializer.validated_data.get('reference', ''),
                notes=serializer.validated_data.get('notes', ''),
                created_by=request.user
            )
            return Response({
                'success': True,
                'message': 'Vente enregistrée',
                'nouveau_compteur': nouveau_compteur,
                'pompe': PompeSerializer(pompe).data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='changer-statut')
    def changer_statut(self, request, pk=None):
        """Changer le statut de la pompe"""
        pompe = self.get_object()
        nouveau_statut = request.data.get('statut')
        if nouveau_statut not in dict(Pompe.STATUT_CHOICES):
            return Response(
                {'error': 'Statut invalide'},
                status=status.HTTP_400_BAD_REQUEST
            )
        pompe.statut = nouveau_statut
        pompe.save(update_fields=['statut', 'updated_at'])
        return Response(PompeSerializer(pompe).data)

    @action(detail=False, methods=['get'], url_path='disponibles')
    def disponibles(self, request):
        """Pompes disponibles"""
        pompes = self.get_queryset().filter(statut='active', is_active=True)
        serializer = PompeListSerializer(pompes, many=True)
        return Response(serializer.data)


# ============================================================
# 4. MOUVEMENT DE POMPE
# ============================================================

class MouvementPompeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MouvementPompe.objects.select_related(
        'pompe', 'created_by').all()
    serializer_class = MouvementPompeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = MouvementPompeFilter
    ordering_fields = ['created_at', 'quantite', 'montant']
    ordering = ['-created_at']


# ============================================================
# 5. VENTE DE CARBURANT
# ============================================================

class VenteCarburantViewSet(viewsets.ModelViewSet):
    queryset = VenteCarburant.objects.select_related(
        'pompe', 'client', 'facture', 'created_by'
    ).all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend,
                       filters.SearchFilter, filters.OrderingFilter]
    filterset_class = VenteCarburantFilter
    search_fields = ['numero_vente', 'reference_paiement']
    ordering_fields = ['date_vente', 'montant_net', 'quantite']
    ordering = ['-date_vente']

    def get_serializer_class(self):
        if self.action == 'list':
            return VenteCarburantListSerializer
        return VenteCarburantSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'], url_path='aujourd-hui')
    def aujourd_hui(self, request):
        """Ventes du jour"""
        today = timezone.now().date()
        ventes = self.get_queryset().filter(date_vente__date=today)
        serializer = VenteCarburantListSerializer(ventes, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """Statistiques des ventes carburant"""
        qs = self.filter_queryset(self.get_queryset())
        total = qs.aggregate(
            total_litres=Sum('quantite'),
            total_montant=Sum('montant_net'),
            nb_ventes=Count('id')
        )
        return Response(total)


# ============================================================
# 6. SERVICE
# ============================================================

class ServiceViewSet(viewsets.ModelViewSet):
    queryset = Service.objects.select_related('created_by').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend,
                       filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'nom', 'description']
    filterset_fields = ['type_service', 'est_actif']
    ordering_fields = ['nom', 'prix', 'created_at']
    ordering = ['nom']

    def get_serializer_class(self):
        if self.action == 'list':
            return ServiceListSerializer
        return ServiceSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'], url_path='actifs')
    def actifs(self, request):
        """Services actifs"""
        services = self.get_queryset().filter(est_actif=True)
        serializer = ServiceListSerializer(services, many=True)
        return Response(serializer.data)


# ============================================================
# 7. VENTE DE SERVICE
# ============================================================

class VenteServiceViewSet(viewsets.ModelViewSet):
    queryset = VenteService.objects.select_related(
        'service', 'client', 'facture', 'created_by'
    ).all()
    serializer_class = VenteServiceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend,
                       filters.SearchFilter, filters.OrderingFilter]
    filterset_class = VenteServiceFilter
    search_fields = ['numero_vente']
    ordering_fields = ['date_vente', 'montant_net', 'quantite']
    ordering = ['-date_vente']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'], url_path='aujourd-hui')
    def aujourd_hui(self, request):
        """Ventes de services du jour"""
        today = timezone.now().date()
        ventes = self.get_queryset().filter(date_vente__date=today)
        serializer = VenteServiceSerializer(ventes, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """Statistiques des ventes de services"""
        qs = self.filter_queryset(self.get_queryset())
        total = qs.aggregate(
            total_montant=Sum('montant_net'),
            nb_ventes=Count('id')
        )
        return Response(total)


# ============================================================
# 8. PRIX CARBURANT
# ============================================================

class PrixCarburantViewSet(viewsets.ModelViewSet):
    queryset = PrixCarburant.objects.select_related('cuve', 'created_by').all()
    serializer_class = PrixCarburantSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['cuve', 'est_actif']
    ordering_fields = ['date_application', 'prix_litre']
    ordering = ['-date_application']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'], url_path='actifs')
    def actifs(self, request):
        """Prix actifs"""
        prix = self.get_queryset().filter(est_actif=True)
        serializer = PrixCarburantSerializer(prix, many=True)
        return Response(serializer.data)


# ============================================================
# 9. STATISTIQUES STATION
# ============================================================

class StatistiquesStationViewSet(viewsets.ModelViewSet):
    queryset = StatistiquesStation.objects.all()
    serializer_class = StatistiquesStationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['date']
    ordering_fields = ['date']
    ordering = ['-date']

    @action(detail=False, methods=['post'], url_path='calculer')
    def calculer(self, request):
        """Calculer/actualiser les statistiques d'une date"""
        date_str = request.data.get('date')
        if date_str:
            try:
                target_date = date.fromisoformat(date_str)
            except ValueError:
                return Response(
                    {'error': 'Format de date invalide (YYYY-MM-DD)'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            target_date = timezone.now().date()

        # Calcul des ventes carburant
        ventes_carb = VenteCarburant.objects.filter(
            date_vente__date=target_date)
        total_carb = ventes_carb.aggregate(
            total=Sum('montant_net'),
            litres=Sum('quantite'),
            nb=Count('id')
        )

        # Calcul des ventes services
        ventes_serv = VenteService.objects.filter(date_vente__date=target_date)
        total_serv = ventes_serv.aggregate(
            total=Sum('montant_net'),
            nb=Count('id')
        )

        total_ca = (total_carb['total'] or Decimal('0')) + \
            (total_serv['total'] or Decimal('0'))

        stats, _ = StatistiquesStation.objects.update_or_create(
            date=target_date,
            defaults={
                'total_ventes_carburant': total_carb['total'] or Decimal('0'),
                'total_litres_vendus': total_carb['litres'] or Decimal('0'),
                'total_ventes_services': total_serv['total'] or Decimal('0'),
                'total_ca': total_ca,
                'nb_ventes_carburant': total_carb['nb'] or 0,
                'nb_ventes_services': total_serv['nb'] or 0,
            }
        )
        return Response(StatistiquesStationSerializer(stats).data)

    @action(detail=False, methods=['get'], url_path='dashboard')
    def dashboard(self, request):
        """Tableau de bord global"""
        today = timezone.now().date()
        debut_mois = today.replace(day=1)

        # Ventes carburant du jour
        ventes_carb_jour = VenteCarburant.objects.filter(date_vente__date=today).aggregate(
            total=Sum('montant_net'), litres=Sum('quantite'), nb=Count('id')
        )
        # Ventes services du jour
        ventes_serv_jour = VenteService.objects.filter(date_vente__date=today).aggregate(
            total=Sum('montant_net'), nb=Count('id')
        )
        # Ventes carburant du mois
        ventes_carb_mois = VenteCarburant.objects.filter(
            date_vente__date__gte=debut_mois
        ).aggregate(total=Sum('montant_net'), litres=Sum('quantite'))

        # Cuves en alerte
        cuves_alerte = Cuve.objects.filter(
            niveau_actuel__lte=models.F('capacite_alerte'),
            est_active=True
        ).count()

        # Pompes disponibles
        pompes_dispo = Pompe.objects.filter(
            statut='active', is_active=True).count()

        return Response({
            'date': today,
            'ventes_carburant_jour': ventes_carb_jour,
            'ventes_services_jour': ventes_serv_jour,
            'ventes_carburant_mois': ventes_carb_mois,
            'cuves_en_alerte': cuves_alerte,
            'pompes_disponibles': pompes_dispo,
            'ca_jour': (ventes_carb_jour['total'] or 0) + (ventes_serv_jour['total'] or 0),
        })
