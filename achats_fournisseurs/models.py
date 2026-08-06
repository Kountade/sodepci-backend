# apps/achats_fournisseurs/models.py
from django.db.models import Sum, F
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
import json
import qrcode

from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone

from users.models import CustomUser
from produits_stocks.models import Product, UnitMeasure, Warehouse, Lot, Stock, StockMovement

# ⚠️ AUCUN IMPORT DE tresorerie.models ICI


# ============================================================
# UTILITAIRES
# ============================================================

def generate_number(model, field_name, prefix):
    """Génère un numéro séquentiel"""
    year = date.today().year

    last_object = (
        model.objects
        .filter(**{
            f"{field_name}__startswith": f"{prefix}-{year}-"
        })
        .order_by("-id")
        .first()
    )

    if last_object:
        last_number = getattr(last_object, field_name)
        try:
            number = int(last_number.split("-")[-1]) + 1
        except (ValueError, IndexError):
            number = 1
    else:
        number = 1

    return f"{prefix}-{year}-{number:04d}"


def generate_qr_image(data):
    """Génère une image QR Code"""
    qr_data = json.dumps(data, ensure_ascii=False, default=str)

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)

    image = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)

    return qr_data, buffer


# ============================================================
# FOURNISSEUR
# ============================================================

# apps/achats_fournisseurs/models.py
# Partie Supplier uniquement - COMPLET


# ============================================================
# FOURNISSEUR - COMPLET
# ============================================================

