from django.db import models

# Create your models here.
# apps/station_services/models.py

from django.db import models
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date, timedelta

from users.models import CustomUser
from produits_stocks.models import Product, Warehouse
from ventes_clients.models import Client, Facture, Paiement


# ============================================================
# 1. CUVE / RÉSERVOIR DE CARBURANT
# ============================================================

class Cuve(models.Model):
    """
    Cuve de stockage de carburant
    """
    TYPES_CARBURANT = (
        ('essence', 'Essence'),
        ('diesel', 'Diesel'),
        ('gpl', 'GPL'),
        ('ethanol', 'Ethanol'),
        ('e10', 'E10'),
        ('e85', 'E85'),
    )

    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Code cuve"
    )
    nom = models.CharField(
        max_length=100,
        verbose_name="Nom de la cuve"
    )
    type_carburant = models.CharField(
        max_length=20,
        choices=TYPES_CARBURANT,
        verbose_name="Type de carburant"
    )

    # Capacités
    capacite_max = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Capacité maximale (L)"
    )
    capacite_alerte = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=500,
        verbose_name="Seuil d'alerte (L)"
    )
    niveau_actuel = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Niveau actuel (L)"
    )

    # Informations
    emplacement = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Emplacement"
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cuves',
        verbose_name="Entrepôt"
    )
    est_active = models.BooleanField(
        default=True,
        verbose_name="Cuve active"
    )

    # Dates
    derniere_livraison = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Dernière livraison"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cuves_created'
    )

    class Meta:
        verbose_name = "Cuve"
        verbose_name_plural = "Cuves"
        ordering = ['nom']

    def __str__(self):
        return f"{self.code} - {self.nom} ({self.get_type_carburant_display()})"

    @property
    def taux_remplissage(self):
        """Pourcentage de remplissage"""
        if self.capacite_max > 0:
            return (self.niveau_actuel / self.capacite_max) * 100
        return 0

    @property
    def est_en_alerte(self):
        """Vérifie si la cuve est en alerte"""
        return self.niveau_actuel <= self.capacite_alerte

    @property
    def niveau_display(self):
        """Affichage du niveau"""
        return f"{self.niveau_actuel:,.0f} L / {self.capacite_max:,.0f} L"

    def ajouter_stock(self, quantite, reference='', notes='', created_by=None):
        """Ajouter du carburant dans la cuve"""
        if quantite <= 0:
            raise ValidationError("La quantité doit être supérieure à zéro")

        ancien_niveau = self.niveau_actuel
        nouveau_niveau = ancien_niveau + quantite

        if nouveau_niveau > self.capacite_max:
            raise ValidationError(
                f"La cuve ne peut pas contenir plus de {self.capacite_max} L"
            )

        self.niveau_actuel = nouveau_niveau
        self.derniere_livraison = timezone.now()
        self.save(update_fields=['niveau_actuel',
                  'derniere_livraison', 'updated_at'])

        # Créer le mouvement
        MouvementCuve.objects.create(
            cuve=self,
            type_mouvement='approvisionnement',
            quantite=quantite,
            ancien_niveau=ancien_niveau,
            nouveau_niveau=nouveau_niveau,
            reference=reference,
            notes=notes,
            created_by=created_by
        )

        return nouveau_niveau

    def retirer_stock(self, quantite, reference='', notes='', created_by=None):
        """Retirer du carburant de la cuve (pour vente)"""
        if quantite <= 0:
            raise ValidationError("La quantité doit être supérieure à zéro")

        if quantite > self.niveau_actuel:
            raise ValidationError(
                f"Stock insuffisant. Disponible : {self.niveau_actuel} L"
            )

        ancien_niveau = self.niveau_actuel
        nouveau_niveau = ancien_niveau - quantite

        self.niveau_actuel = nouveau_niveau
        self.save(update_fields=['niveau_actuel', 'updated_at'])

        # Créer le mouvement
        MouvementCuve.objects.create(
            cuve=self,
            type_mouvement='vente',
            quantite=quantite,
            ancien_niveau=ancien_niveau,
            nouveau_niveau=nouveau_niveau,
            reference=reference,
            notes=notes,
            created_by=created_by
        )

        return nouveau_niveau


# ============================================================
# 2. MOUVEMENT DE CUVE
# ============================================================

