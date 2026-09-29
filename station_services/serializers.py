from rest_framework import serializers
from decimal import Decimal
from django.db import transaction

from .models import (
    Cuve, MouvementCuve, Pompe, MouvementPompe,
    VenteCarburant, Service, VenteService,
    PrixCarburant, StatistiquesStation
)

from users.serializers import UserSerializer as CustomUserSerializer
from produits_stocks.serializers import WarehouseSerializer
from ventes_clients.serializers import ClientSerializer, FactureSerializer


# ============================================================
# 1. CUVE
# ============================================================

class CuveSerializer(serializers.ModelSerializer):
    type_carburant_display = serializers.CharField(
        source='get_type_carburant_display', read_only=True
    )
    taux_remplissage = serializers.FloatField(read_only=True)
    est_en_alerte = serializers.BooleanField(read_only=True)
    niveau_display = serializers.CharField(read_only=True)
    warehouse_details = WarehouseSerializer(source='warehouse', read_only=True)
    created_by_details = CustomUserSerializer(
        source='created_by', read_only=True)

    class Meta:
        model = Cuve
        fields = [
            'id', 'code', 'nom', 'type_carburant', 'type_carburant_display',
            'capacite_max', 'capacite_alerte', 'niveau_actuel',
            'taux_remplissage', 'est_en_alerte', 'niveau_display',
            'emplacement', 'warehouse', 'warehouse_details',
            'est_active', 'derniere_livraison',
            'created_at', 'updated_at', 'created_by', 'created_by_details',
        ]
        read_only_fields = [
            'niveau_actuel', 'derniere_livraison',
            'created_at', 'updated_at', 'created_by',
        ]

    def validate(self, attrs):
        capacite_max = attrs.get('capacite_max', getattr(
            self.instance, 'capacite_max', 0))
        capacite_alerte = attrs.get('capacite_alerte', getattr(
            self.instance, 'capacite_alerte', 0))
        if capacite_alerte and capacite_max and capacite_alerte >= capacite_max:
            raise serializers.ValidationError(
                "Le seuil d'alerte doit être inférieur à la capacité maximale."
            )
        return attrs


class CuveListSerializer(serializers.ModelSerializer):
    type_carburant_display = serializers.CharField(
        source='get_type_carburant_display', read_only=True
    )
    taux_remplissage = serializers.FloatField(read_only=True)
    est_en_alerte = serializers.BooleanField(read_only=True)

    class Meta:
        model = Cuve
        fields = [
            'id', 'code', 'nom', 'type_carburant', 'type_carburant_display',
            'niveau_actuel', 'capacite_max', 'taux_remplissage',
            'est_en_alerte', 'est_active',
        ]


class ApprovisionnementCuveSerializer(serializers.Serializer):
    """Serializer pour ajouter du stock à une cuve"""
    quantite = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    reference = serializers.CharField(
        required=False, allow_blank=True, default='')
    notes = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_quantite(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "La quantité doit être supérieure à zéro.")
        return value


class RetraitCuveSerializer(serializers.Serializer):
    """Serializer pour retirer du stock d'une cuve"""
    quantite = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    reference = serializers.CharField(
        required=False, allow_blank=True, default='')
    notes = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_quantite(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "La quantité doit être supérieure à zéro.")
        return value


# ============================================================
# 2. MOUVEMENT DE CUVE
# ============================================================

class MouvementCuveSerializer(serializers.ModelSerializer):
    type_mouvement_display = serializers.CharField(
        source='get_type_mouvement_display', read_only=True
    )
    cuve_details = CuveListSerializer(source='cuve', read_only=True)
    created_by_details = CustomUserSerializer(
        source='created_by', read_only=True)

    class Meta:
        model = MouvementCuve
        fields = [
            'id', 'cuve', 'cuve_details', 'type_mouvement', 'type_mouvement_display',
            'quantite', 'ancien_niveau', 'nouveau_niveau',
            'reference', 'notes', 'created_at', 'created_by', 'created_by_details',
        ]
        read_only_fields = fields


# ============================================================
# 3. POMPE
# ============================================================

class PompeSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    total_vendu = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True)
    est_disponible = serializers.BooleanField(read_only=True)
    cuve_details = CuveListSerializer(source='cuve', read_only=True)
    created_by_details = CustomUserSerializer(
        source='created_by', read_only=True)

    class Meta:
        model = Pompe
        fields = [
            'id', 'code', 'nom', 'cuve', 'cuve_details',
            'statut', 'statut_display', 'prix_litre',
            'compteur_initial', 'compteur_actuel', 'total_ventes', 'total_vendu',
            'emplacement', 'is_active', 'est_disponible',
            'created_at', 'updated_at', 'created_by', 'created_by_details',
        ]
        read_only_fields = [
            'compteur_actuel', 'total_ventes',
            'created_at', 'updated_at', 'created_by',
        ]


class PompeListSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    est_disponible = serializers.BooleanField(read_only=True)

    class Meta:
        model = Pompe
        fields = [
            'id', 'code', 'nom', 'cuve', 'statut', 'statut_display',
            'prix_litre', 'compteur_actuel', 'est_disponible', 'is_active',
        ]


class VentePompeSerializer(serializers.Serializer):
    """Serializer pour enregistrer une vente sur une pompe"""
    quantite = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    montant = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal('0.00'))
    reference = serializers.CharField(
        required=False, allow_blank=True, default='')
    notes = serializers.CharField(required=False, allow_blank=True, default='')


# ============================================================
# 4. MOUVEMENT DE POMPE
# ============================================================

class MouvementPompeSerializer(serializers.ModelSerializer):
    type_mouvement_display = serializers.CharField(
        source='get_type_mouvement_display', read_only=True
    )
    pompe_details = PompeListSerializer(source='pompe', read_only=True)
    created_by_details = CustomUserSerializer(
        source='created_by', read_only=True)

    class Meta:
        model = MouvementPompe
        fields = [
            'id', 'pompe', 'pompe_details', 'type_mouvement', 'type_mouvement_display',
            'quantite', 'montant', 'ancien_compteur', 'nouveau_compteur',
            'reference', 'notes', 'created_at', 'created_by', 'created_by_details',
        ]
        read_only_fields = fields


# ============================================================
# 5. VENTE DE CARBURANT
# ============================================================

class VenteCarburantSerializer(serializers.ModelSerializer):
    type_vente_display = serializers.CharField(
        source='get_type_vente_display', read_only=True)
    type_paiement_display = serializers.CharField(
        source='get_type_paiement_display', read_only=True)
    pompe_details = PompeListSerializer(source='pompe', read_only=True)
    client_details = ClientSerializer(source='client', read_only=True)
    facture_details = FactureSerializer(source='facture', read_only=True)
    created_by_details = CustomUserSerializer(
        source='created_by', read_only=True)

    class Meta:
        model = VenteCarburant
        fields = [
            'id', 'numero_vente', 'pompe', 'pompe_details',
            'client', 'client_details', 'type_vente', 'type_vente_display',
            'quantite', 'prix_unitaire', 'montant', 'remise', 'montant_net',
            'type_paiement', 'type_paiement_display', 'reference_paiement',
            'est_paye', 'facture', 'facture_details',
            'notes', 'date_vente', 'created_by', 'created_by_details', 'updated_at',
        ]
        read_only_fields = [
            'numero_vente', 'montant_net', 'date_vente',
            'updated_at', 'created_by',
        ]

    def validate(self, attrs):
        quantite = attrs.get('quantite')
        prix_unitaire = attrs.get('prix_unitaire')
        remise = attrs.get('remise', Decimal('0'))

        if quantite and prix_unitaire:
            montant = quantite * prix_unitaire
            attrs['montant'] = montant
            if remise and remise > montant:
                raise serializers.ValidationError(
                    "La remise ne peut pas dépasser le montant total."
                )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['created_by'] = request.user

        # Calculer montant si absent
        if not validated_data.get('montant'):
            validated_data['montant'] = (
                validated_data['quantite'] * validated_data['prix_unitaire']
            )
        validated_data['montant_net'] = (
            validated_data['montant'] -
            validated_data.get('remise', Decimal('0'))
        )

        # Enregistrer la vente sur la pompe
        pompe = validated_data.get('pompe')
        if pompe:
            pompe.enregistrer_vente(
                quantite=validated_data['quantite'],
                montant=validated_data['montant_net'],
                reference=validated_data.get('reference_paiement', ''),
                notes=validated_data.get('notes', ''),
                created_by=validated_data.get('created_by'),
            )

        return super().create(validated_data)