class Supplier(models.Model):
    """
    Fournisseur - Modèle complet avec toutes les propriétés
    """
    TYPE_CHOICES = (
        ('local', 'Local'),
        ('international', 'International'),
        ('importateur', 'Importateur'),
        ('distributeur', 'Distributeur'),
        ('fabricant', 'Fabricant'),
    )

    PAYMENT_TERMS_CHOICES = (
        ('cash', 'Comptant'),
        ('15', '15 jours'),
        ('30', '30 jours'),
        ('45', '45 jours'),
        ('60', '60 jours'),
        ('90', '90 jours'),
    )

    # ========== IDENTIFIANTS ==========
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Code fournisseur"
    )
    name = models.CharField(
        max_length=200,
        verbose_name="Nom / Raison sociale"
    )
    commercial_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Nom commercial"
    )

    # ========== TYPE ==========
    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='local',
        verbose_name="Type"
    )

    # ========== CONTACTS ==========
    contact_person = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Personne de contact"
    )
    phone = models.CharField(
        max_length=20,
        verbose_name="Téléphone"
    )
    mobile = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Mobile"
    )
    email = models.EmailField(
        verbose_name="Email"
    )
    website = models.URLField(
        blank=True,
        verbose_name="Site web"
    )

    # ========== ADRESSE ==========
    address = models.TextField(
        verbose_name="Adresse"
    )
    city = models.CharField(
        max_length=100,
        verbose_name="Ville"
    )
    country = models.CharField(
        max_length=100,
        default='Sénégal',
        verbose_name="Pays"
    )
    postal_code = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Code postal"
    )

    # ========== INFORMATIONS FISCALES ==========
    tax_id = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="N° Identification fiscale"
    )
    registration_number = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="N° Registre de commerce"
    )

    # ========== CONDITIONS COMMERCIALES ==========
    payment_terms = models.CharField(
        max_length=20,
        choices=PAYMENT_TERMS_CHOICES,
        default='30',
        verbose_name="Délai de paiement"
    )
    delivery_lead_time = models.IntegerField(
        default=7,
        verbose_name="Délai de livraison (jours)"
    )
    minimum_order = models.IntegerField(
        default=0,
        verbose_name="Commande minimum"
    )

    # ========== ÉVALUATION ==========
    rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0,
        verbose_name="Note (0-5)"
    )
    total_purchases = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name="Total achats"
    )
    total_orders = models.IntegerField(
        default=0,
        verbose_name="Nombre de commandes"
    )
    on_time_delivery_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name="Taux livraison à temps (%)"
    )

    # ========== STATUT ==========
    is_active = models.BooleanField(
        default=True,
        verbose_name="Actif"
    )
    is_preferred = models.BooleanField(
        default=False,
        verbose_name="Fournisseur privilégié"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Notes"
    )

    # ========== MÉTADONNÉES ==========
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date création"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Date modification"
    )
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fournisseurs_created',
        verbose_name="Créé par"
    )

    class Meta:
        verbose_name = "Fournisseur"
        verbose_name_plural = "Fournisseurs"
        ordering = ['name']

    def __str__(self):
        return f"{self.code} - {self.name}"

    # ========== PROPRIÉTÉS ==========

    @property
    def full_address(self):
        """Adresse complète formatée"""
        parts = [self.address, self.city, self.country]
        return ", ".join([p for p in parts if p])

    @property
    def total_debt(self):
        """
        ✅ Total de la dette envers ce fournisseur
        Calculé à partir des factures non payées
        """
        total = self.invoices.filter(
            paiement_status__in=['unpaid', 'partial', 'overdue']
        ).aggregate(
            total=Sum(F('total_amount') - F('amount_paid'))
        )['total']
        return total or Decimal('0')

    @property
    def overdue_debt(self):
        """
        ✅ Dette en retard envers ce fournisseur
        Calculé à partir des factures en retard
        """
        total = self.invoices.filter(
            due_date__lt=date.today(),
            paiement_status__in=['unpaid', 'partial']
        ).aggregate(
            total=Sum(F('total_amount') - F('amount_paid'))
        )['total']
        return total or Decimal('0')

    @property
    def total_invoices_count(self):
        """Nombre total de factures"""
        return self.invoices.count()

    @property
    def unpaid_invoices_count(self):
        """Nombre de factures non payées"""
        return self.invoices.filter(
            paiement_status__in=['unpaid', 'partial', 'overdue']
        ).count()

    @property
    def average_purchase_amount(self):
        """Montant moyen des achats"""
        if self.total_orders == 0:
            return Decimal('0')
        return self.total_purchases / self.total_orders

    @property
    def is_good_standing(self):
        """Vérifie si le fournisseur est en bon standing"""
        return self.overdue_debt == Decimal('0')

    @property
    def payment_terms_label(self):
        """Libellé des conditions de paiement"""
        return dict(self.PAYMENT_TERMS_CHOICES).get(self.payment_terms, self.payment_terms)

    @property
    def type_label(self):
        """Libellé du type de fournisseur"""
        return dict(self.TYPE_CHOICES).get(self.type, self.type)

    # ========== MÉTHODES ==========

    def update_total_purchases(self):
        """
        Met à jour le total des achats
        """
        from django.db.models import Sum

        total = self.purchase_orders.filter(
            status__in=['confirmed', 'partial', 'received']
        ).aggregate(
            total=Sum('total')
        )['total'] or Decimal('0')

        self.total_purchases = total
        self.total_orders = self.purchase_orders.count()
        self.save(update_fields=['total_purchases', 'total_orders'])

    def get_contacts(self):
        """Récupère tous les contacts"""
        return self.contacts.all()

    def get_primary_contact(self):
        """Récupère le contact principal"""
        return self.contacts.filter(is_primary=True).first()

    def get_products(self):
        """Récupère tous les produits du fournisseur"""
        return self.products.filter(is_active=True)

    def get_purchase_orders(self, status=None):
        """Récupère les commandes du fournisseur"""
        queryset = self.purchase_orders.all()
        if status:
            queryset = queryset.filter(status=status)
        return queryset.order_by('-order_date')

    def get_invoices(self, status=None):
        """Récupère les factures du fournisseur"""
        queryset = self.invoices.all()
        if status:
            queryset = queryset.filter(status=status)
        return queryset.order_by('-invoice_date')

    def get_debt_detail(self):
        """
        ✅ Détail de la dette du fournisseur
        Retourne un dictionnaire avec les détails
        """
        invoices = self.invoices.filter(
            paiement_status__in=['unpaid', 'partial', 'overdue']
        )

        detail = {
            'total_debt': self.total_debt,
            'overdue_debt': self.overdue_debt,
            'invoices_count': invoices.count(),
            'overdue_invoices_count': invoices.filter(
                due_date__lt=date.today()
            ).count(),
            'invoices': []
        }

        for invoice in invoices:
            detail['invoices'].append({
                'id': invoice.id,
                'invoice_number': invoice.invoice_number,
                'total_amount': invoice.total_amount,
                'amount_paid': invoice.amount_paid,
                'remaining': invoice.remaining_amount,
                'due_date': invoice.due_date,
                'is_overdue': invoice.is_overdue,
                'days_overdue': invoice.days_overdue,
                'status': invoice.paiement_status
            })

        return detail

    def to_dict(self):
        """Convertit le fournisseur en dictionnaire"""
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'commercial_name': self.commercial_name,
            'type': self.type,
            'type_label': self.type_label,
            'contact_person': self.contact_person,
            'phone': self.phone,
            'mobile': self.mobile,
            'email': self.email,
            'website': self.website,
            'address': self.address,
            'city': self.city,
            'country': self.country,
            'postal_code': self.postal_code,
            'tax_id': self.tax_id,
            'registration_number': self.registration_number,
            'payment_terms': self.payment_terms,
            'payment_terms_label': self.payment_terms_label,
            'delivery_lead_time': self.delivery_lead_time,
            'minimum_order': self.minimum_order,
            'rating': str(self.rating),
            'total_purchases': str(self.total_purchases),
            'total_orders': self.total_orders,
            'on_time_delivery_rate': str(self.on_time_delivery_rate),
            'is_active': self.is_active,
            'is_preferred': self.is_preferred,
            'is_good_standing': self.is_good_standing,
            'total_debt': str(self.total_debt),
            'overdue_debt': str(self.overdue_debt),
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class SupplierContact(models.Model):
    """Contact chez le fournisseur"""
    supplier = models.ForeignKey(
        Supplier, on_delete=models.CASCADE, related_name='contacts')
    name = models.CharField(max_length=100, verbose_name="Nom complet")
    position = models.CharField(
        max_length=100, blank=True, verbose_name="Poste")
    phone = models.CharField(max_length=20, verbose_name="Téléphone")
    mobile = models.CharField(max_length=20, blank=True, verbose_name="Mobile")
    email = models.EmailField(verbose_name="Email")
    is_primary = models.BooleanField(
        default=False, verbose_name="Contact principal")
    notes = models.TextField(blank=True, verbose_name="Notes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Contact fournisseur"
        verbose_name_plural = "Contacts fournisseurs"

    def __str__(self):
        return f"{self.name} - {self.supplier.name}"


class SupplierProduct(models.Model):
    """Produits proposés par le fournisseur"""
    supplier = models.ForeignKey(
        Supplier, on_delete=models.CASCADE, related_name='products')
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='suppliers')
    supplier_sku = models.CharField(
        max_length=100, blank=True, verbose_name="Référence fournisseur")
    purchase_price = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Prix d'achat")
    lead_time = models.IntegerField(
        default=7, verbose_name="Délai de livraison (jours)")
    minimum_order = models.IntegerField(
        default=1, verbose_name="Quantité minimum")
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    notes = models.TextField(blank=True, verbose_name="Notes")
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Produit fournisseur"
        verbose_name_plural = "Produits fournisseurs"
        unique_together = ['supplier', 'product']

    def __str__(self):
        return f"{self.supplier.name} - {self.product.name}"