class MouvementCuve(models.Model):
    """
    Historique des mouvements de carburant
    """
    TYPES_MOUVEMENT = (
        ('approvisionnement', 'Approvisionnement'),
        ('vente', 'Vente'),
        ('transfert', 'Transfert entre cuves'),
        ('ajustement', 'Ajustement de stock'),
        ('fuite', 'Fuite / Perte'),
    )

    cuve = models.ForeignKey(
        Cuve,
        on_delete=models.CASCADE,
        related_name='mouvements'
    )
    type_mouvement = models.CharField(
        max_length=20,
        choices=TYPES_MOUVEMENT
    )
    quantite = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Quantité (L)"
    )
    ancien_niveau = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Niveau avant"
    )
    nouveau_niveau = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Niveau après"
    )
    reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Référence"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Notes"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mouvements_cuve'
    )

    class Meta:
        verbose_name = "Mouvement de cuve"
        verbose_name_plural = "Mouvements de cuve"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.cuve.nom} - {self.get_type_mouvement_display()} - {self.quantite} L"


# ============================================================
# 3. POMPE À CARBURANT
# ============================================================

class Pompe(models.Model):
    """
    Pompe à carburant
    """
    STATUT_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('maintenance', 'En maintenance'),
        ('panne', 'En panne'),
    )

    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Code pompe"
    )
    nom = models.CharField(
        max_length=100,
        verbose_name="Nom de la pompe"
    )
    cuve = models.ForeignKey(
        Cuve,
        on_delete=models.CASCADE,
        related_name='pompes',
        verbose_name="Cuve associée"
    )
    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default='active',
        verbose_name="Statut"
    )
    prix_litre = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Prix au litre (FCFA)"
    )
    compteur_initial = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name="Compteur initial (L)"
    )
    compteur_actuel = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name="Compteur actuel (L)"
    )
    total_ventes = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name="Total vendu (L)"
    )
    emplacement = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Emplacement"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Pompe active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pompes_created'
    )

    class Meta:
        verbose_name = "Pompe"
        verbose_name_plural = "Pompes"
        ordering = ['nom']

    def __str__(self):
        return f"{self.code} - {self.nom} ({self.get_statut_display()})"

    @property
    def total_vendu(self):
        """Total vendu depuis la mise en service"""
        return self.compteur_actuel - self.compteur_initial

    @property
    def est_disponible(self):
        """Vérifie si la pompe est disponible"""
        return self.statut == 'active' and self.is_active

    def enregistrer_vente(self, quantite, montant, reference='', notes='', created_by=None):
        """
        Enregistre une vente sur la pompe
        """
        if not self.est_disponible:
            raise ValidationError("La pompe n'est pas disponible")

        if quantite <= 0:
            raise ValidationError("La quantité doit être supérieure à zéro")

        # Vérifier le stock dans la cuve
        if quantite > self.cuve.niveau_actuel:
            raise ValidationError(
                f"Stock insuffisant dans la cuve. Disponible : {self.cuve.niveau_actuel} L"
            )

        # Mettre à jour la pompe
        ancien_compteur = self.compteur_actuel
        nouveau_compteur = ancien_compteur + quantite
        self.compteur_actuel = nouveau_compteur
        self.total_ventes += quantite
        self.save(update_fields=['compteur_actuel',
                  'total_ventes', 'updated_at'])

        # Retirer de la cuve
        self.cuve.retirer_stock(
            quantite=quantite,
            reference=reference or f"Vente pompe {self.code}",
            notes=notes,
            created_by=created_by
        )

        # Créer le mouvement de pompe
        MouvementPompe.objects.create(
            pompe=self,
            type_mouvement='vente',
            quantite=quantite,
            montant=montant,
            ancien_compteur=ancien_compteur,
            nouveau_compteur=nouveau_compteur,
            reference=reference,
            notes=notes,
            created_by=created_by
        )

        return nouveau_compteur


# ============================================================
# 4. MOUVEMENT DE POMPE
# ============================================================

