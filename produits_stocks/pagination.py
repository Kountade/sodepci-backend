# apps/produits_stocks/pagination.py
# ============================================================
# PAGINATION PERSONNALISÉE POUR PRODUITS_STOCKS
# ============================================================

from rest_framework.pagination import PageNumberPagination


class ProductPagination(PageNumberPagination):
    """
    Pagination pour les produits.
    - Taille par défaut : 50
    - Taille max : 200
    """
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


class StockPagination(PageNumberPagination):
    """
    Pagination pour les stocks.
    - Taille par défaut : 100
    - Taille max : 500
    """
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 500


class MovementPagination(PageNumberPagination):
    """
    Pagination pour les mouvements.
    - Taille par défaut : 100
    - Taille max : 500
    """
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 500


class LotPagination(PageNumberPagination):
    """
    Pagination pour les lots.
    - Taille par défaut : 100
    - Taille max : 500
    """
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 500


class LargePagination(PageNumberPagination):
    """
    Pagination large (catégories, unités, entrepôts).
    """
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 1000