# ============================================================
# BON DE COMMANDE
# ============================================================

class PurchaseOrder(models.Model):
    """Bon de commande avec QR Code"""
    STATUS_CHOICES = (
        ('draft', 'Brouillon'),
        ('sent', 'Envoyé'),
        ('confirmed', 'Confirmé'),
        ('partial', 'Partiellement reçu'),
        ('received', 'Reçu'),
        ('cancelled', 'Annulé'),
    )

    DISCOUNT_CHOICES = (
        ('percentage', 'Pourcentage'),
        ('amount', 'Montant fixe'),
    )

    po_number = models.CharField(
        max_length=50, unique=True, verbose_name="N° Bon de commande")
    supplier_reference = models.CharField(
        max_length=100, blank=True, verbose_name="Référence fournisseur")
    supplier = models.ForeignKey(
        Supplier, on_delete=models.SET_NULL, null=True, related_name='purchase_orders')
    order_date = models.DateTimeField(
        auto_now_add=True, verbose_name="Date commande")
    expected_delivery_date = models.DateField(
        verbose_name="Date livraison prévue")
    actual_delivery_date = models.DateField(
        null=True, blank=True, verbose_name="Date livraison réelle")
    subtotal = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name="Sous-total")
    discount_type = models.CharField(
        max_length=10, choices=DISCOUNT_CHOICES, default='amount', verbose_name="Type de remise")
    discount_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Valeur de la remise")
    discount_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Montant de la remise")
    tax_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, verbose_name="Taux TVA (%)")
    tax_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Montant TVA")
    shipping_cost = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Frais de livraison")
    total = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name="Total")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name="Statut")
    notes = models.TextField(blank=True, verbose_name="Notes")
    internal_notes = models.TextField(
        blank=True, verbose_name="Notes internes")
    shipping_address = models.TextField(
        blank=True, verbose_name="Adresse de livraison")
    tracking_number = models.CharField(
        max_length=100, blank=True, verbose_name="N° de suivi")

    # Suivi des réceptions et paiements
    total_received_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, verbose_name="Montant total reçu")
    total_invoiced_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, verbose_name="Montant total facturé")
    total_paid_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, verbose_name="Montant total payé")
    is_fully_received = models.BooleanField(
        default=False, verbose_name="Entièrement reçue")
    is_fully_invoiced = models.BooleanField(
        default=False, verbose_name="Entièrement facturée")
    is_fully_paid = models.BooleanField(
        default=False, verbose_name="Entièrement payée")

    # QR Code
    qr_code = models.ImageField(
        upload_to='qrcodes/purchase_orders/', null=True, blank=True, verbose_name="QR Code")
    qr_code_data = models.TextField(blank=True, verbose_name="Données QR Code")

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name='purchase_orders', verbose_name="Créé par")
    approved_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name='approved_orders', verbose_name="Approuvé par")
    approved_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Date approbation")

    class Meta:
        verbose_name = "Bon de commande"
        verbose_name_plural = "Bons de commande"
        ordering = ['-order_date']

    def __str__(self):
        return f"{self.po_number} - {self.supplier.name if self.supplier else 'N/A'}"

    @property
    def remaining_to_receive(self):
        return self.total - self.total_received_amount

    @property
    def remaining_to_invoice(self):
        return self.total - self.total_invoiced_amount

    @property
    def remaining_to_pay(self):
        return self.total_invoiced_amount - self.total_paid_amount

    @property
    def receipt_progress(self):
        if self.total == 0:
            return 0
        return (self.total_received_amount / self.total) * 100

    @property
    def payment_progress(self):
        if self.total_invoiced_amount == 0:
            return 0
        return (self.total_paid_amount / self.total_invoiced_amount) * 100

    def calculate_totals(self):
        self.subtotal = sum(line.total for line in self.lines.all())
        if self.discount_type == 'percentage':
            self.discount_amount = self.subtotal * (self.discount_value / 100)
        else:
            self.discount_amount = self.discount_value
        after_discount = self.subtotal - self.discount_amount
        self.tax_amount = after_discount * (self.tax_rate / 100)
        self.total = after_discount + self.tax_amount + self.shipping_cost
        self.save(update_fields=['subtotal',
                  'discount_amount', 'tax_amount', 'total'])

    def update_receipt_status(self):
        total_ordered = self.lines.aggregate(
            total=Sum('quantity'))['total'] or 0
        total_received = self.lines.aggregate(
            total=Sum('quantity_received'))['total'] or 0
        if total_ordered == 0:
            self.is_fully_received = False
        else:
            self.is_fully_received = total_received >= total_ordered
        if self.is_fully_received and self.status not in ['cancelled']:
            if self.status != 'received':
                self.status = 'received'
        elif total_received > 0 and self.status not in ['cancelled']:
            self.status = 'partial'
        self.save(update_fields=['is_fully_received', 'status'])

    def update_invoice_status(self):
        if self.total == 0:
            self.is_fully_invoiced = False
        else:
            total_invoiced = self.invoices.aggregate(
                total=Sum('total_amount'))['total'] or 0
            self.total_invoiced_amount = total_invoiced
            self.is_fully_invoiced = total_invoiced >= self.total
        self.save(update_fields=['total_invoiced_amount', 'is_fully_invoiced'])

    def update_payment_status(self):
        # Import local pour éviter les problèmes
        from .models import FournisseurPaiement
        total_paid = self.paiements.filter(status='confirmed').aggregate(
            total=Sum('amount'))['total'] or 0
        self.total_paid_amount = total_paid
        if self.total_invoiced_amount == 0:
            self.is_fully_paid = False
        else:
            self.is_fully_paid = total_paid >= self.total_invoiced_amount
        self.save(update_fields=['total_paid_amount', 'is_fully_paid'])

    def generate_qr_code(self):
        if not self.po_number:
            return
        qr_data = {
            'type': 'purchase_order',
            'id': self.id,
            'number': self.po_number,
            'supplier': self.supplier.name if self.supplier else '',
            'supplier_code': self.supplier.code if self.supplier else '',
            'total': str(self.total),
            'date': self.order_date.strftime('%Y-%m-%d %H:%M:%S'),
            'status': self.status,
            'expected_delivery': self.expected_delivery_date.strftime('%Y-%m-%d') if self.expected_delivery_date else '',
            'url': f'/commandes-fournisseurs/{self.id}/'
        }
        qr_data_str, buffer = generate_qr_image(qr_data)
        self.qr_code_data = qr_data_str
        filename = f"qr_po_{self.po_number}.png"
        self.qr_code.save(filename, File(buffer), save=False)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new or not self.qr_code or not self.qr_code_data:
            self.generate_qr_code()
            super().save(update_fields=['qr_code', 'qr_code_data'])


