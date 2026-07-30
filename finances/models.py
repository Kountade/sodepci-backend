from django.db import models

# Create your models here.
# finances/models.py

from django.db import models
from django.utils import timezone
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator

from users.models import CustomUser
from produits_stocks.models import Product, Warehouse, Lot
# ✅ Imports corrects pour les applications existantes
from achats_fournisseurs.models import Supplier, PurchaseOrder, SupplierInvoice
from ventes_clients.models import Vente, Facture, Paiement, Client


# ==================== COMPTE COMPTABLE ====================
class CompteComptable(models.Model):
    """
    Plan comptable - Gestion des comptes
    """
    TYPE_CHOICES = (
        ('actif', 'Actif'),
        ('passif', 'Passif'),
        ('capitaux', 'Capitaux propres'),
        ('produits', 'Produits'),
        ('charges', 'Charges'),
    )

    CLASSE_CHOICES = (
        ('1', 'Classe 1 - Capital'),
        ('2', 'Classe 2 - Immobilisations'),
        ('3', 'Classe 3 - Stocks'),
        ('4', 'Classe 4 - Tiers'),
        ('5', 'Classe 5 - Trésorerie'),
        ('6', 'Classe 6 - Charges'),
        ('7', 'Classe 7 - Produits'),
        ('8', 'Classe 8 - Comptes de régularisation'),
    )

    # Identifiants
    numero = models.CharField(
        max_length=20, unique=True, verbose_name="Numéro de compte")
    nom = models.CharField(max_length=200, verbose_name="Nom du compte")
    nom_complet = models.CharField(
        max_length=255, blank=True, verbose_name="Nom complet")

    # Classification
    type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, verbose_name="Type")
    classe = models.CharField(
        max_length=20, choices=CLASSE_CHOICES, verbose_name="Classe")

    # Hiérarchie
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
        verbose_name="Compte parent"
    )
    niveau = models.PositiveIntegerField(
        default=0, verbose_name="Niveau hiérarchique")

    # Solde
    solde = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, verbose_name="Solde actuel")
    solde_initial = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, verbose_name="Solde initial")

    # Caractéristiques
    is_analytique = models.BooleanField(
        default=False, verbose_name="Compte analytique")
    is_budgetaire = models.BooleanField(
        default=False, verbose_name="Compte budgétaire")
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    is_imported = models.BooleanField(default=False, verbose_name="Importé")

    # Métadonnées
    notes = models.TextField(blank=True, verbose_name="Notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Compte comptable"
        verbose_name_plural = "Comptes comptables"
        ordering = ['numero']

    def __str__(self):
        return f"{self.numero} - {self.nom}"

    def get_full_path(self):
        """Récupère le chemin complet du compte"""
        if self.parent:
            return f"{self.parent.get_full_path()} > {self.nom}"
        return self.nom

    def update_solde(self):
        """Met à jour le solde du compte"""
        from django.db.models import Sum

        debit_total = self.ecritures_debit.aggregate(total=Sum('montant'))[
            'total'] or Decimal('0')
        credit_total = self.ecritures_credit.aggregate(total=Sum('montant'))[
            'total'] or Decimal('0')

        self.solde = debit_total - credit_total
        self.save()


# ==================== ÉCRITURE COMPTABLE ====================
class EcritureComptable(models.Model):
    """
    Écriture comptable
    """
    TYPE_CHOICES = (
        ('vente', 'Vente'),
        ('achat', 'Achat'),
        ('paiement_client', 'Paiement client'),
        ('paiement_fournisseur', 'Paiement fournisseur'),
        ('recette', 'Recette'),
        ('depense', 'Dépense'),
        ('tresorerie', 'Trésorerie'),
        ('regularisation', 'Régularisation'),
        ('autre', 'Autre'),
    )

    STATUT_CHOICES = (
        ('brouillon', 'Brouillon'),
        ('valide', 'Validée'),
        ('annulee', 'Annulée'),
    )

    # Numéro d'écriture
    numero = models.CharField(
        max_length=50, unique=True, verbose_name="N° d'écriture")

    # Dates
    date_ecriture = models.DateField(verbose_name="Date d'écriture")
    date_comptable = models.DateField(
        auto_now_add=True, verbose_name="Date comptable")
    date_echeance = models.DateField(
        null=True, blank=True, verbose_name="Date d'échéance")

    # Comptes
    compte_debit = models.ForeignKey(
        CompteComptable,
        on_delete=models.CASCADE,
        related_name='ecritures_debit',
        verbose_name="Compte débit"
    )
    compte_credit = models.ForeignKey(
        CompteComptable,
        on_delete=models.CASCADE,
        related_name='ecritures_credit',
        verbose_name="Compte crédit"
    )

    # Montants
    montant = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name="Montant")
    taxe = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, verbose_name="Taxe")
    total = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name="Total TTC")

    # Références
    reference = models.CharField(
        max_length=100, blank=True, verbose_name="Référence")
    type = models.CharField(
        max_length=30, choices=TYPE_CHOICES, verbose_name="Type")
    statut = models.CharField(
        max_length=20, choices=STATUT_CHOICES, default='brouillon', verbose_name="Statut")

    # ✅ Liens vers les modèles existants
    vente = models.ForeignKey(
        Vente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Vente"
    )
    facture = models.ForeignKey(
        Facture,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Facture client"
    )
    paiement = models.ForeignKey(
        Paiement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Paiement client"
    )
    supplier_invoice = models.ForeignKey(
        SupplierInvoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Facture fournisseur"
    )
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Bon de commande"
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Fournisseur"
    )
    client = models.ForeignKey(
        Client,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Client"
    )

    # Description
    description = models.TextField(verbose_name="Description")
    notes = models.TextField(blank=True, verbose_name="Notes")

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ecritures_created'
    )
    validated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ecritures_validated'
    )
    validated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Écriture comptable"
        verbose_name_plural = "Écritures comptables"
        ordering = ['-date_ecriture']

    def __str__(self):
        return f"{self.numero} - {self.montant} FCFA"

    def save(self, *args, **kwargs):
        self.total = self.montant + self.taxe
        super().save(*args, **kwargs)
        self.compte_debit.update_solde()
        self.compte_credit.update_solde()

    def valider(self, user):
        """Valide l'écriture comptable"""
        self.statut = 'valide'
        self.validated_by = user
        self.validated_at = timezone.now()
        self.save()


