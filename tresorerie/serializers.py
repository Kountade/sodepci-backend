from rest_framework import serializers
from django.utils import timezone
from decimal import Decimal

from .models import (
    Caisse, CompteBancaire, MouvementTresorerie, Frais,
    PrevisionTresorerie, RapprochementBancaire, TresorerieJournaliere
)


# ----------------------------------------------
# 1. CAISSES
# ----------------------------------------------
class CaisseSerializer(serializers.ModelSerializer):
    est_sous_seuil_min = serializers.BooleanField(read_only=True)
    est_sur_seuil_max = serializers.BooleanField(read_only=True)
    total_mouvements = serializers.IntegerField(read_only=True)

    class Meta:
        model = Caisse
        fields = [
            'id', 'code', 'nom', 'type_caisse', 'warehouse', 'responsable',
            'solde_initial', 'solde_actuel', 'seuil_min', 'seuil_max',
            'devise', 'is_active', 'is_default', 'description',
            'est_sous_seuil_min', 'est_sur_seuil_max', 'total_mouvements',
            'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = ['solde_actuel',
                            'created_at', 'updated_at', 'created_by']

    def validate(self, data):
        # Vérifier qu'une seule caisse par défaut par warehouse
        if data.get('is_default', False):
            warehouse = data.get('warehouse')
            if warehouse and Caisse.objects.filter(warehouse=warehouse, is_default=True).exclude(
                    pk=self.instance.pk if self.instance else None).exists():
                raise serializers.ValidationError(
                    {"is_default": "Une caisse par défaut existe déjà pour cet entrepôt."}
                )
        return data


# ----------------------------------------------
# 2. COMPTES BANCAIRES
# ----------------------------------------------
class CompteBancaireSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompteBancaire
        fields = [
            'id', 'banque', 'code', 'nom', 'type_compte', 'warehouse',
            'numero_compte', 'iban', 'bic', 'devise',
            'solde_initial', 'solde_actuel',
            'is_active', 'is_default', 'date_ouverture', 'description',
            'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = ['solde_actuel',
                            'created_at', 'updated_at', 'created_by']


# ----------------------------------------------
# 3. MOUVEMENTS DE TRÉSORERIE (le plus complexe)
# ----------------------------------------------
class MouvementTresorerieSerializer(serializers.ModelSerializer):
    # Champs en lecture seule pour l'affichage
    est_encaissement = serializers.BooleanField(read_only=True)
    est_decaissement = serializers.BooleanField(read_only=True)
    est_transfert = serializers.BooleanField(read_only=True)

    class Meta:
        model = MouvementTresorerie
        fields = [
            'id', 'reference', 'type_mouvement', 'warehouse',
            'source_type', 'source_id', 'source_reference',
            'montant', 'mode_paiement',
            'caisse', 'compte_bancaire',
            'date_mouvement', 'date_valeur', 'date_prevue',
            'status', 'reference_externe', 'piece_justificative',
            'date_rapprochement', 'rapproche',
            'libelle', 'notes',
            'vente', 'purchase_order', 'facture_vente', 'paiement',
            'created_at', 'updated_at', 'created_by',
            'valide_par', 'date_validation',
            'est_encaissement', 'est_decaissement', 'est_transfert'
        ]
        read_only_fields = [
            'reference', 'date_rapprochement', 'rapproche',
            'created_at', 'updated_at', 'created_by', 'valide_par', 'date_validation'
        ]

    def validate(self, data):
        # Un mouvement doit être lié soit à une caisse, soit à un compte bancaire
        if not data.get('caisse') and not data.get('compte_bancaire'):
            raise serializers.ValidationError(
                "Vous devez spécifier une caisse ou un compte bancaire."
            )

        # Un transfert nécessite les deux (caisse et compte) ou deux caisses ? Ici on simplifie.
        if data.get('type_mouvement') == 'transfert':
            # Pour un transfert, on pourrait exiger caisse ET compte, ou gérer via un champ 'caisse_dest'.
            # Par défaut on autorise mais on peut ajouter une règle.
            pass

        return data

    def create(self, validated_data):
        # La référence est générée automatiquement par le modèle
        # On force le statut 'planifié' si non spécifié
        if 'status' not in validated_data:
            validated_data['status'] = 'planifie'

        # Si le mouvement est déjà 'effectué', la méthode save du modèle mettra à jour les soldes
        mouvement = MouvementTresorerie.objects.create(**validated_data)

        # Si le statut est 'effectué', on met à jour les soldes (déjà fait dans save, mais on assure)
        if mouvement.status == 'effectue':
            mouvement._mettre_a_jour_soldes()

        return mouvement

    def update(self, instance, validated_data):
        # Si on passe le statut à 'effectué', on doit mettre à jour les soldes
        if validated_data.get('status') == 'effectue' and instance.status != 'effectue':
            # Avant de modifier, on applique la mise à jour des soldes
            instance.type_mouvement = validated_data.get(
                'type_mouvement', instance.type_mouvement)
            instance.montant = validated_data.get('montant', instance.montant)
            instance.caisse = validated_data.get('caisse', instance.caisse)
            instance.compte_bancaire = validated_data.get(
                'compte_bancaire', instance.compte_bancaire)
            instance._mettre_a_jour_soldes()

        return super().update(instance, validated_data)