class VenteCarburantListSerializer(serializers.ModelSerializer):
    type_paiement_display = serializers.CharField(
        source='get_type_paiement_display', read_only=True)

    class Meta:
        model = VenteCarburant
        fields = [
            'id', 'numero_vente', 'pompe', 'client',
            'quantite', 'montant_net', 'type_paiement',
            'type_paiement_display', 'est_paye', 'date_vente',
        ]


# ============================================================
# 6. SERVICE
# ============================================================

class ServiceSerializer(serializers.ModelSerializer):
    type_service_display = serializers.CharField(
        source='get_type_service_display', read_only=True
    )
    created_by_details = CustomUserSerializer(
        source='created_by', read_only=True)

    class Meta:
        model = Service
        fields = [
            'id', 'code', 'nom', 'type_service', 'type_service_display',
            'prix', 'description', 'duree_estimee', 'est_actif',
            'created_at', 'updated_at', 'created_by', 'created_by_details',
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']


class ServiceListSerializer(serializers.ModelSerializer):
    type_service_display = serializers.CharField(
        source='get_type_service_display', read_only=True
    )

    class Meta:
        model = Service
        fields = ['id', 'code', 'nom', 'type_service', 'type_service_display',
                  'prix', 'duree_estimee', 'est_actif']


# ============================================================
# 7. VENTE DE SERVICE
# ============================================================

class VenteServiceSerializer(serializers.ModelSerializer):
    type_paiement_display = serializers.CharField(
        source='get_type_paiement_display', read_only=True
    )
    service_details = ServiceListSerializer(source='service', read_only=True)
    client_details = ClientSerializer(source='client', read_only=True)
    facture_details = FactureSerializer(source='facture', read_only=True)
    created_by_details = CustomUserSerializer(
        source='created_by', read_only=True)

    class Meta:
        model = VenteService
        fields = [
            'id', 'numero_vente', 'service', 'service_details',
            'client', 'client_details', 'quantite',
            'prix_unitaire', 'montant', 'remise', 'montant_net',
            'type_paiement', 'type_paiement_display', 'est_paye',
            'facture', 'facture_details', 'notes',
            'date_vente', 'created_by', 'created_by_details', 'updated_at',
        ]
        read_only_fields = [
            'numero_vente', 'montant_net', 'date_vente',
            'updated_at', 'created_by',
        ]

    def validate(self, attrs):
        service = attrs.get('service')
        quantite = attrs.get('quantite', 1)
        prix_unitaire = attrs.get('prix_unitaire')
        remise = attrs.get('remise', Decimal('0'))

        if service and not prix_unitaire:
            attrs['prix_unitaire'] = service.prix

        if prix_unitaire and quantite:
            montant = prix_unitaire * quantite
            attrs['montant'] = montant
            if remise and remise > montant:
                raise serializers.ValidationError(
                    "La remise ne peut pas dépasser le montant total."
                )
        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['created_by'] = request.user

        if not validated_data.get('montant'):
            validated_data['montant'] = (
                validated_data['prix_unitaire'] *
                validated_data.get('quantite', 1)
            )
        validated_data['montant_net'] = (
            validated_data['montant'] -
            validated_data.get('remise', Decimal('0'))
        )
        return super().create(validated_data)


# ============================================================
# 8. PRIX CARBURANT
# ============================================================

class PrixCarburantSerializer(serializers.ModelSerializer):
    cuve_details = CuveListSerializer(source='cuve', read_only=True)
    created_by_details = CustomUserSerializer(
        source='created_by', read_only=True)

    class Meta:
        model = PrixCarburant
        fields = [
            'id', 'cuve', 'cuve_details', 'prix_litre',
            'date_application', 'date_fin', 'est_actif',
            'notes', 'created_by', 'created_by_details', 'created_at',
        ]
        read_only_fields = ['created_at', 'created_by']


# ============================================================
# 9. STATISTIQUES STATION
# ============================================================

class StatistiquesStationSerializer(serializers.ModelSerializer):
    class Meta:
        model = StatistiquesStation
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']
