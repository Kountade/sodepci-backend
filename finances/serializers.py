# finances/serializers.py

from rest_framework import serializers
from django.db import transaction
from decimal import Decimal
from datetime import date

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
from users.models import CustomUser
from ventes_clients.models import Vente, Facture, Paiement, Client
from achats_fournisseurs.models import Supplier, PurchaseOrder, SupplierInvoice


# ==================== COMPTE COMPTABLE ====================
class CompteComptableSerializer(serializers.ModelSerializer):
    """Serializer pour les comptes comptables"""
    type_display = serializers.CharField(
        source='get_type_display', read_only=True)
    classe_display = serializers.CharField(
        source='get_classe_display', read_only=True)
    parent_nom = serializers.CharField(source='parent.nom', read_only=True)
    full_path = serializers.ReadOnlyField()
    solde_display = serializers.SerializerMethodField()

    class Meta:
        model = CompteComptable
        fields = [
            'id', 'numero', 'nom', 'nom_complet',
            'type', 'type_display',
            'classe', 'classe_display',
            'parent', 'parent_nom',
            'niveau', 'full_path',
            'solde', 'solde_display',
            'solde_initial',
            'is_analytique', 'is_budgetaire',
            'is_active', 'is_imported',
            'notes',
            'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'solde']

    def get_solde_display(self, obj):
        return f"{obj.solde:,.0f} FCFA" if obj.solde else "0 FCFA"

    def validate_numero(self, value):
        if CompteComptable.objects.exclude(id=self.instance.id if self.instance else None).filter(numero=value).exists():
            raise serializers.ValidationError(
                "Ce numéro de compte existe déjà")
        return value


class CompteComptableListSerializer(serializers.ModelSerializer):
    """Serializer léger pour la liste des comptes"""
    solde_display = serializers.SerializerMethodField()
    full_path = serializers.ReadOnlyField()

    class Meta:
        model = CompteComptable
        fields = [
            'id', 'numero', 'nom', 'type', 'classe',
            'solde', 'solde_display',
            'is_active', 'full_path'
        ]

    def get_solde_display(self, obj):
        return f"{obj.solde:,.0f} FCFA" if obj.solde else "0 FCFA"


# ==================== ÉCRITURE COMPTABLE ====================
class EcritureComptableSerializer(serializers.ModelSerializer):
    """Serializer pour les écritures comptables"""
    type_display = serializers.CharField(
        source='get_type_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    compte_debit_nom = serializers.CharField(
        source='compte_debit.nom', read_only=True)
    compte_debit_numero = serializers.CharField(
        source='compte_debit.numero', read_only=True)
    compte_credit_nom = serializers.CharField(
        source='compte_credit.nom', read_only=True)
    compte_credit_numero = serializers.CharField(
        source='compte_credit.numero', read_only=True)

    created_by_name = serializers.CharField(
        source='created_by.full_name', read_only=True)
    validated_by_name = serializers.CharField(
        source='validated_by.full_name', read_only=True)

    vente_number = serializers.CharField(
        source='vente.invoice_number', read_only=True)
    facture_number = serializers.CharField(
        source='facture.invoice_number', read_only=True)
    supplier_name = serializers.CharField(
        source='supplier.name', read_only=True)
    client_name = serializers.CharField(source='client.name', read_only=True)

    class Meta:
        model = EcritureComptable
        fields = [
            'id', 'numero',
            'date_ecriture', 'date_comptable', 'date_echeance',
            'compte_debit', 'compte_debit_nom', 'compte_debit_numero',
            'compte_credit', 'compte_credit_nom', 'compte_credit_numero',
            'montant', 'taxe', 'total',
            'reference', 'type', 'type_display',
            'statut', 'statut_display',
            'vente', 'vente_number',
            'facture', 'facture_number',
            'paiement',
            'supplier_invoice',
            'purchase_order',
            'supplier', 'supplier_name',
            'client', 'client_name',
            'description', 'notes',
            'created_at', 'updated_at',
            'created_by', 'created_by_name',
            'validated_by', 'validated_by_name',
            'validated_at'
        ]
        read_only_fields = [
            'id', 'numero', 'date_comptable',
            'created_at', 'updated_at',
            'statut', 'validated_by', 'validated_at'
        ]

    def validate(self, data):
        """Validation croisée"""
        if data.get('compte_debit') == data.get('compte_credit'):
            raise serializers.ValidationError(
                "Le compte débit et le compte crédit ne peuvent pas être identiques"
            )
        if data.get('montant', 0) <= 0:
            raise serializers.ValidationError(
                {"montant": "Le montant doit être supérieur à 0"}
            )
        return data

# finances/serializers.py


class EcritureComptableCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création d'écritures comptables"""

    class Meta:
        model = EcritureComptable
        fields = [
            'date_ecriture', 'date_echeance',
            'compte_debit', 'compte_credit',
            'montant', 'taxe',
            'reference', 'type',
            'vente', 'facture', 'paiement',
            'supplier_invoice', 'purchase_order',
            'supplier', 'client',
            'description', 'notes'
        ]

    @transaction.atomic
    def create(self, validated_data):
        from django.utils import timezone

        # Générer le numéro d'écriture
        last_ecriture = EcritureComptable.objects.order_by('-id').first()
        if last_ecriture and last_ecriture.numero:
            try:
                num = int(last_ecriture.numero.split('-')[-1]) + 1
            except (ValueError, IndexError):
                num = 1
        else:
            num = 1
        numero = f"EC-{date.today().year}-{num:04d}"

        # ✅ Récupérer l'utilisateur depuis le contexte
        user = self.context.get('request').user

        # ✅ Créer l'écriture sans 'created_by' dans validated_data
        ecriture = EcritureComptable.objects.create(
            numero=numero,
            statut='brouillon',
            created_by=user,  # ✅ Passé explicitement
            **validated_data  # ✅ validated_data ne contient PAS 'created_by'
        )
        return ecriture


# ==================== TRÉSORERIE ====================
class TresorerieSerializer(serializers.ModelSerializer):
    """Serializer pour la trésorerie"""
    type_display = serializers.CharField(
        source='get_type_display', read_only=True)
    solde_actuel_display = serializers.SerializerMethodField()
    solde_initial_display = serializers.SerializerMethodField()

    class Meta:
        model = Tresorerie
        fields = [
            'id', 'nom', 'code',
            'type', 'type_display',
            'banque', 'iban', 'bic', 'titulaire',
            'solde_initial', 'solde_initial_display',
            'solde_actuel', 'solde_actuel_display',
            'solde_minimum',
            'is_active', 'is_default',
            'notes',
            'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'solde_actuel']

    def get_solde_actuel_display(self, obj):
        return f"{obj.solde_actuel:,.0f} FCFA" if obj.solde_actuel else "0 FCFA"

    def get_solde_initial_display(self, obj):
        return f"{obj.solde_initial:,.0f} FCFA" if obj.solde_initial else "0 FCFA"

    def validate_code(self, value):
        if Tresorerie.objects.exclude(id=self.instance.id if self.instance else None).filter(code=value).exists():
            raise serializers.ValidationError("Ce code existe déjà")
        return value


class TresorerieListSerializer(serializers.ModelSerializer):
    """Serializer léger pour la liste des trésoreries"""
    solde_display = serializers.SerializerMethodField()

    class Meta:
        model = Tresorerie
        fields = [
            'id', 'nom', 'code', 'type',
            'solde_actuel', 'solde_display',
            'is_active', 'is_default'
        ]

    def get_solde_display(self, obj):
        return f"{obj.solde_actuel:,.0f} FCFA" if obj.solde_actuel else "0 FCFA"


# ==================== MOUVEMENT TRÉSORERIE ====================
class MouvementTresorerieSerializer(serializers.ModelSerializer):
    """Serializer pour les mouvements de trésorerie"""
    type_display = serializers.CharField(
        source='get_type_display', read_only=True)
    categorie_display = serializers.CharField(
        source='get_categorie_display', read_only=True)

    tresorerie_nom = serializers.CharField(
        source='tresorerie.nom', read_only=True)
    created_by_name = serializers.CharField(
        source='created_by.full_name', read_only=True)

    vente_number = serializers.CharField(
        source='vente.invoice_number', read_only=True)
    supplier_name = serializers.CharField(
        source='supplier.name', read_only=True)

    class Meta:
        model = MouvementTresorerie
        fields = [
            'id',
            'tresorerie', 'tresorerie_nom',
            'type', 'type_display',
            'categorie', 'categorie_display',
            'montant',
            'date_mouvement', 'date_valeur',
            'reference', 'description',
            'ecriture',
            'vente', 'vente_number',
            'paiement',
            'supplier_invoice',
            'supplier', 'supplier_name',
            'notes',
            'created_at', 'created_by', 'created_by_name'
        ]
        read_only_fields = ['id', 'date_mouvement', 'created_at']

# finances/serializers.py - MouvementTresorerieCreateSerializer


class MouvementTresorerieCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création de mouvements de trésorerie"""

    class Meta:
        model = MouvementTresorerie
        fields = [
            'tresorerie', 'type', 'categorie',
            'montant', 'date_valeur',
            'reference', 'description',
            'ecriture',
            'vente', 'paiement',
            'supplier_invoice', 'supplier',
            'notes'
        ]

    def validate_montant(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Le montant doit être supérieur à 0")
        return value

    @transaction.atomic
    def create(self, validated_data):
        # ✅ Récupérer l'utilisateur depuis le contexte
        user = self.context.get('request').user

        # ✅ Créer le mouvement sans 'created_by' dans validated_data
        mouvement = MouvementTresorerie.objects.create(
            created_by=user,  # ✅ Passé explicitement
            **validated_data   # ✅ validated_data ne contient PAS 'created_by'
        )
        return mouvement

# ==================== DÉPENSE ====================


class DepenseSerializer(serializers.ModelSerializer):
    """Serializer pour les dépenses"""
    categorie_display = serializers.CharField(
        source='get_categorie_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    supplier_name = serializers.CharField(
        source='supplier.name', read_only=True)
    created_by_name = serializers.CharField(
        source='created_by.full_name', read_only=True)
    approuve_par_name = serializers.CharField(
        source='approuve_par.full_name', read_only=True)

    tresorerie_nom = serializers.CharField(
        source='tresorerie.nom', read_only=True)
    purchase_order_number = serializers.CharField(
        source='purchase_order.po_number', read_only=True)

    class Meta:
        model = Depense
        fields = [
            'id', 'reference',
            'categorie', 'categorie_display',
            'description',
            'montant', 'taxe', 'total',
            'date_depense', 'date_echeance',
            'mode_paiement', 'reference_paiement', 'date_paiement',
            'supplier', 'supplier_name',
            'statut', 'statut_display',
            'piece_jointe',
            'tresorerie', 'tresorerie_nom',
            'ecriture',
            'purchase_order', 'purchase_order_number',
            'notes',
            'created_at', 'updated_at',
            'created_by', 'created_by_name',
            'approuve_par', 'approuve_par_name',
            'approuve_le'
        ]
        read_only_fields = ['id', 'reference', 'created_at', 'updated_at']

# finances/serializers.py - DepenseCreateSerializer


class DepenseCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création de dépenses"""

    class Meta:
        model = Depense
        fields = [
            'categorie', 'description',
            'montant', 'taxe',
            'date_depense', 'date_echeance',
            'mode_paiement', 'reference_paiement',
            'supplier',
            'piece_jointe',
            'tresorerie',
            'purchase_order',
            'notes'
        ]

    def validate_montant(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Le montant doit être supérieur à 0")
        return value

    @transaction.atomic
    def create(self, validated_data):
        # Générer la référence
        last_depense = Depense.objects.order_by('-id').first()
        if last_depense and last_depense.reference:
            try:
                num = int(last_depense.reference.split('-')[-1]) + 1
            except (ValueError, IndexError):
                num = 1
        else:
            num = 1
        reference = f"DEP-{date.today().year}-{num:04d}"

        # ✅ Récupérer l'utilisateur depuis le contexte
        user = self.context.get('request').user

        # ✅ Créer la dépense sans 'created_by' dans validated_data
        depense = Depense.objects.create(
            reference=reference,
            statut='en_attente',
            created_by=user,  # ✅ Passé explicitement
            **validated_data   # ✅ validated_data ne contient PAS 'created_by'
        )
        return depense


class DepenseApproveSerializer(serializers.Serializer):
    """Serializer pour l'approbation des dépenses"""
    notes = serializers.CharField(required=False, allow_blank=True)


# ==================== BUDGET ====================
class BudgetCategorieSerializer(serializers.ModelSerializer):
    """Serializer pour les catégories de budget"""

    class Meta:
        model = BudgetCategorie
        fields = ['id', 'nom', 'description', 'code', 'is_active']
        read_only_fields = ['id']


class BudgetLigneSerializer(serializers.ModelSerializer):
    """Serializer pour les lignes de budget"""
    categorie_nom = serializers.CharField(
        source='categorie.nom', read_only=True)
    categorie_code = serializers.CharField(
        source='categorie.code', read_only=True)
    montant_prevu_display = serializers.SerializerMethodField()
    montant_utilise_display = serializers.SerializerMethodField()
    montant_restant_display = serializers.SerializerMethodField()
    pourcentage_utilise = serializers.SerializerMethodField()

    class Meta:
        model = BudgetLigne
        fields = [
            'id',
            'categorie', 'categorie_nom', 'categorie_code',
            'montant_prevu', 'montant_prevu_display',
            'montant_utilise', 'montant_utilise_display',
            'montant_restant', 'montant_restant_display',
            'pourcentage_utilise',
            'notes'
        ]

    def get_montant_prevu_display(self, obj):
        return f"{obj.montant_prevu:,.0f} FCFA"

    def get_montant_utilise_display(self, obj):
        return f"{obj.montant_utilise:,.0f} FCFA"

    def get_montant_restant_display(self, obj):
        return f"{obj.montant_restant:,.0f} FCFA"

    def get_pourcentage_utilise(self, obj):
        if obj.montant_prevu > 0:
            return round((obj.montant_utilise / obj.montant_prevu) * 100, 2)
        return 0


class BudgetSerializer(serializers.ModelSerializer):
    """Serializer pour les budgets"""
    type_display = serializers.CharField(
        source='get_type_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    lignes = BudgetLigneSerializer(many=True, read_only=True)

    montant_total_display = serializers.SerializerMethodField()
    montant_utilise_display = serializers.SerializerMethodField()
    montant_restant_display = serializers.SerializerMethodField()
    pourcentage_utilise = serializers.SerializerMethodField()

    created_by_name = serializers.CharField(
        source='created_by.full_name', read_only=True)

    class Meta:
        model = Budget
        fields = [
            'id', 'nom', 'type', 'type_display',
            'montant_total', 'montant_total_display',
            'montant_utilise', 'montant_utilise_display',
            'montant_restant', 'montant_restant_display',
            'pourcentage_utilise',
            'date_debut', 'date_fin',
            'statut', 'statut_display',
            'lignes',
            'notes',
            'created_at', 'updated_at', 'created_by', 'created_by_name'
        ]
        read_only_fields = ['id', 'created_at',
                            'updated_at', 'montant_utilise', 'montant_restant']

    def get_montant_total_display(self, obj):
        return f"{obj.montant_total:,.0f} FCFA"

    def get_montant_utilise_display(self, obj):
        return f"{obj.montant_utilise:,.0f} FCFA"

    def get_montant_restant_display(self, obj):
        return f"{obj.montant_restant:,.0f} FCFA"

    def get_pourcentage_utilise(self, obj):
        if obj.montant_total > 0:
            return round((obj.montant_utilise / obj.montant_total) * 100, 2)
        return 0

# finances/serializers.py - BudgetCreateSerializer


class BudgetCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création de budgets"""
    lignes = BudgetLigneSerializer(many=True, required=False)

    class Meta:
        model = Budget
        fields = [
            'nom', 'type',
            'montant_total',
            'date_debut', 'date_fin',
            'lignes',
            'notes'
        ]

    @transaction.atomic
    def create(self, validated_data):
        lignes_data = validated_data.pop('lignes', [])

        # ✅ Récupérer l'utilisateur depuis le contexte
        user = self.context.get('request').user

        # ✅ Créer le budget sans 'created_by' dans validated_data
        budget = Budget.objects.create(
            statut='en_cours',
            created_by=user,  # ✅ Passé explicitement
            **validated_data   # ✅ validated_data ne contient PAS 'created_by'
        )

        for ligne_data in lignes_data:
            BudgetLigne.objects.create(budget=budget, **ligne_data)

        # Mettre à jour le montant utilisé
        budget.update_utilise()

        return budget

# ==================== RAPPORT FINANCIER ====================


class RapportFinancierSerializer(serializers.ModelSerializer):
    """Serializer pour les rapports financiers"""
    type_display = serializers.CharField(
        source='get_type_display', read_only=True)
    format_display = serializers.CharField(
        source='get_format_display', read_only=True)
    created_by_name = serializers.CharField(
        source='created_by.full_name', read_only=True)

    class Meta:
        model = RapportFinancier
        fields = [
            'id', 'type', 'type_display',
            'nom',
            'date_debut', 'date_fin',
            'format', 'format_display',
            'contenu',
            'fichier',
            'created_at', 'created_by', 'created_by_name'
        ]
        read_only_fields = ['id', 'created_at']

# finances/serializers.py - RapportFinancierCreateSerializer


class RapportFinancierCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création de rapports financiers"""

    class Meta:
        model = RapportFinancier
        fields = [
            'type', 'nom',
            'date_debut', 'date_fin',
            'format'
        ]

    @transaction.atomic
    def create(self, validated_data):
        # ✅ Récupérer l'utilisateur depuis le contexte
        user = self.context.get('request').user

        # ✅ Créer le rapport sans 'created_by' dans validated_data
        rapport = RapportFinancier.objects.create(
            created_by=user,  # ✅ Passé explicitement
            **validated_data   # ✅ validated_data ne contient PAS 'created_by'
        )

        # Ici, vous pouvez déclencher la génération du rapport
        # rapport.generer()

        return rapport
# ==================== CONFIGURATION FINANCIÈRE ====================


class ConfigurationFinanciereSerializer(serializers.ModelSerializer):
    """Serializer pour la configuration financière"""
    updated_by_name = serializers.CharField(
        source='updated_by.full_name', read_only=True)

    class Meta:
        model = ConfigurationFinanciere
        fields = [
            'id',
            'devise', 'devise_symbole',
            'exercice_debut', 'exercice_fin',
            'taxe_default',
            'arrondi',
            'auto_validation', 'budget_alerte',
            'updated_at', 'updated_by', 'updated_by_name'
        ]
        read_only_fields = ['id', 'updated_at']


# ==================== STATISTIQUES FINANCIÈRES ====================
class FinancesStatsSerializer(serializers.Serializer):
    """Serializer pour les statistiques financières"""

    # Trésorerie
    tresorerie_total = serializers.DecimalField(
        max_digits=15, decimal_places=2)
    tresorerie_par_type = serializers.DictField()

    # Ventes
    ventes_total = serializers.DecimalField(max_digits=15, decimal_places=2)
    ventes_mois = serializers.DecimalField(max_digits=15, decimal_places=2)
    ventes_jour = serializers.DecimalField(max_digits=15, decimal_places=2)

    # Dépenses
    depenses_total = serializers.DecimalField(max_digits=15, decimal_places=2)
    depenses_mois = serializers.DecimalField(max_digits=15, decimal_places=2)
    depenses_par_categorie = serializers.DictField()

    # Budget
    budget_total = serializers.DecimalField(max_digits=15, decimal_places=2)
    budget_utilise = serializers.DecimalField(max_digits=15, decimal_places=2)
    budget_restant = serializers.DecimalField(max_digits=15, decimal_places=2)

    # Créances / Dettes
    creances_client = serializers.DecimalField(max_digits=15, decimal_places=2)
    dettes_fournisseurs = serializers.DecimalField(
        max_digits=15, decimal_places=2)

    # Indicateurs
    marge_beneficiaire = serializers.DecimalField(
        max_digits=5, decimal_places=2)
    ratio_creances = serializers.DecimalField(max_digits=5, decimal_places=2)


# ==================== DASHBOARD FINANCES ====================
class FinancesDashboardSerializer(serializers.Serializer):
    """Serializer pour le dashboard des finances"""

    # Résumé
    total_ventes = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_depenses = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_tresorerie = serializers.DecimalField(
        max_digits=15, decimal_places=2)
    benefice = serializers.DecimalField(max_digits=15, decimal_places=2)

    # Évolution
    evolution_ventes = serializers.DecimalField(max_digits=5, decimal_places=2)
    evolution_depenses = serializers.DecimalField(
        max_digits=5, decimal_places=2)

    # Alertes
    alertes_budget = serializers.ListField()
    alertes_tresorerie = serializers.ListField()
    alertes_echeances = serializers.ListField()

    # Graphiques
    ventes_mensuelles = serializers.ListField()
    depenses_mensuelles = serializers.ListField()
    tresorerie_par_type = serializers.DictField()
    depenses_par_categorie = serializers.DictField()
