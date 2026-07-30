# dashboard/serializers.py
from rest_framework import serializers


class DashboardSummarySerializer(serializers.Serializer):
    ventes = serializers.DictField()
    achats = serializers.DictField()
    stocks = serializers.DictField()
    tresorerie = serializers.DictField()
    clients_fournisseurs = serializers.DictField()
    alertes = serializers.DictField()


class StatistiquesFilterSerializer(serializers.Serializer):
    date_debut = serializers.DateField(required=False)
    date_fin = serializers.DateField(required=False)
    entrepot_id = serializers.IntegerField(required=False)


class StatistiquesSerializer(serializers.Serializer):
    periode = serializers.DictField()
    ventes = serializers.DictField()
    achats = serializers.DictField()
    tresorerie = serializers.DictField()
    top_produits = serializers.ListField()


class TendancesSerializer(serializers.Serializer):
    periode_label = serializers.CharField()
    total_ventes = serializers.IntegerField()
    montant_total = serializers.DecimalField(max_digits=15, decimal_places=2)
    panier_moyen = serializers.DecimalField(max_digits=15, decimal_places=2)


class PrevisionsSerializer(serializers.Serializer):
    previsions = serializers.DictField()
    moyenne_mensuelle = serializers.DecimalField(
        max_digits=15, decimal_places=2)
    montant_mois_dernier = serializers.DecimalField(
        max_digits=15, decimal_places=2)
    evolution_pourcentage = serializers.DecimalField(
        max_digits=10, decimal_places=2)