class PurchaseOrderLine(models.Model):
    """Ligne de bon de commande"""
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE, related_name='lines')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(verbose_name="Quantité commandée")
    quantity_received = models.IntegerField(
        default=0, verbose_name="Quantité reçue")
    unit_price = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Prix unitaire")
    discount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Remise")
    tax_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, verbose_name="TVA (%)")
    total = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Total ligne")
    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        verbose_name = "Ligne de commande"
        verbose_name_plural = "Lignes de commande"

    def __str__(self):
        return f"{self.purchase_order.po_number} - {self.product.name}"

    @property
    def quantity_remaining(self):
        return self.quantity - self.quantity_received

    def save(self, *args, **kwargs):
        self.total = (self.quantity * self.unit_price) - self.discount
        super().save(*args, **kwargs)
        self.purchase_order.calculate_totals()


# ============================================================
# RÉCEPTION (CORRIGÉ - SANS FK VERS TRESORERIE)
# ============================================================

class Receipt(models.Model):
    """Réception de marchandises"""
    STATUS_CHOICES = (
        ('pending', 'En attente'),
        ('in_progress', 'En cours'),
        ('completed', 'Terminée'),
        ('cancelled', 'Annulée'),
    )

    receipt_number = models.CharField(
        max_length=50, unique=True, verbose_name="N° de réception")
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE, related_name='receipts')
    receipt_date = models.DateTimeField(
        auto_now_add=True, verbose_name="Date de réception")
    expected_date = models.DateField(verbose_name="Date prévue")
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.SET_NULL, null=True, verbose_name="Entrepôt de destination")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Statut")
    notes = models.TextField(blank=True, verbose_name="Notes")
    delivery_note = models.CharField(
        max_length=100, blank=True, verbose_name="N° Bon de livraison")
    invoice_number = models.CharField(
        max_length=100, blank=True, verbose_name="N° Facture")

    # ⚠️ UTILISATION D'IntegerField POUR ÉVITER LES IMPORTS CIRCULAIRES
    caisse_destination_id = models.IntegerField(
        null=True, blank=True, verbose_name="ID Caisse de décaissement")
    compte_destination_id = models.IntegerField(
        null=True, blank=True, verbose_name="ID Compte bancaire de décaissement")
    montant_decaissement = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, verbose_name="Montant décaissé")
    mouvement_tresorerie_id = models.IntegerField(
        null=True, blank=True, verbose_name="ID Mouvement de trésorerie")

    # QR Code
    qr_code = models.ImageField(
        upload_to='qrcodes/receipts/', null=True, blank=True, verbose_name="QR Code")
    qr_code_data = models.TextField(blank=True, verbose_name="Données QR Code")

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name='receptions_created', verbose_name="Réceptionné par")

    class Meta:
        verbose_name = "Réception"
        verbose_name_plural = "Réceptions"
        ordering = ['-receipt_date']

    def __str__(self):
        return f"{self.receipt_number} - {self.purchase_order.po_number}"

    def generate_qr_code(self):
        if not self.receipt_number:
            return
        qr_data = {
            'type': 'receipt',
            'id': self.id,
            'number': self.receipt_number,
            'purchase_order': self.purchase_order.po_number if self.purchase_order else '',
            'supplier': self.purchase_order.supplier.name if self.purchase_order and self.purchase_order.supplier else '',
            'warehouse': self.warehouse.name if self.warehouse else '',
            'date': self.receipt_date.strftime('%Y-%m-%d %H:%M:%S') if self.receipt_date else '',
            'status': self.status,
            'url': f'/receptions/{self.id}/'
        }
        qr_data_str, buffer = generate_qr_image(qr_data)
        self.qr_code_data = qr_data_str
        filename = f"qr_rec_{self.receipt_number}.png"
        self.qr_code.save(filename, File(buffer), save=False)

    def creer_mouvement_decaissement(self, user):
        """Crée un mouvement de trésorerie pour le décaissement"""
        if self.mouvement_tresorerie_id:
            return self.mouvement_tresorerie_id

        # Import différé pour éviter les imports circulaires
        try:
            from tresorerie.models import MouvementTresorerie, Caisse, CompteBancaire
        except ImportError:
            return None

        # Calculer le montant
        total_recu = Decimal('0')
        for line in self.lines.all():
            if line.quantity_received > 0:
                total_recu += line.quantity_received * line.po_line.unit_price

        if total_recu <= 0:
            return None

        self.montant_decaissement = total_recu

        # Récupérer la caisse ou le compte
        caisse = None
        compte = None

        if self.caisse_destination_id:
            try:
                caisse = Caisse.objects.get(id=self.caisse_destination_id)
            except Caisse.DoesNotExist:
                pass

        if self.compte_destination_id:
            try:
                compte = CompteBancaire.objects.get(
                    id=self.compte_destination_id)
            except CompteBancaire.DoesNotExist:
                pass

        if not caisse and not compte:
            if self.warehouse:
                caisse = Caisse.objects.filter(
                    warehouse=self.warehouse, is_default=True).first()
            if not caisse and not compte:
                caisse = Caisse.objects.filter(is_default=True).first()

        if not caisse and not compte:
            return None

        # Créer le mouvement
        mouvement = MouvementTresorerie.objects.create(
            type_mouvement='decaissement',
            warehouse=self.warehouse,
            source_type='achat',
            source_id=self.purchase_order.id,
            source_reference=self.purchase_order.po_number,
            montant=total_recu,
            mode_paiement='virement',
            caisse=caisse,
            compte_bancaire=compte,
            date_mouvement=timezone.now(),
            date_valeur=timezone.now().date(),
            status='effectue',
            libelle=f"Décaissement pour réception {self.receipt_number} - commande {self.purchase_order.po_number}",
            created_by=user
        )

        self.mouvement_tresorerie_id = mouvement.id
        self.save(update_fields=[
                  'montant_decaissement', 'mouvement_tresorerie_id'])

        return self.mouvement_tresorerie_id

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new or not self.qr_code or not self.qr_code_data:
            self.generate_qr_code()
            super().save(update_fields=['qr_code', 'qr_code_data'])