class MouvementPompe(models.Model):
    """
    Historique des mouvements de pompe
    """
    TYPES_MOUVEMENT = (
        ('vente', 'Vente'),
        ('ajustement', 'Ajustement'),
        ('transfert', 'Transfert'),
    )

    pompe = models.ForeignKey(
        Pompe,
        on_delete=models.CASCADE,
        related_name='mouvements'
    )
    type_mouvement = models.CharField(
        max_length=20,
        choices=TYPES_MOUVEMENT
    )
    quantite = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Quantité (L)"
    )
    montant = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Montant (FCFA)"
    )
    ancien_compteur = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Compteur avant"
    )
    nouveau_compteur = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Compteur après"
    )
    reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Référence"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Notes"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mouvements_pompe'
    )

    class Meta:
        verbose_name = "Mouvement de pompe"
        verbose_name_plural = "Mouvements de pompe"
        ordering = ['-created_at']


# ============================================================
# 5. VENTE DE CARBURANT
# ============================================================

class VenteCarburant(models.Model):
    """
    Vente de carburant
    """
    TYPES_VENTE = (
        ('client', 'Client'),
        ('interne', 'Interne'),
    )

    TYPES_PAIEMENT = (
        ('cash', 'Espèces'),
        ('carte', 'Carte bancaire'),
        ('mobile_money', 'Mobile Money'),
        ('carte_carburant', 'Carte carburant'),
        ('wallet', 'Porte-monnaie'),
        ('credit', 'Crédit'),
    )

    numero_vente = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="N° vente"
    )
    pompe = models.ForeignKey(
        Pompe,
        on_delete=models.SET_NULL,
        null=True,
        related_name='ventes',
        verbose_name="Pompe"
    )
    client = models.ForeignKey(
        Client,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ventes_carburant'
    )
    type_vente = models.CharField(
        max_length=20,
        choices=TYPES_VENTE,
        default='client',
        verbose_name="Type de vente"
    )

    # Quantités et prix
    quantite = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Quantité (L)"
    )
    prix_unitaire = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Prix unitaire (FCFA/L)"
    )
    montant = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Montant total (FCFA)"
    )
    remise = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Remise"
    )
    montant_net = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Montant net"
    )

    # Paiement
    type_paiement = models.CharField(
        max_length=20,
        choices=TYPES_PAIEMENT,
        default='cash',
        verbose_name="Mode de paiement"
    )
    reference_paiement = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Référence paiement"
    )
    est_paye = models.BooleanField(
        default=False,
        verbose_name="Payé"
    )

    # Facture associée
    facture = models.ForeignKey(
        Facture,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ventes_carburant'
    )

    # Informations
    notes = models.TextField(
        blank=True,
        verbose_name="Notes"
    )
    date_vente = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de vente"
    )
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ventes_carburant'
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Vente de carburant"
        verbose_name_plural = "Ventes de carburant"
        ordering = ['-date_vente']

    def __str__(self):
        return f"{self.numero_vente} - {self.quantite} L - {self.montant_net} FCFA"

    def save(self, *args, **kwargs):
        if not self.numero_vente:
            self.numero_vente = self.generate_number()

        if not self.montant_net:
            self.montant_net = self.montant - self.remise

        super().save(*args, **kwargs)

    def generate_number(self):
        """Génère un numéro de vente"""
        year = date.today().year
        last = VenteCarburant.objects.filter(
            numero_vente__startswith=f"CARB-{year}-"
        ).order_by('-id').first()

        if last:
            try:
                num = int(last.numero_vente.split('-')[-1]) + 1
            except (ValueError, IndexError):
                num = 1
        else:
            num = 1

        return f"CARB-{year}-{num:04d}"


# ============================================================
# 6. SERVICE (LAVAGE, GONFLAGE, ETC)
# ============================================================

class Service(models.Model):
    """
    Service proposé par la station
    """
    TYPES_SERVICE = (
        ('lavage_manuel', 'Lavage manuel'),
        ('lavage_auto', 'Lavage automatique'),
        ('gonflage', 'Gonflage des pneus'),
        ('vidange', 'Vidange'),
        ('graissage', 'Graissage'),
        ('autre', 'Autre service'),
    )

    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Code service"
    )
    nom = models.CharField(
        max_length=100,
        verbose_name="Nom du service"
    )
    type_service = models.CharField(
        max_length=20,
        choices=TYPES_SERVICE,
        verbose_name="Type de service"
    )
    prix = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Prix (FCFA)"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description"
    )
    duree_estimee = models.PositiveIntegerField(
        default=15,
        help_text="Durée estimée en minutes",
        verbose_name="Durée estimée (min)"
    )
    est_actif = models.BooleanField(
        default=True,
        verbose_name="Service actif"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='services_created'
    )

    class Meta:
        verbose_name = "Service"
        verbose_name_plural = "Services"
        ordering = ['nom']

    def __str__(self):
        return f"{self.code} - {self.nom} ({self.prix} FCFA)"


