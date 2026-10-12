# apps/ventes_clients/pagination.py
# ============================================================
# PAGINATION PERSONNALISÉE POUR OPTIMISATION
# ============================================================

from rest_framework.pagination import PageNumberPagination


class VentePagination(PageNumberPagination):
    """
    Pagination optimisée pour les ventes.
    - Taille par défaut : 50
    - Taille max : 200
    """
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


class OptimizedPagination(PageNumberPagination):
    """
    Pagination optimisée pour les autres endpoints (factures, paiements).
    - Taille par défaut : 100
    - Taille max : 500
    """
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 500


class LargePagination(PageNumberPagination):
    """
    Pagination pour les endpoints admin (wallets, clients).
    """
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 1000