class ReceiptLine(models.Model):
    """Ligne de réception"""
    receipt = models.ForeignKey(
        Receipt, on_delete=models.CASCADE, related_name='lines')
    po_line = models.ForeignKey(
        PurchaseOrderLine, on_delete=models.CASCADE, related_name='receipt_lines')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity_ordered = models.IntegerField(verbose_name="Quantité commandée")
    quantity_received = models.IntegerField(verbose_name="Quantité reçue")
    quantity_damaged = models.IntegerField(
        default=0, verbose_name="Quantité endommagée")
    lot = models.ForeignKey(Lot, on_delete=models.SET_NULL,
                            null=True, blank=True, verbose_name="Lot associé")
    lot_number = models.CharField(
        max_length=100, blank=True, verbose_name="Numéro de lot")
    expiry_date = models.DateField(
        null=True, blank=True, verbose_name="Date d'expiration")
    manufacturing_date = models.DateField(
        null=True, blank=True, verbose_name="Date de fabrication")
    is_quality_checked = models.BooleanField(
        default=False, verbose_name="Contrôle qualité effectué")
    quality_status = models.CharField(max_length=20, blank=True, choices=[(
        'passed', 'Approuvé'), ('failed', 'Refusé'), ('pending', 'En attente')], default='pending')
    quality_notes = models.TextField(blank=True, verbose_name="Notes qualité")
    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        verbose_name = "Ligne de réception"
        verbose_name_plural = "Lignes de réception"

    def __str__(self):
        return f"{self.receipt.receipt_number} - {self.product.name}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        total_received = ReceiptLine.objects.filter(po_line=self.po_line).aggregate(
            total=Sum('quantity_received'))['total'] or 0
        self.po_line.quantity_received = total_received
        self.po_line.save()
        self.receipt.purchase_order.update_receipt_status()