# ============================================================
# 7. VENTE DE SERVICE
# ============================================================

class VenteService(models.Model):
    """
    Vente d'un service
    """
    numero_vente = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="N° vente"
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name='ventes'
    )
    client = models.ForeignKey(
        Client,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='services_achetes'
    )
    quantite = models.PositiveIntegerField(
        default=1,
        verbose_name="Quantité"
    )
    prix_unitaire = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Prix unitaire"
    )
    montant = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Montant total"
    )
    remise = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Remise"
    )
    montant_net = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Montant net"
    )
    type_paiement = models.CharField(
        max_length=20,
        choices=VenteCarburant.TYPES_PAIEMENT,
        default='cash',
        verbose_name="Mode de paiement"
    )
    est_paye = models.BooleanField(
        default=False,
        verbose_name="Payé"
    )
    facture = models.ForeignKey(
        Facture,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='services_vendus'
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Notes"
    )
    date_vente = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de vente"
    )
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ventes_services'
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Vente de service"
        verbose_name_plural = "Ventes de services"
        ordering = ['-date_vente']

    def __str__(self):
        return f"{self.numero_vente} - {self.service.nom} - {self.montant_net} FCFA"

    def save(self, *args, **kwargs):
        if not self.numero_vente:
            self.numero_vente = self.generate_number()

        if not self.montant_net:
            self.montant_net = self.montant - self.remise

        super().save(*args, **kwargs)

    def generate_number(self):
        """Génère un numéro de vente"""
        year = date.today().year
        last = VenteService.objects.filter(
            numero_vente__startswith=f"SERV-{year}-"
        ).order_by('-id').first()

        if last:
            try:
                num = int(last.numero_vente.split('-')[-1]) + 1
            except (ValueError, IndexError):
                num = 1
        else:
            num = 1

        return f"SERV-{year}-{num:04d}"


# ============================================================
# 8. PRIX DU CARBURANT (HISTORIQUE)
# ============================================================

class PrixCarburant(models.Model):
    """
    Historique des prix du carburant
    """
    cuve = models.ForeignKey(
        Cuve,
        on_delete=models.CASCADE,
        related_name='prix'
    )
    prix_litre = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Prix au litre (FCFA)"
    )
    date_application = models.DateTimeField(
        default=timezone.now,
        verbose_name="Date d'application"
    )
    date_fin = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de fin"
    )
    est_actif = models.BooleanField(
        default=True,
        verbose_name="Prix actif"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Notes"
    )
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='prix_carburant'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Prix du carburant"
        verbose_name_plural = "Historique des prix"
        ordering = ['-date_application']

    def __str__(self):
        return f"{self.cuve.nom} - {self.prix_litre} FCFA/L ({self.date_application.date()})"


# ============================================================
# 9. STATISTIQUES STATION
# ============================================================

class StatistiquesStation(models.Model):
    """
    Statistiques quotidiennes de la station
    """
    date = models.DateField(
        unique=True,
        verbose_name="Date"
    )

    # Carburant
    total_ventes_carburant = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Total ventes carburant (FCFA)"
    )
    total_litres_vendus = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Total litres vendus"
    )

    # Services
    total_ventes_services = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Total ventes services (FCFA)"
    )

    # Totaux
    total_ca = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Chiffre d'affaires total"
    )
    total_paiements = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Total encaissements"
    )

    # Nombre de transactions
    nb_ventes_carburant = models.PositiveIntegerField(
        default=0,
        verbose_name="Nombre ventes carburant"
    )
    nb_ventes_services = models.PositiveIntegerField(
        default=0,
        verbose_name="Nombre ventes services"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Statistiques station"
        verbose_name_plural = "Statistiques station"
        ordering = ['-date']

    def __str__(self):
        return f"Statistiques du {self.date.strftime('%d/%m/%Y')}"