# ==================== TRÉSORERIE ====================
class Tresorerie(models.Model):
    """
    Gestion de la trésorerie
    """
    TYPE_CHOICES = (
        ('banque', 'Banque'),
        ('caisse', 'Caisse'),
        ('especes', 'Espèces'),
        ('mobile_money', 'Mobile Money'),
        ('virement', 'Virement'),
    )

    # Identifiants
    nom = models.CharField(max_length=100, verbose_name="Nom")
    code = models.CharField(max_length=20, unique=True, verbose_name="Code")
    type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, verbose_name="Type")

    # Informations bancaires
    banque = models.CharField(
        max_length=100, blank=True, verbose_name="Banque")
    iban = models.CharField(max_length=50, blank=True, verbose_name="IBAN")
    bic = models.CharField(max_length=20, blank=True, verbose_name="BIC/SWIFT")
    titulaire = models.CharField(
        max_length=100, blank=True, verbose_name="Titulaire")

    # Solde
    solde_initial = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, verbose_name="Solde initial")
    solde_actuel = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, verbose_name="Solde actuel")
    solde_minimum = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, verbose_name="Solde minimum")

    # Caractéristiques
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    is_default = models.BooleanField(default=False, verbose_name="Par défaut")

    # Métadonnées
    notes = models.TextField(blank=True, verbose_name="Notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Trésorerie"
        verbose_name_plural = "Trésoreries"
        ordering = ['nom']

    def __str__(self):
        return f"{self.nom} - {self.solde_actuel} FCFA"

    def update_solde(self):
        """Met à jour le solde actuel"""
        from django.db.models import Sum

        entree_total = self.mouvements.filter(type='entree').aggregate(
            total=Sum('montant'))['total'] or Decimal('0')
        sortie_total = self.mouvements.filter(type='sortie').aggregate(
            total=Sum('montant'))['total'] or Decimal('0')

        self.solde_actuel = self.solde_initial + entree_total - sortie_total
        self.save()


# ==================== MOUVEMENT TRÉSORERIE ====================
class MouvementTresorerie(models.Model):
    """
    Mouvement de trésorerie
    """
    TYPE_CHOICES = (
        ('entree', 'Entrée'),
        ('sortie', 'Sortie'),
    )

    CATEGORIE_CHOICES = (
        ('vente', 'Vente'),
        ('paiement_fournisseur', 'Paiement fournisseur'),
        ('recette', 'Recette'),
        ('depense', 'Dépense'),
        ('transfert', 'Transfert entre comptes'),
        ('regularisation', 'Régularisation'),
        ('autre', 'Autre'),
    )

    tresorerie = models.ForeignKey(
        Tresorerie,
        on_delete=models.CASCADE,
        related_name='mouvements'
    )

    type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, verbose_name="Type")
    categorie = models.CharField(
        max_length=30, choices=CATEGORIE_CHOICES, verbose_name="Catégorie")

    montant = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name="Montant")
    date_mouvement = models.DateTimeField(
        auto_now_add=True, verbose_name="Date du mouvement")
    date_valeur = models.DateField(verbose_name="Date de valeur")

    reference = models.CharField(
        max_length=100, blank=True, verbose_name="Référence")
    description = models.TextField(verbose_name="Description")

    # ✅ Liens vers les modèles existants
    ecriture = models.ForeignKey(
        EcritureComptable,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    vente = models.ForeignKey(
        Vente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    paiement = models.ForeignKey(
        Paiement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    supplier_invoice = models.ForeignKey(
        SupplierInvoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # Métadonnées
    notes = models.TextField(blank=True, verbose_name="Notes")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Mouvement de trésorerie"
        verbose_name_plural = "Mouvements de trésorerie"
        ordering = ['-date_mouvement']

    def __str__(self):
        return f"{self.type} - {self.montant} FCFA"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.tresorerie:
            self.tresorerie.update_solde()


# ==================== DÉPENSE ====================
class Depense(models.Model):
    """
    Gestion des dépenses
    """
    CATEGORIE_CHOICES = (
        ('fournitures', 'Fournitures de bureau'),
        ('utilities', 'Services publics (eau, électricité)'),
        ('loyer', 'Loyer'),
        ('salaires', 'Salaires'),
        ('marketing', 'Marketing et publicité'),
        ('transport', 'Transport et déplacements'),
        ('maintenance', 'Maintenance et réparation'),
        ('formation', 'Formation'),
        ('informatique', 'Informatique'),
        ('telecommunication', 'Télécommunication'),
        ('frais_bancaires', 'Frais bancaires'),
        ('impots', 'Impôts et taxes'),
        ('assurance', 'Assurance'),
        ('frais_professionnels', 'Frais professionnels'),
        ('achat_stock', 'Achat de stock'),
        ('autre', 'Autre'),
    )

    STATUS_CHOICES = (
        ('en_attente', 'En attente'),
        ('approuve', 'Approuvé'),
        ('paye', 'Payé'),
        ('annule', 'Annulé'),
        ('rejete', 'Rejeté'),
    )

    # Identifiants
    reference = models.CharField(
        max_length=50, unique=True, verbose_name="Référence")

    # Informations
    categorie = models.CharField(
        max_length=30, choices=CATEGORIE_CHOICES, verbose_name="Catégorie")
    description = models.TextField(verbose_name="Description")
    montant = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name="Montant")
    taxe = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, verbose_name="TVA")
    total = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name="Total TTC")

    # Dates
    date_depense = models.DateField(verbose_name="Date de la dépense")
    date_echeance = models.DateField(
        null=True, blank=True, verbose_name="Date d'échéance")

    # Paiement
    mode_paiement = models.CharField(
        max_length=50, blank=True, verbose_name="Mode de paiement")
    reference_paiement = models.CharField(
        max_length=100, blank=True, verbose_name="Référence paiement")
    date_paiement = models.DateField(
        null=True, blank=True, verbose_name="Date de paiement")

    # ✅ Fournisseur - Utiliser Supplier de achats_fournisseurs
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Fournisseur"
    )
    supplier_name = models.CharField(
        max_length=200, blank=True, verbose_name="Nom du fournisseur")

    # Statut
    statut = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='en_attente', verbose_name="Statut")

    # Pièces justificatives
    piece_jointe = models.FileField(
        upload_to='depenses/', null=True, blank=True, verbose_name="Pièce jointe")

    # ✅ Liens vers les modèles existants
    tresorerie = models.ForeignKey(
        Tresorerie,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    ecriture = models.ForeignKey(
        EcritureComptable,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Bon de commande"
    )

    # Métadonnées
    notes = models.TextField(blank=True, verbose_name="Notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    approuve_par = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='depenses_approuvees'
    )
    approuve_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Dépense"
        verbose_name_plural = "Dépenses"
        ordering = ['-date_depense']

    def __str__(self):
        return f"{self.reference} - {self.montant} FCFA"

    def save(self, *args, **kwargs):
        self.total = self.montant + self.taxe
        super().save(*args, **kwargs)

    def approuver(self, user):
        """Approuve une dépense"""
        self.statut = 'approuve'
        self.approuve_par = user
        self.approuve_le = timezone.now()
        self.save()

    def payer(self, user):
        """Marque la dépense comme payée"""
        self.statut = 'paye'
        self.date_paiement = timezone.now().date()
        self.save()


# ==================== BUDGET ====================
class Budget(models.Model):
    """
    Gestion des budgets
    """
    TYPE_CHOICES = (
        ('annuel', 'Annuel'),
        ('trimestriel', 'Trimestriel'),
        ('mensuel', 'Mensuel'),
        ('projet', 'Projet'),
    )

    STATUT_CHOICES = (
        ('en_cours', 'En cours'),
        ('termine', 'Terminé'),
        ('annule', 'Annulé'),
    )

    nom = models.CharField(max_length=100, verbose_name="Nom")
    type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, verbose_name="Type")

    montant_total = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name="Montant total")
    montant_utilise = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, verbose_name="Montant utilisé")
    montant_restant = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, verbose_name="Montant restant")

    date_debut = models.DateField(verbose_name="Date début")
    date_fin = models.DateField(verbose_name="Date fin")

    statut = models.CharField(
        max_length=20, choices=STATUT_CHOICES, default='en_cours', verbose_name="Statut")

    # Lignes de budget
    categories = models.ManyToManyField(
        'BudgetCategorie', through='BudgetLigne', verbose_name="Catégories")

    # Métadonnées
    notes = models.TextField(blank=True, verbose_name="Notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Budget"
        verbose_name_plural = "Budgets"
        ordering = ['-date_debut']

    def __str__(self):
        return f"{self.nom} - {self.montant_total} FCFA"

    def update_utilise(self):
        """Met à jour le montant utilisé"""
        total_utilise = self.lignes.aggregate(
            total=models.Sum('montant_utilise')
        )['total'] or Decimal('0')

        self.montant_utilise = total_utilise
        self.montant_restant = self.montant_total - self.montant_utilise
        self.save()


# ==================== BUDGET CATÉGORIE ====================
class BudgetCategorie(models.Model):
    """
    Catégorie de budget
    """
    nom = models.CharField(max_length=100, verbose_name="Nom")
    description = models.TextField(blank=True, verbose_name="Description")
    code = models.CharField(max_length=20, unique=True, verbose_name="Code")

    is_active = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        verbose_name = "Catégorie de budget"
        verbose_name_plural = "Catégories de budget"
        ordering = ['nom']

    def __str__(self):
        return self.nom


# ==================== BUDGET LIGNE ====================
class BudgetLigne(models.Model):
    """
    Ligne de budget
    """
    budget = models.ForeignKey(
        Budget, on_delete=models.CASCADE, related_name='lignes')
    categorie = models.ForeignKey(BudgetCategorie, on_delete=models.CASCADE)

    montant_prevu = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name="Montant prévu")
    montant_utilise = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, verbose_name="Montant utilisé")
    montant_restant = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, verbose_name="Montant restant")

    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        verbose_name = "Ligne de budget"
        verbose_name_plural = "Lignes de budget"

    def __str__(self):
        return f"{self.budget.nom} - {self.categorie.nom}"

    def save(self, *args, **kwargs):
        self.montant_restant = self.montant_prevu - self.montant_utilise
        super().save(*args, **kwargs)
        self.budget.update_utilise()