# ============================================================
# RETOUR FOURNISSEUR
# ============================================================

class PurchaseReturn(models.Model):
    """Retour fournisseur"""
    REASON_CHOICES = (
        ('defective', 'Produit défectueux'),
        ('wrong_product', 'Produit incorrect'),
        ('expired', 'Produit expiré'),
        ('damaged', 'Produit endommagé'),
        ('other', 'Autre'),
    )
    STATUS_CHOICES = (
        ('requested', 'Demandé'),
        ('approved', 'Approuvé'),
        ('shipped', 'Expédié'),
        ('refunded', 'Remboursé'),
        ('replaced', 'Remplacé'),
        ('rejected', 'Refusé'),
    )

    return_number = models.CharField(
        max_length=50, unique=True, verbose_name="N° de retour")
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE, related_name='returns')
    receipt = models.ForeignKey(
        Receipt, on_delete=models.CASCADE, null=True, blank=True, related_name='returns')
    return_date = models.DateTimeField(
        auto_now_add=True, verbose_name="Date de retour")
    reason = models.CharField(
        max_length=20, choices=REASON_CHOICES, verbose_name="Raison")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='requested', verbose_name="Statut")
    notes = models.TextField(blank=True, verbose_name="Notes")
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL,
                                   null=True, related_name='returns_created', verbose_name="Créé par")
    qr_code = models.ImageField(
        upload_to='qrcodes/purchase_returns/', null=True, blank=True, verbose_name="QR Code")
    qr_code_data = models.TextField(blank=True, verbose_name="Données QR Code")

    class Meta:
        verbose_name = "Retour fournisseur"
        verbose_name_plural = "Retours fournisseurs"
        ordering = ['-return_date']

    def __str__(self):
        return f"{self.return_number} - {self.purchase_order.po_number}"

    def generate_qr_code(self):
        if not self.return_number:
            return
        qr_data = {
            'type': 'purchase_return',
            'id': self.id,
            'number': self.return_number,
            'purchase_order': self.purchase_order.po_number if self.purchase_order else '',
            'supplier': self.purchase_order.supplier.name if self.purchase_order and self.purchase_order.supplier else '',
            'reason': self.reason,
            'status': self.status,
            'date': self.return_date.strftime('%Y-%m-%d %H:%M:%S') if self.return_date else '',
            'url': f'/purchase-returns/{self.id}/'
        }
        qr_data_str, buffer = generate_qr_image(qr_data)
        self.qr_code_data = qr_data_str
        filename = f"qr_ret_{self.return_number}.png"
        self.qr_code.save(filename, File(buffer), save=False)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new or not self.qr_code or not self.qr_code_data:
            self.generate_qr_code()
            super().save(update_fields=['qr_code', 'qr_code_data'])


class PurchaseReturnLine(models.Model):
    """Ligne de retour fournisseur"""
    purchase_return = models.ForeignKey(
        PurchaseReturn, on_delete=models.CASCADE, related_name='lines')
    receipt_line = models.ForeignKey(
        ReceiptLine, on_delete=models.CASCADE, related_name='return_lines')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(verbose_name="Quantité retournée")
    unit_price = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Prix unitaire")
    total = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Total")

    def save(self, *args, **kwargs):
        self.total = self.quantity * self.unit_price
        super().save(*args, **kwargs)


