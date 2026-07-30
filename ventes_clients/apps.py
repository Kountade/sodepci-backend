# apps/ventes_clients/apps.py
from django.apps import AppConfig


class VentesClientsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ventes_clients'
    verbose_name = 'Ventes et Clients'

    def ready(self):
        # Commenté pour éviter d'importer les signaux
        # import ventes_clients.signals
        pass