# ==================== RAPPORT FINANCIER ====================
class RapportFinancier(models.Model):
    """
    Rapports financiers
    """
    TYPE_CHOICES = (
        ('bilan', 'Bilan comptable'),
        ('compte_resultat', 'Compte de résultat'),
        ('tresorerie', 'Tableau de trésorerie'),
        ('budget', 'Suivi budgétaire'),
        ('ventes', 'Rapport de ventes'),
        ('depenses', 'Rapport de dépenses'),
        ('achats', 'Rapport d\'achats'),
        ('client', 'Rapport client'),
        ('fournisseur', 'Rapport fournisseur'),
    )

    FORMAT_CHOICES = (
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
        ('csv', 'CSV'),
    )

    type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, verbose_name="Type")
    nom = models.CharField(max_length=200, verbose_name="Nom du rapport")

    date_debut = models.DateField(verbose_name="Date début")
    date_fin = models.DateField(verbose_name="Date fin")

    format = models.CharField(
        max_length=10, choices=FORMAT_CHOICES, default='pdf', verbose_name="Format")

    # Contenu du rapport (stocké en JSON)
    contenu = models.JSONField(
        default=dict, blank=True, verbose_name="Contenu")

    # Fichier généré
    fichier = models.FileField(
        upload_to='rapports/', null=True, blank=True, verbose_name="Fichier")

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Rapport financier"
        verbose_name_plural = "Rapports financiers"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.nom} - {self.type}"


# ==================== CONFIGURATION FINANCIÈRE ====================
class ConfigurationFinanciere(models.Model):
    """
    Configuration financière de l'entreprise
    """
    # Devise
    devise = models.CharField(
        max_length=3, default='XOF', verbose_name="Devise")
    devise_symbole = models.CharField(
        max_length=5, default='CFA', verbose_name="Symbole devise")

    # Exercice comptable
    exercice_debut = models.DateField(verbose_name="Début de l'exercice")
    exercice_fin = models.DateField(verbose_name="Fin de l'exercice")

    # Taxes
    taxe_default = models.DecimalField(
        max_digits=5, decimal_places=2, default=18, verbose_name="TVA par défaut (%)")

    # Arrondi
    arrondi = models.PositiveIntegerField(
        default=0, verbose_name="Nombre de décimales")

    # Options
    auto_validation = models.BooleanField(
        default=False, verbose_name="Validation automatique des écritures")
    budget_alerte = models.PositiveIntegerField(
        default=80, verbose_name="Alerte budget (%)")

    # Métadonnées
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Configuration financière"
        verbose_name_plural = "Configurations financières"

    def __str__(self):
        return f"Configuration financière - {self.devise}"