# ============================================================
# FACTURE FOURNISSEUR
# ============================================================

class SupplierInvoice(models.Model):
    """Facture fournisseur"""
    STATUS_CHOICES = (
        ('received', 'Reçue'),
        ('verified', 'Vérifiée'),
        ('paid', 'Payée'),
        ('partial', 'Partiellement payée'),
        ('disputed', 'Contestée'),
    )
    PAIEMENT_STATUS_CHOICES = (
        ('unpaid', 'Non payée'),
        ('partial', 'Partiellement payée'),
        ('paid', 'Payée'),
        ('overdue', 'En retard'),
    )

    invoice_number = models.CharField(
        max_length=100, unique=True, verbose_name="N° Facture")
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE, related_name='invoices')
    supplier = models.ForeignKey(
        Supplier, on_delete=models.CASCADE, related_name='invoices')
    invoice_date = models.DateField(verbose_name="Date facture")
    due_date = models.DateField(verbose_name="Date d'échéance")
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Montant")
    tax_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="TVA")
    total_amount = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Total")
    amount_paid = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name="Montant payé")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='received', verbose_name="Statut")
    paiement_status = models.CharField(
        max_length=20, choices=PAIEMENT_STATUS_CHOICES, default='unpaid', verbose_name="Statut paiement")
    is_fully_paid = models.BooleanField(
        default=False, verbose_name="Entièrement payée")
    payment_date = models.DateField(
        null=True, blank=True, verbose_name="Date de paiement")
    payment_reference = models.CharField(
        max_length=100, blank=True, verbose_name="Référence paiement")
    pdf_file = models.FileField(
        upload_to='invoices/', null=True, blank=True, verbose_name="PDF facture")
    notes = models.TextField(blank=True, verbose_name="Notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Facture fournisseur"
        verbose_name_plural = "Factures fournisseurs"
        ordering = ['-invoice_date']

    def __str__(self):
        return f"{self.invoice_number} - {self.supplier.name}"

    @property
    def remaining_amount(self):
        return self.total_amount - self.amount_paid

    @property
    def is_overdue(self):
        return date.today() > self.due_date and not self.is_fully_paid

    @property
    def days_overdue(self):
        if self.is_overdue:
            return (date.today() - self.due_date).days
        return 0

    def update_payment_status(self):
        if self.amount_paid >= self.total_amount:
            self.is_fully_paid = True
            self.paiement_status = 'paid'
            self.status = 'paid'
            self.payment_date = timezone.now().date()
        elif self.amount_paid > 0:
            self.is_fully_paid = False
            self.paiement_status = 'partial'
            self.status = 'partial'
        else:
            self.is_fully_paid = False
            if self.is_overdue:
                self.paiement_status = 'overdue'
            else:
                self.paiement_status = 'unpaid'

        if self.purchase_order:
            self.purchase_order.update_invoice_status()
            self.purchase_order.update_payment_status()

        self.save(update_fields=['is_fully_paid',
                  'paiement_status', 'status', 'payment_date'])


# ============================================================
# PAIEMENT FOURNISSEUR (CORRIGÉ - SANS FK VERS TRESORERIE)
# ============================================================


# apps/achats_fournisseurs/models.py
# Partie FournisseurPaiement - COMPLÈTEMENT CORRIGÉ
# apps/achats_fournisseurs/models.py
# FournisseurPaiement - COMPLET CORRIGÉ

class FournisseurPaiement(models.Model):
    """Paiement fournisseur"""
    METHOD_CHOICES = (
        ('especes', 'Espèces'),
        ('cheque', 'Chèque'),
        ('virement', 'Virement bancaire'),
        ('transfert', 'Transfert'),
        ('mobile_money', 'Mobile Money'),
        ('autre', 'Autre'),
    )
    STATUS_CHOICES = (
        ('pending', 'En attente'),
        ('confirmed', 'Confirmé'),
        ('cancelled', 'Annulé'),
    )

    reference = models.CharField(
        max_length=50, unique=True, verbose_name="Référence paiement")
    supplier_invoice = models.ForeignKey(
        SupplierInvoice, on_delete=models.CASCADE, related_name='paiements', verbose_name="Facture fournisseur")
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE,
                                       related_name='paiements', null=True, blank=True, verbose_name="Commande associée")
    amount = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name="Montant payé")
    method = models.CharField(
        max_length=20, choices=METHOD_CHOICES, default='virement', verbose_name="Méthode")
    reference_number = models.CharField(
        max_length=100, blank=True, verbose_name="N° de référence")
    payment_date = models.DateTimeField(
        default=timezone.now, verbose_name="Date de paiement")

    # ⚠️ UTILISATION D'IntegerField POUR ÉVITER LES IMPORTS CIRCULAIRES
    caisse_destination_id = models.IntegerField(
        null=True, blank=True, verbose_name="ID Caisse de décaissement")
    compte_destination_id = models.IntegerField(
        null=True, blank=True, verbose_name="ID Compte bancaire de décaissement")
    mouvement_tresorerie_id = models.IntegerField(
        null=True, blank=True, verbose_name="ID Mouvement de trésorerie")

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Statut")
    notes = models.TextField(blank=True, verbose_name="Notes")
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name='paiements_fournisseurs', verbose_name="Créé par")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # QR Code
    qr_code = models.ImageField(
        upload_to='qrcodes/fournisseur_paiements/', null=True, blank=True, verbose_name="QR Code")
    qr_code_data = models.TextField(blank=True, verbose_name="Données QR Code")

    class Meta:
        verbose_name = "Paiement fournisseur"
        verbose_name_plural = "Paiements fournisseurs"
        ordering = ['-payment_date']

    def __str__(self):
        return f"{self.reference} - {self.supplier_invoice.invoice_number} - {self.amount:,.0f} FCFA"

    def generate_qr_code(self):
        if not self.reference:
            return
        qr_data = {
            'type': 'fournisseur_paiement',
            'id': self.id,
            'reference': self.reference,
            'invoice': self.supplier_invoice.invoice_number,
            'supplier': self.supplier_invoice.supplier.name,
            'amount': str(self.amount),
            'date': self.payment_date.strftime('%Y-%m-%d %H:%M:%S'),
            'method': self.method,
            'status': self.status
        }
        qr_data_str, buffer = generate_qr_image(qr_data)
        self.qr_code_data = qr_data_str
        filename = f"qr_fournisseur_paiement_{self.reference}.png"
        self.qr_code.save(filename, File(buffer), save=False)

    def creer_mouvement_tresorerie(self, user):
        """Crée le mouvement de trésorerie associé"""
        if self.mouvement_tresorerie_id:
            return self.mouvement_tresorerie_id

        # Import différé pour éviter les imports circulaires
        try:
            from tresorerie.models import MouvementTresorerie, Caisse, CompteBancaire
        except ImportError:
            return None

        # Récupérer la caisse ou le compte
        caisse = None
        compte = None

        if self.caisse_destination_id:
            try:
                caisse = Caisse.objects.get(id=self.caisse_destination_id)
            except Caisse.DoesNotExist:
                pass

        if self.compte_destination_id:
            try:
                compte = CompteBancaire.objects.get(
                    id=self.compte_destination_id)
            except CompteBancaire.DoesNotExist:
                pass

        if not caisse and not compte:
            caisse = Caisse.objects.filter(is_default=True).first()

        if not caisse and not compte:
            return None

        # ✅ Récupérer le warehouse
        warehouse = None

        # 1. Essayer depuis les réceptions de la commande
        if self.purchase_order:
            receipt = self.purchase_order.receipts.first()
            if receipt:
                warehouse = receipt.warehouse

        # 2. Essayer depuis la facture
        if not warehouse and self.supplier_invoice and self.supplier_invoice.purchase_order:
            receipt = self.supplier_invoice.purchase_order.receipts.first()
            if receipt:
                warehouse = receipt.warehouse

        # 3. Essayer depuis la caisse
        if not warehouse and caisse:
            warehouse = caisse.warehouse

        # 4. Dernier recours : prendre le premier warehouse disponible
        if not warehouse:
            from produits_stocks.models import Warehouse
            warehouse = Warehouse.objects.filter(is_active=True).first()

        # ✅ Créer le mouvement (warehouse peut être None)
        mouvement = MouvementTresorerie.objects.create(
            type_mouvement='decaissement',
            warehouse=warehouse,  # Peut être None
            source_type='paiement_fournisseur',
            source_id=self.id,
            source_reference=self.reference,
            montant=self.amount,
            mode_paiement=self.method,
            caisse=caisse,
            compte_bancaire=compte,
            date_mouvement=self.payment_date,
            date_valeur=self.payment_date.date(),
            status='effectue',
            libelle=f"Paiement fournisseur - {self.supplier_invoice.invoice_number} - {self.supplier_invoice.supplier.name}",
            created_by=user
        )

        self.mouvement_tresorerie_id = mouvement.id
        self.save(update_fields=['mouvement_tresorerie_id'])

        return self.mouvement_tresorerie_id

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if is_new and not self.reference:
            last_paiement = FournisseurPaiement.objects.order_by('-id').first()
            num = 1
            if last_paiement and last_paiement.reference:
                try:
                    num = int(last_paiement.reference.split('-')[-1]) + 1
                except (ValueError, IndexError):
                    num = 1
            self.reference = f"PAYF-{date.today().year}-{num:04d}"

        super().save(*args, **kwargs)
        if is_new or not self.qr_code or not self.qr_code_data:
            self.generate_qr_code()
            super().save(update_fields=['qr_code', 'qr_code_data'])
