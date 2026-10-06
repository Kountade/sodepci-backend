import django_filters
from django.db.models import F   # ✅ Ajouté

from .models import (
    Cuve, Pompe, VenteCarburant, VenteService,
    MouvementCuve, MouvementPompe
)


class CuveFilter(django_filters.FilterSet):
    type_carburant = django_filters.CharFilter(lookup_expr='exact')
    est_active = django_filters.BooleanFilter()
    en_alerte = django_filters.BooleanFilter(method='filter_en_alerte')

    class Meta:
        model = Cuve
        fields = ['type_carburant', 'est_active', 'warehouse']

    def filter_en_alerte(self, queryset, name, value):
        if value:
            # ✅
            return queryset.filter(niveau_actuel__lte=F('capacite_alerte'))
        return queryset


class PompeFilter(django_filters.FilterSet):
    statut = django_filters.CharFilter(lookup_expr='exact')
    is_active = django_filters.BooleanFilter()

    class Meta:
        model = Pompe
        fields = ['statut', 'is_active', 'cuve']


class VenteCarburantFilter(django_filters.FilterSet):
    date_debut = django_filters.DateFilter(
        field_name='date_vente', lookup_expr='date__gte')
    date_fin = django_filters.DateFilter(
        field_name='date_vente', lookup_expr='date__lte')
    type_paiement = django_filters.CharFilter(lookup_expr='exact')
    est_paye = django_filters.BooleanFilter()
    pompe = django_filters.NumberFilter()
    client = django_filters.NumberFilter()

    class Meta:
        model = VenteCarburant
        fields = ['type_paiement', 'est_paye', 'pompe', 'client', 'type_vente']


class VenteServiceFilter(django_filters.FilterSet):
    date_debut = django_filters.DateFilter(
        field_name='date_vente', lookup_expr='date__gte')
    date_fin = django_filters.DateFilter(
        field_name='date_vente', lookup_expr='date__lte')
    type_paiement = django_filters.CharFilter(lookup_expr='exact')
    est_paye = django_filters.BooleanFilter()
    service = django_filters.NumberFilter()
    client = django_filters.NumberFilter()

    class Meta:
        model = VenteService
        fields = ['type_paiement', 'est_paye', 'service', 'client']


class MouvementCuveFilter(django_filters.FilterSet):
    date_debut = django_filters.DateFilter(
        field_name='created_at', lookup_expr='date__gte')
    date_fin = django_filters.DateFilter(
        field_name='created_at', lookup_expr='date__lte')
    type_mouvement = django_filters.CharFilter(lookup_expr='exact')

    class Meta:
        model = MouvementCuve
        fields = ['cuve', 'type_mouvement']


class MouvementPompeFilter(django_filters.FilterSet):
    date_debut = django_filters.DateFilter(
        field_name='created_at', lookup_expr='date__gte')
    date_fin = django_filters.DateFilter(
        field_name='created_at', lookup_expr='date__lte')
    type_mouvement = django_filters.CharFilter(lookup_expr='exact')

    class Meta:
        model = MouvementPompe
        fields = ['pompe', 'type_mouvement']