# ----------------------------------------------
# 4. FRAIS
# ----------------------------------------------
class FraisSerializer(serializers.ModelSerializer):
    class Meta:
        model = Frais
        fields = [
            'id', 'reference', 'titre', 'warehouse', 'categorie',
            'montant', 'date_frais', 'date_paiement', 'beneficiaire',
            'piece_justificative', 'mode_paiement',
            'mouvement', 'supplier',
            'status', 'notes',
            'created_at', 'updated_at', 'created_by',
            'valide_par', 'date_validation'
        ]
        read_only_fields = ['reference', 'mouvement',
                            'created_at', 'updated_at', 'created_by']

    def validate(self, data):
        if data.get('status') == 'paye' and not data.get('mouvement'):
            # Le modèle crée automatiquement le mouvement en save, pas besoin de le faire ici.
            # Mais on peut vérifier que le mode de paiement est bien renseigné.
            pass
        return data


# ----------------------------------------------
# 5. PRÉVISIONS
# ----------------------------------------------
class PrevisionTresorerieSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrevisionTresorerie
        fields = [
            'id', 'reference', 'titre', 'warehouse',
            'type_prevision', 'periode',
            'montant_prevu', 'montant_reel',
            'date_debut', 'date_fin',
            'source_type', 'source_id',
            'categorie', 'sous_categorie',
            'statut', 'probabilite',
            'ecart', 'pourcentage_ecart',
            'notes',
            'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = ['reference', 'ecart', 'pourcentage_ecart',
                            'created_at', 'updated_at', 'created_by']


# ----------------------------------------------
# 6. RAPPROCHEMENT BANCAIRE
# ----------------------------------------------
class RapprochementBancaireSerializer(serializers.ModelSerializer):
    est_rapproche = serializers.BooleanField(read_only=True)

    class Meta:
        model = RapprochementBancaire
        fields = [
            'id', 'reference', 'warehouse', 'compte_bancaire',
            'date_debut', 'date_fin',
            'solde_comptable', 'solde_bancaire', 'solde_rapproche',
            'ecart', 'status',
            'encours_emission', 'encours_encaissement',
            'commissions', 'autres_ecarts',
            'notes',
            'created_at', 'updated_at', 'created_by',
            'valide_par', 'date_validation',
            'est_rapproche'
        ]
        read_only_fields = ['reference', 'solde_rapproche',
                            'ecart', 'created_at', 'updated_at', 'created_by']


# ----------------------------------------------
# 7. TRÉSORERIE JOURNALIÈRE
# ----------------------------------------------
class TresorerieJournaliereSerializer(serializers.ModelSerializer):
    variation = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True)

    class Meta:
        model = TresorerieJournaliere
        fields = [
            'id', 'date', 'warehouse',
            'solde_ouverture', 'solde_fermeture',
            'total_entrees', 'total_sorties',
            'entrees_ventes', 'entrees_reglements', 'entrees_autres',
            'sorties_achats', 'sorties_frais', 'sorties_salaires', 'sorties_autres',
            'nb_operations', 'nb_entrees', 'nb_sorties',
            'variation',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

# ============================================================
# 8. DASHBOARD TRÉSORERIE
# ============================================================
class TresorerieDashboardSerializer(serializers.Serializer):
    """
    Sérialiseur pour les statistiques du tableau de bord de trésorerie
    """
    total_soldes_caisses = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_soldes_comptes = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_global = serializers.DecimalField(max_digits=15, decimal_places=2)
    nb_caisses = serializers.IntegerField()
    nb_comptes = serializers.IntegerField()
    mouvements_recents = serializers.ListField(child=serializers.DictField())
    entree_total_jour = serializers.DecimalField(max_digits=15, decimal_places=2)
    sortie_total_jour = serializers.DecimalField(max_digits=15, decimal_places=2)
    soldes_par_entrepot = serializers.ListField(child=serializers.DictField())